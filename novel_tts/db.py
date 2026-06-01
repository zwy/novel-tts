# novel_tts/db.py
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from novel_tts.models import Base


def create_session_factory(db_url: str, **kwargs):
    engine = create_engine(db_url, **kwargs)
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False)
