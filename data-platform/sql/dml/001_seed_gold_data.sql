SET NOCOUNT ON;

DECLARE @StartDate DATE = '2026-01-01';
DECLARE @EndDate DATE = '2026-01-31';

;WITH d AS (
    SELECT @StartDate AS dt
    UNION ALL
    SELECT DATEADD(DAY, 1, dt)
    FROM d
    WHERE dt < @EndDate
)
INSERT INTO dbo.DimDate (
    DateKey,
    FullDate,
    CalendarYear,
    CalendarMonth,
    CalendarDay,
    MonthName,
    QuarterNumber,
    WeekOfYear,
    IsMonthEnd
)
SELECT
    CONVERT(INT, CONVERT(CHAR(8), dt, 112)) AS DateKey,
    dt,
    DATEPART(YEAR, dt),
    DATEPART(MONTH, dt),
    DATEPART(DAY, dt),
    DATENAME(MONTH, dt),
    DATEPART(QUARTER, dt),
    DATEPART(ISO_WEEK, dt),
    CASE WHEN EOMONTH(dt) = dt THEN 1 ELSE 0 END
FROM d
WHERE NOT EXISTS (
    SELECT 1
    FROM dbo.DimDate x
    WHERE x.FullDate = d.dt
)
OPTION (MAXRECURSION 400);

INSERT INTO dbo.DimSecurity (Ticker, SecurityName, AssetClass, CurrencyCode)
SELECT v.Ticker, v.SecurityName, v.AssetClass, v.CurrencyCode
FROM (VALUES
    ('AAPL', 'Apple Inc.', 'Equity', 'USD'),
    ('MSFT', 'Microsoft Corp.', 'Equity', 'USD'),
    ('SPY', 'SPDR S&P 500 ETF', 'ETF', 'USD')
) AS v(Ticker, SecurityName, AssetClass, CurrencyCode)
WHERE NOT EXISTS (
    SELECT 1
    FROM dbo.DimSecurity s
    WHERE s.Ticker = v.Ticker
);

INSERT INTO dbo.DimPortfolio (PortfolioCode, PortfolioName, BaseCurrency, RiskProfile, InceptionDate)
SELECT 'MAIN', 'Main Tactical Portfolio', 'USD', 'Balanced', '2026-01-01'
WHERE NOT EXISTS (
    SELECT 1
    FROM dbo.DimPortfolio p
    WHERE p.PortfolioCode = 'MAIN'
);

DECLARE @PortfolioMain INT = (SELECT PortfolioKey FROM dbo.DimPortfolio WHERE PortfolioCode = 'MAIN');
DECLARE @SecAAPL INT = (SELECT SecurityKey FROM dbo.DimSecurity WHERE Ticker = 'AAPL');
DECLARE @SecMSFT INT = (SELECT SecurityKey FROM dbo.DimSecurity WHERE Ticker = 'MSFT');
DECLARE @SecSPY INT = (SELECT SecurityKey FROM dbo.DimSecurity WHERE Ticker = 'SPY');

INSERT INTO dbo.FactPrice (DateKey, SecurityKey, ClosePrice, Volume, SourceSystem)
SELECT v.DateKey, v.SecurityKey, v.ClosePrice, v.Volume, 'demo_seed'
FROM (VALUES
    (20260102, @SecAAPL, 186.100000, 10050000),
    (20260102, @SecMSFT, 414.250000, 8520000),
    (20260102, @SecSPY, 502.120000, 22500000),
    (20260103, @SecAAPL, 187.550000, 9800000),
    (20260103, @SecMSFT, 416.400000, 7900000),
    (20260103, @SecSPY, 503.880000, 21400000),
    (20260104, @SecAAPL, 188.020000, 9400000),
    (20260104, @SecMSFT, 417.850000, 7600000),
    (20260104, @SecSPY, 505.240000, 21000000)
) AS v(DateKey, SecurityKey, ClosePrice, Volume)
WHERE NOT EXISTS (
    SELECT 1
    FROM dbo.FactPrice fp
    WHERE fp.DateKey = v.DateKey
      AND fp.SecurityKey = v.SecurityKey
);

INSERT INTO dbo.FactTrades (
    TradeDateKey,
    SettleDateKey,
    PortfolioKey,
    SecurityKey,
    Side,
    Quantity,
    Price,
    FeeAmount,
    SlippageAmount,
    CurrencyCode,
    StrategyCode,
    OrderType
)
SELECT
    v.TradeDateKey,
    v.SettleDateKey,
    @PortfolioMain,
    v.SecurityKey,
    v.Side,
    v.Quantity,
    v.Price,
    v.FeeAmount,
    v.SlippageAmount,
    'USD',
    v.StrategyCode,
    v.OrderType
FROM (VALUES
    (20260102, 20260104, @SecAAPL, 'BUY', 120.000000, 186.100000, 2.500000, 1.800000, 'MOMENTUM', 'MARKET'),
    (20260102, 20260104, @SecMSFT, 'BUY', 60.000000, 414.250000, 2.000000, 1.500000, 'CORE', 'MARKET'),
    (20260103, 20260105, @SecSPY, 'BUY', 40.000000, 503.880000, 1.800000, 1.200000, 'HEDGE', 'MARKET')
) AS v(TradeDateKey, SettleDateKey, SecurityKey, Side, Quantity, Price, FeeAmount, SlippageAmount, StrategyCode, OrderType)
WHERE NOT EXISTS (
    SELECT 1
    FROM dbo.FactTrades t
    WHERE t.TradeDateKey = v.TradeDateKey
      AND t.PortfolioKey = @PortfolioMain
      AND t.SecurityKey = v.SecurityKey
      AND t.Side = v.Side
      AND t.Quantity = v.Quantity
      AND t.Price = v.Price
);

INSERT INTO dbo.PortfolioPositionsDaily (
    DateKey,
    PortfolioKey,
    SecurityKey,
    Quantity,
    AvgCost,
    MarketValue,
    UnrealizedPnL,
    WeightPct
)
SELECT v.DateKey, @PortfolioMain, v.SecurityKey, v.Quantity, v.AvgCost, v.MarketValue, v.UnrealizedPnL, v.WeightPct
FROM (VALUES
    (20260104, @SecAAPL, 120.000000, 186.100000, 22562.400000, 230.400000, 0.331200),
    (20260104, @SecMSFT, 60.000000, 414.250000, 25071.000000, 216.000000, 0.368100),
    (20260104, @SecSPY, 40.000000, 503.880000, 20209.600000, 56.000000, 0.296700)
) AS v(DateKey, SecurityKey, Quantity, AvgCost, MarketValue, UnrealizedPnL, WeightPct)
WHERE NOT EXISTS (
    SELECT 1
    FROM dbo.PortfolioPositionsDaily p
    WHERE p.DateKey = v.DateKey
      AND p.PortfolioKey = @PortfolioMain
      AND p.SecurityKey = v.SecurityKey
);

INSERT INTO dbo.PortfolioPnLDaily (
    DateKey,
    PortfolioKey,
    DailyPnL,
    CumPnL,
    Nav,
    ReturnPct,
    ContributionPct
)
SELECT v.DateKey, @PortfolioMain, v.DailyPnL, v.CumPnL, v.Nav, v.ReturnPct, v.ContributionPct
FROM (VALUES
    (20260102, 0.000000, 0.000000, 100000.000000, 0.000000, 0.000000),
    (20260103, 345.600000, 345.600000, 100345.600000, 0.003456, 0.003456),
    (20260104, 156.800000, 502.400000, 100502.400000, 0.001563, 0.001563)
) AS v(DateKey, DailyPnL, CumPnL, Nav, ReturnPct, ContributionPct)
WHERE NOT EXISTS (
    SELECT 1
    FROM dbo.PortfolioPnLDaily x
    WHERE x.DateKey = v.DateKey
      AND x.PortfolioKey = @PortfolioMain
);

INSERT INTO dbo.RiskMetricsDaily (
    DateKey,
    PortfolioKey,
    Volatility20d,
    MaxDrawdown,
    VaR95,
    Beta,
    SharpeRatio
)
SELECT v.DateKey, @PortfolioMain, v.Volatility20d, v.MaxDrawdown, v.VaR95, v.Beta, v.SharpeRatio
FROM (VALUES
    (20260103, 0.124000, -0.010200, -980.000000, 0.940000, 1.280000),
    (20260104, 0.121500, -0.009600, -950.000000, 0.930000, 1.300000)
) AS v(DateKey, Volatility20d, MaxDrawdown, VaR95, Beta, SharpeRatio)
WHERE NOT EXISTS (
    SELECT 1
    FROM dbo.RiskMetricsDaily r
    WHERE r.DateKey = v.DateKey
      AND r.PortfolioKey = @PortfolioMain
);

INSERT INTO dbo.AI_DailyBriefing (
    DateKey,
    PortfolioKey,
    ModelName,
    PromptVersion,
    OutputJson,
    Summary,
    Assumptions
)
SELECT
    20260104,
    @PortfolioMain,
    'mock-gpt',
    'v1',
    '{"market_regime":"neutral","focus":["AAPL","MSFT"]}',
    'Portfolio remains balanced with mild positive momentum.',
    'Assumes normal liquidity and no macro shock.'
WHERE NOT EXISTS (
    SELECT 1
    FROM dbo.AI_DailyBriefing b
    WHERE b.DateKey = 20260104
      AND b.PortfolioKey = @PortfolioMain
      AND b.PromptVersion = 'v1'
);

INSERT INTO dbo.AI_Recommendations (
    DateKey,
    PortfolioKey,
    SecurityKey,
    Action,
    ConfidenceScore,
    Reasoning,
    ConstraintsCheck,
    OutputJson,
    Status
)
SELECT
    20260104,
    @PortfolioMain,
    @SecAAPL,
    'BUY',
    0.7200,
    'Trend and risk-adjusted return are favorable over 20d horizon.',
    'Exposure limit respected; no concentration breach.',
    '{"target_weight":0.36,"horizon_days":20}',
    'proposed'
WHERE NOT EXISTS (
    SELECT 1
    FROM dbo.AI_Recommendations r
    WHERE r.DateKey = 20260104
      AND r.PortfolioKey = @PortfolioMain
      AND r.SecurityKey = @SecAAPL
      AND r.Action = 'BUY'
);

INSERT INTO dbo.AI_WhatIf (
    DateKey,
    PortfolioKey,
    ScenarioName,
    InputJson,
    ResultJson,
    Narrative
)
SELECT
    20260104,
    @PortfolioMain,
    'Reduce SPY by 5 percent',
    '{"rebalance":{"SPY":-0.05,"AAPL":0.03,"MSFT":0.02}}',
    '{"expected_volatility_delta":-0.004,"expected_return_delta":0.0012}',
    'Risk decreases slightly while maintaining expected return.'
WHERE NOT EXISTS (
    SELECT 1
    FROM dbo.AI_WhatIf w
    WHERE w.DateKey = 20260104
      AND w.PortfolioKey = @PortfolioMain
      AND w.ScenarioName = 'Reduce SPY by 5 percent'
);

INSERT INTO dbo.AI_AuditLog (EventType, Component, Status, Detail)
SELECT
    'seed',
    'scripts/001_seed_gold_data.sql',
    'success',
    'Initial demo seed inserted for Gold + AI tables.'
WHERE NOT EXISTS (
    SELECT 1
    FROM dbo.AI_AuditLog a
    WHERE a.EventType = 'seed'
      AND a.Component = 'scripts/001_seed_gold_data.sql'
);

