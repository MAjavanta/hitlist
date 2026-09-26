import re

import requests
from bs4 import BeautifulSoup

from .config import BASE_URL, REQUEST_HEADERS
from .models import game_tag, steam_game, steam_review, steam_tag


def get_tags() -> list[steam_tag]:
    search_html = requests.get(
        BASE_URL, params={"category1": 998}, headers=REQUEST_HEADERS
    )
    soup = BeautifulSoup(search_html.text, "lxml")

    tags_list: list[steam_tag] = []

    for row in soup.find_all("span", attrs={"data-param": "tags"}):
        tag_name: str = str(row["data-loc"])
        tag_id: int = int(str(row["data-value"]))
        tags_list.append(steam_tag(tag_id=tag_id, tag_name=tag_name))

    return tags_list


def get_games(tag_id: int) -> tuple[list[steam_game], list[game_tag]]:
    games_list: list[steam_game] = []
    game_tags_list: list[game_tag] = []
    for start in range(0, 1):
        resp = requests.get(
            BASE_URL + "results/",
            params={
                "infinite": 1,
                "category1": 998,
                "tags": tag_id,
                "ignore_preferences": 1,
                "count": 25,
                "start": start,
            },
            headers=REQUEST_HEADERS,
        )
        data = resp.json()
        soup = BeautifulSoup(data["results_html"], "lxml")

        games = soup.find_all("a", class_="search_result_row")
        for game_row in games:
            review_span = game_row.find("span", class_="search_review_summary")
            if review_span is None:
                continue
            review_text = str(review_span["data-tooltip-html"])
            review_match = re.match(
                r"([A-Za-z ]+)<br>(\d+)% of the ([\d,]+) user reviews", review_text
            )
            if review_match is None:
                continue
            review_name = steam_review(review_match.group(1))
            review_score = int(review_match.group(2))
            review_count = int(review_match.group(3).replace(",", ""))
            game_id = int(str(game_row["data-ds-appid"]))
            title_span = game_row.find("span", class_="title")
            game_tags = game_row["data-ds-tagids"]
            for position, tag in enumerate(str(game_tags[1:-1]).split(",")):
                game_tags_list.append(
                    game_tag(game_id=game_id, tag_id=int(tag), position=position + 1)
                )
            if title_span is not None:
                game_title = title_span.text
            else:
                game_title = "TITLE NOT FOUND"

            games_list.append(
                (
                    steam_game(
                        game_id=game_id,
                        game_name=game_title,
                        review_name=review_name,
                        review_count=review_count,
                        review_score=review_score,
                    )
                )
            )
    return (games_list, game_tags_list)


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
