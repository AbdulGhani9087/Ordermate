import pytest
from fastapi.testclient import TestClient
from sqlmodel import SQLModel, create_engine, Session
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401
from app.main import app as fastapi_app
from app.db.database import get_session

# Global shared in-memory test engine for the test suite
test_engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)


@pytest.fixture(autouse=True)
def clean_db():
    SQLModel.metadata.create_all(test_engine)
    yield
    SQLModel.metadata.drop_all(test_engine)


@pytest.fixture
def session():
    with Session(test_engine) as sess:
        yield sess


@pytest.fixture
def client(session):
    def _override_get_session():
        yield session

    fastapi_app.dependency_overrides[get_session] = _override_get_session
    with TestClient(fastapi_app) as c:
        yield c
    fastapi_app.dependency_overrides.clear()
