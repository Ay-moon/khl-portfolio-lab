"""
Module Comptabilité — Journal en partie double (plan CIB)
───────────────────────────────────────────────────────────────────
Qui est concerné : ASSET_MANAGER, TRADER, RISK_ANALYST, ALM_OFFICER, ADMIN
Ce que ça fait :
  • Journal FactAccountingMovement (plan comptes CIB : 120100, 140200, 510100…)
  • Balance des comptes par AccountCode
  • Suivi settlement PENDING/SETTLED par portefeuille
  • Contrôles de rapprochement EOD (FactReconciliationControl)
  Ref : docs/12_CONTEXTE_CIBLE_CIB_COMPTA.md
"""
from flask import Blueprint, render_template, session, request
from auth.routes import login_required, role_required
import db

accounting_bp = Blueprint("accounting", __name__, url_prefix="/accounting")


@accounting_bp.route("/")
@login_required
@role_required("COMPTABLE", "DATA_ANALYST", "ADMIN")
def index():
    portfolios = db.get_portfolios()
    pf_key     = request.args.get("portfolio_key", type=int)

    movements    = []
    balance      = []
    settlements  = []
    reco_history = []
    total_debit  = 0.0
    total_credit = 0.0

    try:
        with db.db_cursor() as cur:

            # ── Mouvements FactAccountingMovement ────────────────────
            sql = """
                SELECT TOP 200
                    m.AccountingMovementKey,
                    FORMAT(e.EventTs,'yyyy-MM-dd HH:mm') as ts,
                    p.PortfolioCode,
                    a.AccountCode, a.AccountLabel, a.AccountType,
                    m.CurrencyCode,
                    m.DebitAmount, m.CreditAmount,
                    m.Narrative, e.EventType, e.Status as EvtStatus,
                    e.CorrelationId,
                    m.PostingDateKey
                FROM dbo.FactAccountingMovement m
                JOIN dbo.FactAccountingEvent    e ON e.AccountingEventKey = m.AccountingEventKey
                JOIN dbo.DimAccountInternal     a ON a.AccountKey         = m.AccountKey
                JOIN dbo.DimPortfolio           p ON p.PortfolioKey       = e.PortfolioKey
                WHERE 1=1
            """
            params = []
            if pf_key:
                sql += " AND e.PortfolioKey = ?"
                params.append(pf_key)
            sql += " ORDER BY m.AccountingMovementKey DESC"
            cur.execute(sql, *params)
            for r in cur.fetchall():
                movements.append({
                    "key":        r[0],
                    "ts":         r[1],
                    "portfolio":  r[2],
                    "acc_code":   r[3],
                    "acc_label":  r[4],
                    "acc_type":   r[5],
                    "currency":   r[6],
                    "debit":      float(r[7]),
                    "credit":     float(r[8]),
                    "narrative":  r[9] or "",
                    "event_type": r[10],
                    "evt_status": r[11],
                    "corr_id":    r[12] or "",
                    "date_key":   r[13],
                })
            total_debit  = sum(m["debit"]  for m in movements)
            total_credit = sum(m["credit"] for m in movements)

            # ── Balance des comptes ───────────────────────────────────
            sql_bal = """
                SELECT a.AccountCode, a.AccountLabel, a.AccountType,
                       ISNULL(SUM(m.DebitAmount),0)  as total_debit,
                       ISNULL(SUM(m.CreditAmount),0) as total_credit
                FROM dbo.FactAccountingMovement m
                JOIN dbo.FactAccountingEvent    e ON e.AccountingEventKey = m.AccountingEventKey
                JOIN dbo.DimAccountInternal     a ON a.AccountKey         = m.AccountKey
                {where}
                GROUP BY a.AccountCode, a.AccountLabel, a.AccountType
                ORDER BY a.AccountCode
            """.format(where="WHERE e.PortfolioKey=?" if pf_key else "")
            if pf_key:
                cur.execute(sql_bal, pf_key)
            else:
                cur.execute(sql_bal)
            for r in cur.fetchall():
                d = float(r[3])
                c = float(r[4])
                balance.append({
                    "code":   r[0], "label": r[1], "type": r[2],
                    "debit":  d, "credit": c, "net": d - c,
                })

            # ── Settlements PENDING ───────────────────────────────────
            sql_stl = """
                SELECT TOP 50
                    s.SettlementMovementKey,
                    p.PortfolioCode, sec.Ticker, s.Side,
                    s.ExpectedQty, s.ExpectedCashAmount,
                    s.SettlementStatus, s.SettleDateKey,
                    FORMAT(s.LastUpdateTs,'yyyy-MM-dd HH:mm') as updated
                FROM dbo.FactSettlementMovement s
                JOIN dbo.DimPortfolio p   ON p.PortfolioKey = s.PortfolioKey
                JOIN dbo.DimSecurity  sec ON sec.SecurityKey= s.SecurityKey
                WHERE 1=1
            """
            stl_params = []
            if pf_key:
                sql_stl += " AND s.PortfolioKey = ?"
                stl_params.append(pf_key)
            sql_stl += " ORDER BY s.SettlementMovementKey DESC"
            cur.execute(sql_stl, *stl_params)
            for r in cur.fetchall():
                settlements.append({
                    "key":       r[0],
                    "portfolio": r[1],
                    "ticker":    r[2],
                    "side":      r[3],
                    "qty":       float(r[4]),
                    "cash":      float(r[5]),
                    "status":    r[6],
                    "settle_dk": r[7],
                    "updated":   r[8],
                })

            # ── Historique contrôles rapprochement ────────────────────
            cur.execute("""
                SELECT TOP 10
                    DateKey, ControlName, ControlStatus,
                    DifferenceAmount, Comment,
                    FORMAT(CheckedAt,'yyyy-MM-dd HH:mm') as ts
                FROM dbo.FactReconciliationControl
                ORDER BY RecoKey DESC
            """)
            for r in cur.fetchall():
                reco_history.append({
                    "date_key": r[0], "control": r[1], "status": r[2],
                    "diff": float(r[3]) if r[3] is not None else 0.0,
                    "comment": r[4] or "", "ts": r[5],
                })

    except Exception as e:
        db.app_log("accounting", "LOAD ERROR", detail=str(e)[:300],
                   level="ERROR", username=session.get("username"))

    balanced = abs(total_debit - total_credit) < 0.01

    return render_template(
        "modules/accounting/index.html",
        movements=movements,
        balance=balance,
        settlements=settlements,
        reco_history=reco_history,
        portfolios=portfolios,
        selected_pf=pf_key,
        total_debit=total_debit,
        total_credit=total_credit,
        balanced=balanced,
        move_count=len(movements),
        pending_count=sum(1 for s in settlements if s["status"] == "PENDING"),
    )
