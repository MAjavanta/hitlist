import requests
from bs4 import BeautifulSoup

from .config import BASE_URL
from .models import steam_tags


def get_tags() -> list[steam_tags]:
    search_html = requests.get(BASE_URL + "?category1=998")
    soup = BeautifulSoup(search_html.text, "lxml")

    tags_list: list[steam_tags] = []

    for row in soup.find_all("span", attrs={"data-param": "tags"}):
        tag_name: str = str(row["data-loc"])
        tag_id: int = int(str(row["data-value"]))
        tags_list.append(steam_tags(tag_id=tag_id, tag_name=tag_name))

    return tags_list
