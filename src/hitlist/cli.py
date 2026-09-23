import typer
from rich import print

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
    get_tags()


@db_app.command()
def init() -> None:
    print("Initialising database")
