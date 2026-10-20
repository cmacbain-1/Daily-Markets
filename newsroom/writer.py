"""Writes the brief Claude follows when it writes the day's article.

On GitHub, Claude Code reads work/brief.md, searches the news, and saves
the article to work/article.md, using your Claude subscription.
"""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

from .market_data import MarketData, format_change, format_level

SECTIONS = """\
# <Headline: punchy, specific, at most 12 words>
*<Standfirst: one or two sentences summing up the day>*

## The big story
## Around the world
## Sectors and stocks
## Rates, currencies and commodities
## Crypto
## On the radar
## What to watch today
## Term of the day
## Sources"""

BRIEF = """\
# Brief: today's edition of {name}

You are the editor of {name}, a daily markets newspaper read by finance students \
and young professionals. You write like a good financial newspaper: clear, lively, \
precise, and never hyped. You explain *why* markets moved, not just *that* they moved.

It is {today}, {time} {timezone} time. Write today's edition.

## Rules
- Every price, index level and percentage move you quote must come from the market \
data below. Never invent or estimate a number.
- Use web search to find the news behind the biggest moves (earnings, central banks, \
economic data, geopolitics) from the last day or so, and what is scheduled for today. \
Facts from the news (e.g. an earnings figure or an inflation reading) are fine to \
quote, attributed to their source. Use at most {max_searches} searches.
- Check each market's "as of" date: some figures are the previous session's close, \
while markets trading now (e.g. Europe, crypto) show their latest price.
- Note when markets were closed (e.g. a public holiday) instead of reading meaning into flat numbers.
- Briefly explain jargon the first time it appears - readers are still learning.
- Give no buy, sell or hold recommendations. This is news, not investment advice.

## Structure
Use exactly this structure, in Markdown:

{sections}

- The big story: the single most important market story, 150-250 words.
- Around the world: US, Europe and Asia in a paragraph each.
- Sectors and stocks: what led and lagged, and notable moves in Big Tech, banks and other heavyweights.
- Rates, currencies and commodities: bond yields, the dollar, oil and gold, and what they signal.
- Crypto: Bitcoin and the other majors, briefly.
- On the radar: one or two themes "on the come-up" from the On the come-up group or the news \
(e.g. AI chips, uranium, India) and why they are worth watching.
- What to watch today: a bulleted list of 3-6 scheduled events (data releases, central bank speakers, big earnings).
- Term of the day: explain one finance concept that came up today, in plain English, 80-120 words.
- Sources: a bulleted list of the articles you used, as Markdown links.

Aim for 900-1,300 words before the sources. The file must start with the "# " headline \
line - nothing before it.

## Market data
"1d" = change over the latest session, "1w" about five sessions, "1m" about 21 sessions, \
"YTD" since the end of last year. Bond yields move in basis points (1 bp = 0.01 percentage \
points). "as of" is the date of the latest price.
{data}
"""


def _data_table(data: MarketData) -> str:
    lines = []
    for group in data.groups:
        quotes = data.group_quotes(group["id"])
        if not quotes:
            continue
        lines.append(f"\n### {group['title']}")
        for q in quotes:
            lines.append(
                f"- {q.name} ({q.symbol}): {format_level(q)}"
                f" | 1d {format_change(q.change_1d, q.kind)}"
                f" | 1w {format_change(q.change_1w, q.kind)}"
                f" | 1m {format_change(q.change_1m, q.kind)}"
                f" | YTD {format_change(q.change_ytd, q.kind)}"
                f" | 52-week range {q.low_52w:,.2f}-{q.high_52w:,.2f}"
                f" | as of {q.as_of}"
            )
    return "\n".join(lines)


def write_brief(data: MarketData, config: dict, now: datetime, path: Path) -> None:
    paper = config["paper"]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(BRIEF.format(
        name=paper["name"],
        today=now.strftime("%A %d %B %Y"),
        time=now.strftime("%H:%M"),
        timezone=paper["timezone"],
        max_searches=config["writer"]["max_searches"],
        sections=SECTIONS,
        data=_data_table(data),
    ), encoding="utf-8")


def read_article(path: Path) -> str | None:
    """Returns Claude's article, or None if it's missing or doesn't look like an article."""
    if not path.exists():
        print("No article from Claude - publishing a numbers-only edition.")
        return None
    text = path.read_text(encoding="utf-8")
    headline = re.search(r"^# ", text, re.MULTILINE)
    if not headline:
        print("Claude's article had no headline - publishing a numbers-only edition.")
        return None
    return text[headline.start():].strip()
