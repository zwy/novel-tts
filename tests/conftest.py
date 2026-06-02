# tests/conftest.py
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from novel_tts.models import Base


@pytest.fixture
def session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    s = Session()
    yield s
    s.close()


@pytest.fixture
def test_client(tmp_path):
    import novel_tts.api as api_module
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool
    from novel_tts.models import Base
    from novel_tts.repository import JobRepository
    from novel_tts.worker import WorkerService
    from novel_tts.tts_engine import FakeTTSEngine
    from fastapi.testclient import TestClient

    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    test_session = Session()

    repo = JobRepository(test_session)
    # The fake engine is shared by every model_id the worker might dispatch to,
    # which keeps the fixture trivial — tests that need per-model behaviour
    # override the relevant entry in `app.state.tts_engines` directly.
    fake_engine = FakeTTSEngine(sample_rate=24000)
    tts_engines = {
        "qwen3_tts_0_6b_customvoice": fake_engine,
        "qwen3_tts_1_7b_customvoice": fake_engine,
        "mimo_v2_5_tts": fake_engine,
    }
    worker = WorkerService(
        repo=repo,
        tts_engines=tts_engines,
        temp_dir=tmp_path / "temp",
        out_dir=tmp_path / "audio",
        sample_rate=24000,
    )

    api_module.app.state.repo = repo
    api_module.app.state.worker = worker
    api_module.app.state.tts_engines = tts_engines

    client = TestClient(api_module.app)
    yield client

    test_session.close()
