"""
Module Performance & Reporting
─────────────────────────────────────────────────────────────
Qui est concerné : ASSET_MANAGER, RISK_ANALYST, DATA_ANALYST
Ce que ça fait :
  • Dashboard NAV, ReturnPct, CumPnL, PnL journalier
  • Attribution de performance (si données dispo)
  • Lien Power BI
"""
from flask import Blueprint, render_template, request, session, flash, redirect, url_for
from auth.routes import login_required, role_required
import db

performance_bp = Blueprint("performance", __name__, url_prefix="/performance")


@performance_bp.route("/")
@login_required
def index():
    portfolio_code = request.args.get("portfolio", "MAIN")
    pnl_data = []
    risk_data = {}
    portfolio_info = {}

    try:
        with db.db_cursor() as cur:
            # Infos portfolio
            cur.execute(
                "SELECT PortfolioKey, PortfolioCode, PortfolioName, BaseCurrency "
                "FROM dbo.DimPortfolio WHERE PortfolioCode = ?",
                portfolio_code
            )
            row = cur.fetchone()
            if row:
                portfolio_info = {"key": row[0], "code": row[1], "name": row[2], "currency": row[3]}

                # PnL historique (60 derniers jours)
                cur.execute("""
                    SELECT d.FullDate, pl.Nav, pl.DailyPnL, pl.CumPnL, pl.ReturnPct
                    FROM dbo.PortfolioPnLDaily pl
                    JOIN dbo.DimDate d ON d.DateKey = pl.DateKey
                    WHERE pl.PortfolioKey = ?
                    ORDER BY d.FullDate ASC
                """, portfolio_info["key"])
                for r in cur.fetchall():
                    pnl_data.append({
                        "date":       str(r[0])[:10],
                        "nav":        round(float(r[1] or 0), 2),
                        "daily_pnl":  round(float(r[2] or 0), 2),
                        "cum_pnl":    round(float(r[3] or 0), 2),
                        "return_pct": round(float(r[4] or 0) * 100, 4),
                    })

                # Métriques risque (dernière date)
                cur.execute("""
                    SELECT TOP 1
                        rm.Volatility20d, rm.MaxDrawdown, rm.VaR95,
                        rm.SharpeRatio, rm.Beta
                    FROM dbo.RiskMetricsDaily rm
                    WHERE rm.PortfolioKey = ?
                    ORDER BY rm.DateKey DESC
                """, portfolio_info["key"])
                r2 = cur.fetchone()
                if r2:
                    risk_data = {
                        "vol20d":   round(float(r2[0] or 0) * 100, 2),
                        "drawdown": round(float(r2[1] or 0) * 100, 2),
                        "var95":    round(float(r2[2] or 0) * 100, 2),
                        "sharpe":   round(float(r2[3] or 0), 2),
                        "beta":     round(float(r2[4] or 0), 2),
                    }

            # Tous les portfolios pour le sélecteur
            cur.execute("SELECT PortfolioCode, PortfolioName FROM dbo.DimPortfolio WHERE IsActive=1 ORDER BY PortfolioCode")
            all_portfolios = [{"code": r[0], "name": r[1]} for r in cur.fetchall()]

    except Exception as e:
        all_portfolios = []

    # KPIs résumés
    latest_nav    = pnl_data[-1]["nav"] if pnl_data else 0
    total_return  = pnl_data[-1]["cum_pnl"] if pnl_data else 0
    best_day      = max((p["daily_pnl"] for p in pnl_data), default=0)
    worst_day     = min((p["daily_pnl"] for p in pnl_data), default=0)

    return render_template(
        "modules/performance/index.html",
        portfolio_code=portfolio_code,
        portfolio_info=portfolio_info,
        pnl_data=pnl_data,
        risk_data=risk_data,
        all_portfolios=all_portfolios,
        latest_nav=latest_nav,
        total_return=total_return,
        best_day=best_day,
        worst_day=worst_day,
    )


@performance_bp.route("/powerbi", methods=["GET", "POST"])
@login_required
def powerbi():
    """
    Power BI Service — configuration + accès iframe.
    - Tout utilisateur ayant 'powerbi' dans ses modules peut accéder.
    - Seul ADMIN peut modifier la configuration.
    - Stockage dans AppSettings : powerbi.server, powerbi.service_name,
      powerbi.login, powerbi.password, powerbi.service_url (URL rapport embed).
    """
    is_admin = session.get("role") == "ADMIN"
    msg   = None
    error = None

    # Lecture config actuelle
    pbi_server   = db.get_setting("powerbi.server", "")
    pbi_name     = db.get_setting("powerbi.service_name", "")
    pbi_login    = db.get_setting("powerbi.login", "")
    pbi_password = db.get_setting("powerbi.password", "")
    pbi_url      = db.get_setting("powerbi.service_url", "")

    is_configured = bool(pbi_server and pbi_login)

    if request.method == "POST":
        if not is_admin:
            flash("Seul un administrateur peut modifier la configuration Power BI.", "danger")
            return redirect(url_for("performance.powerbi"))

        action = request.form.get("action")

        if action == "save_config":
            new_server   = request.form.get("pbi_server", "").strip()
            new_name     = request.form.get("pbi_name", "").strip()
            new_login    = request.form.get("pbi_login", "").strip()
            new_password = request.form.get("pbi_password", "").strip()
            new_url      = request.form.get("pbi_url", "").strip()

            if not new_server:
                error = "L'adresse du serveur est obligatoire."
            elif not new_login:
                error = "Le login de service est obligatoire."
            else:
                try:
                    db.set_setting("powerbi.server",       new_server,   "Serveur Power BI",           session.get("username"))
                    db.set_setting("powerbi.service_name", new_name,     "Nom affiché du service PBI", session.get("username"))
                    db.set_setting("powerbi.login",        new_login,    "Login compte de service PBI", session.get("username"))
                    if new_password:
                        db.set_setting("powerbi.password", new_password, "Mot de passe compte service PBI", session.get("username"))
                    if new_url:
                        db.set_setting("powerbi.service_url", new_url,   "URL rapport embed PBI",      session.get("username"))
                    db.app_log("powerbi", "CONFIG SAVE", detail=f"server={new_server} login={new_login}", username=session.get("username"))
                    # Relire après sauvegarde
                    pbi_server   = new_server
                    pbi_name     = new_name
                    pbi_login    = new_login
                    pbi_url      = new_url
                    is_configured = True
                    msg = "Configuration Power BI enregistrée avec succès."
                except Exception as e:
                    error = f"Erreur lors de la sauvegarde : {e}"

        elif action == "clear_config":
            try:
                for key in ("powerbi.server", "powerbi.service_name", "powerbi.login",
                            "powerbi.password", "powerbi.service_url"):
                    db.set_setting(key, "", updated_by=session.get("username"))
                db.app_log("powerbi", "CONFIG CLEARED", username=session.get("username"))
                pbi_server = pbi_name = pbi_login = pbi_password = pbi_url = ""
                is_configured = False
                msg = "Configuration Power BI effacée."
            except Exception as e:
                error = str(e)

    return render_template(
        "modules/performance/powerbi.html",
        pbi_server=pbi_server, pbi_name=pbi_name,
        pbi_login=pbi_login, pbi_password=pbi_password,
        pbi_url=pbi_url,
        is_admin=is_admin, is_configured=is_configured,
        msg=msg, error=error,
    )
