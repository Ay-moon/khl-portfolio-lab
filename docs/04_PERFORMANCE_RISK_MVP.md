# Step 4 - Performance & Risk

## Implemented MVP

Script:
- `analytics/performance_risk_mvp.py`

Outputs written to:
- `dbo.PortfolioPnLDaily`
- `dbo.RiskMetricsDaily`

Source data used:
- `dbo.PortfolioPositionsDaily`
- `dbo.FactTrades`
- `dbo.FactPrice` (real market data expected)

## Functional logic

Performance:
- Rebuild daily NAV from:
  - cash ledger (trade cash flows from `FactTrades`)
  - market value (positions x close price from `FactPrice`)
- Compute:
  - `DailyPnL`
  - `CumPnL`
  - `Nav`
  - `ReturnPct`
  - `ContributionPct`

Risk:
- Compute:
  - `Volatility20d` (rolling 20-day annualized volatility)
  - `MaxDrawdown` (running peak-to-trough drawdown)
  - `VaR95` (historical 5th percentile on returns, converted to value)
  - `SharpeRatio` (rolling, risk-free = 0)

Guardrail:
- If a position exists without matching close price in `FactPrice`, the job fails with explicit error.

## Re-run behavior

Before insert, the script purges existing rows in the target date range for the selected portfolio, then re-inserts computed rows.

## Run command

```bash
python analytics/performance_risk_mvp.py --portfolio-code MAIN --initial-nav 100000
```

Optional filters:
- `--start-date YYYY-MM-DD`
- `--end-date YYYY-MM-DD`

## DoD (current)
- Metrics calculated
- Re-runnable load implemented
- Unit tests added for core formulas

