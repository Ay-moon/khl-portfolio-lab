"""
Module Risk Management
─────────────────────────────────────────────────────────────
Qui est concerné : RISK_ANALYST, ASSET_MANAGER, ALM_OFFICER
Ce que ça fait :
  • Tableau de bord des métriques risque (VaR, Vol, Drawdown, Sharpe)
  • Stress tests et scénarios what-if
  • Heat map de concentration
  • Alertes de dépassement de limites
"""
from flask import Blueprint, render_template, request
from auth.routes import login_required
import db

risk_bp = Blueprint("risk", __name__, url_prefix="/risk")

RISK_LIMITS = {
    "vol20d":   {"warn": 15.0,  "breach": 20.0,  "label": "Volatilité 20j (%)"},
    "drawdown": {"warn": -10.0, "breach": -20.0,  "label": "Max Drawdown (%)"},
    "var95":    {"warn": -2.5,  "breach": -5.0,   "label": "VaR 95% (%)"},
    "sharpe":   {"warn": 0.5,   "breach": 0.0,    "label": "Ratio Sharpe"},
}


@risk_bp.route("/")
@login_required
def index():
    portfolio_code = request.args.get("portfolio", "MAIN")
    risk_history   = []
    current_risk   = {}
    positions      = []
    alerts         = []
    all_portfolios = []

    try:
        with db.db_cursor() as cur:
            cur.execute("SELECT PortfolioCode, PortfolioName FROM dbo.DimPortfolio WHERE IsActive=1")
            all_portfolios = [{"code": r[0], "name": r[1]} for r in cur.fetchall()]

            # Clé portfolio
            cur.execute("SELECT PortfolioKey FROM dbo.DimPortfolio WHERE PortfolioCode=?", portfolio_code)
            row = cur.fetchone()
            if row:
                pf_key = row[0]

                # Historique métriques risque
                cur.execute("""
                    SELECT d.FullDate, rm.Volatility20d, rm.MaxDrawdown,
                           rm.VaR95, rm.SharpeRatio, rm.Beta
                    FROM dbo.RiskMetricsDaily rm
                    JOIN dbo.DimDate d ON d.DateKey = rm.DateKey
                    WHERE rm.PortfolioKey = ?
                    ORDER BY d.FullDate ASC
                """, pf_key)
                for r in cur.fetchall():
                    row_d = {
                        "date":     str(r[0])[:10],
                        "vol20d":   round(float(r[1] or 0) * 100, 2),
                        "drawdown": round(float(r[2] or 0) * 100, 2),
                        "var95":    round(float(r[3] or 0) * 100, 2),
                        "sharpe":   round(float(r[4] or 0), 2),
                        "beta":     round(float(r[5] or 0), 2),
                    }
                    risk_history.append(row_d)

                if risk_history:
                    current_risk = risk_history[-1]
                    # Génération des alertes
                    for metric, limits in RISK_LIMITS.items():
                        val = current_risk.get(metric, 0)
                        if metric in ("drawdown","var95"):
                            if val <= limits["breach"]:
                                alerts.append({"metric": metric, "level": "BREACH",
                                               "val": val, "limit": limits["breach"],
                                               "label": limits["label"]})
                            elif val <= limits["warn"]:
                                alerts.append({"metric": metric, "level": "WARN",
                                               "val": val, "limit": limits["warn"],
                                               "label": limits["label"]})
                        else:
                            if val >= limits["breach"] and metric not in ("sharpe",):
                                alerts.append({"metric": metric, "level": "BREACH",
                                               "val": val, "limit": limits["breach"],
                                               "label": limits["label"]})
                            elif metric == "sharpe" and val <= limits["breach"]:
                                alerts.append({"metric": metric, "level": "WARN",
                                               "val": val, "limit": limits["warn"],
                                               "label": limits["label"]})

                # Positions pour heat map
                cur.execute("""
                    SELECT s.Ticker, pos.WeightPct, pos.UnrealizedPnL
                    FROM dbo.PortfolioPositionsDaily pos
                    JOIN dbo.DimSecurity s ON s.SecurityKey = pos.SecurityKey
                    WHERE pos.PortfolioKey = ?
                      AND pos.DateKey = (SELECT MAX(DateKey) FROM dbo.PortfolioPositionsDaily WHERE PortfolioKey = ?)
                    ORDER BY pos.WeightPct DESC
                """, pf_key, pf_key)
                for r in cur.fetchall():
                    positions.append({
                        "ticker": r[0],
                        "weight": round(float(r[1] or 0), 2),
                        "pnl":    round(float(r[2] or 0), 2),
                    })

    except Exception as e:
        pass

    return render_template(
        "modules/risk/index.html",
        portfolio_code=portfolio_code,
        current_risk=current_risk,
        risk_history=risk_history,
        positions=positions,
        alerts=alerts,
        all_portfolios=all_portfolios,
        limits=RISK_LIMITS,
    )
