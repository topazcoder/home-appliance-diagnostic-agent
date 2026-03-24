import logging
import structlog

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.middleware import add_request_response_logger_middleware
from app.routes import media, sessions, technicians, twilio


# disable uvicorn access logs (handled by custom middleware instead)
logging.getLogger('uvicorn.access').disabled = True

structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.StackInfoRenderer(),
        structlog.dev.set_exc_info,
        structlog.processors.TimeStamper(fmt='iso'),
        structlog.processors.JSONRenderer(),
    ],
    wrapper_class=structlog.make_filtering_bound_logger(logging.DEBUG),
    context_class=dict,
    logger_factory=structlog.PrintLoggerFactory(),
    cache_logger_on_first_use=False,
)

app = FastAPI(title="SHS Appliance Diagnostic Agent")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

add_request_response_logger_middleware(app)

# REST routes
app.include_router(sessions.router)
app.include_router(technicians.router)
app.include_router(twilio.router)
app.include_router(media.router)
