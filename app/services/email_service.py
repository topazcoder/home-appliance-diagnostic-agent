import uuid
import httpx

from app.settings import BREVO_API_KEY, BREVO_FROM_EMAIL, BREVO_FROM_NAME, PUBLIC_BASE_URL

_BREVO_SEND_URL = "https://api.brevo.com/v3/smtp/email"


class EmailService:
    """Send transactional emails via Brevo (free tier, no credit card)."""

    async def send_image_upload_email(
        self,
        customer_email: str,
        customer_name: str,
        session_id: str,
        appliance_type: str,
    ) -> dict:
        upload_token = str(uuid.uuid4())
        upload_url = f"{PUBLIC_BASE_URL}/media/upload/{session_id}/{upload_token}"

        payload = {
            "sender": {"name": BREVO_FROM_NAME, "email": BREVO_FROM_EMAIL},
            "to": [{"email": customer_email, "name": customer_name}],
            "subject": f"Upload your {appliance_type} photo — Sears Home Services",
            "htmlContent": (
                f"<html><body style='font-family:Arial,sans-serif;color:#333'>"
                f"<h2>Hi {customer_name},</h2>"
                f"<p>Please upload a photo of your <strong>{appliance_type}</strong> "
                f"so our technician can better diagnose the issue.</p>"
                f"<p><a href='{upload_url}' style='background:#2563eb;color:white;"
                f"padding:12px 24px;border-radius:6px;text-decoration:none;"
                f"font-weight:bold;display:inline-block'>Upload Photo</a></p>"
                f"<p><strong>This link expires in 1 hour.</strong></p>"
                f"<p>Best regards,<br/>Sears Home Services</p>"
                f"</body></html>"
            ),
        }

        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(
                    _BREVO_SEND_URL,
                    json=payload,
                    headers={"api-key": BREVO_API_KEY, "content-type": "application/json"},
                )

            if resp.status_code not in (200, 201):
                return {
                    "success": False,
                    "upload_token": upload_token,
                    "upload_url": upload_url,
                    "error": f"Brevo API error {resp.status_code}: {resp.text}",
                }

            return {
                "success": True,
                "upload_token": upload_token,
                "upload_url": upload_url,
                "message": f"Upload link sent to {customer_email}",
            }

        except Exception as exc:
            return {
                "success": False,
                "upload_token": upload_token,
                "upload_url": upload_url,
                "error": str(exc),
            }