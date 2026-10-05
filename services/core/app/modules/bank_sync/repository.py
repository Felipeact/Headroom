import uuid
from collections.abc import Sequence

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.modules.bank_sync.models import BankAccount, BankConnection, BankTransaction


def has_institution(
    session: Session, *, business_id: uuid.UUID, institution_id: str
) -> bool:
    return (
        session.scalar(
            select(BankConnection.id).where(
                BankConnection.business_id == business_id,
                BankConnection.plaid_institution_id == institution_id,
            )
        )
        is not None
    )


def insert_connection(
    session: Session,
    *,
    business_id: uuid.UUID,
    plaid_item_id: str,
    plaid_institution_id: str,
    institution_name: str,
    access_token_ciphertext: str,
) -> BankConnection:
    connection = BankConnection(
        business_id=business_id,
        plaid_item_id=plaid_item_id,
        plaid_institution_id=plaid_institution_id,
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
    session: Session, *, plaid_item_id: str
) -> BankConnection | None:
    """The connection for a Plaid item, whatever its business.

    The one lookup without a business: a Plaid webhook names only the item. Everything
    after it is scoped to the business this returns.
    """
    return session.scalar(
        select(BankConnection).where(BankConnection.plaid_item_id == plaid_item_id)
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


def transactions_by_plaid_id(
    session: Session, *, business_id: uuid.UUID, plaid_transaction_ids: Sequence[str]
) -> dict[str, BankTransaction]:
    if not plaid_transaction_ids:
        return {}
    rows = session.scalars(
        select(BankTransaction).where(
            BankTransaction.business_id == business_id,
            BankTransaction.plaid_transaction_id.in_(plaid_transaction_ids),
        )
    )
    return {row.plaid_transaction_id: row for row in rows}


def insert_transaction(
    session: Session, *, business_id: uuid.UUID, transaction: BankTransaction
) -> None:
    if transaction.business_id != business_id:
        raise ValueError("transaction belongs to another business")
    session.add(transaction)
    session.flush()


def delete_transactions(
    session: Session, *, business_id: uuid.UUID, plaid_transaction_ids: Sequence[str]
) -> int:
    """Delete these transactions of the business; returns how many existed."""
    if not plaid_transaction_ids:
        return 0
    result = session.execute(
        delete(BankTransaction).where(
            BankTransaction.business_id == business_id,
            BankTransaction.plaid_transaction_id.in_(plaid_transaction_ids),
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
