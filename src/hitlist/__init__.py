import requests
from bs4 import BeautifulSoup


def has_class_search_result_row(tag):
    return tag.has_attr("class") and "search_result_row" in tag["class"]


def main() -> None:
    x = requests.get("https://store.steampowered.com/search?hwtype=0&category1=998")
    soup = BeautifulSoup(x.text, "html.parser")

    for row in soup.find_all("a", class_="search_result_row"):
        appid = row["data-ds-appid"]
        tags = row["data-ds-tagids"]
        title = row.find("span", class_="title").get_text(strip=True)
        print(title, appid, tags)
