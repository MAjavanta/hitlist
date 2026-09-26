import typer
from rich import print
from sqlmodel import Session, SQLModel

from . import models
from .db import engine
from .steam import get_games, get_tags, test_game

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
def tags(load_db: bool = False):
    tags: list[models.steam_tags] = get_tags()

    if load_db:
        with Session(engine) as session:
            for tag in tags:
                session.add(tag)

            session.commit()
    else:
        print(tags)


@steam_app.command()
def games(tag_id: int):
    games_list = get_games(tag_id)
    print(games_list)


@steam_app.command()
def game_test():
    test_game()


@db_app.command()
def init() -> None:
    print("Initialising database")
    SQLModel.metadata.create_all(engine)
