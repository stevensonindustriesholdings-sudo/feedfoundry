"""Ensure worker image dependencies match Railway DATABASE_URL dialects (postgresql:// → psycopg2)."""


def test_worker_db_stack_importable():
    import psycopg2  # noqa: F401
    import sqlalchemy  # noqa: F401

    import worker  # noqa: F401 — module load only; does not run main()
