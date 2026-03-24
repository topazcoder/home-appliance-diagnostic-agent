"""
Media upload route — Tier 3 (Visual Diagnosis).

POST /media/upload/{session_id}/{token}
  Accepts a multipart image upload from the customer's email link.
  Saves the file to local storage and returns the object_key
  the agent passes to analyze_appliance_image.

GET /media/upload/{session_id}/{token}
  Returns a minimal HTML form so customers can upload from any browser.
"""
import uuid
from pathlib import Path

import redis.asyncio as redis
import structlog
from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse

from app.settings import REDIS_URL, UPLOADS_DIR

_redis = redis.from_url(REDIS_URL, decode_responses=True)
# Redis key pattern: "image_ready:{session_id}" → object_key
_IMAGE_READY_TTL = 3600  # 1 hour

logger = structlog.get_logger(__name__)
_uploads = Path(UPLOADS_DIR)
_uploads.mkdir(parents=True, exist_ok=True)

_ALLOWED_MIME = {"image/jpeg", "image/png", "image/webp", "image/gif"}
_MAX_BYTES = 10 * 1024 * 1024  # 10 MB

router = APIRouter(prefix="/media", tags=["media"])


@router.get("/upload/{session_id}/{token}", response_class=HTMLResponse)
async def upload_form(session_id: str, token: str):
    """Serve a simple HTML upload form for the customer."""
    return HTMLResponse(f"""
    <!doctype html><html><head><meta charset="utf-8">
    <meta name="viewport" content="width=device-width,initial-scale=1">
    <title>Upload Appliance Photo</title>
    <style>
      body{{font-family:Arial,sans-serif;max-width:480px;margin:60px auto;padding:0 16px;color:#333}}
      h2{{color:#1e40af}} button{{background:#2563eb;color:#fff;border:none;padding:12px 28px;
      border-radius:6px;font-size:1rem;cursor:pointer;margin-top:12px}}
      input[type=file]{{margin-top:12px;display:block}}
    </style></head><body>
    <h2>Sears Home Services</h2>
    <p>Please upload a clear photo of your appliance so our technician can diagnose the issue.</p>
    <form method="post" enctype="multipart/form-data"
          action="/media/upload/{session_id}/{token}">
      <input type="file" name="file" accept="image/*" required>
      <button type="submit">Upload Photo</button>
    </form>
    </body></html>
    """)


@router.post("/upload/{session_id}/{token}")
async def upload_image(session_id: str, token: str, file: UploadFile = File(...)):
    """Receive and save the uploaded appliance photo."""
    if file.content_type not in _ALLOWED_MIME:
        raise HTTPException(status_code=415, detail="Only JPEG, PNG, WebP, or GIF allowed.")

    contents = await file.read()
    if len(contents) > _MAX_BYTES:
        raise HTTPException(status_code=413, detail="File too large (max 10 MB).")

    ext = (file.filename or "photo.jpg").rsplit(".", 1)[-1].lower()
    if ext not in {"jpg", "jpeg", "png", "webp", "gif"}:
        ext = "jpg"

    dest_dir = _uploads / session_id
    dest_dir.mkdir(parents=True, exist_ok=True)

    filename = f"{uuid.uuid4()}.{ext}"
    dest = dest_dir / filename
    dest.write_bytes(contents)

    object_key = f"{session_id}/{filename}"
    logger.info("Image uploaded", session_id=session_id, object_key=object_key, bytes=len(contents))

    # Notify the active call: push object_key so the agent can pick it up
    await _redis.set(f"image_ready:{session_id}", object_key, ex=_IMAGE_READY_TTL)

    return JSONResponse(
        content={"success": True, "object_key": object_key, "session_id": session_id},
        status_code=201,
    )
