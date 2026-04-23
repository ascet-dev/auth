from datetime import datetime
from uuid import UUID

from adc_aiopg.types import Base
from sqlalchemy import UUID as SA_UUID
from sqlalchemy import MetaData, text
from sqlmodel import Field

from settings import cfg

meta = MetaData(schema=cfg.pg.schema_name)
NOW = text("(now() at time zone 'utc')")
UUIDV7 = text("uuidv7()")


class BaseModel(Base):
    id: UUID = Field(sa_type=SA_UUID, sa_column_kwargs={"server_default": UUIDV7, "primary_key": True})
    created: datetime | None = Field(
        default=None,
        sa_column_kwargs={"server_default": NOW, "nullable": False, "insert_default": None},
    )
    updated: datetime | None = Field(
        default=None,
        sa_column_kwargs={"server_default": NOW, "nullable": False, "insert_default": None},
    )
    archived: bool | None = Field(
        default=None,
        sa_column_kwargs={"server_default": text("false"), "nullable": False, "insert_default": None},
    )

    model_config = {"exclude": {"created", "updated", "archived"}, "arbitrary_types_allowed": True}


class BaseSearch(Base):
    limit: int = 100
    offset: int = 0

    created_ge: datetime | None = None
    created_le: datetime | None = None

    archived: bool = False
