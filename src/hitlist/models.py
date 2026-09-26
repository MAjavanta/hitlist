from enum import Enum

from sqlmodel import Field, SQLModel


class steam_review(Enum):
    OverwhelminglyNegative = "Overwhelmingly Negative"
    VeryNegative = "Very Negative"
    MostlyNegative = "Mostly Negative"
    Negative = "Negative"
    Mixed = "Mixed"
    Positive = "Positive"
    MostlyPositive = "Mostly Positive"
    VeryPositive = "Very Positive"
    OverwhelminglyPositive = "Overwhelmingly Positive"


class steam_tag(SQLModel, table=True):
    tag_id: int = Field(primary_key=True)
    tag_name: str


class steam_game(SQLModel, table=True):
    game_id: int = Field(primary_key=True)
    game_name: str
    review_name: steam_review
    review_count: int
    review_score: int


class game_tag(SQLModel, table=True):
    game_id: int = Field(foreign_key="steam_game.game_id", primary_key=True)
    tag_id: int = Field(foreign_key="steam_tag.tag_id", primary_key=True)
    position: int
