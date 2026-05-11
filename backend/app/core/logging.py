from __future__ import annotations

import logging
import time
from collections.abc import Awaitable, Callable

from fastapi import Request, Response

LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s - %(message)s"


def setup_logging() -> None:
    logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)


async def request_logging_middleware(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    logger = logging.getLogger("api.requests")
    start = time.perf_counter()

    try:
        response = await call_next(request)
    except Exception:  # noqa: BLE001
        logger.exception("Unhandled error: %s %s", request.method, request.url.path)
        raise

    duration_ms = round((time.perf_counter() - start) * 1000, 2)
    logger.info(
        "%s %s -> %s in %sms",
        request.method,
        request.url.path,
        response.status_code,
        duration_ms,
    )
    return response
