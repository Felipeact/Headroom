import uuid
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.bank_sync.models import BankAccount, BankConnection


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
