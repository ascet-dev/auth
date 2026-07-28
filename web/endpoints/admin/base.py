"""Базовые классы admin CRUD API: guard, роли, generic list/get/create/update/archive."""

from __future__ import annotations

from abc import ABC
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Any, ClassVar

from adc_aiopg import RowNotFoundError
from adc_webkit.errors import BadRequest, Forbidden, NotFound, Unauthorized
from adc_webkit.web import Ctx, JsonEndpoint
from asyncpg.exceptions import UniqueViolationError

from models.enums import AdminRole
from web.auth import admin_jwt

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from adc_aiopg.repository import PGDataAccessObject

    from services import App


class Conflict(BadRequest):
    description = "Conflict"
    status_code = 409


@asynccontextmanager
async def conflict_on_unique() -> AsyncIterator[None]:
    """
    Гонка на unique-индексе — это 409, а не 500: pre-check в эндпоинтах ловит
    обычный случай, но два параллельных create проскакивают мимо него.
    """
    try:
        yield
    except UniqueViolationError as e:
        raise Conflict(message="Resource with these unique fields already exists") from e


def dump_entity(entity: Any) -> dict:
    """model_dump + системные поля, которые BaseModel исключает из сериализации."""
    data = entity.model_dump()
    for field in ("created", "updated", "archived"):
        if hasattr(entity, field):
            data.setdefault(field, getattr(entity, field))
    return data


class AdminEndpoint(JsonEndpoint, ABC):
    """Все admin-эндпоинты: admin_jwt guard + DB-проверка гранта через CurrentAdmin."""

    auth = admin_jwt

    # None — достаточно любого активного гранта; AdminRole.OWNER — только владелец
    require_role: ClassVar[AdminRole | None] = None

    @asynccontextmanager
    async def admin_scope(self, ctx: Ctx) -> AsyncIterator[App]:
        app: App = ctx.request.app.state.app
        scope = app.request_scope({"current_admin": {"sub": ctx.auth_payload.sub, "dao": app.dao}})
        try:
            await scope.__aenter__()
        except ValueError as e:
            # identity не активна или грант отозван — токен больше не годится
            raise Unauthorized(message=str(e)) from e
        try:
            if self.require_role and app.current_admin.role != self.require_role:
                raise Forbidden(message=f"{self.require_role} role required")
            yield app
        finally:
            await scope.__aexit__(None, None, None)


class AdminResourceEndpoint(AdminEndpoint, ABC):
    table: ClassVar[str]  # имя атрибута DAO, например "client_apps"

    def dao(self, app: App) -> PGDataAccessObject:
        return getattr(app.dao, self.table)

    def serialize(self, entity: Any) -> dict:
        return dump_entity(entity)


class AdminList(AdminResourceEndpoint, ABC):
    order_by: ClassVar[str] = "-created"

    async def execute(self, ctx: Ctx) -> dict:
        async with self.admin_scope(ctx) as app:
            filters = ctx.query.model_dump(exclude_none=True, exclude={"limit", "offset"})
            result = await self.dao(app).paginated_search(
                order_by=self.order_by,
                limit=ctx.query.limit,
                offset=ctx.query.offset,
                **filters,
            )
            return {
                "items": [self.serialize(item) for item in result.items],
                "pagination": result.pagination.model_dump(),
            }


class AdminGet(AdminResourceEndpoint, ABC):
    async def execute(self, ctx: Ctx) -> dict:
        async with self.admin_scope(ctx) as app:
            try:
                entity = await self.dao(app).get_by_id(ctx.query.id)
            except RowNotFoundError:
                raise NotFound(message="Not found") from None
            return self.serialize(entity)


class AdminCreate(AdminResourceEndpoint, ABC):
    async def execute(self, ctx: Ctx) -> dict:
        async with self.admin_scope(ctx) as app, conflict_on_unique():
            payload = self.build_create_payload(ctx)
            entity = await self.dao(app).create(**payload)
            return self.serialize(entity)

    def build_create_payload(self, ctx: Ctx) -> dict:
        return ctx.body.model_dump()


class AdminUpdate(AdminResourceEndpoint, ABC):
    async def execute(self, ctx: Ctx) -> dict:
        async with self.admin_scope(ctx) as app, conflict_on_unique():
            payload = self.build_update_payload(ctx)
            if not payload:
                raise BadRequest(message="Nothing to update")
            try:
                entity = await self.dao(app).update_by_id(ctx.query.id, **payload)
            except RowNotFoundError:
                raise NotFound(message="Not found") from None
            return self.serialize(entity)

    def build_update_payload(self, ctx: Ctx) -> dict:
        # exclude_none: явный null в PATCH означает «не менять», а не «записать NULL»
        # (иначе {"name": null} доезжал до БД и падал на NOT NULL с 500)
        return ctx.body.model_dump(exclude_unset=True, exclude_none=True)


class AdminArchive(AdminResourceEndpoint, ABC):
    async def execute(self, ctx: Ctx) -> dict:
        async with self.admin_scope(ctx) as app:
            try:
                await self.dao(app).archive_by_id(ctx.query.id)
            except RowNotFoundError:
                raise NotFound(message="Not found") from None
            return {"ok": True}
