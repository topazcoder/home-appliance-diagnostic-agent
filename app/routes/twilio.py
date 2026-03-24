"""
Twilio Voice webhook routes.

POST /voice/incoming  — Twilio calls this when a call arrives.
WS   /voice/stream    — Twilio Media Streams bidirectional audio.
"""
import asyncio
import base64
import json
import redis.asyncio as redis
import structlog

from fastapi import APIRouter, Depends, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.chat import run_agent
from app.db.database import get_db
from app.services import SessionService
from app.settings import REDIS_URL
from app.utils import is_valid_text
from app.utils.speech.stt import WhisperSTTClient
from app.utils.speech.tts import stream_tts
from app.utils.twiml_builder import build_stream_twiml

logger = structlog.get_logger(__name__)

redis_client = redis.from_url(REDIS_URL, decode_responses=True)

router = APIRouter(
    prefix='/voice',
    tags=['voice'],
    responses={
        200: {'description': 'Success'},
        404: {'description': 'Not found'},
    },
)


@router.get("/health")
async def health():
    return "Hello!"


@router.post("/incoming")
async def incoming_call(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    Entry point for all inbound Twilio calls.
    Responds with TwiML that connects the call to a Media Stream WebSocket.
    """
    form = await request.form()
    call_sid = form.get("CallSid", "unknown")
    caller = form.get("From", "unknown")

    logger.info("Incoming call", call_sid=call_sid, caller=caller)

    # Create a fresh session for this call
    session_service = SessionService(db)
    await session_service.create(call_sid)

    twiml = build_stream_twiml(call_sid)

    return Response(content=twiml, media_type="application/xml")


@router.websocket("/stream")
async def media_stream(
    websocket: WebSocket,
    db: AsyncSession = Depends(get_db),
):
    """
    Twilio Media Streams WebSocket handler.
    Receives raw mulaw audio, buffers and transcribes via Whisper, feeds
    transcript to the agent orchestrator, synthesizes TTS, sends audio back.
    """
    await websocket.accept()
    call_sid: str | None = None
    stream_sid: str | None = None
    stt_client: WhisperSTTClient | None = None
    tts_task: asyncio.Task | None = None
    interrupt_event = asyncio.Event()

    session_service = SessionService(db)
    should_end_call = False

    async def on_transcript(text: str):
        """Called by WhisperSTT when a transcript is ready."""
        try:
            nonlocal tts_task, should_end_call

            content = await redis_client.get(call_sid)
            if content == None:
                content = ""
            content += text

            if not is_valid_text(content):
                content = ""
            
            await redis_client.set(call_sid, content)
            
            if not content or is_valid_text(text):
                return None
            
            session_data = await session_service.load_latest(call_sid)

            logger.info("Transcript", session_id=session_data.id, call_sid=call_sid, text=content)

            await redis_client.set(call_sid, "")

            # Also fire the agent immediately if a photo just arrived
            # (the image_ready key was set by the upload endpoint)
            has_pending_image = await redis_client.exists(f"image_ready:{call_sid}")

            if not content and not has_pending_image:
                return None
            if not content and has_pending_image:
                pass  # agent turn triggered by image only; no speech to barge-in on
            else:
                # Valid speech arrived — interrupt any in-progress TTS
                interrupt_event.set()
                tts_task.cancel()
                try:
                    await tts_task
                except asyncio.CancelledError:
                    pass
                interrupt_event.clear()
                # Flush any audio already queued in Twilio's jitter buffer
                try:
                    await websocket.send_json({"event": "clear", "streamSid": stream_sid})
                except Exception:
                    pass

            # Run orchestrator turn
            try:
                reply, end_call = await run_agent(call_sid, content, session_data, db)
                await session_service.save(call_sid, session_data)
                if end_call:
                    should_end_call = True
            except Exception:
                logger.exception("Orchestrator error", call_sid=call_sid)
                reply = "I'm sorry, I ran into an issue. Could you repeat that?"
                end_call = False

            logger.info("Agent reply", call_sid=call_sid, reply=reply)

            # Synthesize and stream TTS back to Twilio
            tts_task = asyncio.create_task(
                stream_tts(websocket, stream_sid, reply, interrupt_event)
            )

            # If the agent signalled end-of-call, wait for TTS to finish then hang up
            if should_end_call:
                try:
                    await tts_task
                except asyncio.CancelledError:
                    pass
                except Exception:
                    pass
                logger.info("Ending call after farewell", call_sid=call_sid)
                await websocket.close()
        except Exception as e:
            logger.error(f"Exception: {e!s}")

    try:
        async for raw_message in websocket.iter_text():
            data = json.loads(raw_message)
            event = data.get("event")

            if event == "start":
                call_sid = data["start"]["callSid"]
                stream_sid = data["start"]["streamSid"]
                logger.info("Media stream started", call_sid=call_sid)

                stt_client = WhisperSTTClient(on_transcript=on_transcript)

                # Send greeting immediately
                session = await session_service.load_latest(call_sid)
                if session:
                    greeting = (
                        "Thank you for calling Sears Home Services. "
                        "I'm your virtual assistant. "
                        "Can you tell me which appliance is giving you trouble today?"
                    )
                    tts_task = asyncio.create_task(
                        stream_tts(websocket, stream_sid, greeting, interrupt_event)
                    )

            elif event == "media":
                if stt_client:
                    audio_bytes = base64.b64decode(data["media"]["payload"])
                    await stt_client.send_audio(audio_bytes)

            elif event == "stop":
                logger.info("Media stream stopped", call_sid=call_sid)
                break

    except WebSocketDisconnect:
        logger.info("WebSocket disconnected", call_sid=call_sid)
    except Exception:
        logger.exception("WebSocket error", call_sid=call_sid)
    finally:
        if stt_client:
            await stt_client.close()
        if tts_task and not tts_task.done():
            tts_task.cancel()
        try:
            await websocket.close()
        except Exception:
            pass
