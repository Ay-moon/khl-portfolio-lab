SET NOCOUNT ON;
GO

CREATE OR ALTER VIEW dbo.vw_FactTradesEnriched
AS
SELECT
    t.TradeKey,
    t.TradeDateKey,
    dd.FullDate AS TradeDate,
    t.PortfolioKey,
    p.PortfolioCode,
    p.PortfolioName,
    t.SecurityKey,
    s.Ticker,
    s.SecurityName,
    t.Side,
    t.Quantity,
    t.Price,
    t.FeeAmount,
    t.SlippageAmount,
    (t.Quantity * t.Price) AS GrossAmount,
    (t.Quantity * t.Price) + t.FeeAmount + t.SlippageAmount AS NetAmount,
    t.CurrencyCode,
    t.StrategyCode,
    t.OrderType,
    t.ExecutionTs
FROM dbo.FactTrades t
INNER JOIN dbo.DimDate dd ON dd.DateKey = t.TradeDateKey
INNER JOIN dbo.DimPortfolio p ON p.PortfolioKey = t.PortfolioKey
INNER JOIN dbo.DimSecurity s ON s.SecurityKey = t.SecurityKey;
GO

CREATE OR ALTER VIEW dbo.vw_PortfolioDashboardDaily
AS
SELECT
    pnl.DateKey,
    dd.FullDate,
    pnl.PortfolioKey,
    p.PortfolioCode,
    p.PortfolioName,
    pnl.DailyPnL,
    pnl.CumPnL,
    pnl.Nav,
    pnl.ReturnPct,
    pnl.ContributionPct,
    r.Volatility20d,
    r.MaxDrawdown,
    r.VaR95,
    r.Beta,
    r.SharpeRatio
FROM dbo.PortfolioPnLDaily pnl
INNER JOIN dbo.DimDate dd ON dd.DateKey = pnl.DateKey
INNER JOIN dbo.DimPortfolio p ON p.PortfolioKey = pnl.PortfolioKey
LEFT JOIN dbo.RiskMetricsDaily r
    ON r.DateKey = pnl.DateKey
   AND r.PortfolioKey = pnl.PortfolioKey;
GO

CREATE OR ALTER VIEW dbo.vw_PositionSnapshot
AS
SELECT
    pos.DateKey,
    dd.FullDate,
    pos.PortfolioKey,
    p.PortfolioCode,
    p.PortfolioName,
    pos.SecurityKey,
    s.Ticker,
    s.SecurityName,
    pos.Quantity,
    pos.AvgCost,
    pos.MarketValue,
    pos.UnrealizedPnL,
    pos.WeightPct
FROM dbo.PortfolioPositionsDaily pos
INNER JOIN dbo.DimDate dd ON dd.DateKey = pos.DateKey
INNER JOIN dbo.DimPortfolio p ON p.PortfolioKey = pos.PortfolioKey
INNER JOIN dbo.DimSecurity s ON s.SecurityKey = pos.SecurityKey;
GO

CREATE OR ALTER VIEW dbo.vw_AI_LatestRecommendations
AS
WITH ranked AS (
    SELECT
        ar.RecommendationId,
        ar.DateKey,
        ar.PortfolioKey,
        ar.SecurityKey,
        ar.Action,
        ar.ConfidenceScore,
        ar.Reasoning,
        ar.ConstraintsCheck,
        ar.Status,
        ar.CreatedAt,
        ROW_NUMBER() OVER (
            PARTITION BY ar.PortfolioKey, ar.SecurityKey
            ORDER BY ar.CreatedAt DESC
        ) AS rn
    FROM dbo.AI_Recommendations ar
)
SELECT
    r.RecommendationId,
    r.DateKey,
    dd.FullDate,
    r.PortfolioKey,
    p.PortfolioCode,
    r.SecurityKey,
    s.Ticker,
    r.Action,
    r.ConfidenceScore,
    r.Reasoning,
    r.ConstraintsCheck,
    r.Status,
    r.CreatedAt
FROM ranked r
LEFT JOIN dbo.DimDate dd ON dd.DateKey = r.DateKey
LEFT JOIN dbo.DimPortfolio p ON p.PortfolioKey = r.PortfolioKey
LEFT JOIN dbo.DimSecurity s ON s.SecurityKey = r.SecurityKey
WHERE r.rn = 1;
GO
