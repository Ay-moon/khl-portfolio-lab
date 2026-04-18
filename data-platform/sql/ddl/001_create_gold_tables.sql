SET NOCOUNT ON;

IF SCHEMA_ID('dbo') IS NULL
BEGIN
    EXEC('CREATE SCHEMA [dbo]');
END;
GO

IF OBJECT_ID('dbo.DimDate', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.DimDate (
        DateKey INT NOT NULL PRIMARY KEY,
        FullDate DATE NOT NULL,
        CalendarYear SMALLINT NOT NULL,
        CalendarMonth TINYINT NOT NULL,
        CalendarDay TINYINT NOT NULL,
        MonthName NVARCHAR(20) NOT NULL,
        QuarterNumber TINYINT NOT NULL,
        WeekOfYear TINYINT NOT NULL,
        IsMonthEnd BIT NOT NULL
    );
END;
GO

IF NOT EXISTS (
    SELECT 1
    FROM sys.indexes
    WHERE name = 'UX_DimDate_FullDate'
      AND object_id = OBJECT_ID('dbo.DimDate')
)
BEGIN
    CREATE UNIQUE INDEX UX_DimDate_FullDate ON dbo.DimDate(FullDate);
END;
GO

IF OBJECT_ID('dbo.DimSecurity', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.DimSecurity (
        SecurityKey INT IDENTITY(1,1) NOT NULL PRIMARY KEY,
        Ticker NVARCHAR(20) NOT NULL,
        SecurityName NVARCHAR(200) NOT NULL,
        AssetClass NVARCHAR(50) NOT NULL,
        CurrencyCode CHAR(3) NOT NULL,
        IsActive BIT NOT NULL CONSTRAINT DF_DimSecurity_IsActive DEFAULT (1),
        CreatedAt DATETIME2(3) NOT NULL CONSTRAINT DF_DimSecurity_CreatedAt DEFAULT (SYSUTCDATETIME())
    );
END;
GO

IF NOT EXISTS (
    SELECT 1
    FROM sys.indexes
    WHERE name = 'UX_DimSecurity_Ticker'
      AND object_id = OBJECT_ID('dbo.DimSecurity')
)
BEGIN
    CREATE UNIQUE INDEX UX_DimSecurity_Ticker ON dbo.DimSecurity(Ticker);
END;
GO

IF OBJECT_ID('dbo.DimPortfolio', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.DimPortfolio (
        PortfolioKey INT IDENTITY(1,1) NOT NULL PRIMARY KEY,
        PortfolioCode NVARCHAR(50) NOT NULL,
        PortfolioName NVARCHAR(200) NOT NULL,
        BaseCurrency CHAR(3) NOT NULL,
        RiskProfile NVARCHAR(50) NOT NULL,
        InceptionDate DATE NULL,
        IsActive BIT NOT NULL CONSTRAINT DF_DimPortfolio_IsActive DEFAULT (1),
        CreatedAt DATETIME2(3) NOT NULL CONSTRAINT DF_DimPortfolio_CreatedAt DEFAULT (SYSUTCDATETIME())
    );
END;
GO

IF NOT EXISTS (
    SELECT 1
    FROM sys.indexes
    WHERE name = 'UX_DimPortfolio_Code'
      AND object_id = OBJECT_ID('dbo.DimPortfolio')
)
BEGIN
    CREATE UNIQUE INDEX UX_DimPortfolio_Code ON dbo.DimPortfolio(PortfolioCode);
END;
GO

IF OBJECT_ID('dbo.FactPrice', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.FactPrice (
        FactPriceId BIGINT IDENTITY(1,1) NOT NULL PRIMARY KEY,
        DateKey INT NOT NULL,
        SecurityKey INT NOT NULL,
        ClosePrice DECIMAL(19,6) NOT NULL,
        Volume BIGINT NULL,
        SourceSystem NVARCHAR(50) NULL,
        LoadDts DATETIME2(3) NOT NULL CONSTRAINT DF_FactPrice_LoadDts DEFAULT (SYSUTCDATETIME()),
        CONSTRAINT FK_FactPrice_DimDate FOREIGN KEY (DateKey) REFERENCES dbo.DimDate(DateKey),
        CONSTRAINT FK_FactPrice_DimSecurity FOREIGN KEY (SecurityKey) REFERENCES dbo.DimSecurity(SecurityKey)
    );
END;
GO

IF NOT EXISTS (
    SELECT 1
    FROM sys.indexes
    WHERE name = 'UX_FactPrice_Date_Security'
      AND object_id = OBJECT_ID('dbo.FactPrice')
)
BEGIN
    CREATE UNIQUE INDEX UX_FactPrice_Date_Security ON dbo.FactPrice(DateKey, SecurityKey);
END;
GO

IF OBJECT_ID('dbo.FactTrades', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.FactTrades (
        TradeKey BIGINT IDENTITY(1,1) NOT NULL PRIMARY KEY,
        TradeDateKey INT NOT NULL,
        SettleDateKey INT NULL,
        PortfolioKey INT NOT NULL,
        SecurityKey INT NOT NULL,
        Side CHAR(4) NOT NULL,
        Quantity DECIMAL(19,6) NOT NULL,
        Price DECIMAL(19,6) NOT NULL,
        FeeAmount DECIMAL(19,6) NOT NULL CONSTRAINT DF_FactTrades_FeeAmount DEFAULT (0),
        SlippageAmount DECIMAL(19,6) NOT NULL CONSTRAINT DF_FactTrades_SlippageAmount DEFAULT (0),
        CurrencyCode CHAR(3) NOT NULL,
        StrategyCode NVARCHAR(50) NULL,
        OrderType NVARCHAR(20) NULL,
        ExecutionTs DATETIME2(3) NOT NULL CONSTRAINT DF_FactTrades_ExecutionTs DEFAULT (SYSUTCDATETIME()),
        CONSTRAINT CK_FactTrades_Side CHECK (Side IN ('BUY', 'SELL')),
        CONSTRAINT FK_FactTrades_TradeDate FOREIGN KEY (TradeDateKey) REFERENCES dbo.DimDate(DateKey),
        CONSTRAINT FK_FactTrades_SettleDate FOREIGN KEY (SettleDateKey) REFERENCES dbo.DimDate(DateKey),
        CONSTRAINT FK_FactTrades_Portfolio FOREIGN KEY (PortfolioKey) REFERENCES dbo.DimPortfolio(PortfolioKey),
        CONSTRAINT FK_FactTrades_Security FOREIGN KEY (SecurityKey) REFERENCES dbo.DimSecurity(SecurityKey)
    );
END;
GO

IF NOT EXISTS (
    SELECT 1
    FROM sys.indexes
    WHERE name = 'IX_FactTrades_Date_Portfolio'
      AND object_id = OBJECT_ID('dbo.FactTrades')
)
BEGIN
    CREATE INDEX IX_FactTrades_Date_Portfolio ON dbo.FactTrades(TradeDateKey, PortfolioKey);
END;
GO

IF OBJECT_ID('dbo.PortfolioPositionsDaily', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.PortfolioPositionsDaily (
        PositionKey BIGINT IDENTITY(1,1) NOT NULL PRIMARY KEY,
        DateKey INT NOT NULL,
        PortfolioKey INT NOT NULL,
        SecurityKey INT NOT NULL,
        Quantity DECIMAL(19,6) NOT NULL,
        AvgCost DECIMAL(19,6) NOT NULL,
        MarketValue DECIMAL(19,6) NOT NULL,
        UnrealizedPnL DECIMAL(19,6) NOT NULL,
        WeightPct DECIMAL(9,6) NULL,
        CONSTRAINT FK_Positions_DimDate FOREIGN KEY (DateKey) REFERENCES dbo.DimDate(DateKey),
        CONSTRAINT FK_Positions_DimPortfolio FOREIGN KEY (PortfolioKey) REFERENCES dbo.DimPortfolio(PortfolioKey),
        CONSTRAINT FK_Positions_DimSecurity FOREIGN KEY (SecurityKey) REFERENCES dbo.DimSecurity(SecurityKey)
    );
END;
GO

IF NOT EXISTS (
    SELECT 1
    FROM sys.indexes
    WHERE name = 'UX_Positions_Date_Portfolio_Security'
      AND object_id = OBJECT_ID('dbo.PortfolioPositionsDaily')
)
BEGIN
    CREATE UNIQUE INDEX UX_Positions_Date_Portfolio_Security
        ON dbo.PortfolioPositionsDaily(DateKey, PortfolioKey, SecurityKey);
END;
GO

IF OBJECT_ID('dbo.PortfolioPnLDaily', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.PortfolioPnLDaily (
        PnLKey BIGINT IDENTITY(1,1) NOT NULL PRIMARY KEY,
        DateKey INT NOT NULL,
        PortfolioKey INT NOT NULL,
        DailyPnL DECIMAL(19,6) NOT NULL,
        CumPnL DECIMAL(19,6) NOT NULL,
        Nav DECIMAL(19,6) NOT NULL,
        ReturnPct DECIMAL(9,6) NULL,
        ContributionPct DECIMAL(9,6) NULL,
        CONSTRAINT FK_PnL_DimDate FOREIGN KEY (DateKey) REFERENCES dbo.DimDate(DateKey),
        CONSTRAINT FK_PnL_DimPortfolio FOREIGN KEY (PortfolioKey) REFERENCES dbo.DimPortfolio(PortfolioKey)
    );
END;
GO

IF NOT EXISTS (
    SELECT 1
    FROM sys.indexes
    WHERE name = 'UX_PnL_Date_Portfolio'
      AND object_id = OBJECT_ID('dbo.PortfolioPnLDaily')
)
BEGIN
    CREATE UNIQUE INDEX UX_PnL_Date_Portfolio ON dbo.PortfolioPnLDaily(DateKey, PortfolioKey);
END;
GO

IF OBJECT_ID('dbo.RiskMetricsDaily', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.RiskMetricsDaily (
        RiskKey BIGINT IDENTITY(1,1) NOT NULL PRIMARY KEY,
        DateKey INT NOT NULL,
        PortfolioKey INT NOT NULL,
        Volatility20d DECIMAL(9,6) NULL,
        MaxDrawdown DECIMAL(9,6) NULL,
        VaR95 DECIMAL(19,6) NULL,
        Beta DECIMAL(9,6) NULL,
        SharpeRatio DECIMAL(9,6) NULL,
        CONSTRAINT FK_Risk_DimDate FOREIGN KEY (DateKey) REFERENCES dbo.DimDate(DateKey),
        CONSTRAINT FK_Risk_DimPortfolio FOREIGN KEY (PortfolioKey) REFERENCES dbo.DimPortfolio(PortfolioKey)
    );
END;
GO

IF NOT EXISTS (
    SELECT 1
    FROM sys.indexes
    WHERE name = 'UX_Risk_Date_Portfolio'
      AND object_id = OBJECT_ID('dbo.RiskMetricsDaily')
)
BEGIN
    CREATE UNIQUE INDEX UX_Risk_Date_Portfolio ON dbo.RiskMetricsDaily(DateKey, PortfolioKey);
END;
GO

IF OBJECT_ID('dbo.AI_DailyBriefing', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.AI_DailyBriefing (
        BriefingId BIGINT IDENTITY(1,1) NOT NULL PRIMARY KEY,
        DateKey INT NOT NULL,
        PortfolioKey INT NULL,
        ModelName NVARCHAR(100) NOT NULL,
        PromptVersion NVARCHAR(50) NOT NULL,
        OutputJson NVARCHAR(MAX) NOT NULL,
        Summary NVARCHAR(MAX) NULL,
        Assumptions NVARCHAR(MAX) NULL,
        CreatedAt DATETIME2(3) NOT NULL CONSTRAINT DF_AI_DailyBriefing_CreatedAt DEFAULT (SYSUTCDATETIME()),
        CreatedBy NVARCHAR(100) NOT NULL CONSTRAINT DF_AI_DailyBriefing_CreatedBy DEFAULT (SUSER_SNAME()),
        CONSTRAINT FK_AI_DailyBriefing_DimDate FOREIGN KEY (DateKey) REFERENCES dbo.DimDate(DateKey),
        CONSTRAINT FK_AI_DailyBriefing_DimPortfolio FOREIGN KEY (PortfolioKey) REFERENCES dbo.DimPortfolio(PortfolioKey)
    );
END;
GO

IF OBJECT_ID('dbo.AI_Recommendations', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.AI_Recommendations (
        RecommendationId BIGINT IDENTITY(1,1) NOT NULL PRIMARY KEY,
        DateKey INT NOT NULL,
        PortfolioKey INT NULL,
        SecurityKey INT NULL,
        Action NVARCHAR(20) NOT NULL,
        ConfidenceScore DECIMAL(5,4) NULL,
        Reasoning NVARCHAR(MAX) NULL,
        ConstraintsCheck NVARCHAR(MAX) NULL,
        OutputJson NVARCHAR(MAX) NULL,
        Status NVARCHAR(20) NOT NULL CONSTRAINT DF_AI_Recommendations_Status DEFAULT ('draft'),
        CreatedAt DATETIME2(3) NOT NULL CONSTRAINT DF_AI_Recommendations_CreatedAt DEFAULT (SYSUTCDATETIME()),
        CONSTRAINT FK_AI_Recommendations_DimDate FOREIGN KEY (DateKey) REFERENCES dbo.DimDate(DateKey),
        CONSTRAINT FK_AI_Recommendations_DimPortfolio FOREIGN KEY (PortfolioKey) REFERENCES dbo.DimPortfolio(PortfolioKey),
        CONSTRAINT FK_AI_Recommendations_DimSecurity FOREIGN KEY (SecurityKey) REFERENCES dbo.DimSecurity(SecurityKey)
    );
END;
GO

IF OBJECT_ID('dbo.AI_WhatIf', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.AI_WhatIf (
        WhatIfId BIGINT IDENTITY(1,1) NOT NULL PRIMARY KEY,
        DateKey INT NOT NULL,
        PortfolioKey INT NULL,
        ScenarioName NVARCHAR(200) NOT NULL,
        InputJson NVARCHAR(MAX) NOT NULL,
        ResultJson NVARCHAR(MAX) NULL,
        Narrative NVARCHAR(MAX) NULL,
        CreatedAt DATETIME2(3) NOT NULL CONSTRAINT DF_AI_WhatIf_CreatedAt DEFAULT (SYSUTCDATETIME()),
        CONSTRAINT FK_AI_WhatIf_DimDate FOREIGN KEY (DateKey) REFERENCES dbo.DimDate(DateKey),
        CONSTRAINT FK_AI_WhatIf_DimPortfolio FOREIGN KEY (PortfolioKey) REFERENCES dbo.DimPortfolio(PortfolioKey)
    );
END;
GO

IF OBJECT_ID('dbo.AI_AuditLog', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.AI_AuditLog (
        AuditId BIGINT IDENTITY(1,1) NOT NULL PRIMARY KEY,
        EventTs DATETIME2(3) NOT NULL CONSTRAINT DF_AI_AuditLog_EventTs DEFAULT (SYSUTCDATETIME()),
        EventType NVARCHAR(50) NOT NULL,
        Component NVARCHAR(100) NOT NULL,
        RequestId UNIQUEIDENTIFIER NOT NULL CONSTRAINT DF_AI_AuditLog_RequestId DEFAULT (NEWID()),
        InputHash NVARCHAR(128) NULL,
        Status NVARCHAR(20) NOT NULL,
        Detail NVARCHAR(MAX) NULL
    );
END;
GO

IF NOT EXISTS (
    SELECT 1
    FROM sys.indexes
    WHERE name = 'IX_AI_AuditLog_EventTs'
      AND object_id = OBJECT_ID('dbo.AI_AuditLog')
)
BEGIN
    CREATE INDEX IX_AI_AuditLog_EventTs ON dbo.AI_AuditLog(EventTs DESC);
END;
GO

