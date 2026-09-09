import pytest
from app.db.database import Base, SessionLocal, engine


@pytest.fixture(scope="session", autouse=True)
def setup_test_database():
    """Ensure all database tables exist before running tests."""
    Base.metadata.create_all(bind=engine)


@pytest.fixture
def db_session():
    """Provides a transactional database session that rolls back after each test."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()