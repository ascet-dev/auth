from datetime import timedelta
from pathlib import Path

from pydantic import model_validator
from pydantic_settings import BaseSettings


class Auth(BaseSettings):
    # JWT Configuration
    algorithms: list[str] = ["RS256"]
    access_token_lifetime: timedelta = timedelta(minutes=1)
    refresh_token_lifetime: timedelta = timedelta(days=30)

    # Telegram Mini App (fallback, если нет TMA-коннектора)
    telegram_bot_token: str | None = None
    tma_auth_date_max_age: int = 300  # секунд, максимальный возраст auth_date

    # Bootstrap владельца (manage.py bootstrap-owner)
    # Вне LOCAL-окружения пароль обязателен: AUTH__OWNER_PASSWORD
    owner_login: str = "admin"
    owner_password: str | None = None

    # RSA-ключи для подписи access-токенов. Дефолтов нет и быть не может:
    # захардкоженная пара в репозитории означала бы, что любой может выписать
    # себе токен (включая админский). Передаются либо содержимым, либо путями
    # к PEM (удобнее для docker/k8s), генерируются `make keys`.
    private_key: str | None = None
    public_key: str | None = None
    private_key_path: Path | None = None
    public_key_path: Path | None = None

    @model_validator(mode="after")
    def _load_keys_from_files(self) -> "Auth":
        for field, path in (("private_key", self.private_key_path), ("public_key", self.public_key_path)):
            if not path:
                continue
            try:
                setattr(self, field, path.read_text(encoding="utf-8"))
            except OSError as e:
                env_name = f"AUTH__{field.upper()}_PATH"
                raise ValueError(
                    f"Cannot read JWT {field} from {path}: {e.strerror}. "
                    f"Run 'make keys' to generate a keypair in ./secrets, "
                    f"or unset {env_name} to pass the key contents instead.",
                ) from e
        return self

    def require_keys(self) -> None:
        """
        Проверка перед стартом того, что подписывает или проверяет токены.
        Не в валидаторе: CLI-командам вроде apply-sql ключи не нужны.
        """
        missing = [name for name in ("private_key", "public_key") if not getattr(self, name)]
        if missing:
            raise ValueError(
                f"JWT keys are not configured ({', '.join(missing)}). "
                f"Run 'make keys' to generate a keypair in ./secrets, then pass "
                f"AUTH__PRIVATE_KEY_PATH / AUTH__PUBLIC_KEY_PATH (or AUTH__PRIVATE_KEY / AUTH__PUBLIC_KEY).",
            )
