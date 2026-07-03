"""Constants, defaults, and the run configuration dataclass."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

DEFAULT_TICKER = ""          # leave empty → interactive prompt; or set e.g. "AAPL"
DEFAULT_PERIOD = "5y"
DEFAULT_INTERVAL = "1d"
REQUIRED_HISTORY_COLUMNS = {"Open", "High", "Low", "Close"}
CACHE_DIR = Path(".cache")
CACHE_TTL_SECONDS = 4 * 3600
VALID_PERIODS = ["1y", "2y", "3y", "5y", "10y", "max"]

SECTOR_BENCHMARK_MAP: dict[str, str] = {
    "Technology": "XLK",
    "Healthcare": "XLV",
    "Financial Services": "XLF",
    "Financials": "XLF",
    "Consumer Cyclical": "XLY",
    "Consumer Defensive": "XLP",
    "Energy": "XLE",
    "Industrials": "XLI",
    "Basic Materials": "XLB",
    "Real Estate": "XLRE",
    "Utilities": "XLU",
    "Communication Services": "XLC",
}

IR_URL_OVERRIDES: dict[str, str] = {
    "SAP": "https://www.sap.com/investors/en.html",
    "SAP.DE": "https://www.sap.com/investors/en.html",
}

# Default peer groups for the peer-comparison section, used when --peers is
# not passed. Peers only need Yahoo profile data, so any listed ticker works.
# Tickers without an entry simply skip the section unless --peers is given.
PEER_MAP: dict[str, list[str]] = {
    "AAPL":   ["MSFT", "GOOGL", "AMZN", "META", "NVDA"],
    "MSFT":   ["AAPL", "GOOGL", "AMZN", "ORCL", "CRM"],
    "GOOGL":  ["META", "MSFT", "AAPL", "AMZN"],
    "GOOG":   ["META", "MSFT", "AAPL", "AMZN"],
    "AMZN":   ["WMT", "GOOGL", "MSFT", "BABA"],
    "META":   ["GOOGL", "SNAP", "PINS", "MSFT"],
    "NVDA":   ["AMD", "AVGO", "INTC", "QCOM", "TSM"],
    "AMD":    ["NVDA", "INTC", "AVGO", "QCOM"],
    "TSLA":   ["GM", "F", "RIVN", "TM"],
    "NFLX":   ["DIS", "WBD", "PARA", "CMCSA"],
    "SAP":    ["ORCL", "CRM", "MSFT", "WDAY", "NOW"],
    "SAP.DE": ["ORCL", "CRM", "MSFT", "WDAY", "NOW"],
    "ORCL":   ["SAP", "MSFT", "CRM", "IBM"],
    "CRM":    ["SAP", "ORCL", "NOW", "WDAY"],
    "XOM":    ["CVX", "SHEL", "BP", "TTE", "COP"],
    "CVX":    ["XOM", "SHEL", "BP", "TTE", "COP"],
    "JPM":    ["BAC", "WFC", "C", "GS", "MS"],
    "V":      ["MA", "AXP", "PYPL"],
    "MA":     ["V", "AXP", "PYPL"],
    "KO":     ["PEP", "KDP", "MNST"],
    "PEP":    ["KO", "KDP", "MNST"],
    "JNJ":    ["PFE", "MRK", "ABBV", "LLY"],
    "LLY":    ["NVO", "MRK", "PFE", "ABBV"],
    "7203.T": ["HMC", "TM", "GM", "F", "VOW3.DE"],
    "NESN.SW": ["UL", "DANOY", "KHC", "MDLZ"],
    "VOW3.DE": ["MBG.DE", "BMW.DE", "STLA", "F"],
    "ASML":   ["AMAT", "LRCX", "KLAC", "TSM"],
}


@dataclass(frozen=True)
class ReportConfig:
    ticker: str
    period: str = DEFAULT_PERIOD
    interval: str = DEFAULT_INTERVAL
    risk_free_rate: float = 0.045
    market_return: float = 0.085
    terminal_growth: float = 0.025
    forecast_years: int = 5
    monte_carlo_paths: int = 250
    monte_carlo_days: int = 252
    benchmark_ticker: str = "SPY"
    use_cache: bool = False
    peers: tuple[str, ...] = ()
