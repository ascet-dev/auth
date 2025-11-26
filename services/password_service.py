from passlib.context import CryptContext


class PasswordService:
    def __init__(self):
        self._pwd_context = CryptContext(
            schemes=["argon2"],
            argon2__type="ID",
            argon2__memory_cost=65536,
            argon2__time_cost=3,
            argon2__parallelism=4,
        )

    def hash_password(self, password: str) -> str:
        return self._pwd_context.hash(password)

    def verify_password(self, password: str, password_hash: str) -> bool:
        return self._pwd_context.verify(password, password_hash)
