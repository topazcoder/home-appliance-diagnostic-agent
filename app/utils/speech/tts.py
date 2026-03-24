"""
Text-to-Speech synthesis using OpenAI TTS.

Returns audio as mulaw-encoded chunks ready to stream back to Twilio.

Pipeline (no pydub, no ffmpeg):
  OpenAI TTS → raw PCM16 @ 24kHz → downsample to 8kHz → G.711 mulaw → 160-byte chunks

We request response_format="pcm" from OpenAI TTS (signed 16-bit little-endian, 24kHz mono)
and convert entirely in pure Python — zero external binary dependencies.
"""
import asyncio
import base64
import struct
import structlog

from fastapi import WebSocket
from openai import AsyncOpenAI

from app.settings import OPENAI_API_KEY, OPENAI_TTS_MODEL, OPENAI_TTS_VOICE

logger = structlog.get_logger(__name__)

_openai_client = AsyncOpenAI(api_key=OPENAI_API_KEY)

# OpenAI TTS pcm output: 24 kHz, mono, signed 16-bit little-endian
OPENAI_PCM_RATE = 24_000

# Twilio Media Streams expects: 8 kHz, 1 channel, mulaw (G.711)
TWILIO_SAMPLE_RATE = 8_000
CHUNK_SIZE = 160  # 20 ms of audio at 8 kHz


async def synthesize_speech(text: str) -> list[bytes]:
    """
    Synthesize ``text`` using OpenAI TTS and return a list of 160-byte mulaw
    audio chunks (each = 20 ms) suitable for Twilio Media Streams.
    """
    if not text.strip():
        return []

    try:
        response = await _openai_client.audio.speech.create(
            model=OPENAI_TTS_MODEL,
            voice=OPENAI_TTS_VOICE,
            input=text,
            response_format="pcm",  # raw PCM16 @ 24 kHz, no container
        )
        pcm_24k = response.content
    except Exception:
        logger.exception("tts_synthesis_error", text=text[:60])
        return []

    try:
        mulaw_raw = _pcm24k_to_mulaw8k(pcm_24k)
        chunks = _chunk(mulaw_raw, CHUNK_SIZE)
        
        return chunks
    except Exception:
        logger.exception("tts_conversion_error")
        return []


async def stream_tts(
    websocket: WebSocket,
    stream_sid: str,
    text: str,
    interrupt_event: asyncio.Event,
):
    """
    Synthesize speech sentence-by-sentence and stream mulaw audio back to Twilio.
    Sentences are split to reduce perceived latency.
    """
    sentences = _split_sentences(text)
    for sentence in sentences:
        if interrupt_event.is_set():
            break
        try:
            mulaw_chunks = await synthesize_speech(sentence)
            # Re-check after the (potentially slow) OpenAI synthesis call —
            # the caller may have started speaking while we were waiting.
            if interrupt_event.is_set():
                break
            for chunk in mulaw_chunks:
                if interrupt_event.is_set():
                    break
                payload = base64.b64encode(chunk).decode("utf-8")
                await websocket.send_json({
                    "event": "media",
                    "streamSid": stream_sid,
                    "media": {"payload": payload},
                })
                # Yield to the event loop so cancellation / interrupt can land
                # between chunks instead of only at the next sentence boundary.
                await asyncio.sleep(0)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("TTS error for sentence: %s", sentence)


def _split_sentences(text: str) -> list[str]:
    """Split text on sentence boundaries for low-latency streaming TTS."""
    import re
    parts = re.split(r'(?<=[.!?])\s+', text.strip())
    return [p for p in parts if p]


def _pcm24k_to_mulaw8k(pcm_24k: bytes) -> bytes:
    """
    Convert raw PCM16 @ 24 kHz → mulaw @ 8 kHz in pure Python.
    Downsamples by keeping every 3rd sample (24000 / 8000 = 3),
    then encodes each PCM16 sample to G.711 mulaw.
    """
    n = len(pcm_24k) // 2
    samples = struct.unpack_from(f'<{n}h', pcm_24k)
    step = OPENAI_PCM_RATE // TWILIO_SAMPLE_RATE  # 3
    downsampled = samples[::step]
    mulaw = bytearray(len(downsampled))
    for i, sample in enumerate(downsampled):
        mulaw[i] = _lin2ulaw(sample)
    return bytes(mulaw)


def _lin2ulaw(sample: int) -> int:
    """Encode a signed 16-bit PCM sample to a G.711 ulaw byte."""
    BIAS = 0x84
    CLIP = 32635
    sample = max(-CLIP, min(CLIP, sample))
    sign = 0
    if sample < 0:
        sample = -sample
        sign = 0x80
    sample += BIAS
    exp = 7
    for exp_mask in (0x4000, 0x2000, 0x1000, 0x0800, 0x0400, 0x0200, 0x0100):
        if sample >= exp_mask:
            break
        exp -= 1
    mantissa = (sample >> (exp + 3)) & 0x0F
    return ~(sign | (exp << 4) | mantissa) & 0xFF


def _chunk(data: bytes, size: int) -> list[bytes]:
    """Split bytes into fixed-size chunks."""
    return [data[i: i + size] for i in range(0, len(data), size)]
