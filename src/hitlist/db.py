from sqlmodel import create_engine

from .config import SQLITE_URL

engine = create_engine(SQLITE_URL, echo=True)
