from datetime import datetime, timezone

from sqlalchemy import create_engine, inspect, text
from sqlalchemy import event
from sqlalchemy.orm import DeclarativeBase, sessionmaker


def utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)

DATABASE_URL = "sqlite:///./clinic.db"
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
)


@event.listens_for(engine, "connect")
def enable_sqlite_foreign_keys(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def migrate_ownership_schema() -> None:
    with engine.begin() as connection:
        additions = [
            ("users", "demo_seeded BOOLEAN DEFAULT 0"),
            ("users", "remember_token VARCHAR(128)"),
            ("doctors", "user_id INTEGER REFERENCES users(id)"),
            ("patients", "user_id INTEGER REFERENCES users(id)"),
            ("appointments", "user_id INTEGER REFERENCES users(id)"),
            ("clock_state", "user_id INTEGER REFERENCES users(id)"),
            ("outbox_notifications", "user_id INTEGER REFERENCES users(id)"),
        ]
        for table, definition in additions:
            inspector = inspect(connection)
            if table in inspector.get_table_names() and definition.split()[0] not in {column["name"] for column in inspector.get_columns(table)}:
                connection.execute(text(f"ALTER TABLE {table} ADD COLUMN {definition}"))
        inspector = inspect(connection)
        # Existing prototype records had no owner and cannot safely be assigned to an account.
        if "outbox_notifications" in inspector.get_table_names():
            connection.execute(text("DELETE FROM outbox_notifications WHERE user_id IS NULL"))
        if "appointments" in inspector.get_table_names():
            connection.execute(text("DELETE FROM appointments WHERE user_id IS NULL"))
        if "doctors" in inspector.get_table_names():
            connection.execute(text("DELETE FROM doctors WHERE user_id IS NULL"))
        if "patients" in inspector.get_table_names():
            connection.execute(text("DELETE FROM patients WHERE user_id IS NULL"))
        if "clock_state" in inspector.get_table_names():
            connection.execute(text("DELETE FROM clock_state WHERE user_id IS NULL"))