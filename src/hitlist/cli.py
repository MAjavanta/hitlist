import typer
from rich import print
from sqlmodel import Session, SQLModel

from . import models  # noqa: F401
from .db import engine
from .steam import get_tags

app = typer.Typer()
db_app = typer.Typer()
steam_app = typer.Typer()
app.add_typer(db_app, name="db")
app.add_typer(steam_app, name="steam")


@app.command()
def ping() -> None:
    """
    Health check for the cli. Expect "pong".
    """
    print("pong")


@steam_app.command()
def tags():
    tags = get_tags()

    with Session(engine) as session:
        for tag in tags:
            session.add(tag)

        session.commit()


@db_app.command()
def init() -> None:
    print("Initialising database")
    SQLModel.metadata.create_all(engine)
