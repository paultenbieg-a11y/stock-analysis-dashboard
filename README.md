# Full Scale Stock Analysis

This project creates an interactive HTML equity-research report with fundamental analysis, WACC-based valuation (including sensitivity and reverse DCF), peer comparison, earnings tracking, benchmark comparison, quarterly snapshots, technical chart analysis, risk metrics, scenario modelling, and simulated forward paths.

## What You Get

Running the script creates a self-contained interactive HTML report in the `reports` folder. The report includes:

- **Interactive launcher**: a styled terminal prompt asks for ticker, period, peers, and DCF settings — no code editing required.
- **Sticky navigation and numbered sections** in a clean dark research-report layout.
- Executive summary with fundamental, valuation, chart, reverse-DCF, and peer interpretation.
- Company overview with business description, sector, industry, headquarters, employees, and specialization tags.
- **Earnings and quarterly trends**: last eight quarters of revenue/gross profit/net income, reported EPS vs consensus estimates with surprise percentages, a "days until next earnings" card, and earnings-date markers on the price chart.
- Candlestick chart with moving averages, Bollinger Bands, volume, RSI, and MACD.
- Annual income statement, balance sheet, and cash flow statement (most recent annual release plus the previous two).
- Fundamental dashboard with margins, growth, leverage, liquidity, ROE, ROA, and cash flow metrics.
- **WACC-based DCF** plus a **fair-value sensitivity heatmap** (WACC × terminal growth), a **tornado chart** of which input moves fair value most, and a **reverse DCF** stating the FCF growth the current price implies.
- **Peer comparison**: a comparables table (multiples, margins, growth, ROE, FCF yield) with the subject highlighted, percentile positioning, and a growth-vs-EV/EBITDA bubble chart.
- **Benchmark comparison**: cumulative return vs SPY (or the sector ETF), with relative return, tracking error, information ratio, beta, and alpha.
- Risk dashboard with dividend-adjusted returns, drawdowns, distribution, VaR/CVaR, proper Sharpe/Sortino, and options-implied volatility where available.
- Forward scenario table and Monte Carlo price cone.
- **Watchlist mode**: analyze multiple tickers in one run; a summary comparison table is printed in the terminal.
- **Download cache**: optional 4-hour cache so re-runs skip the network round-trip.

For a full explanation of every output and assumption, read [OUTPUTS_AND_ASSUMPTIONS.md](OUTPUTS_AND_ASSUMPTIONS.md).

## Project Structure

The code lives in the `stockanalysis` package; `stock_analysis.py` is a thin entry point, so all previous commands still work.

```text
stock_analysis.py              entry point (unchanged usage)
stockanalysis/
  config.py                    constants, ReportConfig, peer map
  utils.py                     formatting / coercion helpers
  terminal.py                  ANSI styling, interactive prompt, watchlist table
  cache.py                     optional 4-hour download cache
  data.py                      all Yahoo Finance fetching (prices, statements,
                               benchmark, options IV, earnings, peers)
  indicators.py                technical indicators
  fundamentals.py              statement parsing, ratios, Piotroski score
  valuation.py                 WACC, DCF, sensitivity grid, reverse DCF, tornado
  risk.py                      risk metrics, Monte Carlo
  narrative.py                 plain-English interpretation
  peers.py                     peer table + percentile positioning
  report/
    theme.py                   palette, Plotly defaults, stylesheet
    charts.py                  every chart builder
    components.py              HTML fragments (cards, tables, sections)
    builder.py                 assembles the final report
  cli.py                       argument parsing and orchestration
tests/                         pytest suite on synthetic yfinance-shaped fixtures
```

## Setup

Open a terminal in this project folder, then run:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

You only need to do this once unless you delete the `.venv` folder.

## Run — Interactive (default)

Just run the script with no arguments. A styled prompt will ask for everything:

```bash
source .venv/bin/activate
python stock_analysis.py
```

Press Enter on any optional field to keep the default. The peers question is optional — leave it empty to use the built-in peer map.

## Run — Command Line (scripting / CI)

Pass `--ticker` to skip the interactive prompt:

```bash
python stock_analysis.py --ticker AAPL
python stock_analysis.py --ticker MSFT --period 10y
python stock_analysis.py --ticker GOOGL --risk-free-rate 0.04 --market-return 0.085 --terminal-growth 0.025
```

### Peer comparison

Well-known tickers get a default peer set from `PEER_MAP` in `stockanalysis/config.py`. Override it per run:

```bash
python stock_analysis.py --ticker AAPL --peers MSFT GOOGL META AMZN
```

Tickers with no map entry and no `--peers` simply skip the section.

### Watchlist mode

Analyze several tickers at once. Individual reports are written to `reports/`, and a comparison table is printed in the terminal:

```bash
python stock_analysis.py --watchlist AAPL MSFT NVDA GOOGL
```

### Download cache

Add `--cache` to store downloaded data for 4 hours. Subsequent runs with the same ticker, period, and peers skip the network call:

```bash
python stock_analysis.py --ticker SAP.DE --cache
```

### Benchmark

Override the benchmark ticker (default SPY). The script auto-selects the matching sector ETF when it can:

```bash
python stock_analysis.py --ticker XOM --benchmark XLE
```

### Skip the prompt entirely

If you set `DEFAULT_TICKER` in `stockanalysis/config.py` and want to run non-interactively:

```bash
python stock_analysis.py --no-interactive
```

## Tests

The test suite runs on synthetic fixtures shaped like yfinance output, so no network is needed:

```bash
pip install -r requirements-dev.txt
python -m pytest
```

Because yfinance changes its API shape regularly, the tests are the early-warning system: run them after upgrading dependencies.

## Find the Report

Reports are written to:

```text
reports/<TICKER>_stock_analysis.html
```

Open the file in a browser to use the interactive charts. Charts and fonts load from CDNs (Plotly, Google Fonts), so the charts need an internet connection when viewing.

Generated reports are ignored by Git. The `reports` folder is kept via `reports/.gitkeep`.

## Ticker Formats

- `AAPL` — Apple on Nasdaq
- `SAP` — SAP US ADR
- `SAP.DE` — SAP on Xetra (German listing)
- `7203.T` — Toyota in Tokyo
- `NESN.SW` — Nestlé in Switzerland

## Currency Handling

The report separates the market quote currency from the financial statement currency.

When they differ (e.g., a USD-traded ADR with EUR statements), the report shows the statements in the financial currency. Currency-sensitive ratios and the DCF-to-price comparison are marked cautiously or as `n/a`.

## DCF, Sensitivity, and Reverse DCF

The valuation uses a WACC built from three components:

- **Cost of equity**: CAPM — risk-free rate + beta × equity risk premium.
- **Cost of debt**: interest expense / total debt (or risk-free + 200 bps if unavailable), after-tax.
- **Weights**: market-value equity and book-value debt.

When no debt exists the discount rate falls back to cost of equity alone.

Because a DCF point estimate is assumption-driven, the report also shows:

- a **sensitivity heatmap** of fair value across WACC ± 2pp and terminal growth ± 1pp,
- a **tornado chart** ranking which input (FCF level, initial growth, discount rate, terminal growth) moves fair value most, and
- a **reverse DCF** that solves for the initial FCF growth implied by the current price — often the more useful question than "what is fair value?".

DCF assumptions can be overridden via CLI flags or the advanced prompt section:

```bash
python stock_analysis.py --ticker MSFT --risk-free-rate 0.04 --market-return 0.09 --terminal-growth 0.03
```

## Sharpe and Sortino

Both ratios subtract the risk-free rate:

```text
Sharpe  = (annualized return − risk-free rate) / annualized volatility
Sortino = (annualized return − risk-free rate) / annualized downside volatility
```

## Notes

- The script uses Yahoo Finance via `yfinance`. An internet connection is required.
- This is analytical software, not financial advice.
- Fundamental data availability varies by ticker, exchange, and instrument type.
- No paid API key is required.
