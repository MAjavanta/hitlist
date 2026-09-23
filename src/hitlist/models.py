from sqlmodel import Field, SQLModel


class steam_tags(SQLModel, table=True):
    tag_id: int = Field(primary_key=True)
    tag_name: str
