"""Rate limiting por IP para el endpoint /ask/.

Groq solo ve a nuestro servidor (todas las llamadas salen con la misma API key),
así que no puede distinguir usuarios. El límite por IP que distingue a un
abusador de un usuario real tiene que vivir acá, en el backend.

Detalle clave detrás del proxy de Render: la IP del socket (request.client.host)
es la del proxy, no la del visitante. La IP real viene en X-Forwarded-For. Pero
ese header es falsificable: el cliente puede mandar "X-Forwarded-For: 1.2.3.4" y
el proxy de Render AGREGA la IP real al final. Por eso NO se toma la primera
(izquierda, que el cliente controla) sino la que agregó nuestro proxy de
confianza, contando desde la derecha.
"""

import logging
import os

from fastapi import Request
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

logger = logging.getLogger(__name__)

# Cuántos proxies de confianza hay entre el visitante y la app. En Render suele
# ser 1 (su load balancer). Si el XFF real trae más saltos (ej. Cloudflare
# delante), subí este número. Para verificar: poné LOG_CLIENT_IP=1 y mirá en los
# logs el XFF crudo vs la IP resuelta con tráfico real.
TRUSTED_PROXY_HOPS = max(1, int(os.getenv("TRUSTED_PROXY_HOPS", "1")))

# Permite desactivar el límite en tests (ver tests/conftest.py).
RATE_LIMIT_ENABLED = os.getenv("RATE_LIMIT_ENABLED", "true").lower() != "false"

_LOG_CLIENT_IP = os.getenv("LOG_CLIENT_IP", "").lower() in ("1", "true", "yes")


def client_ip(request: Request) -> str:
    """IP real del visitante, resistente al spoofeo de X-Forwarded-For."""
    xff = request.headers.get("x-forwarded-for")
    ip: str
    if xff:
        parts = [p.strip() for p in xff.split(",") if p.strip()]
        if parts:
            # La IP que agregó nuestro proxy de confianza, contando desde la
            # derecha. Con 1 salto es la última; el cliente no la puede falsear.
            idx = max(0, len(parts) - TRUSTED_PROXY_HOPS)
            ip = parts[idx]
        else:
            ip = get_remote_address(request)
    else:
        # Sin proxy delante (local/tests): la IP del socket.
        ip = get_remote_address(request)

    if _LOG_CLIENT_IP:
        logger.info("client_ip: xff=%r hops=%d -> %s", xff, TRUSTED_PROXY_HOPS, ip)
    return ip


limiter = Limiter(
    key_func=client_ip,
    enabled=RATE_LIMIT_ENABLED,
    # Ventana deslizante: un límite por minuto no deja colar ráfagas al filo del
    # reloj como haría la ventana fija.
    strategy="moving-window",
    # Almacenamiento en memoria: alcanza para una sola instancia como la de
    # Render. Si algún día escalás a varias instancias, cambiá esto por Redis
    # (storage_uri="redis://...") para que el contador sea global.
)


async def rate_limit_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    """Respuesta amable en 429 cuando se supera el límite."""
    return JSONResponse(
        status_code=429,
        content={"detail": "Demasiados pedidos. Esperá un momento y volvé a intentar."},
    )
