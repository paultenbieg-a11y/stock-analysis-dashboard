# Full Scale Stock Analysis

This project creates an interactive HTML stock report with fundamental analysis, valuation signals, technical chart analysis, historical returns, risk metrics, scenario modeling, and simulated forward paths.

## What You Get

Running the script creates a self-contained interactive HTML report in the `reports` folder. The report includes:

- Executive summary with fundamental, valuation, and chart interpretation.
- Company overview with business description, sector, industry, headquarters, employee count, exchange, website, and specialization tags when Yahoo Finance provides them.
- Candlestick chart with moving averages, Bollinger Bands, volume, RSI, and MACD.
- Annual income statement, balance sheet, and cash flow statement for the most recent annual release plus the previous two annual releases.
- Fundamental dashboard with margins, growth, leverage, liquidity, ROE, ROA, and cash flow metrics.
- Valuation dashboard with multiples and a simplified discounted cash flow estimate.
- Risk dashboard with cumulative returns, drawdowns, return distribution, volatility, VaR, CVaR, Sharpe proxy, and Sortino proxy.
- Forward scenario table and Monte Carlo price cone.

For a full explanation of every output and assumption, read [OUTPUTS_AND_ASSUMPTIONS.md](OUTPUTS_AND_ASSUMPTIONS.md).

## Setup

Open a terminal in this project folder, then run:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

You only need to do this setup once unless you delete the `.venv` folder.

## Run

You have two ways to choose the stock.

### Option 1: Edit the ticker inside the script

Open `stock_analysis.py` and change this line near the top to any ticker supported by Yahoo Finance:

```python
DEFAULT_TICKER = "SAP"
```

For example:

```python
DEFAULT_TICKER = "MSFT"
```

Useful ticker formats:

- `AAPL` for Apple on Nasdaq.
- `SAP` for the US-listed SAP ADR.
- `SAP.DE` for SAP's German/Xetra listing.
- `7203.T` for Toyota in Tokyo.
- `NESN.SW` for Nestle in Switzerland.

Then run:

```bash
source .venv/bin/activate
python stock_analysis.py
```

### Option 2: Pass the ticker from the terminal

This is usually faster if you want to analyze many stocks:

```bash
source .venv/bin/activate
python stock_analysis.py --ticker AAPL
```

You can also change the price history period:

```bash
python stock_analysis.py --ticker NVDA --period 10y
```

Common period values supported by Yahoo Finance include `1y`, `2y`, `5y`, `10y`, and `max`.

## Find the Report

The report is written to:

```text
reports/<TICKER>_stock_analysis.html
```

Example:

```text
reports/AAPL_stock_analysis.html
```

Open that HTML file in a browser to use the interactive charts.

Generated report files are intentionally ignored by Git. The `reports` folder stays in the project through `reports/.gitkeep`, but past analysis outputs stay local on your Mac and are not pushed to GitHub.

## Currency Handling

The report separates the market quote currency from the financial statement currency.

Example: an ADR can trade in USD while the company's annual statements are reported in EUR. In that case, the report still shows the annual statements, but currency-sensitive ratios and the DCF price comparison are handled cautiously or shown as `n/a` instead of forcing a misleading comparison.

## Investor Relations Link

The report tries to link the company name in the hero section to an investor-relations page.

It checks:

- known manual overrides in `IR_URL_OVERRIDES`
- investor-relations fields from Yahoo Finance, if available
- the company's corporate website from Yahoo Finance
- a fallback web search for the company investor-relations page

If Yahoo only gives a generic company website and you want a precise IR link, add an optional ticker-specific override near the top of `stock_analysis.py`:

```python
IR_URL_OVERRIDES = {
    "SAP": "https://www.sap.com/investors/en.html",
    "SAP.DE": "https://www.sap.com/investors/en.html",
}
```

This override is optional. The analysis itself is not hardcoded to those companies.

## Useful Commands

Analyze Apple:

```bash
python stock_analysis.py --ticker AAPL
```

Analyze Microsoft with 10 years of history:

```bash
python stock_analysis.py --ticker MSFT --period 10y
```

Use custom DCF assumptions:

```bash
python stock_analysis.py --ticker GOOGL --risk-free-rate 0.04 --market-return 0.085 --terminal-growth 0.025
```

## Reading Markdown Files in VS Code on Mac

To switch a Markdown file like this README into a cleaner preview view:

- Press `Cmd + Shift + V` to open the Markdown preview.
- Press `Cmd + K`, then `V` to open the preview side-by-side with the editable file.

The side-by-side view is usually best: edit on the left, readable preview on the right.

## Notes

- The script uses Yahoo Finance via `yfinance`, so an internet connection is required at runtime.
- This is analytical software, not financial advice. The report frames probabilities, valuation assumptions, and technical scenarios rather than making guaranteed predictions.
- Fundamental data availability varies by ticker, exchange, and instrument type.
- The project currently uses free data only. No paid API key is required.
