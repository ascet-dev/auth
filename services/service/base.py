"""Общий контракт для миксинов бизнес-логики."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from services.components import AdminContext
    from services.password_service import PasswordService
    from services.repositories import DAO


class ServiceBase:
    """
    Атрибуты, которые миксины получают от App.

    Только аннотации: реальные компоненты объявлены в `App` через DI, здесь они
    нужны, чтобы миксины были читаемы по отдельности (и чтобы IDE подсказывала).
    Методы соседних миксинов вызываются через MRO готового `App`.
    """

    dao: DAO
    password_service: PasswordService
    current_admin: AdminContext
