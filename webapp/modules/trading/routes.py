"""
Module Trading Desk
─────────────────────────────────────────────────────────────
Qui est concerné : TRADER, QUANT, ADMIN
Ce que ça fait :
  • Visualise les trades exécutés (FactTrades)
  • Lance une simulation de journée
  • Affiche P&L intraday par position
  • Accès aux outils Excel/VBA de pricing (TRADER, QUANT, ADMIN)
"""
import os, subprocess
from datetime import date as _date, datetime
from decimal import Decimal
from flask import Blueprint, render_template, session, send_file, flash, redirect, url_for, abort, jsonify, request
from auth.routes import login_required, role_required
import db, config

_REPO_BASE     = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
_COMMANDO_DIR  = os.path.join(_REPO_BASE, "commando-quant")
_COMMANDO_XLSM = os.path.join(_COMMANDO_DIR, "CommandoQuant.xlsm")
_COMMANDO_VAR  = os.path.join(_COMMANDO_DIR, "var_results.xlsx")

# Outils téléchargeables (xlsx sans macro, rapports)
_VBA_TOOLS = [
    {
        "id":       "commando_quant",
        "label":    "CommandoQuant — Pricing & VaR Dérivés",
        "desc":     "Blotter VBA options : pricing Black-Scholes, Grecques (Δ Γ ν θ ρ), VaR 3 méthodes, stress tests. Connecté à SQL Server CommandoQuant (tbl_Greeks). S'ouvre directement dans Excel.",
        "filepath": _COMMANDO_XLSM,
        "icon":     "lightning-charge-fill",
        "color":    "#4a1a7a",
        "roles":    ["TRADER", "QUANT", "ADMIN"],
        "open_inplace": True,
    },
    {
        "id":       "var_rapport",
        "label":    "Rapport VaR Dérivés (dernier calcul)",
        "desc":     "Rapport Excel généré par le moteur CommandoQuant. Générer d'abord via Monitoring.",
        "filepath": _COMMANDO_VAR,
        "icon":     "file-earmark-bar-graph",
        "color":    "#8b1a1a",
        "roles":    ["TRADER", "QUANT", "ADMIN", "RISK_ANALYST"],
        "open_inplace": True,
    },
]

_REPO_ROOT = _REPO_BASE


trading_bp = Blueprint("trading", __name__, url_prefix="/trading")


@trading_bp.route("/")
@login_required
def index():
    trades     = []
    pnl_today  = {}
    portfolios = []

    try:
        with db.db_cursor() as cur:
            # Liste des portfolios
            cur.execute("SELECT PortfolioKey, PortfolioCode, PortfolioName FROM dbo.DimPortfolio WHERE IsActive=1")
            portfolios = [{"key": r[0], "code": r[1], "name": r[2]} for r in cur.fetchall()]

            # Derniers trades — inclut TradeKey pour lien cinématique
            cur.execute("""
                SELECT TOP 100
                    t.TradeKey, d.FullDate, p.PortfolioCode, s.Ticker, t.Side,
                    t.Quantity, t.Price, t.FeeAmount, t.SlippageAmount,
                    t.Quantity * t.Price as notional,
                    -- Statut le plus avancé du cycle de vie (NULL si pas encore généré)
                    (SELECT TOP 1 Status FROM dbo.FactTradeLifecycle
                     WHERE TradeKey = t.TradeKey ORDER BY EventTs DESC) as lifecycle_status
                FROM dbo.FactTrades t
                JOIN dbo.DimDate d      ON d.DateKey      = t.TradeDateKey
                JOIN dbo.DimPortfolio p ON p.PortfolioKey = t.PortfolioKey
                JOIN dbo.DimSecurity  s ON s.SecurityKey  = t.SecurityKey
                ORDER BY d.FullDate DESC, t.TradeKey DESC
            """)
            for r in cur.fetchall():
                trades.append({
                    "trade_key": r[0],
                    "date":      str(r[1])[:10],
                    "portfolio": r[2],
                    "ticker":    r[3],
                    "side":      r[4],
                    "qty":       int(r[5] or 0),
                    "price":     round(float(r[6] or 0), 4),
                    "fee":       round(float(r[7] or 0), 2),
                    "slippage":  round(float(r[8] or 0), 2),
                    "notional":  round(float(r[9] or 0), 2),
                    "lifecycle_status": r[10] or None,
                })
    except Exception as e:
        trades = []

    # Stats rapides
    buy_count  = sum(1 for t in trades if t["side"] == "BUY")
    sell_count = sum(1 for t in trades if t["side"] == "SELL")
    total_notional = sum(t["notional"] for t in trades)
    total_fees = sum(t["fee"] + t["slippage"] for t in trades)

    # Outils VBA filtrés par rôle
    user_role = session.get("role", "")
    vba_tools = [t for t in _VBA_TOOLS if user_role in t["roles"]]

    return render_template(
        "modules/trading/index.html",
        trades=trades, portfolios=portfolios,
        buy_count=buy_count, sell_count=sell_count,
        total_notional=total_notional, total_fees=total_fees,
        vba_tools=vba_tools,
    )


@trading_bp.route("/vba/<tool_id>")
@login_required
def download_vba(tool_id):
    """Téléchargement ou ouverture d'un fichier Excel/VBA."""
    user_role = session.get("role", "")
    tool = next((t for t in _VBA_TOOLS if t["id"] == tool_id), None)

    if not tool:
        abort(404)
    if user_role not in tool["roles"]:
        flash("Accès non autorisé pour votre rôle.", "danger")
        return redirect(url_for("trading.index"))

    # Outil avec chemin absolu (open_inplace) → ouvre dans Excel sur la machine serveur
    if tool.get("open_inplace"):
        filepath = tool["filepath"]
        if not os.path.exists(filepath):
            flash(f"Fichier introuvable : {filepath}", "warning")
            return redirect(url_for("trading.index"))
        try:
            os.startfile(filepath)
            db.app_log("trading", f"OPEN INPLACE — {os.path.basename(filepath)}", username=session.get("username"))
            flash(f"{tool['label']} ouvert dans Excel.", "success")
        except Exception as e:
            flash(f"Impossible d'ouvrir le fichier : {e}", "danger")
        return redirect(url_for("trading.index"))

    # Outil téléchargeable classique
    filepath = os.path.join(_REPO_ROOT, tool["subdir"], tool["filename"])
    if not os.path.exists(filepath):
        flash(f"Fichier introuvable : {tool['filename']}", "warning")
        return redirect(url_for("trading.index"))

    db.app_log("trading", f"VBA DOWNLOAD — {tool['filename']}", username=session.get("username"))
    return send_file(filepath, as_attachment=True, download_name=tool["filename"])


@trading_bp.route("/order/new", methods=["POST"])
@login_required
@role_required("TRADER", "ADMIN")
def order_new():
    """
    Saisie manuelle d'un ordre.
    Flux : SUBMITTED → pré-trade risk check → EXECUTED (ou BLOCKED)
    Enregistre dans :
      dbo.Orders, dbo.FactTrades,
      dbo.FactAccountingEvent + dbo.FactAccountingMovement (plan CIB),
      dbo.JournalEntries (compat. legacy),
      dbo.FactSettlementMovement (PENDING J+2)
    """
    import uuid
    from datetime import timedelta

    username       = session.get("username", "unknown")
    correlation_id = str(uuid.uuid4())[:16]

    try:
        portfolio_key = int(request.form["portfolio_key"])
        ticker        = request.form["ticker"].strip().upper()
        side          = request.form["side"].upper()
        qty           = Decimal(request.form["qty"])
        price         = Decimal(request.form["price"])
        order_type    = request.form.get("order_type", "MARKET").upper()
        fee_bps       = Decimal(request.form.get("fee_bps", "10"))
        notes         = request.form.get("notes", "").strip() or None

        if side not in ("BUY", "SELL"):
            flash("Côté invalide (BUY ou SELL attendu).", "danger")
            return redirect(url_for("trading.index"))
        if qty <= 0 or price <= 0:
            flash("Quantité et prix doivent être positifs.", "danger")
            return redirect(url_for("trading.index"))

        notional   = qty * price
        fee_amount = notional * fee_bps / Decimal("10000")
        slippage   = notional * Decimal("0.0005")
        today      = _date.today()
        settle_d   = today + timedelta(days=2)   # J+2 standard

        # ── Pré-trade risk check ──────────────────────────────────────
        # Vérifie que le notional de l'ordre ne dépasse pas une limite globale simple.
        # Si RiskLimits contient 'max_order_notional', on compare.
        risk_limits = db.get_risk_limits(portfolio_key)
        blocked     = False
        block_reason = ""
        max_notional_limit = risk_limits.get("max_order_notional")
        if max_notional_limit:
            breach_val = max_notional_limit.get("breach")
            if breach_val and float(notional) > breach_val:
                blocked = True
                block_reason = (f"Notional {float(notional):,.0f} EUR dépasse la limite "
                                f"max_order_notional ({breach_val:,.0f} EUR)")

        order_status = "BLOCKED" if blocked else "EXECUTED"

        db.app_log("trading", f"ORDER SUBMIT {side} {qty} {ticker} @ {price}",
                   detail=f"portfolio={portfolio_key} notional={float(notional):.2f} status={order_status}",
                   username=username, correlation_id=correlation_id)

        if blocked:
            # Enregistre l'ordre bloqué sans toucher les tables comptables
            with db.db_cursor() as cur:
                cur.execute("""
                    INSERT INTO dbo.Orders
                        (PortfolioKey, Ticker, Side, OrderQty, OrderPrice, OrderType, Status,
                         FeeAmount, SlippageAmount, Notional, CurrencyCode, CreatedBy, Notes)
                    VALUES (?,?,?,?,?,?,?,  ?,?,?,?,?,?)
                """,
                    portfolio_key, ticker, side, float(qty), float(price), order_type, "BLOCKED",
                    float(fee_amount), float(slippage), float(notional), "EUR", username,
                    f"[PRE-TRADE BLOCK] {block_reason}"
                )
            db.app_log("trading", "ORDER BLOCKED", detail=block_reason,
                       level="WARN", username=username, correlation_id=correlation_id)
            flash(f"Ordre BLOQUE par le contrôle pre-trade : {block_reason}", "warning")
            return redirect(url_for("trading.index"))

        with db.db_cursor() as cur:
            # 1 — Carnet d'ordres (EXECUTED)
            cur.execute("""
                INSERT INTO dbo.Orders
                    (PortfolioKey, Ticker, Side, OrderQty, OrderPrice, OrderType, Status,
                     ExecutedQty, ExecutedPrice, ExecutedAt,
                     FeeAmount, SlippageAmount, Notional, CurrencyCode, CreatedBy, Notes)
                OUTPUT INSERTED.OrderKey
                VALUES (?,?,?,?,?,?,?,  ?,?,SYSUTCDATETIME(),  ?,?,?,?,?,?)
            """,
                portfolio_key, ticker, side, float(qty), float(price), order_type, "EXECUTED",
                float(qty), float(price),
                float(fee_amount), float(slippage), float(notional), "EUR", username, notes
            )
            order_key = cur.fetchone()[0]

            # 2 — DimSecurity
            cur.execute("SELECT SecurityKey FROM dbo.DimSecurity WHERE Ticker=?", ticker)
            row = cur.fetchone()
            if row:
                security_key = row[0]
            else:
                cur.execute("""
                    INSERT INTO dbo.DimSecurity
                        (Ticker, SecurityName, AssetClass, CurrencyCode, IsActive)
                    VALUES (?,?,'EQUITY','EUR',1)
                """, ticker, ticker)
                cur.execute("SELECT SecurityKey FROM dbo.DimSecurity WHERE Ticker=?", ticker)
                security_key = cur.fetchone()[0]

            # 3 — DimDate trade + settle
            date_key    = int(today.strftime("%Y%m%d"))
            settle_key  = int(settle_d.strftime("%Y%m%d"))
            import calendar as _cal
            _MONTH_NAMES = ['January','February','March','April','May','June',
                            'July','August','September','October','November','December']
            for dk, dd in [(date_key, today), (settle_key, settle_d)]:
                cur.execute("SELECT DateKey FROM dbo.DimDate WHERE DateKey=?", dk)
                if not cur.fetchone():
                    last_day = _cal.monthrange(dd.year, dd.month)[1]
                    cur.execute("""
                        INSERT INTO dbo.DimDate
                            (DateKey, FullDate, CalendarYear, CalendarMonth, CalendarDay,
                             MonthName, QuarterNumber, WeekOfYear, IsMonthEnd)
                        VALUES (?,?,?,?,?,  ?,?,?,?)
                    """, dk, dd, dd.year, dd.month, dd.day,
                         _MONTH_NAMES[dd.month - 1],
                         (dd.month - 1) // 3 + 1,
                         dd.isocalendar()[1],
                         1 if dd.day == last_day else 0)

            # 4 — FactTrades
            cur.execute("""
                INSERT INTO dbo.FactTrades
                    (TradeDateKey, SettleDateKey, PortfolioKey, SecurityKey,
                     Side, Quantity, Price, FeeAmount, SlippageAmount,
                     CurrencyCode, OrderType, ExecutionTs)
                OUTPUT INSERTED.TradeKey
                VALUES (?,?,?,?,  ?,?,?,?,?,  ?,?,SYSUTCDATETIME())
            """,
                date_key, settle_key, portfolio_key, security_key,
                side, float(qty), float(price),
                float(fee_amount), float(slippage),
                "EUR", order_type
            )
            trade_key = cur.fetchone()[0]

            # 5 — Plan de comptes CIB (DimAccountInternal)
            #   BUY trade date :
            #     Débit  120100 Titres de transaction - Actions
            #     Crédit 140200 Dettes brokers
            #   SELL trade date :
            #     Débit  140100 Créances brokers
            #     Crédit 120100 Titres de transaction - Actions
            #   Frais :
            #     Débit  510100 Charges de courtage
            #     Crédit 150100 Frais à payer - exécution
            acc_map = {}
            cur.execute("""
                SELECT AccountCode, AccountKey FROM dbo.DimAccountInternal
                WHERE AccountCode IN ('120100','140100','140200','150100','510100','110100')
            """)
            for r in cur.fetchall():
                acc_map[r[0]] = r[1]

            if side == "BUY":
                trade_debit_acc  = acc_map.get("120100")  # Titres transaction
                trade_credit_acc = acc_map.get("140200")  # Dettes brokers
            else:
                trade_debit_acc  = acc_map.get("140100")  # Créances brokers
                trade_credit_acc = acc_map.get("120100")  # Titres transaction
            fee_debit_acc   = acc_map.get("510100")  # Charges courtage
            fee_credit_acc  = acc_map.get("150100")  # Frais à payer

            # 5a — Event TRADE
            cur.execute("""
                INSERT INTO dbo.FactAccountingEvent
                    (EventType, SourceSystem, PortfolioKey, TradeKey, OrderKey,
                     Status, CorrelationId, CreatedBy)
                OUTPUT INSERTED.AccountingEventKey
                VALUES ('TRADE','TRADING',?,?,?,'POSTED',?,?)
            """, portfolio_key, trade_key, order_key, correlation_id, username)
            event_key_trade = cur.fetchone()[0]

            # Ligne débit trade
            if trade_debit_acc:
                cur.execute("""
                    INSERT INTO dbo.FactAccountingMovement
                        (AccountingEventKey, PostingDateKey, ValueDateKey, AccountKey,
                         CurrencyCode, DebitAmount, CreditAmount, ReferenceId, Narrative)
                    VALUES (?,?,?,?,  'EUR',?,0,  ?,?)
                """, event_key_trade, date_key, settle_key, trade_debit_acc,
                     float(notional), str(order_key),
                     f"{side} {float(qty):.0f} {ticker} @ {float(price):.4f}")
            # Ligne crédit trade
            if trade_credit_acc:
                cur.execute("""
                    INSERT INTO dbo.FactAccountingMovement
                        (AccountingEventKey, PostingDateKey, ValueDateKey, AccountKey,
                         CurrencyCode, DebitAmount, CreditAmount, ReferenceId, Narrative)
                    VALUES (?,?,?,?,  'EUR',0,?,  ?,?)
                """, event_key_trade, date_key, settle_key, trade_credit_acc,
                     float(notional), str(order_key),
                     f"{side} {float(qty):.0f} {ticker} @ {float(price):.4f}")

            # 5b — Event FEE
            cur.execute("""
                INSERT INTO dbo.FactAccountingEvent
                    (EventType, SourceSystem, PortfolioKey, TradeKey, OrderKey,
                     Status, CorrelationId, CreatedBy)
                OUTPUT INSERTED.AccountingEventKey
                VALUES ('FEE','TRADING',?,?,?,'POSTED',?,?)
            """, portfolio_key, trade_key, order_key, correlation_id, username)
            event_key_fee = cur.fetchone()[0]

            if fee_debit_acc:
                cur.execute("""
                    INSERT INTO dbo.FactAccountingMovement
                        (AccountingEventKey, PostingDateKey, ValueDateKey, AccountKey,
                         CurrencyCode, DebitAmount, CreditAmount, ReferenceId, Narrative)
                    VALUES (?,?,?,?,  'EUR',?,0,  ?,?)
                """, event_key_fee, date_key, date_key, fee_debit_acc,
                     float(fee_amount), str(order_key), f"Courtage {ticker}")
            if fee_credit_acc:
                cur.execute("""
                    INSERT INTO dbo.FactAccountingMovement
                        (AccountingEventKey, PostingDateKey, ValueDateKey, AccountKey,
                         CurrencyCode, DebitAmount, CreditAmount, ReferenceId, Narrative)
                    VALUES (?,?,?,?,  'EUR',0,?,  ?,?)
                """, event_key_fee, date_key, date_key, fee_credit_acc,
                     float(fee_amount), str(order_key), f"Courtage {ticker}")

            # 6 — JournalEntries (compat. legacy — conservé pour l'affichage accounting)
            if side == "BUY":
                acc_d_leg, acc_c_leg = "120100 Titres transaction", "140200 Dettes brokers"
            else:
                acc_d_leg, acc_c_leg = "140100 Creances brokers", "120100 Titres transaction"

            for entry_type, label, amount, ad, ac in [
                ("TRADE_GROSS",
                 f"{side} {float(qty):.0f} {ticker} @ {float(price):.4f}",
                 float(notional), acc_d_leg, acc_c_leg),
                ("TRADE_FEE",
                 f"Courtage {ticker}",
                 float(fee_amount), "510100 Charges courtage", "150100 Frais a payer"),
            ]:
                cur.execute("""
                    INSERT INTO dbo.JournalEntries
                        (EntryDate, PortfolioKey, TradeKey, OrderKey,
                         AccountDebit, AccountCredit, Amount, Currency,
                         Label, EntryType, CreatedBy)
                    VALUES (?,?,?,?,  ?,?,?,?,  ?,?,?)
                """, today, portfolio_key, trade_key, order_key,
                     ad, ac, amount, "EUR", label, entry_type, username)

            # 7 — Settlement PENDING (J+2)
            cur.execute("""
                INSERT INTO dbo.FactSettlementMovement
                    (TradeKey, OrderKey, PortfolioKey, SecurityKey,
                     TradeDateKey, SettleDateKey, Side,
                     ExpectedQty, ExpectedCashAmount, SettlementStatus)
                VALUES (?,?,?,?,  ?,?,?,  ?,?,?)
            """,
                trade_key, order_key, portfolio_key, security_key,
                date_key, settle_key, side,
                float(qty), float(notional + fee_amount), "PENDING"
            )

        db.app_log("trading", f"ORDER EXECUTED {side} {qty} {ticker} @ {price}",
                   detail=f"notional={float(notional):.2f} fee={float(fee_amount):.2f} settle={settle_d}",
                   username=username, rows_affected=1,
                   correlation_id=correlation_id,
                   after_payload=f"trade_key={trade_key} order_key={order_key}")

        # ── Cycle de vie du trade (broker, SWIFT simulés) ─────────────
        try:
            db.create_trade_lifecycle(
                trade_key=trade_key, order_key=order_key,
                portfolio_key=portfolio_key,
                ticker=ticker, side=side,
                qty=float(qty), price=float(price),
                notional=float(notional), fee=float(fee_amount),
                settle_date=settle_d, username=username,
                correlation_id=correlation_id
            )
        except Exception as lc_err:
            db.app_log("trading", "LIFECYCLE CREATE WARNING",
                       detail=str(lc_err)[:200], level="WARN", username=username)

        flash(
            f"Ordre {side} {int(qty)} {ticker} @ {float(price):.4f} EUR exécuté "
            f"(TradeKey={trade_key}, Settlement {settle_d.strftime('%d/%m/%Y')}).",
            "success"
        )

    except (KeyError, ValueError, TypeError) as e:
        flash(f"Données invalides : {e}", "danger")
    except Exception as e:
        db.app_log("trading", "ORDER ERROR", detail=str(e)[:300], level="ERROR",
                   username=username, correlation_id=correlation_id)
        flash(f"Erreur lors de l'enregistrement : {e}", "danger")

    return redirect(url_for("trading.index"))


@trading_bp.route("/trade/<int:trade_key>")
@login_required
def trade_lifecycle(trade_key: int):
    """
    Vue cinématique d'un trade : cycle de vie complet, broker, SWIFT, comptabilité.
    Accessible : TRADER, QUANT, RISK_ANALYST, ADMIN
    """
    trade    = None
    events   = []
    broker   = None
    swift_msgs = []
    accounting = []

    try:
        with db.db_cursor() as cur:
            # ── Trade principal (FactTrades Gold — pas d'OrderKey dans ce schéma) ──
            cur.execute("""
                SELECT t.TradeKey, d.FullDate, p.PortfolioCode, p.PortfolioName,
                       s.Ticker, t.Side, t.Quantity, t.Price, t.FeeAmount, t.SlippageAmount,
                       t.Quantity * t.Price AS notional, t.CurrencyCode, t.OrderType,
                       t.ExecutionTs, sd.FullDate AS settle_date
                FROM dbo.FactTrades t
                JOIN dbo.DimDate d      ON d.DateKey      = t.TradeDateKey
                JOIN dbo.DimDate sd     ON sd.DateKey     = t.SettleDateKey
                JOIN dbo.DimPortfolio p ON p.PortfolioKey = t.PortfolioKey
                JOIN dbo.DimSecurity  s ON s.SecurityKey  = t.SecurityKey
                WHERE t.TradeKey = ?
            """, trade_key)
            row = cur.fetchone()
            if not row:
                flash(f"Trade {trade_key} introuvable.", "warning")
                return redirect(url_for("trading.index"))
            notional = float(row[10] or 0)
            fee      = float(row[8]  or 0)
            trade = {
                "key":           row[0],
                "order_key":     None,
                "date":          str(row[1])[:10],
                "portfolio_code":row[2],
                "portfolio":     row[3],
                "ticker":        row[4],
                "side":          row[5],
                "qty":           float(row[6] or 0),
                "price":         round(float(row[7] or 0), 4),
                "fee":           round(fee, 2),
                "slippage":      round(float(row[9] or 0), 2),
                "notional":      round(notional, 2),
                "currency":      row[11],
                "order_type":    row[12],
                "exec_ts":       str(row[13])[:19] if row[13] else "—",
                "settle_date":   str(row[14])[:10] if row[14] else "—",
                "total_cost":    round(notional + fee, 2),
                "order_status":  None,
                "created_by":    None,
            }

            # ── Ordre associé via FactTradeLifecycle.OrderKey (si disponible) ──
            cur.execute("""
                SELECT TOP 1 lc.OrderKey FROM dbo.FactTradeLifecycle lc
                WHERE lc.TradeKey = ? AND lc.OrderKey IS NOT NULL
            """, trade_key)
            lc_ord = cur.fetchone()
            if lc_ord:
                trade["order_key"] = lc_ord[0]
                cur.execute("""
                    SELECT o.Status, o.CreatedBy FROM dbo.Orders o WHERE o.OrderKey = ?
                """, lc_ord[0])
                ord_row = cur.fetchone()
                if ord_row:
                    trade["order_status"] = ord_row[0]
                    trade["created_by"]   = ord_row[1]

            # ── Cycle de vie ─────────────────────────────────────────
            cur.execute("""
                SELECT lc.EventKey, lc.EventTs, lc.Status, lc.Actor,
                       lc.BrokerKey, b.BrokerName, b.BIC,
                       lc.SwiftMsgType, lc.SwiftRef, lc.Detail
                FROM dbo.FactTradeLifecycle lc
                LEFT JOIN dbo.DimBroker b ON b.BrokerKey = lc.BrokerKey
                WHERE lc.TradeKey = ?
                ORDER BY lc.EventTs ASC
            """, trade_key)
            for r in cur.fetchall():
                events.append({
                    "key":        r[0],
                    "ts":         str(r[1])[:19] if r[1] else "—",
                    "status":     r[2],
                    "actor":      r[3] or "—",
                    "broker_key": r[4],
                    "broker":     r[5] or "—",
                    "bic":        r[6] or "—",
                    "swift_type": r[7],
                    "swift_ref":  r[8],
                    "detail":     r[9] or "",
                })

            # ── Broker principal (premier événement avec broker) ──────
            for ev in events:
                if ev["broker_key"]:
                    broker = {"name": ev["broker"], "bic": ev["bic"]}
                    break

            # ── Messages SWIFT (événements avec SwiftMsgType) ────────
            swift_msgs = [ev for ev in events if ev["swift_type"]]

            # ── Écritures comptables ─────────────────────────────────
            cur.execute("""
                SELECT ae.EventType, ae.Status, ae.EventTs,
                       a.AccountCode, a.AccountLabel, a.AccountType,
                       am.DebitAmount, am.CreditAmount, am.Narrative
                FROM dbo.FactAccountingEvent ae
                JOIN dbo.FactAccountingMovement am ON am.AccountingEventKey = ae.AccountingEventKey
                JOIN dbo.DimAccountInternal a       ON a.AccountKey = am.AccountKey
                WHERE ae.TradeKey = ?
                ORDER BY ae.AccountingEventKey, am.AccountingMovementKey
            """, trade_key)
            for r in cur.fetchall():
                accounting.append({
                    "event_type": r[0], "status": r[1],
                    "ts":         str(r[2])[:16] if r[2] else "—",
                    "acc_code":   r[3], "acc_label": r[4], "acc_type": r[5],
                    "debit":      float(r[6] or 0),
                    "credit":     float(r[7] or 0),
                    "narrative":  r[8] or "",
                })

            # ── Settlement ───────────────────────────────────────────
            cur.execute("""
                SELECT SettlementStatus, ExpectedQty, ExpectedCashAmount,
                       SettledQty, SettledCashAmount, LastUpdateTs
                FROM dbo.FactSettlementMovement WHERE TradeKey = ?
            """, trade_key)
            sm = cur.fetchone()
            trade["settlement"] = {
                "status":     sm[0] if sm else "—",
                "exp_qty":    float(sm[1] or 0) if sm else 0,
                "exp_cash":   float(sm[2] or 0) if sm else 0,
                "settled_qty":float(sm[3] or 0) if sm else 0,
                "settled_cash":float(sm[4] or 0) if sm else 0,
                "last_update":str(sm[5])[:19] if sm and sm[5] else "—",
            } if sm else None

    except Exception as e:
        flash(f"Erreur : {e}", "danger")
        return redirect(url_for("trading.index"))

    if trade is None:
        flash("Trade introuvable.", "warning")
        return redirect(url_for("trading.index"))

    # Statuts ordonnés pour la timeline
    STATUS_ORDER = [
        "PRE_TRADE_CHECK", "ORDER_PLACED", "SENT_TO_BROKER", "BROKER_ACK",
        "MARKET_EXECUTED", "TRADE_CONFIRMED", "PENDING_SETTLEMENT",
        "SETTLED", "ACCOUNTING_POSTED", "RECONCILED"
    ]
    completed_statuses = {ev["status"] for ev in events}
    last_status = events[-1]["status"] if events else None

    return render_template(
        "modules/trading/trade_lifecycle.html",
        trade=trade, events=events, broker=broker,
        swift_msgs=swift_msgs, accounting=accounting,
        status_order=STATUS_ORDER, completed=completed_statuses,
        last_status=last_status,
    )
