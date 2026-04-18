"""
KHL Bank Platform — Couche d'accès base de données
Connexion Windows Auth, logging automatique dans AppLog
"""
import pyodbc
import time
from datetime import datetime
from contextlib import contextmanager
import config


def get_connection(database: str = None):
    """Retourne une connexion SQL Server (Windows Auth)."""
    return pyodbc.connect(config.conn_str(database), autocommit=False)


@contextmanager
def db_cursor(database: str = None, autocommit: bool = False):
    """
    Context manager pour requêtes SQL.
    Usage:
        with db_cursor() as cur:
            cur.execute("SELECT ...")
            rows = cur.fetchall()
    Passe database="KHLWorldInvest" pour cibler la base staging.
    Sans argument → config.SQL_DB_MAIN (SmartAssetAdvicedb).
    """
    try:
        conn = pyodbc.connect(config.conn_str(database), autocommit=autocommit)
    except pyodbc.Error as e:
        db_name = database or config.SQL_DB_MAIN
        raise RuntimeError(
            f"Connexion SQL Server impossible — serveur={config.SQL_SERVER} "
            f"base={db_name} driver={config.SQL_DRIVER}\n{e}"
        ) from e
    cur = conn.cursor()
    try:
        yield cur
        if not autocommit:
            conn.commit()
    except Exception:
        if not autocommit:
            conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()


def app_log(module: str, action: str, detail: str = None,
            level: str = "INFO", username: str = None,
            duration_ms: int = None, rows_affected: int = None,
            correlation_id: str = None,
            before_payload: str = None, after_payload: str = None):
    """Écrit une entrée dans AppLog (traçage technique visible dans le monitoring)."""
    try:
        with db_cursor(autocommit=True) as cur:
            cur.execute("""
                INSERT INTO dbo.AppLog
                    (level, module, action, detail, username, duration_ms, rows_affected,
                     correlation_id, before_payload, after_payload)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, level, module, action, detail, username, duration_ms, rows_affected,
                 correlation_id, before_payload, after_payload)
    except Exception:
        pass  # Le log ne doit jamais faire planter l'app


def get_setting(key: str, default: str = None) -> str:
    """Lit une clé dans AppSettings."""
    try:
        with db_cursor() as cur:
            cur.execute("SELECT SettingValue FROM dbo.AppSettings WHERE SettingKey=?", key)
            row = cur.fetchone()
            return row[0] if row else default
    except Exception:
        return default


def set_setting(key: str, value: str, description: str = None, updated_by: str = None) -> None:
    """Upsert une clé dans AppSettings."""
    with db_cursor() as cur:
        cur.execute("""
            IF EXISTS (SELECT 1 FROM dbo.AppSettings WHERE SettingKey=?)
                UPDATE dbo.AppSettings
                SET SettingValue=?, UpdatedAt=SYSUTCDATETIME(), UpdatedBy=?
                WHERE SettingKey=?
            ELSE
                INSERT INTO dbo.AppSettings (SettingKey, SettingValue, Description, UpdatedBy)
                VALUES (?, ?, ?, ?)
        """, key, value, updated_by, key,
             key, value, description, updated_by)


def get_table_stats():
    """
    Retourne les stats de toutes les tables Gold + App
    pour le panneau monitoring.
    """
    tables = [
        ("AppUsers",               config.SQL_DB_MAIN),
        ("DimPortfolio",           config.SQL_DB_MAIN),
        ("DimSecurity",            config.SQL_DB_MAIN),
        ("DimBroker",              config.SQL_DB_MAIN),
        ("DimDate",                config.SQL_DB_MAIN),
        ("FactPrice",              config.SQL_DB_MAIN),
        ("FactTrades",             config.SQL_DB_MAIN),
        ("FactTradeLifecycle",     config.SQL_DB_MAIN),
        ("FactSettlementMovement", config.SQL_DB_MAIN),
        ("FactAccountingEvent",    config.SQL_DB_MAIN),
        ("FactAccountingMovement", config.SQL_DB_MAIN),
        ("FactReconciliationControl", config.SQL_DB_MAIN),
        ("PortfolioPositionsDaily",config.SQL_DB_MAIN),
        ("PortfolioPnLDaily",      config.SQL_DB_MAIN),
        ("RiskMetricsDaily",       config.SQL_DB_MAIN),
        ("AI_DailyBriefing",       config.SQL_DB_MAIN),
        ("AI_Recommendations",     config.SQL_DB_MAIN),
        ("AppLog",                 config.SQL_DB_MAIN),
    ]
    results = []
    with db_cursor() as cur:
        for table_name, db in tables:
            try:
                cur.execute(f"SELECT COUNT(*) FROM [{db}].[dbo].[{table_name}]")
                count = cur.fetchone()[0]
                # Cherche la dernière date de mise à jour si colonne existe
                results.append({
                    "table": table_name,
                    "database": db,
                    "rows": count,
                    "status": "ok"
                })
            except Exception as e:
                results.append({
                    "table": table_name,
                    "database": db,
                    "rows": None,
                    "status": f"error: {str(e)[:60]}"
                })
    return results


def get_stg_stats():
    """Stats de la table staging Boursorama/STOOQ."""
    stats = {}
    try:
        with db_cursor(database=config.SQL_DB_STG) as cur:
            cur.execute("""
                SELECT produit_type, COUNT(*) as cnt, COUNT(DISTINCT libelle) as tickers
                FROM [stg].[stg_bourso_price_history]
                WHERE produit_type IN ('STOOQ','ACTION','turbo','warrant')
                GROUP BY produit_type
            """)
            for r in cur.fetchall():
                stats[r[0]] = {"rows": r[1], "tickers": r[2]}
    except Exception as e:
        stats["error"] = str(e)
    return stats


def get_risk_limits(portfolio_key: int = None) -> dict:
    """
    Retourne les limites de risque actives pour un portefeuille.
    Priorité : limite spécifique au portefeuille > limite globale (NULL).
    Retourne dict {nom: {warn, breach, desc}}.
    """
    defaults = {
        "vol20d":   {"warn": 0.15,  "breach": 0.20,  "desc": "Volatilité 20j annualisée"},
        "drawdown": {"warn": -0.10, "breach": -0.20, "desc": "Drawdown max"},
        "var95":    {"warn": -0.025,"breach": -0.05, "desc": "VaR 95%"},
        "sharpe":   {"warn": 0.50,  "breach": 0.00,  "desc": "Sharpe ratio"},
        "beta":     {"warn": 1.20,  "breach": 1.50,  "desc": "Bêta vs marché"},
    }
    try:
        with db_cursor() as cur:
            cur.execute("""
                SELECT LimitName, WarnLevel, BreachLevel, Description
                FROM dbo.RiskLimits
                WHERE PortfolioKey IS NULL OR PortfolioKey = ?
                ORDER BY PortfolioKey DESC  -- spécifique avant global
            """, portfolio_key)
            seen = {}
            for r in cur.fetchall():
                name = r[0]
                if name not in seen:   # garde la plus spécifique (premiere = portfolio)
                    seen[name] = {
                        "warn": float(r[1]) if r[1] is not None else None,
                        "breach": float(r[2]) if r[2] is not None else None,
                        "desc": r[3] or "",
                    }
            return seen if seen else defaults
    except Exception:
        return defaults


def get_portfolios() -> list:
    """Retourne la liste des portefeuilles actifs."""
    try:
        with db_cursor() as cur:
            cur.execute("""
                SELECT PortfolioKey, PortfolioCode, PortfolioName, BaseCurrency
                FROM dbo.DimPortfolio WHERE IsActive=1 ORDER BY PortfolioCode
            """)
            return [{"key": r[0], "code": r[1], "name": r[2], "currency": r[3]}
                    for r in cur.fetchall()]
    except Exception:
        return []


def get_or_create_security(ticker: str) -> int:
    """Retourne le SecurityKey pour un ticker, le crée si absent."""
    with db_cursor() as cur:
        cur.execute("SELECT SecurityKey FROM dbo.DimSecurity WHERE Ticker=?", ticker)
        row = cur.fetchone()
        if row:
            return row[0]
        cur.execute("""
            INSERT INTO dbo.DimSecurity (Ticker, SecurityName, AssetClass, CurrencyCode, IsActive)
            VALUES (?, ?, 'EQUITY', 'EUR', 1)
        """, ticker, ticker)
        cur.execute("SELECT SecurityKey FROM dbo.DimSecurity WHERE Ticker=?", ticker)
        return cur.fetchone()[0]


def get_or_create_datekey(d=None) -> int:
    """Retourne le DateKey (YYYYMMDD) pour une date, le crée si absent."""
    import calendar as _cal
    from datetime import date as _date
    _MONTH_NAMES = ['January','February','March','April','May','June',
                    'July','August','September','October','November','December']
    if d is None:
        d = _date.today()
    dk       = int(d.strftime("%Y%m%d"))
    last_day = _cal.monthrange(d.year, d.month)[1]
    with db_cursor() as cur:
        cur.execute("SELECT DateKey FROM dbo.DimDate WHERE DateKey=?", dk)
        if cur.fetchone():
            return dk
        cur.execute("""
            INSERT INTO dbo.DimDate
                (DateKey, FullDate, CalendarYear, CalendarMonth, CalendarDay,
                 MonthName, QuarterNumber, WeekOfYear, IsMonthEnd)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, dk, d,
             d.year, d.month, d.day,
             _MONTH_NAMES[d.month - 1],
             (d.month - 1) // 3 + 1,
             d.isocalendar()[1],
             1 if d.day == last_day else 0)
        return dk


def get_account_key(account_code: str) -> int:
    """Retourne l'AccountKey pour un code compte CIB (ex: '120100')."""
    with db_cursor() as cur:
        cur.execute("SELECT AccountKey FROM dbo.DimAccountInternal WHERE AccountCode=?", account_code)
        row = cur.fetchone()
        if not row:
            raise ValueError(f"Compte introuvable : {account_code}")
        return row[0]


def run_debit_credit_control(date_key: int = None, checked_by: str = "SYSTEM") -> dict:
    """
    Contrôle EOD : vérifie que ∑Débits = ∑Crédits dans FactAccountingMovement.
    Insère un enregistrement dans FactReconciliationControl.
    Retourne {'status': 'OK'|'BREAK', 'difference': float}.
    """
    from datetime import date as _date
    if date_key is None:
        date_key = int(_date.today().strftime("%Y%m%d"))
    try:
        with db_cursor() as cur:
            cur.execute("""
                SELECT
                    ISNULL(SUM(DebitAmount),0)  as total_debit,
                    ISNULL(SUM(CreditAmount),0) as total_credit
                FROM dbo.FactAccountingMovement
                WHERE PostingDateKey = ?
            """, date_key)
            row = cur.fetchone()
            total_d = float(row[0])
            total_c = float(row[1])
            diff    = round(total_d - total_c, 4)
            status  = "OK" if abs(diff) < 0.01 else "BREAK"
            comment = f"Debit={total_d:.2f} Credit={total_c:.2f} Diff={diff:.4f}"

            cur.execute("""
                INSERT INTO dbo.FactReconciliationControl
                    (DateKey, PortfolioKey, ControlName, ControlStatus, DifferenceAmount, Comment, CheckedBy)
                VALUES (?, NULL, 'DEBIT_CREDIT_BALANCE', ?, ?, ?, ?)
            """, date_key, status, diff, comment, checked_by)
        return {"status": status, "difference": diff, "comment": comment}
    except Exception as e:
        return {"status": "ERROR", "difference": None, "comment": str(e)}


def create_trade_lifecycle(
    trade_key: int, order_key: int, portfolio_key: int,
    ticker: str, side: str, qty: float, price: float,
    notional: float, fee: float, settle_date,
    username: str, correlation_id: str = None
) -> None:
    """
    Génère les événements du cycle de vie d'un trade dans FactTradeLifecycle.
    Simule le workflow complet :
      PRE_TRADE_CHECK → ORDER_PLACED → SENT_TO_BROKER → BROKER_ACK
      → MARKET_EXECUTED → TRADE_CONFIRMED (MT515)
      → PENDING_SETTLEMENT (MT541/543) → SETTLED (MT544/546)
      → ACCOUNTING_POSTED → RECONCILED
    Tous les timestamps sont simulés à partir de l'heure réelle d'exécution.
    """
    from datetime import datetime, timedelta
    import random

    now = datetime.utcnow()

    # Choisir un broker (round-robin sur trade_key pour cohérence)
    broker_key = None
    broker_bic = "BNPAFRPP"
    broker_name = "BNP Paribas CIB"
    try:
        with db_cursor() as cur:
            cur.execute("SELECT BrokerKey, BIC, BrokerName FROM dbo.DimBroker WHERE IsActive=1 ORDER BY BrokerKey")
            brokers = cur.fetchall()
            if brokers:
                b = brokers[trade_key % len(brokers)]
                broker_key, broker_bic, broker_name = b[0], b[1], b[2]
    except Exception:
        pass

    # Référence SWIFT simulée (format pseudo-réel)
    swift_base = f"KHL{now.strftime('%Y%m%d')}{trade_key:05d}"
    # MT515: confirmation trade | MT541: receive AgainstPayment | MT543: deliver AgainstPayment
    # MT544: confirmation receipt | MT546: confirmation delivery
    mt_confirm = "MT515"
    mt_instruct = "MT541" if side == "BUY" else "MT543"
    mt_complete = "MT544" if side == "BUY" else "MT546"

    # Date de settlement à 09:00 UTC
    from datetime import date as _date
    sd = settle_date if isinstance(settle_date, _date) else _date.today()
    settle_dt_open = datetime(sd.year, sd.month, sd.day, 9, 0, 0)
    settle_dt_eod  = datetime(sd.year, sd.month, sd.day, 17, 0, 0)

    # Détail du broker pour les messages
    exchange = "NYSE" if ticker.endswith(".US") or not ("." in ticker) else "Euronext"

    events = [
        # (EventTs, Status, Actor, BrokerKey, SwiftMsgType, SwiftRef, Detail)
        (now - timedelta(minutes=2),
         "PRE_TRADE_CHECK", username, None, None, None,
         f"Controle pre-trade OK — Notional {notional:,.0f} EUR dans les limites de risque"),

        (now - timedelta(minutes=1),
         "ORDER_PLACED", username, None, None, None,
         f"Ordre {side} {qty:.0f} {ticker} @ {price:.4f} EUR cree (OrderKey={order_key})"),

        (now - timedelta(seconds=30),
         "SENT_TO_BROKER", "SYSTEM", broker_key, None, None,
         f"FIX NewOrderSingle transmis a {broker_name} (BIC: {broker_bic})"),

        (now + timedelta(minutes=1, seconds=23),
         "BROKER_ACK", "BROKER", broker_key, None, None,
         f"FIX ExecutionReport — OrdStatus=Acknowledged — {broker_name}"),

        (now + timedelta(minutes=2, seconds=45),
         "MARKET_EXECUTED", "BROKER", broker_key, None, None,
         f"FIX ExecutionReport — OrdStatus=Filled @ {price:.4f} EUR — {exchange}"),

        (now + timedelta(minutes=30),
         "TRADE_CONFIRMED", "BROKER", broker_key, mt_confirm, f"{mt_confirm}-{swift_base}",
         f"SWIFT {mt_confirm} recu — Confirmation achat/vente titres {ticker}"),

        (now + timedelta(minutes=31),
         "PENDING_SETTLEMENT", "SYSTEM", None, mt_instruct, f"{mt_instruct}-{swift_base}",
         f"SWIFT {mt_instruct} envoye — Instructions reglement-livraison J+2 ({sd.strftime('%d/%m/%Y')})"),

        (settle_dt_open,
         "SETTLED", "CSD", broker_key, mt_complete, f"{mt_complete}-{swift_base}",
         f"SWIFT {mt_complete} — DVP confirme : {ticker} livre, {notional + fee:,.0f} EUR debite"),

        (settle_dt_open + timedelta(minutes=5),
         "ACCOUNTING_POSTED", "SYSTEM", None, None, None,
         f"Ecritures CIB passees : 120100/140200 (trade) + 510100/150100 (frais)"),

        (settle_dt_eod,
         "RECONCILED", "SYSTEM", None, None, None,
         f"Controle EOD Debit=Credit — FactReconciliationControl OK"),
    ]

    with db_cursor() as cur:
        for ts, status, actor, bkey, swift_type, swift_ref, detail in events:
            cur.execute("""
                INSERT INTO dbo.FactTradeLifecycle
                    (TradeKey, OrderKey, EventTs, Status, Actor, BrokerKey,
                     SwiftMsgType, SwiftRef, Detail)
                VALUES (?,?,?,?,?,?,?,?,?)
            """, trade_key, order_key, ts, status, actor, bkey,
                 swift_type, swift_ref, detail)


def init_db():
    """
    Vérifie et crée les tables applicatives si elles n'existent pas.
    Appelé au démarrage de l'app Flask.
    """
    ddl_stmts = [
        """
        IF OBJECT_ID('dbo.AppUsers', 'U') IS NULL
        BEGIN
            CREATE TABLE dbo.AppUsers (
                user_id       INT IDENTITY(1,1) NOT NULL PRIMARY KEY,
                username      NVARCHAR(50)  NOT NULL,
                email         NVARCHAR(200) NOT NULL,
                password_hash NVARCHAR(200) NOT NULL,
                password_salt NVARCHAR(100) NOT NULL,
                role          NVARCHAR(50)  NOT NULL,
                full_name     NVARCHAR(200) NULL,
                department    NVARCHAR(100) NULL,
                is_active     BIT NOT NULL DEFAULT (1),
                created_at    DATETIME2(3) NOT NULL DEFAULT (SYSUTCDATETIME()),
                last_login    DATETIME2(3) NULL
            );
            CREATE UNIQUE INDEX UX_AppUsers_Username ON dbo.AppUsers(username);
            CREATE UNIQUE INDEX UX_AppUsers_Email    ON dbo.AppUsers(email);
        END
        """,
        """
        IF OBJECT_ID('dbo.AppLog', 'U') IS NULL
        BEGIN
            CREATE TABLE dbo.AppLog (
                log_id        BIGINT IDENTITY(1,1) NOT NULL PRIMARY KEY,
                log_ts        DATETIME2(3) NOT NULL DEFAULT (SYSUTCDATETIME()),
                level         NVARCHAR(10)  NOT NULL DEFAULT 'INFO',
                module        NVARCHAR(50)  NULL,
                action        NVARCHAR(200) NOT NULL,
                detail        NVARCHAR(MAX) NULL,
                username      NVARCHAR(50)  NULL,
                duration_ms   INT NULL,
                rows_affected INT NULL
            );
            CREATE INDEX IX_AppLog_Ts ON dbo.AppLog(log_ts DESC);
        END
        """,
        """
        IF OBJECT_ID('dbo.PortfolioWizardDraft', 'U') IS NULL
        BEGIN
            CREATE TABLE dbo.PortfolioWizardDraft (
                draft_id     INT IDENTITY(1,1) NOT NULL PRIMARY KEY,
                username     NVARCHAR(50)  NOT NULL,
                step_reached TINYINT NOT NULL DEFAULT 1,
                draft_json   NVARCHAR(MAX) NOT NULL,
                created_at   DATETIME2(3) NOT NULL DEFAULT (SYSUTCDATETIME()),
                updated_at   DATETIME2(3) NOT NULL DEFAULT (SYSUTCDATETIME())
            );
        END
        """,
        """
        IF OBJECT_ID('dbo.AppSettings', 'U') IS NULL
        BEGIN
            CREATE TABLE dbo.AppSettings (
                SettingKey   NVARCHAR(100) NOT NULL PRIMARY KEY,
                SettingValue NVARCHAR(MAX) NULL,
                Description  NVARCHAR(500) NULL,
                UpdatedAt    DATETIME2(3)  NOT NULL DEFAULT (SYSUTCDATETIME()),
                UpdatedBy    NVARCHAR(50)  NULL
            );
        END
        """,
        """
        IF OBJECT_ID('dbo.PasswordResetTokens', 'U') IS NULL
        BEGIN
            CREATE TABLE dbo.PasswordResetTokens (
                token_id   INT IDENTITY(1,1) NOT NULL PRIMARY KEY,
                username   NVARCHAR(50)  NOT NULL,
                token      NVARCHAR(20)  NOT NULL,
                expires_at DATETIME2(3)  NOT NULL,
                used       BIT NOT NULL DEFAULT (0),
                created_at DATETIME2(3)  NOT NULL DEFAULT (SYSUTCDATETIME())
            );
            CREATE INDEX IX_ResetTokens_Token ON dbo.PasswordResetTokens(token);
        END
        """,
        # ── Carnet d'ordres ──────────────────────────────────────────
        """
        IF OBJECT_ID('dbo.Orders', 'U') IS NULL
        BEGIN
            CREATE TABLE dbo.Orders (
                OrderKey       INT IDENTITY(1,1) NOT NULL PRIMARY KEY,
                CreatedAt      DATETIME2(3) NOT NULL DEFAULT SYSUTCDATETIME(),
                PortfolioKey   INT NOT NULL,
                Ticker         NVARCHAR(20) NOT NULL,
                Side           NVARCHAR(4)  NOT NULL,
                OrderQty       DECIMAL(18,4) NOT NULL,
                OrderPrice     DECIMAL(18,6) NOT NULL,
                OrderType      NVARCHAR(10) NOT NULL DEFAULT 'MARKET',
                Status         NVARCHAR(15) NOT NULL DEFAULT 'EXECUTED',
                ExecutedQty    DECIMAL(18,4) NULL,
                ExecutedPrice  DECIMAL(18,6) NULL,
                ExecutedAt     DATETIME2(3) NULL,
                FeeAmount      DECIMAL(18,4) NULL DEFAULT 0,
                SlippageAmount DECIMAL(18,4) NULL DEFAULT 0,
                Notional       DECIMAL(18,2) NULL,
                CurrencyCode   CHAR(3) NOT NULL DEFAULT 'EUR',
                CreatedBy      NVARCHAR(50) NULL,
                Notes          NVARCHAR(500) NULL
            );
            CREATE INDEX IX_Orders_Portfolio ON dbo.Orders(PortfolioKey, CreatedAt DESC);
        END
        """,
        # ── Comptabilité — journal en partie double ──────────────────
        """
        IF OBJECT_ID('dbo.JournalEntries', 'U') IS NULL
        BEGIN
            CREATE TABLE dbo.JournalEntries (
                EntryKey      INT IDENTITY(1,1) NOT NULL PRIMARY KEY,
                EntryDate     DATE         NOT NULL,
                EntryTs       DATETIME2(3) NOT NULL DEFAULT SYSUTCDATETIME(),
                PortfolioKey  INT NOT NULL,
                TradeKey      INT NULL,
                OrderKey      INT NULL,
                AccountDebit  NVARCHAR(80) NOT NULL,
                AccountCredit NVARCHAR(80) NOT NULL,
                Amount        DECIMAL(18,2) NOT NULL,
                Currency      CHAR(3) NOT NULL DEFAULT 'EUR',
                Label         NVARCHAR(300) NULL,
                EntryType     NVARCHAR(30) NULL,
                CreatedBy     NVARCHAR(50) NULL
            );
            CREATE INDEX IX_Journal_Portfolio ON dbo.JournalEntries(PortfolioKey, EntryDate DESC);
            CREATE INDEX IX_Journal_Trade     ON dbo.JournalEntries(TradeKey);
        END
        """,
        # ── Limites de risque configurables ──────────────────────────
        """
        IF OBJECT_ID('dbo.RiskLimits', 'U') IS NULL
        BEGIN
            CREATE TABLE dbo.RiskLimits (
                LimitKey     INT IDENTITY(1,1) NOT NULL PRIMARY KEY,
                PortfolioKey INT NULL,
                LimitName    NVARCHAR(50)  NOT NULL,
                WarnLevel    DECIMAL(18,6) NULL,
                BreachLevel  DECIMAL(18,6) NULL,
                Description  NVARCHAR(200) NULL,
                UpdatedAt    DATETIME2(3)  NOT NULL DEFAULT SYSUTCDATETIME(),
                UpdatedBy    NVARCHAR(50)  NULL
            );
            CREATE UNIQUE INDEX UX_RiskLimits ON dbo.RiskLimits(PortfolioKey, LimitName)
                WHERE PortfolioKey IS NULL;
            -- Limites globales par défaut
            INSERT INTO dbo.RiskLimits (PortfolioKey,LimitName,WarnLevel,BreachLevel,Description) VALUES
                (NULL,'vol20d',   0.15,  0.20,  'Volatilité 20j annualisée'),
                (NULL,'drawdown',-0.10, -0.20,  'Drawdown max depuis le pic'),
                (NULL,'var95',   -0.025,-0.05,  'VaR 95%% en %% de la NAV'),
                (NULL,'sharpe',   0.50,  0.00,  'Ratio de Sharpe (min)'),
                (NULL,'beta',     1.20,  1.50,  'Bêta vs marché');
        END
        """,
        # ── Plan de comptes interne CIB (DimAccountInternal) ─────────
        """
        IF OBJECT_ID('dbo.DimAccountInternal', 'U') IS NULL
        BEGIN
            CREATE TABLE dbo.DimAccountInternal (
                AccountKey   INT IDENTITY(1,1) NOT NULL PRIMARY KEY,
                AccountCode  NVARCHAR(10)  NOT NULL,
                AccountLabel NVARCHAR(200) NOT NULL,
                AccountType  NVARCHAR(20)  NOT NULL,  -- ASSET/LIABILITY/EQUITY/INCOME/EXPENSE/OFFBALANCE
                IsActive     BIT NOT NULL DEFAULT 1
            );
            CREATE UNIQUE INDEX UX_DimAccount_Code ON dbo.DimAccountInternal(AccountCode);
            -- Plan de comptes CIB minimal (ref: 12_CONTEXTE_CIBLE_CIB_COMPTA.md)
            INSERT INTO dbo.DimAccountInternal (AccountCode, AccountLabel, AccountType) VALUES
                ('110100', 'Cash EUR Nostro',                     'ASSET'),
                ('110200', 'Cash USD Nostro',                     'ASSET'),
                ('120100', 'Titres de transaction - Actions',     'ASSET'),
                ('120200', 'Titres de transaction - Obligations', 'ASSET'),
                ('130100', 'Derives actifs a la juste valeur',    'ASSET'),
                ('130200', 'Derives passifs a la juste valeur',   'LIABILITY'),
                ('140100', 'Creances brokers',                    'ASSET'),
                ('140200', 'Dettes brokers',                      'LIABILITY'),
                ('140300', 'Marges initiales deposees',           'ASSET'),
                ('140400', 'Marges variation a recevoir',         'ASSET'),
                ('140500', 'Marges variation a payer',            'LIABILITY'),
                ('150100', 'Frais a payer - execution',           'LIABILITY'),
                ('150200', 'Taxes sur transactions a payer',      'LIABILITY'),
                ('160100', 'Suspens cash',                        'ASSET'),
                ('160200', 'Suspens titres',                      'ASSET'),
                ('210100', 'Capital / fonds propres internes',    'EQUITY'),
                ('310100', 'Engagements hors bilan - achats',     'OFFBALANCE'),
                ('310200', 'Engagements hors bilan - ventes',     'OFFBALANCE'),
                ('410100', 'PnL realise - trading',               'INCOME'),
                ('410200', 'PnL latent - variation juste valeur', 'INCOME'),
                ('510100', 'Charges de courtage',                 'EXPENSE'),
                ('510200', 'Charges de slippage',                 'EXPENSE'),
                ('510300', 'Charges de financement',              'EXPENSE'),
                ('610100', 'Produits dividendes',                 'INCOME'),
                ('610200', 'Produits coupons',                    'INCOME'),
                ('610300', 'Resultat de change',                  'INCOME');
        END
        """,
        # ── Event comptable (header) ──────────────────────────────────
        """
        IF OBJECT_ID('dbo.FactAccountingEvent', 'U') IS NULL
        BEGIN
            CREATE TABLE dbo.FactAccountingEvent (
                AccountingEventKey INT IDENTITY(1,1) NOT NULL PRIMARY KEY,
                EventTs            DATETIME2(3) NOT NULL DEFAULT SYSUTCDATETIME(),
                EventType          NVARCHAR(30)  NOT NULL,  -- TRADE/FEE/MTM/SETTLEMENT/FX_REVAL
                SourceSystem       NVARCHAR(20)  NOT NULL DEFAULT 'TRADING',
                PortfolioKey       INT NOT NULL,
                TradeKey           INT NULL,
                OrderKey           INT NULL,
                Status             NVARCHAR(15)  NOT NULL DEFAULT 'POSTED',  -- DRAFT/POSTED/REVERSED
                CorrelationId      NVARCHAR(50)  NULL,
                CreatedBy          NVARCHAR(50)  NULL,
                CreatedAt          DATETIME2(3) NOT NULL DEFAULT SYSUTCDATETIME()
            );
            CREATE INDEX IX_AccEvent_Portfolio ON dbo.FactAccountingEvent(PortfolioKey, EventTs DESC);
            CREATE INDEX IX_AccEvent_Trade     ON dbo.FactAccountingEvent(TradeKey);
        END
        """,
        # ── Lignes en partie double (mouvements) ─────────────────────
        """
        IF OBJECT_ID('dbo.FactAccountingMovement', 'U') IS NULL
        BEGIN
            CREATE TABLE dbo.FactAccountingMovement (
                AccountingMovementKey INT IDENTITY(1,1) NOT NULL PRIMARY KEY,
                AccountingEventKey    INT NOT NULL,
                PostingDateKey        INT NOT NULL,
                ValueDateKey          INT NOT NULL,
                AccountKey            INT NOT NULL,
                CurrencyCode          CHAR(3) NOT NULL DEFAULT 'EUR',
                DebitAmount           DECIMAL(18,4) NOT NULL DEFAULT 0,
                CreditAmount          DECIMAL(18,4) NOT NULL DEFAULT 0,
                AmountSigned          AS (DebitAmount - CreditAmount),
                ReferenceId           NVARCHAR(50)  NULL,
                Narrative             NVARCHAR(300) NULL,
                InsertTs              DATETIME2(3) NOT NULL DEFAULT SYSUTCDATETIME()
            );
            CREATE INDEX IX_AccMov_Event   ON dbo.FactAccountingMovement(AccountingEventKey);
            CREATE INDEX IX_AccMov_Account ON dbo.FactAccountingMovement(AccountKey, PostingDateKey DESC);
        END
        """,
        # ── Suivi settlement (dénouement J+2) ────────────────────────
        """
        IF OBJECT_ID('dbo.FactSettlementMovement', 'U') IS NULL
        BEGIN
            CREATE TABLE dbo.FactSettlementMovement (
                SettlementMovementKey INT IDENTITY(1,1) NOT NULL PRIMARY KEY,
                TradeKey              INT NOT NULL,
                OrderKey              INT NULL,
                PortfolioKey          INT NOT NULL,
                SecurityKey           INT NOT NULL,
                TradeDateKey          INT NOT NULL,
                SettleDateKey         INT NOT NULL,
                Side                  NVARCHAR(4)   NOT NULL,
                ExpectedQty           DECIMAL(18,4) NOT NULL,
                SettledQty            DECIMAL(18,4) NOT NULL DEFAULT 0,
                ExpectedCashAmount    DECIMAL(18,2) NOT NULL,
                SettledCashAmount     DECIMAL(18,2) NOT NULL DEFAULT 0,
                SettlementStatus      NVARCHAR(15)  NOT NULL DEFAULT 'PENDING',  -- PENDING/PARTIAL/SETTLED/FAILED
                FailureReason         NVARCHAR(300) NULL,
                LastUpdateTs          DATETIME2(3)  NOT NULL DEFAULT SYSUTCDATETIME()
            );
            CREATE INDEX IX_Settlement_Trade     ON dbo.FactSettlementMovement(TradeKey);
            CREATE INDEX IX_Settlement_Portfolio ON dbo.FactSettlementMovement(PortfolioKey, SettleDateKey);
        END
        """,
        # ── Contrôle de rapprochement EOD ────────────────────────────
        """
        IF OBJECT_ID('dbo.FactReconciliationControl', 'U') IS NULL
        BEGIN
            CREATE TABLE dbo.FactReconciliationControl (
                RecoKey         INT IDENTITY(1,1) NOT NULL PRIMARY KEY,
                DateKey         INT NOT NULL,
                PortfolioKey    INT NULL,
                ControlName     NVARCHAR(50)  NOT NULL,  -- DEBIT_CREDIT_BALANCE / SETTLEMENT / POSITION
                ControlStatus   NVARCHAR(10)  NOT NULL DEFAULT 'OK',  -- OK/WARNING/BREAK
                DifferenceAmount DECIMAL(18,4) NULL,
                Comment         NVARCHAR(500) NULL,
                CheckedBy       NVARCHAR(50)  NULL,
                CheckedAt       DATETIME2(3)  NOT NULL DEFAULT SYSUTCDATETIME()
            );
            CREATE INDEX IX_Reco_Date ON dbo.FactReconciliationControl(DateKey DESC);
        END
        """,
        # ── Enrichissement AppLog (correlation_id, payload) ───────────
        """
        IF NOT EXISTS (
            SELECT 1 FROM sys.columns
            WHERE object_id = OBJECT_ID('dbo.AppLog') AND name = 'correlation_id'
        )
        BEGIN
            ALTER TABLE dbo.AppLog ADD
                correlation_id NVARCHAR(50)  NULL,
                before_payload NVARCHAR(MAX) NULL,
                after_payload  NVARCHAR(MAX) NULL;
        END
        """,
        # ── Dimension Brokers / Contreparties ────────────────────────
        """
        IF OBJECT_ID('dbo.DimBroker', 'U') IS NULL
        BEGIN
            CREATE TABLE dbo.DimBroker (
                BrokerKey    INT IDENTITY(1,1) NOT NULL PRIMARY KEY,
                BrokerCode   NVARCHAR(10)  NOT NULL,
                BrokerName   NVARCHAR(100) NOT NULL,
                BIC          NVARCHAR(11)  NOT NULL,
                Country      NVARCHAR(3)   NOT NULL DEFAULT 'FR',
                MktSegments  NVARCHAR(200) NULL,
                IsActive     BIT NOT NULL DEFAULT 1
            );
            CREATE UNIQUE INDEX UX_DimBroker_Code ON dbo.DimBroker(BrokerCode);
            -- Brokers de démonstration (CIB réels)
            INSERT INTO dbo.DimBroker (BrokerCode, BrokerName, BIC, Country, MktSegments) VALUES
                ('BNPP',   'BNP Paribas CIB',        'BNPAFRPP', 'FRA', 'Equities,Bonds,Forex,Derivatives'),
                ('SGCIB',  'Societe Generale CIB',   'SOGEFRPP', 'FRA', 'Equities,Bonds,Derivatives'),
                ('GS',     'Goldman Sachs Paris',    'GSCOFRP2', 'FRA', 'Equities,Bonds,Forex'),
                ('JPM',    'JPMorgan Securities',    'CHASFRPP', 'FRA', 'Equities,Forex,Derivatives'),
                ('BAML',   'BofA Securities Europe', 'BOFAFRPP', 'FRA', 'Equities,Bonds'),
                ('EXANE',  'Exane BNP Paribas',      'EXANFRPP', 'FRA', 'Equities');
        END
        """,
        # ── Cycle de vie d'un trade (statuts + SWIFT simulés) ────────
        """
        IF OBJECT_ID('dbo.FactTradeLifecycle', 'U') IS NULL
        BEGIN
            CREATE TABLE dbo.FactTradeLifecycle (
                EventKey     INT IDENTITY(1,1) NOT NULL PRIMARY KEY,
                TradeKey     INT NOT NULL,
                OrderKey     INT NULL,
                EventTs      DATETIME2(3) NOT NULL DEFAULT SYSUTCDATETIME(),
                Status       NVARCHAR(30) NOT NULL,
                -- PRE_TRADE_CHECK | ORDER_PLACED | SENT_TO_BROKER | BROKER_ACK
                -- MARKET_EXECUTED | TRADE_CONFIRMED | PENDING_SETTLEMENT
                -- SETTLED | ACCOUNTING_POSTED | RECONCILED
                Actor        NVARCHAR(50)  NULL,
                BrokerKey    INT NULL,
                SwiftMsgType NVARCHAR(10)  NULL,
                SwiftRef     NVARCHAR(40)  NULL,
                Detail       NVARCHAR(500) NULL,
                IsSimulated  BIT NOT NULL DEFAULT 1
            );
            CREATE INDEX IX_TradeLCycle_Trade ON dbo.FactTradeLifecycle(TradeKey, EventTs ASC);
        END
        """,
    ]
    conn = pyodbc.connect(config.conn_str(), autocommit=True)
    cur  = conn.cursor()
    for stmt in ddl_stmts:
        try:
            cur.execute(stmt)
        except pyodbc.Error as e:
            print(f"[DB INIT] Warning: {e}")
    cur.close()
    conn.close()
    print("[DB INIT] Tables applicatives verifiees.")
