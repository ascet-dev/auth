"""Доменные ошибки, на которые реагируют вызывающие слои."""


class AdminGrantRevokedError(ValueError):
    """Грант отозван — токен с ролью выдать нельзя, сессию нужно ревокнуть."""


class IdentityInactiveError(ValueError):
    """Identity не ACTIVE — access-токен выдавать нельзя, сессию нужно ревокнуть."""
