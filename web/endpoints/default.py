import asyncio
from logging import getLogger
from typing import Any

from adc_aiopg.types import Base
from adc_webkit.web import JsonEndpoint, Response
from adc_webkit.web.openapi import Doc
from aiohttp.web import HTTPServiceUnavailable

logger = getLogger(__name__)


async def _check_component_ready(obj: Any) -> bool:
    """
    Return True if component is ready.

    Supports adc-appkit components (with async is_alive) and asyncpg Pool-like objects.
    Never raises (readiness endpoint must not 500).
    """
    try:
        is_alive = getattr(obj, "is_alive", None)
        if callable(is_alive):
            return bool(await is_alive())

        # asyncpg Pool (or pool-like): has acquire()/release() or is async context manager
        acquire = getattr(obj, "acquire", None)
        if callable(acquire):
            conn = await acquire()
            try:
                fetchval = getattr(conn, "fetchval", None)
                if callable(fetchval):
                    await fetchval("SELECT 1")
                return True
            finally:
                release = getattr(obj, "release", None)
                if callable(release):
                    await release(conn)
                else:
                    close = getattr(conn, "close", None)
                    if callable(close):
                        await close()

        return bool(obj)
    except Exception:
        logger.exception("Readiness check failed for %r", obj)
        return False


class LivenessResponse(Base):
    status: str


class Liveness(JsonEndpoint):
    doc = Doc(tags=["default"], summary="check if the server is running")

    response = Response(LivenessResponse)

    async def execute(self, _: object) -> dict[str, str]:
        return {"status": "ok"}


class ReadinessResponse(Base):
    pg: bool
    # s3: bool
    # http: bool


class Readiness(JsonEndpoint):
    doc = Doc(tags=["default"], summary="check if the server is ready")

    response = Response(ReadinessResponse)

    async def execute(self, _: object) -> dict[str, bool]:
        components = list(ReadinessResponse.__annotations__)
        statuses = await asyncio.gather(
            *(_check_component_ready(getattr(self.web.state.app, com)) for com in components),
        )
        result = dict(zip(components, statuses, strict=True))
        if not all(statuses):
            raise HTTPServiceUnavailable(text=str(result))
        return result
