from app.db import Base

DOOR_3 = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


def test_naming_convention_matches_door_3() -> None:
    convention = Base.metadata.naming_convention

    assert {key: convention.get(key) for key in DOOR_3} == DOOR_3
