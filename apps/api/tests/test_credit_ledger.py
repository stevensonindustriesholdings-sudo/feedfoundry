import pytest
from sqlmodel import Session, SQLModel, create_engine

from app import models  # noqa: F401
from app.models import CreditWallet, new_id
from app.services.credit_ledger import (
    CreditLedgerError,
    debit_reserved_credits,
    get_or_create_wallet,
    ledger_debit_key,
    ledger_release_failure_key,
    ledger_release_remainder_key,
    ledger_reserve_key,
    release_reserved_credits,
    reserve_credits,
)


@pytest.fixture
def session():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


def test_reserve_release_roundtrip(session: Session):
    org = new_id("org")
    w = get_or_create_wallet(session, org)
    w.balance_available = 100
    session.add(w)
    session.commit()

    reserve_credits(
        session,
        organisation_id=org,
        job_id="job_1",
        amount=30,
        idempotency_key=ledger_reserve_key("job_1"),
    )
    session.commit()
    w2 = session.get(CreditWallet, w.id)
    assert w2.balance_available == 70
    assert w2.balance_reserved == 30

    release_reserved_credits(
        session,
        organisation_id=org,
        job_id="job_1",
        amount=30,
        idempotency_key=ledger_release_remainder_key("job_1"),
    )
    session.commit()
    w3 = session.get(CreditWallet, w.id)
    assert w3.balance_available == 100
    assert w3.balance_reserved == 0


def test_reserve_insufficient(session: Session):
    org = new_id("org")
    w = get_or_create_wallet(session, org)
    w.balance_available = 5
    session.add(w)
    session.commit()

    with pytest.raises(CreditLedgerError):
        reserve_credits(
            session,
            organisation_id=org,
            job_id="job_1",
            amount=10,
            idempotency_key=ledger_reserve_key("job_1"),
        )


def test_debit_reserved(session: Session):
    org = new_id("org")
    w = get_or_create_wallet(session, org)
    w.balance_available = 50
    session.add(w)
    session.commit()
    reserve_credits(
        session,
        organisation_id=org,
        job_id="job_1",
        amount=20,
        idempotency_key=ledger_reserve_key("job_1"),
    )
    session.commit()

    debit_reserved_credits(
        session,
        organisation_id=org,
        job_id="job_1",
        amount=12,
        idempotency_key=ledger_debit_key("job_1"),
    )
    session.commit()
    w2 = session.get(CreditWallet, w.id)
    assert w2.balance_reserved == 8
    assert w2.balance_spent_lifetime == 12
    assert w2.balance_available == 30


def test_debit_idempotent_no_double_spend(session: Session):
    org = new_id("org")
    w = get_or_create_wallet(session, org)
    w.balance_available = 50
    session.add(w)
    session.commit()
    reserve_credits(
        session,
        organisation_id=org,
        job_id="job_a",
        amount=20,
        idempotency_key=ledger_reserve_key("job_a"),
    )
    session.commit()

    debit_reserved_credits(
        session,
        organisation_id=org,
        job_id="job_a",
        amount=15,
        idempotency_key=ledger_debit_key("job_a"),
    )
    session.commit()
    snap = debit_reserved_credits(
        session,
        organisation_id=org,
        job_id="job_a",
        amount=15,
        idempotency_key=ledger_debit_key("job_a"),
    )
    session.commit()
    w2 = session.get(CreditWallet, w.id)
    assert w2.balance_spent_lifetime == 15
    assert snap.balance_spent_lifetime == 15


def test_completion_debits_and_releases_remainder(session: Session):
    """Mirrors successful job settlement: debit actual, release unused reserve."""
    org = new_id("org")
    w = get_or_create_wallet(session, org)
    w.balance_available = 100
    session.add(w)
    session.commit()
    reserve_credits(
        session,
        organisation_id=org,
        job_id="job_c",
        amount=100,
        idempotency_key=ledger_reserve_key("job_c"),
    )
    session.commit()

    debit_reserved_credits(
        session,
        organisation_id=org,
        job_id="job_c",
        amount=72,
        idempotency_key=ledger_debit_key("job_c"),
    )
    release_reserved_credits(
        session,
        organisation_id=org,
        job_id="job_c",
        amount=28,
        idempotency_key=ledger_release_remainder_key("job_c"),
    )
    session.commit()
    w2 = session.get(CreditWallet, w.id)
    assert w2.balance_reserved == 0
    assert w2.balance_available == 28
    assert w2.balance_spent_lifetime == 72


def test_failure_release_idempotent(session: Session):
    org = new_id("org")
    w = get_or_create_wallet(session, org)
    w.balance_available = 40
    session.add(w)
    session.commit()
    reserve_credits(
        session,
        organisation_id=org,
        job_id="job_f",
        amount=40,
        idempotency_key=ledger_reserve_key("job_f"),
    )
    session.commit()

    release_reserved_credits(
        session,
        organisation_id=org,
        job_id="job_f",
        amount=40,
        idempotency_key=ledger_release_failure_key("job_f"),
    )
    session.commit()
    w2 = session.get(CreditWallet, w.id)
    assert w2.balance_reserved == 0
    assert w2.balance_available == 40

    release_reserved_credits(
        session,
        organisation_id=org,
        job_id="job_f",
        amount=40,
        idempotency_key=ledger_release_failure_key("job_f"),
    )
    session.commit()
    w3 = session.get(CreditWallet, w.id)
    assert w3.balance_reserved == 0
    assert w3.balance_available == 40
