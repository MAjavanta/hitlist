import requests
from bs4 import BeautifulSoup

from .config import BASE_URL


def get_tags() -> list[tuple[int, str]]:
    search_html = requests.get(BASE_URL + "?category1=998")
    soup = BeautifulSoup(search_html.text, "lxml")

    tags_list: list[tuple[int, str]] = []

    for row in soup.find_all("span", attrs={"data-param": "tags"}):
        tag_name: str = str(row["data-loc"])
        tag_id: int = int(str(row["data-value"]))
        tags_list.append((tag_id, tag_name))

    return tags_list
