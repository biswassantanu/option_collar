# simple_collar_backtest_yf.py
"""
Yahoo Finance-only simple annual collar backtest.
- Fetches daily history via yfinance for a given ticker (Adj Close used for total returns).
- Computes annual total returns from the first trading day of each year to the next.
- Applies a European-style collar by clipping each year's return to [floor, cap].
- NO option pricing. NO CSV upload. NO synthetic fallback.
"""

from dataclasses import dataclass
from typing import Optional
import pandas as pd
import yfinance as yf


@dataclass
class BacktestInput:
    ticker: str = "SPY"
    floor: float = -0.02
    cap: float = 0.11
    start_year: Optional[int] = None
    initial_value: float = 100_000.0


def fetch_adj_close(ticker: str) -> pd.Series:
    t = yf.Ticker(ticker)
    hist = t.history(period="max", auto_adjust=False)  # keep Adj Close separate
    if hist.empty or "Adj Close" not in hist.columns:
        raise RuntimeError(f"Could not fetch Adj Close for {ticker} from Yahoo Finance.")
    s = hist["Adj Close"].copy()
    s.index = pd.to_datetime(s.index)
    s = s.sort_index()
    return s


def first_trading_day_each_year(index: pd.DatetimeIndex) -> pd.DatetimeIndex:
    by_year = {}
    for ts in index.sort_values():
        y = ts.year
        if y not in by_year:
            by_year[y] = ts
    return pd.DatetimeIndex(sorted(by_year.values()))


def compute_annual_total_returns(adj_close: pd.Series) -> pd.DataFrame:
    starts = first_trading_day_each_year(adj_close.index)
    rows = []
    for i in range(len(starts) - 1):
        start = starts[i]
        end = starts[i + 1]
        a0 = float(adj_close.loc[:start].iloc[-1])
        a1 = float(adj_close.loc[:end].iloc[-1])
        ret = (a1 / a0) - 1.0
        rows.append({"year": start.year, "start_date": start, "end_date": end, "market_ret": ret})
    return pd.DataFrame(rows)


def run_backtest(inp: BacktestInput) -> pd.DataFrame:
    adj = fetch_adj_close(inp.ticker)
    ann = compute_annual_total_returns(adj)
    if ann.empty:
        return ann

    if inp.start_year is not None:
        ann = ann[ann["year"] >= int(inp.start_year)].copy()
        ann.reset_index(drop=True, inplace=True)

    ann["floor"] = float(inp.floor)
    ann["cap"] = float(inp.cap)
    ann["collar_ret"] = ann["market_ret"].clip(lower=inp.floor, upper=inp.cap)

    ann["market_value"] = float(inp.initial_value) * (1.0 + ann["market_ret"]).cumprod()
    ann["collar_value"] = float(inp.initial_value) * (1.0 + ann["collar_ret"]).cumprod()

    out = ann[[
        "year", "start_date", "market_ret", "floor", "cap", "collar_ret", "market_value", "collar_value"
    ]].copy()
    return out
