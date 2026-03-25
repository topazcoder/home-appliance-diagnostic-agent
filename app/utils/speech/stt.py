"""
OpenAI Whisper Speech-to-Text client.

Buffers incoming mulaw audio from Twilio Media Streams, converts to WAV,
and transcribes via the OpenAI Whisper REST API (whisper-1).

Architecture: buffered-batch with periodic end-of-speech detection.
- Audio chunks (mulaw) are accumulated in the main buffer.
  elapses with no new audio the buffer is flushed to Whisper immediately.
- on_transcript(text) callback fires for every non-empty result.

Twilio delivers 8 kHz, 1-channel, mulaw-encoded audio frames (160 bytes = 20 ms each).
All codec conversions are pure Python — no pydub, no ffmpeg, no audioop.
"""
import asyncio
import io
import struct
import wave
import structlog

from collections.abc import Awaitable, Callable
from fastapi import WebSocket
from openai import AsyncOpenAI

from app.settings import OPENAI_API_KEY
from app.utils import is_valid_text

logger = structlog.get_logger(__name__)

SAMPLE_RATE = 8000
CHANNELS = 1
SAMPLE_WIDTH = 2           # bytes per sample after mulaw → PCM16 conversion

# Safety cap: flush at ~3 seconds of accumulated audio regardless of silence
MAX_PROBE_BUFFER_BYTES = SAMPLE_RATE * SAMPLE_WIDTH * CHANNELS * 1.5

# Pre-computed G.711 ulaw → PCM16 lookup table (avoids per-byte Python loop).
_ULAW_TABLE: list[int] = []
for _b in range(256):
    _byte = ~_b & 0xFF
    _sign = _byte & 0x80
    _exp  = (_byte >> 4) & 0x07
    _mant = _byte & 0x0F
    _s    = (((_mant << 1) | 0x21) << _exp) - 0x21
    _ULAW_TABLE.append(-_s if _sign else _s)

_openai = AsyncOpenAI(api_key=OPENAI_API_KEY)


def _ulaw2lin(data: bytes) -> bytes:
    """Convert G.711 ulaw bytes to signed 16-bit PCM bytes using a lookup table."""
    n = len(data)
    out = bytearray(n * 2)
    for i in range(n):
        struct.pack_into('<h', out, i * 2, _ULAW_TABLE[data[i]])
    return bytes(out)


def _pcm_to_wav(pcm_data: bytes) -> bytes:
    """Wrap raw PCM16 bytes in a minimal WAV container."""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(CHANNELS)
        wf.setsampwidth(SAMPLE_WIDTH)
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(pcm_data)
    return buf.getvalue()


async def _transcribe(wav_bytes: bytes) -> str:
    """Send WAV bytes to Whisper-1 and return the transcript text."""
    try:
        response = await _openai.audio.transcriptions.create(
            model="whisper-1",
            file=("audio.wav", wav_bytes, "audio/wav"),
        )
        text = (response.text or "").strip()
        
        return text
    except Exception:
        logger.exception("stt_transcription_error")
        return ""


class WhisperSTTClient:
    """
    Accumulates mulaw audio from Twilio and transcribes via Whisper when
    the caller pauses or the buffer limit is reached.
    Calls on_transcript(text) for every non-empty transcription.
    """

    def __init__(
        self,
        socket: WebSocket,
        stream_sid: str,
        on_transcript: Callable[[str], Awaitable[None]],
        on_barge_in: Callable[[], Awaitable[None]] | None = None,
    ):
        self._on_transcript = on_transcript
        self._on_barge_in = on_barge_in
        self._pcm_buffer: bytearray = bytearray()
        self._probe_buffer: bytearray = bytearray()
        self._probe_task: asyncio.Task | None = None
        # Guard against concurrent flushes (silence timer vs probe vs cap).
        self._flushing = False
        self.socket = socket
        self.stream_sid = stream_sid

    async def send_audio(self, mulaw_bytes: bytes) -> None:
        """Accept one mulaw audio chunk from Twilio and buffer it."""
        pcm_chunk = _ulaw2lin(mulaw_bytes)
        self._probe_buffer.extend(pcm_chunk)
        self._pcm_buffer.extend(pcm_chunk)

        if len(self._probe_buffer) >= MAX_PROBE_BUFFER_BYTES:
            asyncio.create_task(self._flush())

    async def close(self) -> None:
        """Flush any remaining buffered audio when the call ends."""
        self._cancel_background_tasks()
        if self._pcm_buffer:
            await self._flush()
        logger.info("stt_client_closed")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _cancel_background_tasks(self) -> None:
        if self._probe_task and not self._probe_task.done():
            self._probe_task.cancel()

    async def _flush(self) -> None:
        """Convert buffered Probe to WAV and send to Whisper."""
        if not self._probe_buffer or self._flushing:
            return
        self._flushing = True
        try:
            self._cancel_background_tasks()
            probe_data = bytes(self._probe_buffer)
            self._probe_buffer.clear()
            wav_bytes = _pcm_to_wav(probe_data)
            transcript = await _transcribe(wav_bytes)

            logger.info("Probe", transcript=transcript)

            if not is_valid_text(transcript):
                # Probe window was silent — end of utterance. Transcribe the
                # full accumulated buffer and forward to the agent.
                pcm_data = bytes(self._pcm_buffer)
                self._pcm_buffer.clear()
                wav_bytes = _pcm_to_wav(pcm_data)
                transcript = await _transcribe(wav_bytes)
                if transcript:
                    await self._on_transcript(transcript)
            else:
                # Probe detected active speech — caller is talking over the
                # agent (barge-in). Signal the caller immediately so TTS is
                # cancelled and Twilio's playback queue is cleared.
                if self._on_barge_in:
                    await self._on_barge_in()
        finally:
            self._flushing = False

