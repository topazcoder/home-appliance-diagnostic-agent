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
SAMPLE_WIDTH = 2   # bytes per PCM16 sample
CHUNK_SIZE = 160   # 20 ms of audio at 8 kHz


async def stream_tts(
    websocket: WebSocket,
    stream_sid: str,
    text: str,
    interrupt_event: asyncio.Event,
):
    """
    Synthesize speech sentence-by-sentence using the OpenAI streaming TTS API
    and forward mulaw audio chunks to Twilio as they arrive.

    Each sentence is requested as a streaming HTTP response so the first audio
    bytes reach Twilio before the full sentence has been synthesized, cutting
    perceived TTS latency significantly compared to buffering the whole response.
    """
    sentences = _split_sentences(text)
    pcm_carry = bytearray()  # leftover PCM bytes that didn't fill a full downsample step

    for sentence in sentences:
        if interrupt_event.is_set():
            break
        if not sentence.strip():
            continue
        try:
            async with _openai_client.audio.speech.with_streaming_response.create(
                model=OPENAI_TTS_MODEL,
                voice=OPENAI_TTS_VOICE,
                input=sentence,
                response_format="pcm",  # raw PCM16 @ 24 kHz, no container
            ) as response:
                async for pcm_chunk in response.iter_bytes(chunk_size=4096):
                    if interrupt_event.is_set():
                        return
                    # Accumulate with any leftover bytes from the previous network chunk
                    pcm_carry.extend(pcm_chunk)
                    # Keep only complete pairs of samples for the 3:1 downsampler
                    # (each PCM16 sample = 2 bytes; we consume groups of 6 bytes → 1 mulaw byte)
                    step_bytes = (OPENAI_PCM_RATE // TWILIO_SAMPLE_RATE) * SAMPLE_WIDTH  # 6
                    usable = len(pcm_carry) - (len(pcm_carry) % step_bytes)
                    if usable == 0:
                        continue
                    mulaw_raw = _pcm24k_to_mulaw8k(bytes(pcm_carry[:usable]))
                    pcm_carry = pcm_carry[usable:]
                    for chunk in _chunk(mulaw_raw, CHUNK_SIZE):
                        if interrupt_event.is_set():
                            return
                        payload = base64.b64encode(chunk).decode("utf-8")
                        await websocket.send_json({
                            "event": "media",
                            "streamSid": stream_sid,
                            "media": {"payload": payload},
                        })
                        await asyncio.sleep(0)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("TTS streaming error for sentence: %s", sentence)


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
