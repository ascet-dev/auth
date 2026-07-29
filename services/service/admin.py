"""Админы сервиса: bootstrap, гранты, админский логин."""

from __future__ import annotations

from logging import getLogger
from typing import TYPE_CHECKING

from adc_aiopg import RowNotFoundError

from models.admin_grant import AuthAdminGrant  # noqa: TC001
from models.client_app import ClientApp  # noqa: TC001
from models.enums import AdminRole, AuthClientType, CredentialType, IdentityStatus, SessionStatus
from models.session import Session  # noqa: TC001
from services.service.constants import AUTH_ADMIN_CLIENT_KEY, AUTH_ADMIN_REFRESH_TTL_SEC
from settings import cfg

from .base import ServiceBase

if TYPE_CHECKING:
    from uuid import UUID

log = getLogger(__name__)


class AdminMixin(ServiceBase):
    async def get_admin_client_app(self) -> ClientApp:
        """Возвращает системный client_app для админских сессий."""
        # order_by: детерминированный выбор, даже если в БД оказалось несколько строк
        apps = await self.dao.client_apps.search(
            key=AUTH_ADMIN_CLIENT_KEY,
            archived=False,
            order_by="created",
            limit=1,
        )
        if not apps:
            raise ValueError("Auth service is not initialized: run 'python manage.py bootstrap-owner'")
        return apps[0]

    async def get_active_admin_grant(self, identity_id: UUID) -> AuthAdminGrant | None:
        """Активный (не отозванный) админский грант identity, если есть."""
        grants = await self.dao.admin_grants.search(identity_id=identity_id, archived=False, limit=1)
        return grants[0] if grants else None

    async def check_owner_initialized(self) -> bool:
        """Проверка при старте web: сервис должен быть проинициализирован."""
        owners = await self.dao.admin_grants.search(role=AdminRole.OWNER, archived=False, limit=1)
        if not owners:
            log.error("Auth service is not initialized: run 'python manage.py bootstrap-owner'")
            return False
        return True

    async def bootstrap_owner(self, login: str, password: str, *, adopt_existing: bool = False) -> dict:
        """
        Идемпотентная инициализация сервиса:
        - создаёт системный client_app `auth-admin`, если его нет;
        - если активный OWNER grant уже есть — no-op;
        - иначе создаёт identity + PASSWORD credential + grant OWNER (granted_by=NULL).

        Если credential с таким логином уже существует — отказ: регистрация публична,
        и молчаливый реюз отдал бы OWNER произвольной чужой учётке (а переданный
        пароль был бы проигнорирован). `adopt_existing=True` разрешает выдать грант
        существующей учётке, перезаписав её пароль.
        """
        client_apps = await self.dao.client_apps.search(
            key=AUTH_ADMIN_CLIENT_KEY,
            archived=False,
            order_by="created",
            limit=1,
        )
        if client_apps:
            client_app = client_apps[0]
        else:
            client_app = await self.dao.client_apps.create(
                key=AUTH_ADMIN_CLIENT_KEY,
                name="Auth Admin UI",
                type=AuthClientType.PUBLIC,
                allowed_redirect_uris=[],
                allowed_scopes=[],
                access_token_ttl_sec=int(cfg.auth.access_token_lifetime.total_seconds()),
                refresh_token_ttl_sec=AUTH_ADMIN_REFRESH_TTL_SEC,
            )
            log.info("Created system client_app '%s' (%s)", AUTH_ADMIN_CLIENT_KEY, client_app.id)

        owners = await self.dao.admin_grants.search(role=AdminRole.OWNER, archived=False, limit=1)
        if owners:
            log.info("Active OWNER grant already exists (identity %s), nothing to do", owners[0].identity_id)
            return {"created": False, "identity_id": owners[0].identity_id, "client_app_id": client_app.id}

        credentials = await self.dao.credentials.search(
            identifier=login,
            type=CredentialType.PASSWORD,
            archived=False,
            order_by="created",
            limit=1,
        )
        if credentials:
            if not adopt_existing:
                raise ValueError(
                    f"Credential with login '{login}' already exists. "
                    f"Use a different AUTH__OWNER_LOGIN, or pass --adopt-existing "
                    f"to grant OWNER to that account (its password will be reset).",
                )
            identity_id = credentials[0].identity_id
            # Пароль оператора должен применяться, иначе владельцем станет
            # тот, кто знает старый пароль этой учётки.
            await self.dao.credentials.update_by_id(
                credentials[0].id,
                secret_hash=self.password_service.hash_password(password),
                failed_attempts=0,
                locked_until=None,
            )
            # Учётка могла быть заблокирована/удалена — владелец должен быть активен
            await self.dao.identities.update_by_id(identity_id, status=IdentityStatus.ACTIVE)
            log.warning("Adopted existing credential '%s' as OWNER, password has been reset", login)
        else:
            identity = await self.dao.identities.create(status=IdentityStatus.ACTIVE)
            identity_id = identity.id
            await self.dao.credentials.create(
                identity_id=identity_id,
                type=CredentialType.PASSWORD,
                identifier=login,
                secret_hash=self.password_service.hash_password(password),
                failed_attempts=0,
            )

        # У identity может остаться активный ADMIN grant — заменяем его на OWNER
        # (partial unique index допускает только один активный грант на identity).
        existing_grant = await self.get_active_admin_grant(identity_id)
        if existing_grant:
            await self.dao.admin_grants.archive_by_id(existing_grant.id)

        grant = await self.dao.admin_grants.create(identity_id=identity_id, role=AdminRole.OWNER, granted_by=None)
        log.info("OWNER grant %s created for identity %s (login '%s')", grant.id, identity_id, login)
        return {"created": True, "identity_id": identity_id, "client_app_id": client_app.id}

    async def grant_admin_role(self, identity_id: UUID, role: AdminRole, granted_by: UUID) -> AuthAdminGrant:
        """
        Выдаёт админский грант (только для OWNER-а, проверяется в эндпоинте).
        Partial unique index страхует от гонок, но pre-check даёт чистую ошибку.
        """
        try:
            identity = await self.dao.identities.get_by_id(identity_id)
        except RowNotFoundError:
            raise ValueError("Identity not found") from None

        if identity.status != IdentityStatus.ACTIVE:
            raise ValueError(f"Identity is not active (status: {identity.status})")

        existing = await self.get_active_admin_grant(identity_id)
        if existing:
            raise ValueError("Identity already has an active admin grant")

        return await self.dao.admin_grants.create(identity_id=identity_id, role=role, granted_by=granted_by)

    async def revoke_admin_grant(self, grant_id: UUID) -> None:
        """
        Отзывает грант: archive + немедленная ревокация админских сессий грантополучателя.
        Последнего активного OWNER-а отозвать нельзя.
        """
        try:
            grant = await self.dao.admin_grants.get_by_id(grant_id)
        except RowNotFoundError:
            raise ValueError("Grant not found") from None

        if grant.archived:
            raise ValueError("Grant is already revoked")

        if AdminRole(grant.role) == AdminRole.OWNER:
            owners = await self.dao.admin_grants.search(role=AdminRole.OWNER, archived=False)
            if len(owners) <= 1:
                raise ValueError("Cannot revoke the last active OWNER grant")

        await self.dao.admin_grants.archive_by_id(grant_id)

        # Отзыв прав действует сразу: гасим активные админские сессии
        admin_app = await self.get_admin_client_app()
        await self.dao.sessions.update(
            {"status": SessionStatus.REVOKED},
            identity_id=grant.identity_id,
            client_app_id=admin_app.id,
            status=SessionStatus.ACTIVE,
        )

    async def login_by_admin(
        self,
        identifier: str,
        password: str,
        *,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> tuple[Session, tuple[str, str]]:
        """
        Логин админа auth-сервиса: пароль + активный админский грант.
        Сессия создаётся под системным client_app `auth-admin`,
        access-токен получает claim `role`.
        """
        async with self.log_login_attempt(
            method="admin_password",
            identifier=identifier,
            ip_address=ip_address,
            user_agent=user_agent,
        ) as logger:
            credential = await self._verify_password_credential(identifier, password)

            grant = await self.get_active_admin_grant(credential.identity_id)
            if not grant:
                # Не раскрываем, что учётка существует, но прав нет
                raise ValueError("Invalid credentials")

            identity = await self.dao.identities.get_by_id(credential.identity_id)
            if identity.status != IdentityStatus.ACTIVE:
                # Заблокированный админ — тот же ответ, без деталей
                raise ValueError("Invalid credentials")

            client_app = await self.get_admin_client_app()

            session, tokens = await self.create_session(
                credential.identity_id,
                client_app.id,
                ip=ip_address,
                user_agent=user_agent,
            )

            logger.set(identity_id=credential.identity_id, credential_id=credential.id)

            return session, tokens
