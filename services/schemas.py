from pydantic import BaseModel

from models.session import Session

excluded = "id", "created", "updated", "archived", "updated_by"


class SessionWithTokens(BaseModel):
    session: Session
    tokens: tuple[str, str]
