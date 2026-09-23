import typer

app = typer.Typer()


@app.command()
def ping():
    """
    Health check for the cli. Expect "pong".
    """
    typer.echo("pong")


@app.command()
def health_check():
    """
    Second health check
    """
    typer.echo("healthy")
