"""Turns the article, charts and numbers into the newspaper web pages."""

from __future__ import annotations

import re
import shutil
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

import markdown
from jinja2 import Environment, FileSystemLoader, select_autoescape

from .market_data import MarketData, format_change, format_level

TEMPLATES = Path(__file__).parent / "templates"

# Which chart sits under which section (matched on words in the section heading)
CHART_PLACES = {
    "around the world": ["world"],
    "sectors": ["sectors", "movers"],
    "rates": ["yields"],
    "crypto": ["bitcoin"],
}
CHART_CAPTIONS = {
    "world": "Major stock indexes over the past month",
    "sectors": "How each US sector did in the latest session",
    "movers": "Biggest gainers and fallers on our watchlist",
    "yields": "The US 10-year yield over six months",
    "bitcoin": "Bitcoin over three months",
}
NUMBERS_ONLY_SECTIONS = ["Around the world", "Sectors and stocks", "Rates, currencies and commodities", "Crypto"]

env = Environment(loader=FileSystemLoader(TEMPLATES), autoescape=select_autoescape())


def _author(config: dict) -> dict:
    author = config.get("author", {})
    return {
        "name": author.get("name") or "cmacbain-1",
        "linkedin": author.get("linkedin", ""),
        "blurb": author.get("blurb", ""),
        "github": author.get("github", ""),
    }


def _split_article(md_text: str) -> tuple[str, str, list[dict]]:
    """Splits Claude's Markdown into headline, standfirst and sections."""
    lines = md_text.splitlines()
    headline = lines[0].lstrip("# ").strip()
    body = "\n".join(lines[1:])
    parts = re.split(r"^## +(.+)$", body, flags=re.MULTILINE)
    standfirst = parts[0].strip().strip("*_ ").strip()
    sections = [
        {"title": title.strip(), "html": markdown.markdown(text.strip(), extensions=["extra"])}
        for title, text in zip(parts[1::2], parts[2::2])
    ]
    return headline, standfirst, sections


def _place_charts(sections: list[dict], charts: dict[str, str]) -> list[dict]:
    unplaced = dict(charts)
    for section in sections:
        section["charts"] = []
        title = section["title"].lower()
        for words, chart_ids in CHART_PLACES.items():
            if words in title:
                for chart_id in chart_ids:
                    if chart_id in unplaced:
                        section["charts"].append({"file": unplaced.pop(chart_id), "caption": CHART_CAPTIONS[chart_id]})
    if unplaced:
        sections.append({
            "title": "Charts",
            "html": "",
            "charts": [{"file": f, "caption": CHART_CAPTIONS[c]} for c, f in unplaced.items()],
        })
    return sections


def _tables(data: MarketData) -> list[dict]:
    tables = []
    for group in data.groups:
        quotes = data.group_quotes(group["id"])
        if quotes:
            tables.append({
                "title": group["title"],
                "rows": [{
                    "name": q.name,
                    "level": format_level(q),
                    "day": format_change(q.change_1d, q.kind),
                    "ytd": format_change(q.change_ytd, q.kind),
                    "day_dir": "up" if (q.change_1d or 0) > 0 else "down" if (q.change_1d or 0) < 0 else "",
                    "ytd_dir": "up" if (q.change_ytd or 0) > 0 else "down" if (q.change_ytd or 0) < 0 else "",
                } for q in quotes],
            })
    return tables


def _strip(data: MarketData, symbols: list[str]) -> list[dict]:
    items = []
    for symbol in symbols:
        q = data.quotes.get(symbol)
        if q:
            items.append({
                "name": q.name.split(" (")[0],
                "level": format_level(q),
                "change": format_change(q.change_1d, q.kind),
                "dir": "up" if (q.change_1d or 0) > 0 else "down" if (q.change_1d or 0) < 0 else "",
            })
    return items


def build(docs: Path, edition_dir: Path, data: MarketData, charts: dict[str, str],
          article: str | None, config: dict, now: datetime, number: int) -> None:
    paper = config["paper"]
    if article:
        headline, standfirst, sections = _split_article(article)
    else:
        headline = "Markets at a glance"
        standfirst = "Today's numbers and charts. The full written edition is back tomorrow."
        sections = [{"title": t, "html": ""} for t in NUMBERS_ONLY_SECTIONS]

    date_slug = edition_dir.name
    site_url = paper.get("site_url", "").rstrip("/")
    context = {
        "paper": paper,
        "headline": headline,
        "standfirst": standfirst,
        "sections": _place_charts(sections, charts),
        "tables": _tables(data),
        "strip": _strip(data, config.get("ticker_strip", [])),
        "date_long": now.strftime("%A %d %B %Y").replace(" 0", " "),
        "number": number,
        "og_image": f"{site_url}/editions/{date_slug}/{charts['world']}" if site_url and "world" in charts else "",
        "page_url": f"{site_url}/editions/{date_slug}/" if site_url else "",
        "share_url": f"https://www.linkedin.com/sharing/share-offsite/?url={quote(site_url + '/editions/' + date_slug + '/', safe='')}"
                     if site_url else "",
        "author": _author(config),
    }
    template = env.get_template("edition.html")
    # The dated copy, kept forever in the archive...
    (edition_dir / "index.html").write_text(
        template.render(**context, root="../../", assets=""), encoding="utf-8")
    # ...and the front page, which always shows the latest edition.
    (docs / "index.html").write_text(
        template.render(**context, root="", assets=f"editions/{date_slug}/"), encoding="utf-8")
    # A copy of the main chart at a fixed address, for the GitHub page
    if "world" in charts:
        shutil.copyfile(edition_dir / charts["world"], docs / "latest-chart.png")
    build_site_pages(docs, config)


def build_site_pages(docs: Path, config: dict) -> None:
    """The pages that aren't editions: the archive and the About page."""
    build_archive(docs, config)
    paper = config["paper"]
    hour = paper["publish_hour"]
    city = paper["timezone"].split("/")[-1].replace("_", " ")
    publish_time = f"{hour % 12 or 12}{'am' if hour < 12 else 'pm'} {city} time"
    groups = [{"title": g["title"], "count": len(g["tickers"])} for g in config["groups"]]
    html = env.get_template("about.html").render(
        paper=paper, author=_author(config), root="", publish_time=publish_time, groups=groups,
        market_count=sum(g["count"] for g in groups))
    (docs / "about.html").write_text(html, encoding="utf-8")


def build_archive(docs: Path, config: dict) -> None:
    paper = config["paper"]
    editions = []
    for folder in sorted((docs / "editions").iterdir(), reverse=True):
        page = folder / "index.html"
        if not page.exists():
            continue
        found = re.search(r'<h1 class="headline">(.*?)</h1>', page.read_text(encoding="utf-8"), re.S)
        editions.append({
            "href": f"editions/{folder.name}/",
            "date": datetime.fromisoformat(folder.name).strftime("%a %d %b %Y"),
            "headline": found.group(1).strip() if found else folder.name,
        })
    html = env.get_template("archive.html").render(paper=paper, author=_author(config), editions=editions, root="")
    (docs / "archive.html").write_text(html, encoding="utf-8")
