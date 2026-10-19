import uuid
from collections.abc import Sequence
from datetime import date, datetime

from sqlalchemy import delete, func, select, tuple_
from sqlalchemy.orm import Session

from app.modules.bank_sync.models import BankAccount, BankConnection, BankTransaction


def has_institution(
    session: Session, *, business_id: uuid.UUID, provider: str, institution_id: str
) -> bool:
    return (
        session.scalar(
            select(BankConnection.id).where(
                BankConnection.business_id == business_id,
                BankConnection.provider == provider,
                BankConnection.provider_institution_id == institution_id,
            )
        )
        is not None
    )


def has_provider_item(
    session: Session, *, business_id: uuid.UUID, provider: str, provider_item_id: str
) -> bool:
    return (
        session.scalar(
            select(BankConnection.id).where(
                BankConnection.business_id == business_id,
                BankConnection.provider == provider,
                BankConnection.provider_item_id == provider_item_id,
            )
        )
        is not None
    )


def has_provider_connection(
    session: Session, *, business_id: uuid.UUID, provider: str
) -> bool:
    return (
        session.scalar(
            select(BankConnection.id)
            .where(
                BankConnection.business_id == business_id,
                BankConnection.provider == provider,
            )
            .limit(1)
        )
        is not None
    )


def insert_connection(
    session: Session,
    *,
    business_id: uuid.UUID,
    provider: str = "plaid",
    provider_item_id: str,
    provider_institution_id: str,
    institution_name: str,
    access_token_ciphertext: str,
) -> BankConnection:
    connection = BankConnection(
        business_id=business_id,
        provider=provider,
        provider_item_id=provider_item_id,
        provider_institution_id=provider_institution_id,
        institution_name=institution_name,
        access_token_ciphertext=access_token_ciphertext,
    )
    session.add(connection)
    session.flush()
    session.refresh(connection)
    return connection


def insert_accounts(session: Session, accounts: Sequence[BankAccount]) -> None:
    session.add_all(accounts)
    session.flush()


def has_primary(session: Session, *, business_id: uuid.UUID) -> bool:
    return (
        session.scalar(
            select(BankAccount.id).where(
                BankAccount.business_id == business_id, BankAccount.is_primary
            )
        )
        is not None
    )


def connections(session: Session, *, business_id: uuid.UUID) -> list[BankConnection]:
    return list(
        session.scalars(
            select(BankConnection)
            .where(BankConnection.business_id == business_id)
            .order_by(BankConnection.created_at, BankConnection.id)
        )
    )


def accounts(session: Session, *, business_id: uuid.UUID) -> list[BankAccount]:
    return list(
        session.scalars(
            select(BankAccount)
            .where(BankAccount.business_id == business_id)
            .order_by(BankAccount.name, BankAccount.id)
        )
    )


def lock_accounts(session: Session, *, business_id: uuid.UUID) -> list[BankAccount]:
    """Every account of the business, locked until the transaction ends.

    Changes to inclusion and the primary account take this lock first, so two of them
    for one business run one after the other.
    """
    return list(
        session.scalars(
            select(BankAccount)
            .where(BankAccount.business_id == business_id)
            .order_by(BankAccount.id)
            .with_for_update()
        )
    )


def connection_for_item(
    session: Session, *, provider_item_id: str
) -> BankConnection | None:
    """The connection for a Plaid item, whatever its business.

    The one lookup without a business: a Plaid webhook names only the item. Everything
    after it is scoped to the business this returns.
    """
    return session.scalar(
        select(BankConnection).where(
            BankConnection.provider == "plaid",
            BankConnection.provider_item_id == provider_item_id,
        )
    )


def lock_connection(
    session: Session, *, business_id: uuid.UUID, connection_id: uuid.UUID
) -> BankConnection | None:
    """The connection, locked until the transaction ends, so its syncs run one at a time."""
    return session.scalar(
        select(BankConnection)
        .where(
            BankConnection.business_id == business_id,
            BankConnection.id == connection_id,
        )
        .with_for_update()
    )


def connection_accounts(
    session: Session, *, business_id: uuid.UUID, connection_id: uuid.UUID
) -> list[BankAccount]:
    return list(
        session.scalars(
            select(BankAccount).where(
                BankAccount.business_id == business_id,
                BankAccount.connection_id == connection_id,
            )
        )
    )


def transactions_by_provider_id(
    session: Session, *, business_id: uuid.UUID, provider_transaction_ids: Sequence[str]
) -> dict[str, BankTransaction]:
    if not provider_transaction_ids:
        return {}
    rows = session.scalars(
        select(BankTransaction).where(
            BankTransaction.business_id == business_id,
            BankTransaction.provider_transaction_id.in_(provider_transaction_ids),
        )
    )
    return {row.provider_transaction_id: row for row in rows}


def business_transactions(
    session: Session, *, business_id: uuid.UUID
) -> list[BankTransaction]:
    """Every transaction of the business, freshly read.

    `populate_existing`: rows already in the session are reloaded, so links that Postgres
    cleared when a half was deleted (`ON DELETE SET NULL`) are seen.
    """
    return list(
        session.scalars(
            select(BankTransaction)
            .where(BankTransaction.business_id == business_id)
            .execution_options(populate_existing=True)
        )
    )


def transactions_page(
    session: Session,
    *,
    business_id: uuid.UUID,
    limit: int,
    after: tuple[date, uuid.UUID] | None,
) -> list[BankTransaction]:
    """Up to `limit` transactions, newest first by date then ID, after `after` if set."""
    query = select(BankTransaction).where(BankTransaction.business_id == business_id)
    if after is not None:
        query = query.where(
            tuple_(BankTransaction.date, BankTransaction.id) < tuple_(*after)
        )
    query = query.order_by(BankTransaction.date.desc(), BankTransaction.id.desc())
    return list(session.scalars(query.limit(limit)))


def insert_transaction(
    session: Session, *, business_id: uuid.UUID, transaction: BankTransaction
) -> None:
    if transaction.business_id != business_id:
        raise ValueError("transaction belongs to another business")
    session.add(transaction)
    session.flush()


def delete_transactions(
    session: Session, *, business_id: uuid.UUID, provider_transaction_ids: Sequence[str]
) -> int:
    """Delete these transactions of the business; returns how many existed."""
    if not provider_transaction_ids:
        return 0
    result = session.execute(
        delete(BankTransaction).where(
            BankTransaction.business_id == business_id,
            BankTransaction.provider_transaction_id.in_(provider_transaction_ids),
        )
    )
    return int(result.rowcount)  # type: ignore[attr-defined]


def delete_connection(
    session: Session, *, business_id: uuid.UUID, connection_id: uuid.UUID
) -> int:
    """Delete the connection, its accounts and their transactions.

    Returns how many transactions were deleted. A link from another transaction to a
    deleted one is cleared by its foreign key (`ON DELETE SET NULL`).
    """
    account_ids = select(BankAccount.id).where(
        BankAccount.business_id == business_id,
        BankAccount.connection_id == connection_id,
    )
    result = session.execute(
        delete(BankTransaction).where(
            BankTransaction.business_id == business_id,
            BankTransaction.account_id.in_(account_ids),
        )
    )
    session.execute(
        delete(BankAccount).where(
            BankAccount.business_id == business_id,
            BankAccount.connection_id == connection_id,
        )
    )
    session.execute(
        delete(BankConnection).where(
            BankConnection.business_id == business_id,
            BankConnection.id == connection_id,
        )
    )
    return int(result.rowcount)  # type: ignore[attr-defined]


def nightly_candidates(session: Session) -> list[BankConnection]:
    """Every connection of every business, oldest first, for the nightly sync job.

    The one read across businesses besides `connection_for_item`: the job has to find
    every bank to sync. Each sync after it is scoped to the connection's own business.
    """
    return list(
        session.scalars(
            select(BankConnection).order_by(
                BankConnection.created_at, BankConnection.id
            )
        )
    )


def claim_connection(
    session: Session, *, business_id: uuid.UUID, connection_id: uuid.UUID
) -> BankConnection | None:
    """The connection, locked until the transaction ends; None when another holds it.

    `SKIP LOCKED`: a nightly run moves on instead of waiting for a sync in progress.
    """
    return session.scalar(
        select(BankConnection)
        .where(
            BankConnection.business_id == business_id,
            BankConnection.id == connection_id,
        )
        .with_for_update(skip_locked=True)
    )


def get_connection(
    session: Session, *, business_id: uuid.UUID, connection_id: uuid.UUID
) -> BankConnection | None:
    return session.scalar(
        select(BankConnection).where(
            BankConnection.business_id == business_id,
            BankConnection.id == connection_id,
        )
    )


def first_connection_at(session: Session, *, business_id: uuid.UUID) -> datetime | None:
    """When the business's oldest current connection was created; None without one."""
    return session.scalar(
        select(func.min(BankConnection.created_at)).where(
            BankConnection.business_id == business_id
        )
    )
