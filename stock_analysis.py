"""Full scale stock analysis report generator — thin entry point.

The implementation lives in the `stockanalysis` package:

    stockanalysis/config.py        constants + ReportConfig
    stockanalysis/data.py          Yahoo Finance fetching (prices, statements,
                                   benchmark, options IV, earnings, peers)
    stockanalysis/indicators.py    technical indicators
    stockanalysis/fundamentals.py  statement parsing, ratios, Piotroski
    stockanalysis/valuation.py     WACC, DCF, sensitivity, reverse DCF, tornado
    stockanalysis/risk.py          risk metrics, Monte Carlo
    stockanalysis/narrative.py     plain-English interpretation
    stockanalysis/peers.py         peer comparison analytics
    stockanalysis/report/          theme, charts, HTML components, builder
    stockanalysis/cli.py           argument parsing and orchestration

Interactive use (default):
    python stock_analysis.py

Command-line use (scripting / CI):
    python stock_analysis.py --ticker MSFT --period 5y
    python stock_analysis.py --watchlist AAPL MSFT NVDA --period 5y --cache
    python stock_analysis.py --ticker AAPL --peers MSFT GOOGL META
"""

from stockanalysis.cli import main

if __name__ == "__main__":
    main()
