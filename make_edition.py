"""Makes today's edition of the newspaper, in two halves with Claude in between.

    python make_edition.py prepare           # get prices, draw charts, write Claude's brief
                                             # (only if it's publishing time and today's edition isn't out yet)
    python make_edition.py prepare --force   # do it now regardless
    python make_edition.py publish           # build the pages from the charts and Claude's article
    python make_edition.py rebuild           # redo every edition's page after a design change

In between, Claude reads work/brief.md and saves its article to work/article.md.
If there's no article, publish makes a numbers-only edition.
"""

from __future__ import annotations

import json
import os
import shutil
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import yaml

from newsroom import charts, market_data, page, writer

ROOT = Path(__file__).parent
DOCS = ROOT / "docs"  # everything in here becomes the public website
WORK = ROOT / "work"  # scratch space shared with Claude, never published
BRIEF = WORK / "brief.md"
ARTICLE = WORK / "article.md"
STATE = WORK / "edition.json"


def tell_github(name: str, value: str) -> None:
    """Passes a value on to the next steps of the GitHub Actions workflow."""
    output = os.environ.get("GITHUB_OUTPUT")
    if output:
        with open(output, "a", encoding="utf-8") as f:
            f.write(f"{name}={value}\n")


def prepare(config: dict, force: bool) -> None:
    paper = config["paper"]
    now = datetime.now(ZoneInfo(paper["timezone"]))
    edition_dir = DOCS / "editions" / now.date().isoformat()

    if not force:
        if paper.get("publish_weekdays_only", True) and now.weekday() >= 5:
            print("It's the weekend - no edition today.")
            return
        if now.hour < paper["publish_hour"]:
            print(f"It's {now:%H:%M} in {paper['timezone']} - too early to publish.")
            return
        if (edition_dir / "index.html").exists():
            print("Today's edition is already out.")
            return

    print("Fetching market data...")
    data = market_data.fetch(config)
    print(f"Got {len(data.quotes)} prices.")
    if data.missing:
        print(f"No data for: {', '.join(data.missing)}")
    if not data.quotes:
        sys.exit("No market data at all - stopping so we don't publish an empty paper.")

    edition_dir.mkdir(parents=True, exist_ok=True)
    print("Drawing charts...")
    made = charts.make_all(data, edition_dir)
    (edition_dir / "data.json").write_text(json.dumps(data.to_json(), indent=2), encoding="utf-8")

    shutil.rmtree(WORK, ignore_errors=True)
    writer.write_brief(data, config, now, BRIEF)
    STATE.write_text(json.dumps({"edition_dir": str(edition_dir.relative_to(ROOT)), "charts": made,
                                 "time": now.isoformat()}), encoding="utf-8")
    print(f"Ready for Claude: {BRIEF.relative_to(ROOT)}")
    tell_github("ready", "true")
    tell_github("date", edition_dir.name)


def publish(config: dict) -> None:
    if not STATE.exists():
        sys.exit("Nothing to publish - run 'prepare' first.")
    state = json.loads(STATE.read_text(encoding="utf-8"))
    edition_dir = ROOT / state["edition_dir"]
    now = datetime.fromisoformat(state["time"])
    data = market_data.MarketData.from_json(config, json.loads((edition_dir / "data.json").read_text(encoding="utf-8")))

    article = writer.read_article(ARTICLE)
    if article:
        (edition_dir / "article.md").write_text(article, encoding="utf-8")

    number = len([d for d in (DOCS / "editions").iterdir() if d.is_dir()])
    page.build(DOCS, edition_dir, data, state["charts"], article, config, now, number)
    shutil.rmtree(WORK, ignore_errors=True)
    print(f"Edition No. {number} published to {edition_dir.relative_to(ROOT)}")


def rebuild(config: dict) -> None:
    """Re-renders every past edition from its saved numbers, charts and article."""
    folders = sorted(d for d in (DOCS / "editions").iterdir() if (d / "data.json").exists())
    for number, folder in enumerate(folders, start=1):
        data = market_data.MarketData.from_json(config, json.loads((folder / "data.json").read_text(encoding="utf-8")))
        article_file = folder / "article.md"
        article = article_file.read_text(encoding="utf-8") if article_file.exists() else None
        made = {c: f"{c}.png" for c in charts.CHART_IDS if (folder / f"{c}.png").exists()}
        page.build(DOCS, folder, data, made, article, config, datetime.fromisoformat(folder.name), number)
    print(f"Rebuilt {len(folders)} editions.")


def main() -> None:
    config = yaml.safe_load((ROOT / "config.yaml").read_text(encoding="utf-8"))
    step = sys.argv[1] if len(sys.argv) > 1 else ""
    if step == "prepare":
        prepare(config, force="--force" in sys.argv or os.environ.get("FORCE") == "true")
    elif step == "publish":
        publish(config)
    elif step == "rebuild":
        rebuild(config)
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()
