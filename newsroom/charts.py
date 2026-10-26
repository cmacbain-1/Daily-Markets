"""Draws the charts for each edition as PNG images."""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # draw to files, no screen needed
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.ticker import FuncFormatter

from .market_data import MarketData, format_change

SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK_2 = "#52514e"
MUTED = "#898781"
GRID = "#e1e0d9"
AXIS = "#c3c2b7"
SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"]
UP = "#2a78d6"
DOWN = "#e34948"

# 1200 x 630 px - the shape LinkedIn uses for link previews
SIZE = (8, 4.2)
DPI = 150

WORLD_INDEXES = ["^GSPC", "^IXIC", "^FTSE", "^GDAXI", "^N225"]
MOVER_GROUPS = ["big_tech", "banks", "heavyweights", "rising"]

plt.rcParams.update({
    "font.family": "DejaVu Sans",
    "font.size": 10,
    "text.color": INK,
    "axes.edgecolor": AXIS,
    "axes.labelcolor": INK_2,
    "axes.facecolor": SURFACE,
    "figure.facecolor": SURFACE,
    "xtick.color": MUTED,
    "ytick.color": MUTED,
    "axes.grid": True,
    "grid.color": GRID,
    "grid.linewidth": 0.6,
    "axes.spines.top": False,
    "axes.spines.right": False,
})


def _new_figure(title: str, subtitle: str):
    fig, ax = plt.subplots(figsize=SIZE, dpi=DPI)
    fig.text(0.03, 0.94, title, fontsize=14, fontweight="bold", color=INK, va="top")
    fig.text(0.03, 0.875, subtitle, fontsize=9.5, color=INK_2, va="top")
    fig.subplots_adjust(left=0.08, right=0.97, top=0.78, bottom=0.12)
    return fig, ax


def _signed_percent(v: float, decimals: int) -> str:
    return "0%" if round(v, decimals) == 0 else f"{v:+.{decimals}f}%"


def _date_axis(ax) -> None:
    locator = mdates.AutoDateLocator(minticks=4, maxticks=7)
    ax.xaxis.set_major_locator(locator)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %d"))


def _save(fig, path: Path) -> str:
    fig.savefig(path, facecolor=SURFACE)
    plt.close(fig)
    return path.name


def world_indexes(data: MarketData, path: Path) -> str | None:
    symbols = [s for s in WORLD_INDEXES if s in data.history]
    if len(symbols) < 2:
        return None
    frame = pd.DataFrame({s: data.history[s] for s in symbols})
    frame = frame[frame.index >= frame.index[-1] - pd.Timedelta(days=31)].ffill().dropna()
    rebased = (frame / frame.iloc[0] - 1) * 100

    fig, ax = _new_figure("World stock markets, past month", "% change since one month ago")
    for colour, symbol in zip(SERIES, symbols):
        q = data.quotes[symbol]
        label = f"{q.name.split(' (')[0]}  {rebased[symbol].iloc[-1]:+.1f}%"
        ax.plot(rebased.index, rebased[symbol], color=colour, linewidth=2, label=label)
    ax.axhline(0, color=AXIS, linewidth=1)
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: _signed_percent(v, 0)))
    ax.legend(loc="upper left", frameon=False, fontsize=9, ncol=3)
    _date_axis(ax)
    return _save(fig, path)


def _bars(items: list[tuple[str, float]], title: str, subtitle: str, path: Path) -> str | None:
    if not items:
        return None
    items = sorted(items, key=lambda item: item[1])
    labels = [label for label, _ in items]
    values = [value for _, value in items]
    colours = [UP if v >= 0 else DOWN for v in values]

    fig, ax = _new_figure(title, subtitle)
    fig.subplots_adjust(left=0.27)
    ax.barh(labels, values, color=colours, height=0.62)
    ax.axvline(0, color=AXIS, linewidth=1)
    ax.grid(axis="y", visible=False)
    ax.tick_params(axis="y", colors=INK_2, length=0)
    ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _: _signed_percent(v, 1)))
    span = max(abs(v) for v in values) or 1
    ax.set_xlim(min(min(values), 0) - span * 0.25, max(max(values), 0) + span * 0.25)
    for i, v in enumerate(values):
        ax.text(v + (span * 0.03 if v >= 0 else -span * 0.03), i, format_change(v, "price"),
                va="center", ha="left" if v >= 0 else "right", fontsize=8.5, color=INK_2)
    return _save(fig, path)


def sectors(data: MarketData, path: Path) -> str | None:
    items = [(q.name, q.change_1d) for q in data.group_quotes("sectors") if q.change_1d is not None]
    return _bars(items, "US sectors, latest session", "% change on the day (blue = up, red = down)", path)


def movers(data: MarketData, path: Path) -> str | None:
    quotes = [q for g in MOVER_GROUPS for q in data.group_quotes(g) if q.change_1d is not None]
    quotes.sort(key=lambda q: q.change_1d)
    picked = quotes[:5] + quotes[-5:] if len(quotes) > 10 else quotes
    items = [(q.name.split(" (")[0], q.change_1d) for q in picked]
    return _bars(items, "Biggest movers on our watchlist", "Five best and five worst, % change on the day", path)


def _single_line(series: pd.Series, title: str, subtitle: str, fmt, path: Path) -> str:
    fig, ax = _new_figure(title, subtitle)
    fig.subplots_adjust(left=0.11)
    ax.plot(series.index, series.values, color=SERIES[0], linewidth=2)
    ax.plot(series.index[-1], series.iloc[-1], "o", color=SERIES[0], markersize=6,
            markeredgecolor=SURFACE, markeredgewidth=2)
    ax.annotate(fmt(series.iloc[-1]), (series.index[-1], series.iloc[-1]),
                xytext=(-8, 10), textcoords="offset points", ha="right", fontsize=9.5, color=INK)
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: fmt(v)))
    _date_axis(ax)
    return _save(fig, path)


def bitcoin(data: MarketData, path: Path) -> str | None:
    if "BTC-USD" not in data.history:
        return None
    series = data.history["BTC-USD"]
    series = series[series.index >= series.index[-1] - pd.Timedelta(days=92)]
    return _single_line(series, "Bitcoin, past three months", "Price in US dollars",
                        lambda v: f"${v:,.0f}", path)


def us_10_year(data: MarketData, path: Path) -> str | None:
    if "^TNX" not in data.history:
        return None
    series = data.history["^TNX"]
    series = series[series.index >= series.index[-1] - pd.Timedelta(days=183)]
    return _single_line(series, "US 10-year Treasury yield, past six months",
                        "Yield in percent - the benchmark for borrowing costs worldwide",
                        lambda v: f"{v:.2f}%", path)


CHART_IDS = ["world", "sectors", "movers", "yields", "bitcoin"]


def make_all(data: MarketData, out_dir: Path) -> dict[str, str]:
    """Returns {chart id: image file name} for every chart that could be drawn."""
    makers = {
        "world": world_indexes,
        "sectors": sectors,
        "movers": movers,
        "yields": us_10_year,
        "bitcoin": bitcoin,
    }
    made = {}
    for chart_id, maker in makers.items():
        file_name = maker(data, out_dir / f"{chart_id}.png")
        if file_name:
            made[chart_id] = file_name
    return made
