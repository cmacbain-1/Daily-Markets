"""Makes today's edition of the newspaper.

    python make_edition.py           # only publishes if it's publishing time and today's edition doesn't exist yet
    python make_edition.py --force   # publish now, replacing today's edition if there is one
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import yaml

from newsroom import charts, market_data, page, writer

ROOT = Path(__file__).parent
DOCS = ROOT / "docs"  # everything in here becomes the public website


def tell_github(name: str, value: str) -> None:
    """Passes a value on to the next steps of the GitHub Actions workflow."""
    output = os.environ.get("GITHUB_OUTPUT")
    if output:
        with open(output, "a", encoding="utf-8") as f:
            f.write(f"{name}={value}\n")


def main() -> None:
    config = yaml.safe_load((ROOT / "config.yaml").read_text(encoding="utf-8"))
    paper = config["paper"]
    now = datetime.now(ZoneInfo(paper["timezone"]))
    force = "--force" in sys.argv or os.environ.get("FORCE") == "true"
    edition_dir = DOCS / "editions" / now.date().isoformat()

    if not force:
        if paper.get("publish_weekdays_only", True) and now.weekday() >= 5:
            print("It's the weekend - no edition today.")
            return
        if now.hour < paper["publish_hour"]:
            print(f"It's {now:%H:%M} in {paper['timezone']} - too early to publish.")
            return
        if edition_dir.exists():
            print("Today's edition is already out.")
            return

    edition_dir.mkdir(parents=True, exist_ok=True)
    number = len([d for d in (DOCS / "editions").iterdir() if d.is_dir()])

    print("Fetching market data...")
    data = market_data.fetch(config)
    print(f"Got {len(data.quotes)} prices.")
    if data.missing:
        print(f"No data for: {', '.join(data.missing)}")
    if not data.quotes:
        sys.exit("No market data at all - stopping so we don't publish an empty paper.")

    print("Drawing charts...")
    made = charts.make_all(data, edition_dir)

    print("Writing the article...")
    article = writer.write_article(data, config, now)

    (edition_dir / "data.json").write_text(json.dumps(data.to_json(), indent=2), encoding="utf-8")
    if article:
        (edition_dir / "article.md").write_text(article["markdown"], encoding="utf-8")

    page.build(DOCS, edition_dir, data, made, article, config, now, number)
    print(f"Edition No. {number} published to {edition_dir.relative_to(ROOT)}")
    tell_github("published", "true")


if __name__ == "__main__":
    main()
