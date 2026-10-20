"""Downloads prices from Yahoo Finance and works out how much each one moved."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date, timedelta

import pandas as pd
import yfinance as yf

# Trading days back for each comparison
ONE_WEEK = 5
ONE_MONTH = 21


@dataclass
class Quote:
    symbol: str
    name: str
    group: str
    kind: str  # "price" or "yield"
    last: float
    as_of: str
    change_1d: float | None  # percent, or basis points for yields
    change_1w: float | None
    change_1m: float | None
    change_ytd: float | None
    high_52w: float
    low_52w: float


@dataclass
class MarketData:
    groups: list[dict]
    quotes: dict[str, Quote] = field(default_factory=dict)
    history: dict[str, pd.Series] = field(default_factory=dict)
    missing: list[str] = field(default_factory=list)

    def group_quotes(self, group_id: str) -> list[Quote]:
        return [q for q in self.quotes.values() if q.group == group_id]

    def to_json(self) -> dict:
        return {
            "quotes": [asdict(q) for q in self.quotes.values()],
            "missing": self.missing,
        }


def _change(new: float, old: float, kind: str) -> float:
    if kind == "yield":
        return (new - old) * 100  # percentage points -> basis points
    return (new / old - 1) * 100


def _change_back(closes: pd.Series, rows_back: int, kind: str) -> float | None:
    if len(closes) <= rows_back:
        return None
    return _change(closes.iloc[-1], closes.iloc[-1 - rows_back], kind)


def _change_ytd(closes: pd.Series, kind: str) -> float | None:
    year = closes.index[-1].year
    before_this_year = closes[closes.index.year < year]
    if before_this_year.empty:
        return None
    return _change(closes.iloc[-1], before_this_year.iloc[-1], kind)


def fetch(config: dict) -> MarketData:
    data = MarketData(groups=config["groups"])
    symbols = [s for g in config["groups"] for s in g["tickers"]]

    raw = yf.download(
        symbols,
        start=date.today() - timedelta(days=400),
        interval="1d",
        auto_adjust=True,
        group_by="ticker",
        progress=False,
        threads=True,
    )

    for group in config["groups"]:
        kind = group.get("kind", "price")
        for symbol, name in group["tickers"].items():
            try:
                closes = raw[symbol]["Close"].dropna()
            except KeyError:
                closes = pd.Series(dtype=float)
            if closes.empty:
                data.missing.append(symbol)
                continue

            closes.index = pd.to_datetime(closes.index).tz_localize(None)
            # Yahoo used to quote some yields x10 (e.g. 42.5 for 4.25%)
            if kind == "yield" and closes.iloc[-1] > 20:
                closes = closes / 10

            last_year = closes[closes.index > closes.index[-1] - pd.Timedelta(days=365)]
            data.history[symbol] = closes
            data.quotes[symbol] = Quote(
                symbol=symbol,
                name=name,
                group=group["id"],
                kind=kind,
                last=float(closes.iloc[-1]),
                as_of=closes.index[-1].date().isoformat(),
                change_1d=_change_back(closes, 1, kind),
                change_1w=_change_back(closes, ONE_WEEK, kind),
                change_1m=_change_back(closes, ONE_MONTH, kind),
                change_ytd=_change_ytd(closes, kind),
                high_52w=float(last_year.max()),
                low_52w=float(last_year.min()),
            )

    return data


def format_level(q: Quote) -> str:
    if q.kind == "yield":
        return f"{q.last:.2f}%"
    if q.last >= 1000:
        return f"{q.last:,.0f}"
    if q.last < 10:
        return f"{q.last:,.4f}"
    return f"{q.last:,.2f}"


def format_change(value: float | None, kind: str) -> str:
    if value is None:
        return "–"
    if kind == "yield":
        return f"{value:+.0f} bp"
    return f"{value:+.2f}%"
