from contextlib import contextmanager

from app.models import db


@contextmanager
def session_scope():
    try:
        yield db.session
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise
