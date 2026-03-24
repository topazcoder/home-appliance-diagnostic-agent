import json
import time
import uuid
import structlog

from fastapi import FastAPI, Request, Response
from http import HTTPStatus
from typing import Any

from app.api.request_context import request_id_context
from app.utils.logger_utils import LOGGING_HEADERS

logger = structlog.get_logger(__name__)

# Paths that are polled frequently and should not be logged on every request.
_SKIP_LOGGING_PATHS = frozenset({'/health'})


def _should_skip_logging(request: Request) -> bool:
    """Return True for noisy polling endpoints that should not be logged."""
    if request.url.path in  _SKIP_LOGGING_PATHS:
        return True


def safe_status_code(status_code: int) -> int:
    """Convert non-standard status codes to standard ones"""
    # Check if status_code is a valid HTTP status code
    valid_status_codes = {status.value for status in HTTPStatus}
    if status_code in valid_status_codes:
        return status_code
    else:
        # Unknown non-standard code, default to 500
        logger.warning(f'Unknown non-standard status code {status_code} mapped to 500')
        return 500


def add_request_response_logger_middleware(app: FastAPI) -> None:
    @app.middleware('http')
    async def log_request_response(request: Request, call_next: Any) -> Any:
        request_id = str(uuid.uuid4())
        request_id_context.set(request_id)

        request_body = None
        if request.headers.get('content-type', '') == 'application/json':
            request_body = await request.body()
            request = Request(request.scope, request.receive)
            request._body = request_body

        start_time = time.time()
        response = await call_next(request)
        duration = time.time() - start_time

        skip = _should_skip_logging(request)

        if not skip:
            try:
                parsed_body = json.loads(request_body) if request_body else None
            except (json.JSONDecodeError, ValueError):
                parsed_body = request_body.decode('utf-8') if request_body else None

            logger.info(
                'Request',
                method=request.method,
                path=request.url.path,
                query_params=request.query_params,
                headers={header: value for header, value in request.headers.items() if header in LOGGING_HEADERS},
                message=parsed_body,
            )

        if response.headers.get('content-type', '') == 'application/json':
            try:
                response_body = b''
                async for chunk in response.body_iterator:
                    response_body += chunk

                if not skip:
                    logger.info(
                        'Response',
                        status_code=response.status_code,
                        time_sec=duration,
                        message=json.loads(response_body) if response_body else None,
                    )

                return Response(
                    content=response_body,
                    status_code=safe_status_code(response.status_code),
                    headers=dict(response.headers),
                    media_type=response.media_type,
                )
            except Exception as e:
                logger.exception(
                    'Response',
                    status_code=response.status_code,
                    message='Could not parse response body',
                    exc_info=e,
                )

        if not skip:
            logger.info(
                'Respnose',
                status_code=response.status_code,
                time_sec=duration,
            )

        return response
