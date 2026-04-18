-- ============================================================
-- KHL BANK PLATFORM — Init tables applicatives
-- Base : SmartAssetAdvicedb
-- A exécuter une seule fois (idempotent)
-- ============================================================

USE SmartAssetAdvicedb;
GO

-- ------------------------------------------------------------
-- TABLE : AppUsers (profils utilisateurs de la plateforme)
-- ------------------------------------------------------------
IF OBJECT_ID('dbo.AppUsers', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.AppUsers (
        user_id       INT IDENTITY(1,1) NOT NULL PRIMARY KEY,
        username      NVARCHAR(50)  NOT NULL,
        email         NVARCHAR(200) NOT NULL,
        password_hash NVARCHAR(200) NOT NULL,  -- sha256 + salt
        password_salt NVARCHAR(100) NOT NULL,
        role          NVARCHAR(50)  NOT NULL   -- ASSET_MANAGER | TRADER | RISK_ANALYST | QUANT | ALM_OFFICER | DATA_ANALYST | ADMIN
                      CONSTRAINT CK_AppUsers_Role CHECK (role IN (
                          'ASSET_MANAGER','TRADER','RISK_ANALYST',
                          'QUANT','ALM_OFFICER','DATA_ANALYST','ADMIN'
                      )),
        full_name     NVARCHAR(200) NULL,
        department    NVARCHAR(100) NULL,
        is_active     BIT NOT NULL CONSTRAINT DF_AppUsers_IsActive DEFAULT (1),
        created_at    DATETIME2(3) NOT NULL CONSTRAINT DF_AppUsers_CreatedAt DEFAULT (SYSUTCDATETIME()),
        last_login    DATETIME2(3) NULL
    );
    CREATE UNIQUE INDEX UX_AppUsers_Username ON dbo.AppUsers(username);
    CREATE UNIQUE INDEX UX_AppUsers_Email    ON dbo.AppUsers(email);
    PRINT 'TABLE AppUsers créée';
END
ELSE
    PRINT 'TABLE AppUsers déjà existante';
GO

-- ------------------------------------------------------------
-- TABLE : AppLog (traçage technique de toutes les actions)
-- ------------------------------------------------------------
IF OBJECT_ID('dbo.AppLog', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.AppLog (
        log_id       BIGINT IDENTITY(1,1) NOT NULL PRIMARY KEY,
        log_ts       DATETIME2(3) NOT NULL CONSTRAINT DF_AppLog_LogTs DEFAULT (SYSUTCDATETIME()),
        level        NVARCHAR(10)  NOT NULL DEFAULT 'INFO',  -- INFO | WARN | ERROR | SQL
        module       NVARCHAR(50)  NULL,   -- monitoring | portfolio | trading | ...
        action       NVARCHAR(200) NOT NULL,
        detail       NVARCHAR(MAX) NULL,
        username     NVARCHAR(50)  NULL,
        duration_ms  INT NULL,
        rows_affected INT NULL
    );
    CREATE INDEX IX_AppLog_Ts ON dbo.AppLog(log_ts DESC);
    PRINT 'TABLE AppLog créée';
END
ELSE
    PRINT 'TABLE AppLog déjà existante';
GO

-- ------------------------------------------------------------
-- TABLE : PortfolioWizardDraft (sauvegarde wizard en cours)
-- ------------------------------------------------------------
IF OBJECT_ID('dbo.PortfolioWizardDraft', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.PortfolioWizardDraft (
        draft_id       INT IDENTITY(1,1) NOT NULL PRIMARY KEY,
        username       NVARCHAR(50)  NOT NULL,
        step_reached   TINYINT NOT NULL DEFAULT 1,
        draft_json     NVARCHAR(MAX) NOT NULL,  -- JSON de tous les paramètres
        created_at     DATETIME2(3) NOT NULL CONSTRAINT DF_Draft_CreatedAt DEFAULT (SYSUTCDATETIME()),
        updated_at     DATETIME2(3) NOT NULL CONSTRAINT DF_Draft_UpdatedAt DEFAULT (SYSUTCDATETIME())
    );
    PRINT 'TABLE PortfolioWizardDraft créée';
END
ELSE
    PRINT 'TABLE PortfolioWizardDraft déjà existante';
GO

PRINT '=== INIT TERMINÉ ===';
GO
