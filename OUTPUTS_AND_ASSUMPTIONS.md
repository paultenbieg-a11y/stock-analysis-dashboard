# Outputs and Assumptions

This file explains what the stock analysis report produces, how to read each section, and which assumptions sit behind the calculations.

The report is designed as a research dashboard, not a trading signal machine. It combines several lenses from financial literature: fundamental quality, valuation, trend following, mean reversion, volatility, drawdown behavior, and probabilistic scenario analysis.

## Data Source

The script currently uses `yfinance`, which pulls data from Yahoo Finance.

Used data includes:

- Daily open, high, low, close, adjusted close, and volume.
- Income statement data when available.
- Balance sheet data when available.
- Cash flow statement data when available.
- Company metadata such as market capitalization, beta, share count, currency, and valuation ratios when available.

Important limitations:

- Yahoo Finance data can be delayed, incomplete, or occasionally unavailable.
- Fundamental fields are not equally complete for all companies.
- Some international stocks, ETFs, funds, and special securities may have missing fields.
- The script uses available data and marks unavailable calculations as `n/a`.

## Report File

Each run creates an HTML file:

```text
reports/<TICKER>_stock_analysis.html
```

The file is self-contained except for Plotly and the Inter font, which load from CDNs for the interactive charts and typography. Open it in a browser.

Generated report files are local outputs. The project keeps the `reports` folder with `reports/.gitkeep`, but ignores generated `.html` reports in Git so old personal analyses are not published when the repository is pushed.

## Data Notes

The HTML report can include a `Data Notes` section near the top.

This section appears when the script detects important caveats, such as:

- Yahoo Finance did not return a statement or company profile field.
- Volume data was unavailable.
- The quote currency differs from the financial statement currency.

These notes do not always mean the report is unusable. They show where a calculation needs extra caution or outside verification.

## Ticker Flexibility

The project is designed to analyze whichever ticker you enter manually in `DEFAULT_TICKER` or pass with `--ticker`.

Examples:

- `AAPL` for Apple.
- `SAP` for the US-listed SAP ADR.
- `SAP.DE` for SAP's German/Xetra listing.
- `7203.T` for Toyota in Tokyo.
- `NESN.SW` for Nestle in Switzerland.

The report adapts to the company data returned by Yahoo Finance. If a field is unavailable for a ticker, the report shows `n/a` or an explanatory note instead of forcing a company-specific assumption.

## Currency Handling

The report separates:

- Quote currency: the currency in which the stock trades.
- Financial statement currency: the currency used in annual income statement, balance sheet, and cash flow statement data.

For many tickers these are the same. For ADRs, foreign listings, and cross-listed shares, they can differ.

When the currencies differ, the report avoids direct price comparisons that would be misleading without exchange-rate and share-class adjustments. In that case:

- Annual financial statements are still shown in the financial statement currency.
- Market price and technical levels are shown in the quote currency.
- Currency-sensitive valuation ratios may show `n/a`.
- DCF fair value is shown in the financial statement currency and marked as not price-comparable.

## Executive View

The executive view summarizes the whole analysis in plain English.

It combines:

- Fundamental quality.
- Balance sheet strength.
- Revenue and earnings direction.
- Simplified DCF valuation.
- Piotroski F-score.
- Trend and momentum indicators.
- Volatility range from ATR.

How to read it:

- A strong report usually has both improving fundamentals and constructive price action.
- A weak report often has deteriorating fundamentals and a broken technical trend.
- Mixed reports are common. For example, a great business can still be expensive, or a cheap stock can remain technically weak.

## Company Overview

The company overview section introduces the analyzed business before the financial and chart analysis.

It uses Yahoo Finance profile fields when available:

- Business description.
- Sector.
- Industry.
- Headquarters.
- Employee count.
- Exchange.
- Security type.
- Company website.
- Investor-relations or corporate link.

The specialization tags are generated from the sector, industry, and keywords found in the business description. They are intended as a quick qualitative orientation, not a substitute for reading the company's annual report or official investor-relations materials.

## Key Metrics Cards

The cards near the top of the report show the most important snapshot metrics.

### Last Close

The latest closing price returned by the data source.

### Market Cap

Equity market value:

```text
share price * shares outstanding
```

Used as a scale indicator and for ratios such as free cash flow yield.

### Total Return

The total return over the selected history period:

```text
last adjusted close / first adjusted close - 1
```

Dividend-adjusted closes are used when the data source provides them, so this approximates total shareholder return. The card detail also shows the relative return against the benchmark when available.

### Next Earnings

Days until the next scheduled earnings date from the Yahoo Finance calendar. Treat the date as provisional until the company confirms it.

### Annual Volatility

Annualized realized volatility from daily returns:

```text
daily return standard deviation * sqrt(252)
```

This assumes roughly 252 trading days per year.

### Max Drawdown

Largest peak-to-trough decline during the selected period.

This helps answer: how painful was the worst historical decline in this sample?

### DCF Fair Value

A simplified discounted cash flow estimate per share.

This is an assumption-sensitive valuation anchor, not a true price target.

### FCF Yield

Free cash flow divided by market capitalization:

```text
free cash flow / market cap
```

Higher free cash flow yield can suggest cheaper valuation, but only if the free cash flow is durable.

### Piotroski F-Score

A 0 to 9 accounting quality score based on profitability, leverage, liquidity, dilution, and operating efficiency.

Higher is generally better. The score is most useful for value and quality screening, not short-term trading.

## Technical Structure

The technical chart section visualizes price behavior and market structure.

### Candlestick Chart

Each candle shows open, high, low, and close for one trading interval.

Candles help reveal:

- Intraday or intra-period range.
- Rejection from highs or lows.
- Momentum continuation.
- Volatility expansion.

### Moving Averages

The report uses:

- `SMA_20`: short-term trend.
- `SMA_50`: intermediate trend.
- `SMA_200`: long-term trend.

Common interpretation:

- Price above the 200-day average often indicates a constructive long-term trend.
- Price below the 200-day average often indicates a weaker long-term trend.
- A rising 50-day average above a rising 200-day average is commonly considered bullish.
- A falling 50-day average below a falling 200-day average is commonly considered bearish.

### Bollinger Bands

Bollinger Bands are based on a 20-day moving average plus and minus two standard deviations.

They help show whether price is stretched relative to recent volatility.

Interpretation:

- Price near the upper band can mean strong momentum or short-term overextension.
- Price near the lower band can mean weakness or short-term capitulation.
- Narrow bands can signal volatility compression before a larger move.

### RSI

RSI is a momentum oscillator.

The report uses 14-period RSI.

Common thresholds:

- Above 70: overbought or strong momentum.
- Below 30: oversold or weak momentum.
- Between 30 and 70: neutral range.

RSI should not be used alone. Strong stocks can stay overbought, and weak stocks can stay oversold.

### MACD

MACD compares two exponential moving averages:

- 12-period EMA.
- 26-period EMA.
- Signal line: 9-period EMA of MACD.

Interpretation:

- MACD above the signal line suggests improving momentum.
- MACD below the signal line suggests fading momentum.
- MACD histogram shows the gap between MACD and signal.

### ADX

ADX estimates trend strength, not direction.

Common interpretation:

- Above 25: stronger trend regime.
- Below 25: weaker, choppier, or more range-bound regime.

### ATR

ATR measures average true range and is used as a volatility range estimate.

The report uses ATR to produce an approximate near-term price band around the latest close.

ATR is not a prediction. It is a recent volatility yardstick.

### OBV and Volume

On-balance volume attempts to connect volume with price direction.

Rising OBV can suggest accumulation. Falling OBV can suggest distribution. It is most useful when confirming or diverging from price trend.

## Annual Financial Statements

The report includes annual income statement, balance sheet, and cash flow statement tables directly after the technical structure section.

These annual statement tables are independent of the selected price-history period. For example, even if you run:

```bash
python stock_analysis.py --ticker SAP --period 1y
```

the annual statement section still uses the most recent annual release plus the previous two annual releases returned by Yahoo Finance.

The statement tables follow a finance-style presentation: the currency is stated once above the tables, numbers are shown without repeated currency prefixes, negative figures use parentheses, section headers separate major areas, and subtotal/total rows are emphasized with stronger rules and bold text.

### Income Statement

The report focuses on major annual income statement lines such as:

- Total revenue.
- Cost of revenue.
- Gross profit.
- Research and development.
- Selling, general, and administrative expense.
- Operating income / EBIT.
- EBITDA.
- Interest income and expense.
- Pretax income.
- Tax provision.
- Net income.
- Diluted EPS.
- Diluted average shares.

For IFRS reporters, Yahoo Finance maps the company's financial statements into standardized line labels where possible. That means the report should work for IFRS companies such as SAP as well as US GAAP companies such as Apple, but some line items may still appear as `n/a` depending on the company and Yahoo's coverage.

### Balance Sheet

The report focuses on major annual balance sheet lines such as:

- Cash and short-term investments.
- Receivables.
- Inventory.
- Current assets.
- Goodwill and intangibles.
- Property, plant, and equipment.
- Total assets.
- Current liabilities.
- Total debt.
- Net debt.
- Total liabilities.
- Shareholders equity.
- Minority interest.
- Working capital.
- Invested capital.
- Shares issued.

Balance sheet values are point-in-time values at fiscal year-end.

The balance sheet table is visually split into assets, liabilities, and equity/capitalization to make it easier to read like a normal finance statement.

### Cash Flow Statement

The report focuses on major annual cash flow lines such as:

- Net income from continuing operations.
- Depreciation and amortization.
- Stock-based compensation.
- Change in working capital.
- Operating cash flow.
- Capital expenditure.
- Free cash flow.
- Investing cash flow.
- Business acquisitions or disposals.
- Investment purchases or sales.
- Financing cash flow.
- Dividends paid.
- Share repurchases.
- Debt issued.
- Debt repaid.
- Change in cash.
- Ending cash position.

Cash flow statement values are especially important because they show how accounting profit turns into actual cash.

### Annual Snapshot Charts

The annual statement section includes separate full-width charts for:

- Income statement: revenue, gross profit, operating income, and net income.
- Balance sheet: assets, equity, debt, and cash/short-term investments.
- Cash flow statement: operating cash flow, capital expenditure, free cash flow, and dividends paid.

Each chart sits above the matching annual table so the section is easier to scan vertically.

## Fundamental and Valuation Dashboard

This section focuses on business quality and valuation.

### Revenue

Top-line sales from the income statement.

Rising revenue can indicate demand growth, pricing power, acquisitions, or cyclical recovery.

### Net Income

Accounting profit after expenses, interest, taxes, and other items.

Net income can be distorted by one-time gains, impairments, tax effects, or accounting choices.

### Free Cash Flow

Cash generated after capital expenditures.

The script uses Yahoo Finance free cash flow if available. If unavailable, it estimates:

```text
operating cash flow + capital expenditure
```

Capital expenditure is often reported as a negative number, so adding it usually subtracts investment spending.

### Margins

The report includes:

- Gross margin.
- Operating margin.
- Net margin.

Margins help assess pricing power, cost control, and business model quality.

### ROE

Return on equity:

```text
net income / shareholders equity
```

High ROE can indicate strong profitability, but it can also be inflated by leverage or buybacks.

### ROA

Return on assets:

```text
net income / total assets
```

ROA is useful for comparing asset intensity.

### Debt to Equity

Balance sheet leverage:

```text
total debt / shareholders equity
```

Higher leverage can increase risk, especially in cyclical businesses or high-rate environments.

### Current Ratio

Short-term liquidity:

```text
current assets / current liabilities
```

A ratio above 1.0 generally means current assets exceed current liabilities. The ideal level depends heavily on the industry.

## Valuation Outputs

### P/E Ratio

Price-to-earnings compares equity value to earnings.

The report may show:

- Trailing P/E.
- Forward P/E.

High P/E can imply high expected growth, high quality, or overvaluation. Low P/E can imply cheapness, cyclicality, distress, or low expected growth.

### PEG Ratio

PEG relates P/E to expected growth.

Lower PEG can suggest better growth-adjusted valuation, but the metric depends heavily on the growth estimate.

### Price to Sales

Useful when earnings are temporarily depressed or negative.

It should be interpreted with margins. A high-margin business deserves a higher price-to-sales ratio than a low-margin business.

### Price to Book

Useful for banks, insurers, and asset-heavy companies.

Less useful for asset-light software, brands, and companies with large intangible value.

### EV to Revenue

Enterprise value compared with revenue.

Enterprise value includes debt and subtracts cash, so it can be more capital-structure aware than market cap.

### EV to EBITDA

Enterprise value compared with EBITDA.

Commonly used in corporate finance and acquisition analysis. It ignores capital expenditure, working capital, taxes, and some accounting details, so it should not be used alone.

## Simplified DCF Assumptions

The DCF is intentionally simple and transparent.

It uses:

- Latest available free cash flow.
- Shares outstanding.
- A CAPM-style cost of equity proxy.
- A five-year explicit forecast period.
- A terminal value.

### Risk-Free Rate

Default:

```text
4.5%
```

Command-line option:

```bash
--risk-free-rate 0.045
```

This represents the return investors can theoretically earn from low-risk government bonds.

### Market Return

Default:

```text
8.5%
```

Command-line option:

```bash
--market-return 0.085
```

This is the assumed long-run expected market return.

### Beta

Beta comes from Yahoo Finance when available.

In the DCF proxy, beta adjusts the required return:

```text
cost of equity = risk-free rate + beta * (market return - risk-free rate)
```

### Discount Rate

The script clips the discount rate into a practical range:

```text
7% to 14%
```

This avoids extreme outputs from noisy beta data, but it also means the model is simplified.

### Growth Assumption

Base growth is estimated from available revenue growth, earnings growth, and a normalized anchor.

The growth rate is clipped between:

```text
-5% and 15%
```

This keeps the DCF from becoming unrealistic when recent growth is unusually high or unusually low.

### Terminal Growth

Default:

```text
2.5%
```

Command-line option:

```bash
--terminal-growth 0.025
```

Terminal growth represents long-run cash flow growth after the explicit forecast period. It should normally stay below the discount rate and close to long-run nominal economic growth.

### DCF Fair Value

The script discounts forecast free cash flows and terminal value, then divides by shares outstanding.

Interpretation:

- Fair value above current price may suggest undervaluation under the assumptions.
- Fair value below current price may suggest overvaluation under the assumptions.
- Small differences should not be overinterpreted because DCF is highly sensitive.

Currency limitation:

- Direct DCF-to-price comparison is only shown when quote currency and financial statement currency match.
- If they differ, the DCF value is still shown in the financial statement currency, but it is not treated as a price target.
- This avoids misleading ADR or cross-listing comparisons where exchange rates, depositary ratios, or share-class details may be needed.

## DCF Sensitivity Heatmap

A single fair-value number hides how assumption-driven a DCF is, so the report shows the whole neighborhood: fair value recomputed across WACC ± 2 percentage points (rows) and terminal growth ± 1 percentage point (columns).

How to read it:

- When the DCF is price-comparable, cells above the current price are green and cells below are red.
- A grid that is mostly one colour is a robust signal; a grid that flips colour across plausible assumptions means the valuation verdict depends on inputs you cannot know precisely.
- Cells where the WACC-to-terminal-growth spread would fall below 1.5 percentage points are left blank because the Gordon terminal value becomes unstable there.

## Fair-Value Tornado

The tornado chart varies one DCF input at a time and shows the resulting fair-value range per driver:

- Free cash flow ± 10%.
- Initial growth ± 2 percentage points.
- Discount rate ± 1 percentage point.
- Terminal growth ± 0.5 percentage points.

Drivers are sorted by impact. Typically the discount rate dominates, which is a reminder that the DCF is as much a statement about required return as about the business.

## Reverse DCF

Instead of asking "what is the stock worth?", the reverse DCF asks "what growth does the current price already assume?".

Holding the WACC and terminal growth fixed, it solves for the initial free-cash-flow growth rate (with the same fade schedule as the forward DCF) that reproduces the current market price. The executive view and the valuation section state this implied growth next to the model's own base assumption.

Judging whether the implied growth is plausible for this specific business is usually a more robust exercise than trusting a single fair-value estimate.

## Earnings vs Expectations

The earnings section shows, for up to the last eight reported quarters:

- Consensus EPS estimate and reported EPS as grouped bars (green when reported beat the estimate, red when it missed).
- A table with the surprise percentage, computed as `(reported - estimate) / |estimate|`.

Reported earnings dates inside the selected history window are also marked as dotted vertical lines on the price chart, so volatility around report dates is visible in context. Data availability depends on Yahoo's coverage for the ticker.

## Peer Comparison

The peer section compares the subject company against a peer group on trailing and forward P/E, EV/EBITDA, price/sales, margins, revenue growth, ROE, and free-cash-flow yield.

- Peer metrics come from Yahoo profile fields (one light request per peer), so they can differ slightly from statement-derived figures.
- The subject row is highlighted; peers are sorted by market capitalization.
- A positioning sentence states the subject's percentile inside the group for key metrics.
- The bubble chart plots revenue growth against EV/EBITDA with market cap as bubble size — the classic "what am I paying for growth?" view.

The peer set comes from `PEER_MAP` in `stockanalysis/config.py` or from `--peers` on the command line. Percentiles need at least four names (subject plus three peers) to be shown.

## Risk Outputs

### Annualized Return

Historical daily average return compounded to a yearly estimate.

This is backward-looking and can be heavily affected by the selected period.

### Annualized Volatility

Standard deviation of daily returns annualized by `sqrt(252)`.

Higher volatility means a wider range of possible outcomes.

### Sharpe Ratio

```text
(annualized return - risk-free rate) / annualized volatility
```

The risk-free rate is the configured assumption (default 4.5%).

### Sortino Ratio

Similar to Sharpe, but penalizes downside volatility instead of total volatility:

```text
(annualized return - risk-free rate) / annualized downside volatility
```

This can be more useful when upside volatility is not considered harmful.

### Value at Risk

Daily 95% VaR estimates a bad daily return threshold from historical returns.

Example interpretation:

```text
Daily 95% VaR of -3% means 5% of historical days were worse than about -3%.
```

### Conditional Value at Risk

CVaR estimates the average loss on days worse than the VaR threshold.

It focuses more on tail risk.

### Skew and Kurtosis

Skew shows whether returns have been asymmetric.

Kurtosis shows whether the return distribution has fat tails compared with a normal distribution.

Stocks often have fat tails, so normal-distribution assumptions are imperfect.

## Forward Scenarios

The scenario table gives bull, base, and bear cases.

It combines:

- Current price.
- DCF fair value if available and price-comparable.
- 200-day moving average.
- ATR-based volatility bands.
- Realized volatility.
- Fundamental interpretation.

These are not forecasts. They are structured reference cases to help think about upside, base-case, and downside paths.

## Monte Carlo Price Cone

The Monte Carlo chart simulates one-year price paths using historical daily log returns.

Assumptions:

- Historical drift continues.
- Historical volatility continues.
- Returns are randomly sampled from a normal-style process.
- No explicit jump risk, earnings surprise, recession, dilution, fraud, regulation, or takeover event is modeled.

The chart shows:

- Sample simulated paths.
- 5th percentile.
- 25th percentile.
- Median.
- 75th percentile.
- 95th percentile.

Use this as a volatility map, not a prediction.

## Investor Relations Link

The company name in the report hero links to the company's investor-relations or corporate website when possible.

### Investor Relations Link Logic

The script tries to find an investor-relations link in this order:

- Manual override from `IR_URL_OVERRIDES`.
- Investor-relations fields from Yahoo Finance, if available.
- Company website from Yahoo Finance.
- Search link for the company investor-relations page.

The override system exists because some companies have clean IR pages that Yahoo does not expose directly. It is optional and does not make the analysis company-specific.

## How to Interpret the Whole Report

A stronger setup often has:

- Positive revenue and earnings direction.
- Strong or improving free cash flow.
- Healthy margins.
- Reasonable leverage.
- Fair or attractive valuation.
- Price above long-term trend.
- Momentum confirmed by MACD, RSI, and volume.
- Manageable drawdowns and volatility.

A weaker setup often has:

- Declining revenue or earnings.
- Weak cash conversion.
- High leverage.
- Expensive valuation relative to quality.
- Price below the 200-day average.
- Poor momentum.
- Deep drawdowns or unstable return distribution.

Mixed setups require judgment. The report is meant to make those tradeoffs visible.

## Free Improvements That Would Help Later

The project currently works without paid APIs. Benchmark comparison, peer comparison, watchlist mode, DCF sensitivity, and reverse DCF are already built in. If you want to improve it further while staying free, the best additions would be:

- A local metrics history (SQLite) so each run can show what changed since the last look, enable alerts, and support backtesting.
- Optional free Financial Modeling Prep API key support as a fallback for richer fundamentals.
- CSV/JSON export of the computed metrics.
- PDF export of the final report.
- Total-return and dividend-sustainability analysis (payout vs free cash flow).

## Disclaimer

This project is for research and education only. It is not financial advice, investment advice, or a recommendation to buy or sell any security. Always verify important data against primary filings and professional data sources before making financial decisions.
