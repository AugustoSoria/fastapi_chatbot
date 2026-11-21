"""Rate limiting por IP para el endpoint /ask/."""

import logging
import os

from fastapi import Request
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

logger = logging.getLogger(__name__)

TRUSTED_PROXY_HOPS = max(0, int(os.getenv("TRUSTED_PROXY_HOPS", "2")))

# Permite desactivar el límite en tests (ver tests/conftest.py).
RATE_LIMIT_ENABLED = os.getenv("RATE_LIMIT_ENABLED", "true").lower() != "false"

_LOG_CLIENT_IP = os.getenv("LOG_CLIENT_IP", "").lower() in ("1", "true", "yes")


def client_ip(request: Request) -> str:
    xff = request.headers.get("x-forwarded-for")
    cf = request.headers.get("cf-connecting-ip")
    ip: str
    if xff:
        parts = [p.strip() for p in xff.split(",") if p.strip()]
        if parts:
            idx = len(parts) - 1 - TRUSTED_PROXY_HOPS
            if idx < 0:
                idx = 0
            ip = parts[idx]
        else:
            ip = get_remote_address(request)
    else:
        ip = get_remote_address(request)

    if _LOG_CLIENT_IP:
        logger.warning("client_ip: xff=%r cf=%r hops=%d -> %s", xff, cf, TRUSTED_PROXY_HOPS, ip)
    return ip


limiter = Limiter(
    key_func=client_ip,
    enabled=RATE_LIMIT_ENABLED,
    strategy="moving-window",
)


async def rate_limit_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    return JSONResponse(
        status_code=429,
        content={"detail": "Demasiados pedidos. Esperá un momento y volvé a intentar."},
    )
