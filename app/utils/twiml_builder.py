"""
Helpers to build TwiML XML responses for Twilio Voice.
"""
from app.settings import PUBLIC_BASE_URL


def build_stream_twiml(call_sid: str) -> str:
    """
    Return TwiML that opens a bidirectional Media Stream WebSocket
    back to our /voice/stream endpoint.
    """
    ws_url = (
        PUBLIC_BASE_URL
        .replace("https://", "wss://")
        .replace("http://", "ws://")
        + "/voice/stream"
    )
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Connect>
    <Stream url="{ws_url}">
      <Parameter name="callSid" value="{call_sid}"/>
    </Stream>
  </Connect>
</Response>"""
