import json
import re
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable, List, Set
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

URLS_PATH = Path("scripts/health_center_urls.txt")
OUTPUT_PATH = Path("knowledge.jsonl")
HEADERS = {
    "User-Agent": "HealthCenterRAGBot/1.0"
}
REQUEST_TIMEOUT = 25
PAUSE_SECONDS = 0.5

NAME_REPLACEMENTS = [
    "MC Betnava",
    "MC-Betnava",
    "MC Betnava d.o.o.",
    "Medicinski center Betnava",
    "Medicinski center BETNAVA",
    "Medicinski center Betnava d.o.o.",
    "Medicinski center",
    "Medicinskem centru",
    "Betnava",
]


@dataclass
class PageData:
    url: str
    title: str
    content: str
    fetched_at: str


def clean_text(text: str) -> str:
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def fetch_url(url: str) -> str:
    resp = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
    resp.raise_for_status()
    return resp.text


def replace_center_name(text: str) -> str:
    for name in NAME_REPLACEMENTS:
        text = text.replace(name, "zdravstveni center")
    text = text.replace("zdravstveni center zdravstveni center", "zdravstveni center")
    text = text.replace("zdravstvenem centru zdravstveni center", "zdravstvenem centru")
    return text


def load_urls(path: Path) -> List[str]:
    if not path.exists():
        raise FileNotFoundError(f"Missing URL list: {path}")
    urls: List[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("http"):
            urls.append(line)
    # de-dupe while preserving order
    seen: Set[str] = set()
    deduped: List[str] = []
    for url in urls:
        if url in seen:
            continue
        seen.add(url)
        deduped.append(url)
    return deduped


def extract_content(url: str) -> PageData:
    html = fetch_url(url)
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript", "header", "footer", "nav", "form"]):
        tag.decompose()
    title_tag = soup.find("h1") or soup.find("title")
    title = clean_text(title_tag.get_text()) if title_tag else url
    main = soup.find("main") or soup.body
    text = clean_text(main.get_text(separator=" ")) if main else clean_text(soup.get_text())
    title = replace_center_name(title)
    text = replace_center_name(text)
    return PageData(
        url=url,
        title=title,
        content=text,
        fetched_at=datetime.utcnow().isoformat(),
    )


def scrape_all(urls: Iterable[str]) -> List[PageData]:
    urls_list = list(urls)
    pages: List[PageData] = []
    for idx, url in enumerate(urls_list, start=1):
        try:
            page = extract_content(url)
            pages.append(page)
            print(f"[{idx}/{len(urls_list)}] scraped {url}")
        except Exception as exc:
            print(f"[{idx}/{len(urls_list)}] failed {url}: {exc}")
            pages.append(
                PageData(
                    url=url,
                    title="ERROR",
                    content=f"Failed to fetch content: {exc}",
                    fetched_at=datetime.utcnow().isoformat(),
                )
            )
        time.sleep(PAUSE_SECONDS)
    return pages


def write_jsonl(pages: List[PageData], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for page in pages:
            json.dump(page.__dict__, f, ensure_ascii=False)
            f.write("\n")
    print(f"Wrote {len(pages)} records to {path}")


def main() -> None:
    urls = load_urls(URLS_PATH)
    print(f"Loaded {len(urls)} URLs from {URLS_PATH}")
    pages = scrape_all(urls)
    write_jsonl(pages, OUTPUT_PATH)


if __name__ == "__main__":
    main()
