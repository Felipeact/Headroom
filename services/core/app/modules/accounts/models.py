import uuid
from datetime import datetime
from typing import Literal, get_args

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Text,
    Uuid,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base

Province = Literal[
    "AB", "BC", "MB", "NB", "NL", "NS", "NT", "NU", "ON", "PE", "QC", "SK", "YT"
]
# Quebec waits for French and Law 25 (specs/later), so no business may be there yet.
UNAVAILABLE_PROVINCES: frozenset[str] = frozenset({"QC"})
AVAILABLE_PROVINCES = tuple(
    p for p in get_args(Province) if p not in UNAVAILABLE_PROVINCES
)

TimeZone = Literal[
    "America/St_Johns",
    "America/Halifax",
    "America/Toronto",
    "America/Winnipeg",
    "America/Regina",
    "America/Edmonton",
    "America/Vancouver",
    "America/Whitehorse",
]
TIME_ZONES: tuple[str, ...] = get_args(TimeZone)

NAME_MAX_LENGTH = 100
ROLES = ("owner", "bookkeeper")


def _one_of(column: str, values: tuple[str, ...]) -> str:
    return f"{column} IN ({', '.join(repr(v) for v in values)})"


class User(Base):
    """A person who signed in through Clerk. Name, email and credentials stay in Clerk."""

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    clerk_user_id: Mapped[str] = mapped_column(Text, unique=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class Business(Base):
    """The company whose cash is forecast. Canada only, CAD only, in v1."""

    __tablename__ = "businesses"
    __table_args__ = (
        CheckConstraint(
            f"char_length(name) BETWEEN 1 AND {NAME_MAX_LENGTH}", name="name_length"
        ),
        CheckConstraint(_one_of("province", AVAILABLE_PROVINCES), name="province"),
        CheckConstraint(_one_of("time_zone", TIME_ZONES), name="time_zone"),
        CheckConstraint("country = 'CA'", name="country"),
        CheckConstraint("currency = 'CAD'", name="currency"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(Text)
    province: Mapped[str] = mapped_column(Text)
    time_zone: Mapped[str] = mapped_column(Text)
    country: Mapped[str] = mapped_column(Text, server_default=text("'CA'"))
    currency: Mapped[str] = mapped_column(Text, server_default=text("'CAD'"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class Membership(Base):
    """A user's role in one business. A user owns at most one business (a bookkeeper may
    work for many)."""

    __tablename__ = "memberships"
    __table_args__ = (
        CheckConstraint(_one_of("role", ROLES), name="role"),
        Index(
            "uq_memberships_owner_user_id",
            "user_id",
            unique=True,
            postgresql_where=text("role = 'owner'"),
        ),
    )

    business_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("businesses.id"), primary_key=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), primary_key=True)
    role: Mapped[str] = mapped_column(Text)
    # A bookkeeper's opt-in to this business's alert emails (spec 31). Owners always get them.
    receive_alert_emails: Mapped[bool] = mapped_column(
        Boolean, server_default=text("false")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class Invitation(Base):
    """An owner's invitation for a bookkeeper (spec 31). It holds hashes, never the address
    or the token: the address is hashed so only its owner can accept (AD-020)."""

    __tablename__ = "invitations"
    __table_args__ = (
        Index(
            "uq_invitations_pending_business_id_email_hash",
            "business_id",
            "email_hash",
            unique=True,
            postgresql_where=text("accepted_at IS NULL"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    business_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("businesses.id"))
    invited_by_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    token_hash: Mapped[str] = mapped_column(Text, unique=True)
    email_hash: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    accepted_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id")
    )
