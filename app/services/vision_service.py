import base64
import logging
from pathlib import Path

import openai

from app.settings import OPENAI_API_KEY, UPLOADS_DIR

logger = logging.getLogger(__name__)
_openai = openai.AsyncOpenAI(api_key=OPENAI_API_KEY)
_uploads = Path(UPLOADS_DIR)


class VisionService:
    """Analyze appliance photos with GPT-4o vision (local file storage)."""

    async def analyze_appliance_image(self, object_key: str, appliance_type: str) -> dict:
        """
        Load image from local storage and analyze with GPT-4o vision.

        Args:
            object_key: Relative path inside UPLOADS_DIR (e.g. 'session-id/uuid.jpg')
            appliance_type: e.g. 'washer', 'dryer', 'fridge'
        """
        file_path = _uploads / object_key
        if not file_path.exists():
            return {"success": False, "error": "Image not found", "object_key": object_key}

        suffix = file_path.suffix.lower()
        mime = {"jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png",
                ".webp": "image/webp", ".gif": "image/gif"}.get(suffix, "image/jpeg")

        image_b64 = base64.standard_b64encode(file_path.read_bytes()).decode()

        try:
            resp = await _openai.chat.completions.create(
                model="gpt-4o",
                max_tokens=512,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are an expert appliance repair technician. "
                            "Analyze the photo and describe visible issues concisely."
                        ),
                    },
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": (
                                    f"Analyze this {appliance_type} photo. "
                                    "List visible damage, wear, or anomalies, "
                                    "then give one or two actionable repair recommendations."
                                ),
                            },
                            {
                                "type": "image_url",
                                "image_url": {"url": f"data:{mime};base64,{image_b64}", "detail": "high"},
                            },
                        ],
                    },
                ],
            )
        except Exception as exc:
            logger.error("Vision analysis failed: %s", exc)
            return {"success": False, "error": str(exc), "object_key": object_key}

        return {
            "success": True,
            "appliance_type": appliance_type,
            "object_key": object_key,
            "analysis": resp.choices[0].message.content,
        }
