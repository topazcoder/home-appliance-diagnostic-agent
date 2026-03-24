import os
from dotenv import load_dotenv

load_dotenv()

# Database
DATABASE_URL = os.getenv(
    'DATABASE_URL',
    'postgresql+asyncpg://postgres:123456@127.0.0.1:5432/appdiag'
)

# Redis
REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379')

# OpenAI
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY', '')
LLM_MODEL = os.getenv('LLM_MODEL', 'gpt-4o')
EMBEDDING_MODEL = os.getenv('EMBEDDING_MODEL', 'text-embedding-3-small')
RAG_TOK_K = int(os.getenv('RAG_TOP_K', '4'))

# -----------------------------------------------------------------
# Voice / Telephony
# -----------------------------------------------------------------
# Twilio credentials (required for live calls)
TWILIO_ACCOUNT_SID = os.getenv('TWILIO_ACCOUNT_SID', '')
TWILIO_AUTH_TOKEN = os.getenv('TWILIO_AUTH_TOKEN', '')
TWILIO_PHONE_NUMBER = os.getenv('TWILIO_PHONE_NUMBER', '')

# OpenAI TTS
OPENAI_TTS_MODEL = os.getenv('OPENAI_TTS_MODEL', 'tts-1')
OPENAI_TTS_VOICE = os.getenv('OPENAI_TTS_VOICE', 'alloy')

# Voice session TTL (in-memory, per call)
SESSION_TTL_SECONDS = int(os.getenv('SESSION_TTL_SECONDS', '3600'))

# Public base URL (e.g. ngrok) so Twilio can reach the /voice/stream WebSocket
PUBLIC_BASE_URL = os.getenv('PUBLIC_BASE_URL', 'http://localhost:8000')

# -----------------------------------------------------------------
# Email (Brevo — free tier, no credit card needed)
# -----------------------------------------------------------------
BREVO_API_KEY       = os.getenv('BREVO_API_KEY', '')
BREVO_FROM_EMAIL    = os.getenv('BREVO_FROM_EMAIL', 'noreply@searsappliancecare.com')
BREVO_FROM_NAME     = os.getenv('BREVO_FROM_NAME', 'Sears Home Services')

# Local file storage for uploaded appliance images
UPLOADS_DIR = os.getenv('UPLOADS_DIR', '/tmp/appliance-uploads')
