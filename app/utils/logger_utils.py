import json
import structlog

from httpx import Request, Response
from structlog.typing import EventDict, WrappedLogger

from app.api.request_context import request_id_context


logger = structlog.get_logger(__name__)

LOGGING_HEADERS = {
    'content-type',
    'user-agent',
    'accept',
    'authorization',
    'content-length',
    'host',
}


def log_httpx_request(request: Request) -> None:
    try:
        body_content = None
        if request.content:
            try:
                if 'application/json' in request.headers.get('content-type', ''):
                    body_content = json.loads(request.content.decode())
            except Exception as e:
                body_content = f'|error parsing body: {e!s}'

        logger.info(
            'ClientRequest',
            method=request.method,
            url=str(request.url),
            headers={header: value for header, value in request.headers.item() if header.lower() in LOGGING_HEADERS},
            body=body_content if request.content else '[no content]',
        )
    except Exception as e:
        logger.exception(
            'ClientRequest logging failed',
            error=str(e),
            request_method=getattr(request, 'method', None),
            request_url=str(getattr(request, 'url', None)),
        )


def log_httpx_response(response: Response) -> None:
    try:
        request = response.request
        body_content = None
        if 'application/json' in response.headers.get('content-type', ''):
            response.read()
            body_content = response.json()
        logger.info(
            'ClientResponse',
            request_method=request.method,
            request_url=str(request.url),
            response_status_code=response.status_code,
            response_body=body_content if response.content else None,
            response_latency=f'{response.elapsed.total_seconds():.3f}s' if hasattr(response, 'elapsed') else None,
        )
    except Exception as exc:
        logger.exception(
            'ClientResponse logging failed',
            error=str(exc),
            response_status=getattr(response, 'status_code', None),
            response_url=str(getattr(getattr(response, 'request', None), 'url', None)),
        )


def add_context_fields(logger: WrappedLogger, method_name: str, event_dict: EventDict) -> EventDict:
    event_dict['request_id'] = request_id_context.get()
    return event_dict
