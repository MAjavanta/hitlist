import re

import requests
from bs4 import BeautifulSoup

from .config import BASE_URL
from .models import steam_tags


def get_tags() -> list[steam_tags]:
    search_html = requests.get(BASE_URL, params={"category1": 998})
    soup = BeautifulSoup(search_html.text, "lxml")

    tags_list: list[steam_tags] = []

    for row in soup.find_all("span", attrs={"data-param": "tags"}):
        tag_name: str = str(row["data-loc"])
        tag_id: int = int(str(row["data-value"]))
        tags_list.append(steam_tags(tag_id=tag_id, tag_name=tag_name))

    return tags_list


def get_games(tag_id: int):
    games_list = []
    for start in range(0, 300, 100):
        resp = requests.get(
            BASE_URL + "results/",
            params={
                "infinite": 1,
                "category1": 998,
                "tags": tag_id,
                "ignore_preferences": 1,
                "count": 100,
                "start": start,
            },
        )
        data = resp.json()
        soup = BeautifulSoup(data["results_html"], "lxml")

        games = soup.find_all("a", class_="search_result_row")
        print(f"Start: {start} - games: {len(games)}")
        for game_row in games:
            review_span = game_row.find("span", class_="search_review_summary")
            if review_span is None:
                continue
            review_text = str(review_span["data-tooltip-html"])
            review_match = re.search(r"(\d+)% of the ([\d,]+) use reviews", review_text)
            if review_match is not None:
                review_score = int(review_match.group(1))
                review_count = int(review_match.group(2).replace(",", ""))
            else:
                review_score = 0
                review_count = 0
            game_id = game_row["data-ds-appid"]
            game_tags = game_row["data-ds-tagids"]
            title_span = game_row.find("span", class_="title")
            if title_span is not None:
                game_title = title_span.text
            else:
                game_title = "TITLE NOT FOUND"

            games_list.append(
                (game_id, game_title, game_tags, review_count, review_score)
            )
    return games_list


def test_game():
    resp = requests.get(
        BASE_URL + "results/",
        params={
            "infinite": 1,
            "category1": 998,
            "tags": 597,
            "ignore_preferences": 1,
            "count": 25,
            "start": 0,
        },
    )

    data = resp.json()
    soup = BeautifulSoup(data["results_html"], "lxml")
    game_row = soup.find("a", class_="search_result_row")
    print(game_row)
    review_span = game_row.find("span", class_="search_review_summary")
    print(review_span["data-tooltip-html"])
