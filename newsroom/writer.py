"""Asks Claude to write the day's article from the numbers, using web search for the 'why'."""

from __future__ import annotations

import os
import re
from datetime import datetime

import anthropic

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
## Term of the day"""

SYSTEM = """\
You are the editor of {name}, a daily markets newspaper read by finance students \
and young professionals. You write like a good financial newspaper: clear, lively, \
precise, and never hyped. You explain *why* markets moved, not just *that* they moved.

Rules:
- Every price, index level and percentage move you quote must come from the market \
data the user gives you. Never invent or estimate a number.
- Use web search to find the news behind the biggest moves (earnings, central banks, \
economic data, geopolitics) from the last day or so, and what is scheduled for today. \
Facts from the news (e.g. an earnings figure or an inflation reading) are fine to \
quote, attributed to their source.
- Briefly explain jargon the first time it appears - readers are still learning.
- Give no buy, sell or hold recommendations. This is news, not investment advice.
- Note when markets were closed (e.g. a public holiday) instead of reading meaning into flat numbers."""

INSTRUCTIONS = """\
It is {today}, {time} {timezone} time. Write today's edition of {name}. \
Check each market's "as of" date: some figures are the previous session's close, \
while markets trading now (e.g. Europe, crypto) show their latest price.

Use exactly this structure, in Markdown:

{sections}

Guidance per section:
- The big story: the single most important market story, 150-250 words.
- Around the world: US, Europe and Asia in a paragraph each.
- Sectors and stocks: what led and lagged, and notable moves in Big Tech, banks and other heavyweights.
- Rates, currencies and commodities: bond yields, the dollar, oil and gold, and what they signal.
- Crypto: Bitcoin and the other majors, briefly.
- On the radar: one or two themes "on the come-up" from the On the come-up group or the news (e.g. AI chips, uranium, India) and why they are worth watching.
- What to watch today: a bulleted list of 3-6 scheduled events (data releases, central bank speakers, big earnings).
- Term of the day: explain one finance concept that came up today, in plain English, 80-120 words.

Aim for 900-1,300 words in total. Output only the article - start with the "# " headline \
line and write nothing before it.

Market data ("1d" = change over the latest session, "1w" about five sessions, \
"1m" about 21 sessions, "YTD" since the end of last year; bond yields move in basis points, \
1 bp = 0.01 percentage points; "as of" is the date of the latest price):

{data}"""


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


def _sources(blocks) -> list[dict]:
    seen, sources = set(), []
    for block in blocks:
        for citation in getattr(block, "citations", None) or []:
            url = getattr(citation, "url", None)
            if url and url not in seen:
                seen.add(url)
                sources.append({"url": url, "title": getattr(citation, "title", None) or url})
    return sources


def write_article(data: MarketData, config: dict, now: datetime) -> dict | None:
    """Returns {"markdown": ..., "sources": [...]}, or None if there's no API key or Claude couldn't write it."""
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("No ANTHROPIC_API_KEY set - publishing a numbers-only edition.")
        return None

    name = config["paper"]["name"]
    client = anthropic.Anthropic()
    messages = [{
        "role": "user",
        "content": INSTRUCTIONS.format(
            today=now.strftime("%A %d %B %Y"), time=now.strftime("%H:%M"),
            timezone=config["paper"]["timezone"], name=name, sections=SECTIONS, data=_data_table(data)
        ),
    }]

    try:
        # Web searches can make Claude pause part-way; we simply let it carry on.
        for _ in range(5):
            response = client.beta.messages.create(
                model=config["writer"]["model"],
                max_tokens=16000,
                betas=["server-side-fallback-2026-07-01"],
                fallbacks="default",
                system=SYSTEM.format(name=name),
                output_config={"effort": "medium"},
                tools=[{
                    "type": "web_search_20260209",
                    "name": "web_search",
                    "max_uses": config["writer"]["max_searches"],
                }],
                messages=messages,
            )
            if response.stop_reason != "pause_turn":
                break
            messages.append({"role": "assistant", "content": response.content})
    except anthropic.AuthenticationError:
        print("Claude API key was rejected - check the ANTHROPIC_API_KEY secret.")
        return None
    except anthropic.APIStatusError as e:
        print(f"Claude API error {e.status_code}: {e.message}")
        return None
    except anthropic.APIConnectionError:
        print("Could not reach the Claude API.")
        return None

    if response.stop_reason == "refusal":
        print("Claude declined to write today's article.")
        return None

    # The article is the run of text after Claude's last web search.
    last_tool = max((i for i, b in enumerate(response.content) if b.type != "text"), default=-1)
    article_blocks = [b for b in response.content[last_tool + 1:] if b.type == "text"]
    text = "".join(b.text for b in article_blocks)
    headline = re.search(r"^# ", text, re.MULTILINE)
    if not headline:
        print("Claude's reply didn't contain a headline - publishing a numbers-only edition.")
        return None

    print(f"Article written ({response.usage.output_tokens} output tokens).")
    return {"markdown": text[headline.start():].strip(), "sources": _sources(article_blocks)}
