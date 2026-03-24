"""
OpenAI Whisper Speech-to-Text client.

Buffers incoming mulaw audio from Twilio Media Streams, converts to WAV,
and transcribes via the OpenAI Whisper REST API (whisper-1).

Architecture: buffered-batch (not streaming).
- Audio chunks (mulaw) are accumulated in memory.
- A silence timer resets on every new chunk; when SILENCE_THRESHOLD_MS
  elapses with no new audio the buffer is flushed to Whisper.
- Buffer is also flushed if it exceeds MAX_BUFFER_BYTES (~8 s of audio).
- on_transcript(text) callback fires for every non-empty result.

Twilio delivers 8 kHz, 1-channel, mulaw-encoded audio frames (160 bytes = 20 ms each).
All codec conversions are pure Python — no pydub, no ffmpeg, no audioop.
"""
import asyncio
import io
import struct
import wave
from collections.abc import Awaitable, Callable

import structlog
from openai import AsyncOpenAI

from app.settings import OPENAI_API_KEY

logger = structlog.get_logger(__name__)

SAMPLE_RATE = 8000
CHANNELS = 1
SAMPLE_WIDTH = 2           # bytes per sample after mulaw → PCM16 conversion

# Flush when caller pauses for this long (milliseconds)
SILENCE_THRESHOLD_MS = 700
# Safety cap: flush at ~8 seconds of accumulated audio regardless of silence
MAX_BUFFER_BYTES = SAMPLE_RATE * SAMPLE_WIDTH * CHANNELS * 8

_openai = AsyncOpenAI(api_key=OPENAI_API_KEY)


def _ulaw2lin(data: bytes) -> bytes:
    """Convert G.711 ulaw bytes to signed 16-bit PCM bytes (replaces audioop.ulaw2lin)."""
    out = bytearray(len(data) * 2)
    for i, byte in enumerate(data):
        byte = ~byte & 0xFF
        sign = byte & 0x80
        exp  = (byte >> 4) & 0x07
        mant = byte & 0x0F
        sample = ((mant << 1) | 0x21) << exp
        sample -= 0x21
        if sign:
            sample = -sample
        struct.pack_into('<h', out, i * 2, max(-32768, min(32767, sample)))
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

    def __init__(self, on_transcript: Callable[[str], Awaitable[None]]):
        self._on_transcript = on_transcript
        self._pcm_buffer: bytearray = bytearray()
        self._silence_task: asyncio.Task | None = None

    async def send_audio(self, mulaw_bytes: bytes) -> None:
        """Accept one mulaw audio chunk from Twilio and buffer it."""
        pcm_chunk = _ulaw2lin(mulaw_bytes)
        self._pcm_buffer.extend(pcm_chunk)

        # Reset the silence timer every time new audio arrives
        if self._silence_task and not self._silence_task.done():
            self._silence_task.cancel()

        if len(self._pcm_buffer) >= MAX_BUFFER_BYTES:
            await self._flush()
        else:
            self._silence_task = asyncio.create_task(self._silence_flush())

    async def close(self) -> None:
        """Flush any remaining buffered audio when the call ends."""
        if self._silence_task and not self._silence_task.done():
            self._silence_task.cancel()
        if self._pcm_buffer:
            await self._flush()
        logger.info("stt_client_closed")

    async def _silence_flush(self) -> None:
        """Wait for the silence threshold, then flush."""
        try:
            await asyncio.sleep(SILENCE_THRESHOLD_MS / 1000)
            await self._flush()
        except asyncio.CancelledError:
            pass

    async def _flush(self) -> None:
        """Convert buffered PCM to WAV and send to Whisper."""
        if not self._pcm_buffer:
            return
        pcm_data = bytes(self._pcm_buffer)
        self._pcm_buffer.clear()
        wav_bytes = _pcm_to_wav(pcm_data)
        transcript = await _transcribe(wav_bytes)
        if transcript:
            await self._on_transcript(transcript)
