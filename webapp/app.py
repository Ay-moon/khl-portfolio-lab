"""
KHL Bank CIB Platform — Point d'entrée Flask
═════════════════════════════════════════════
Lancement : python webapp/app.py
URL        : http://localhost:5000

Architecture :
  /auth/*        → Authentification (login, logout, register, profil)
  /monitoring/*  → Monitoring technique (tables, logs, jobs)
  /portfolio/*   → Création et simulation de portefeuilles (wizard 6 étapes)
  /trading/*     → Trading Desk (ordres, P&L)
  /performance/* → Performance & Reporting (NAV, PnL, Power BI)
  /risk/*        → Risk Management (VaR, drawdown, stress tests)
  /alm/*         → ALM (gap liquidité, duration, LCR/NSFR)
  /quant/*       → Quant / Data Lab (exploration STOOQ, backtesting)
"""
import os, sys
from datetime import date

# Ajouter webapp/ au path pour que les imports locaux fonctionnent
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from flask import Flask, render_template, redirect, url_for, session, g

import config
import db
from auth.routes             import auth_bp, get_current_user, login_required
from modules.monitoring.routes  import monitoring_bp
from modules.portfolio.routes   import portfolio_bp
from modules.trading.routes     import trading_bp
from modules.performance.routes import performance_bp
from modules.risk.routes        import risk_bp
from modules.alm.routes         import alm_bp
from modules.quant.routes       import quant_bp
from modules.docs.routes        import docs_bp
from modules.accounting.routes  import accounting_bp


# ── Création de l'app Flask ──────────────────────────────────
app = Flask(
    __name__,
    template_folder="templates",
    static_folder="static",
)
app.secret_key = config.SECRET_KEY
app.config["SESSION_PERMANENT"] = config.SESSION_PERMANENT


# ── Enregistrement des blueprints ────────────────────────────
app.register_blueprint(auth_bp)
app.register_blueprint(monitoring_bp)
app.register_blueprint(portfolio_bp)
app.register_blueprint(trading_bp)
app.register_blueprint(performance_bp)
app.register_blueprint(risk_bp)
app.register_blueprint(alm_bp)
app.register_blueprint(quant_bp)
app.register_blueprint(docs_bp)
app.register_blueprint(accounting_bp)


# ── Context processor global ─────────────────────────────────
@app.context_processor
def inject_globals():
    """Variables disponibles dans tous les templates."""
    return {
        "roles":   config.ROLES,
        "modules": config.MODULES,
    }


# ── Before request : charger user courant ────────────────────
@app.before_request
def load_user():
    g.user = get_current_user() if "user_id" in session else None


# ── Page d'accueil ───────────────────────────────────────────
@app.route("/")
def home():
    if "user_id" not in session:
        return redirect(url_for("auth.login"))

    user      = get_current_user()
    if not user:
        session.clear()
        return redirect(url_for("auth.login"))

    role      = user["role"]
    role_info = config.ROLES.get(role, {})
    user_modules = role_info.get("modules", [])

    # Stats rapides pour le dashboard
    stats = {"portfolios": 0, "securities": 0, "trades": 0}
    try:
        with db.db_cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM dbo.DimPortfolio WHERE IsActive=1")
            stats["portfolios"] = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM dbo.DimSecurity")
            stats["securities"] = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM dbo.FactTrades")
            stats["trades"] = cur.fetchone()[0]
    except Exception:
        pass

    # Stats des tables pour le widget DB
    db_stats = db.get_table_stats()

    # Descriptions courtes des modules
    module_descriptions = {
        "portfolio":   "Construisez un portefeuille professionnel via un wizard guidé en 6 étapes.",
        "trading":     "Passez des ordres BUY/SELL, visualisez le carnet des trades et le P&L intraday.",
        "accounting":  "Journal comptable en partie double : toutes les écritures générées par les trades.",
        "performance": "Suivez la NAV, le rendement cumulé et les métriques de performance.",
        "risk":        "Contrôlez VaR, volatilité, drawdown et les alertes de dépassement de limites.",
        "alm":         "Gap de liquidité, sensibilité taux, ratios LCR/NSFR et stress tests.",
        "quant":       "Explorez 60 000+ instruments historiques, backtestez des stratégies.",
        "monitoring":  "État des tables, logs en temps réel, lancement des jobs de calcul.",
        "powerbi":     "Connectez Power BI Desktop à la base pour un reporting professionnel.",
    }

    # Scénarios storytelling "Une journée à SG CIB"
    daily_scenarios = _get_daily_scenarios(role)

    # Quick actions selon le rôle
    quick_actions = _get_quick_actions(role)

    return render_template(
        "home.html",
        user=user,
        role_info=role_info,
        user_modules=user_modules,
        modules=config.MODULES,
        stats=stats,
        db_stats=db_stats[:8],   # 8 premières tables
        module_descriptions=module_descriptions,
        daily_scenarios=daily_scenarios,
        quick_actions=quick_actions,
        today=date.today().strftime("%d %B %Y"),
    )


def _get_daily_scenarios(role: str) -> list:
    """Retourne les scénarios storytelling adaptés au rôle."""
    all_scenarios = [
        {
            "time": "08h00",
            "actor": "Risk Analyst",
            "action": "Revue des alertes overnight",
            "detail": "Analyse des variations de marché nocturnes (marchés asiatiques). Vérification des limites VaR et des positions à risque.",
            "data_used": ["RiskMetricsDaily", "PortfolioPositionsDaily"],
        },
        {
            "time": "08h30",
            "actor": "Asset Manager",
            "action": "Morning meeting — revue de performance",
            "detail": "Analyse de la performance de la veille. Attribution par ligne. Décision sur les rééquilibrages à effectuer.",
            "data_used": ["PortfolioPnLDaily", "PortfolioPositionsDaily", "FactPrice"],
        },
        {
            "time": "09h00",
            "actor": "Trader",
            "action": "Préparation des ordres",
            "detail": "Traduction des décisions du gérant en ordres de marché. Calcul des impacts de marché et des fourchettes de prix.",
            "data_used": ["FactTrades", "DimSecurity", "FactPrice"],
        },
        {
            "time": "09h30",
            "actor": "Data Engineer",
            "action": "Ingestion des prix d'ouverture",
            "detail": "Pipeline automatique : cotations Boursorama/STOOQ → table Gold FactPrice. Vérification qualité des données.",
            "data_used": ["stg_bourso_price_history", "FactPrice", "DimDate"],
        },
        {
            "time": "17h30",
            "actor": "Quant",
            "action": "Calcul EOD — positions et PnL",
            "detail": "Lancement du moteur de simulation. Calcul des positions journalières, PnL latent, métriques risque.",
            "data_used": ["PortfolioPositionsDaily", "PortfolioPnLDaily", "RiskMetricsDaily"],
        },
        {
            "time": "18h00",
            "actor": "ALM Officer",
            "action": "Rapport ALM hebdomadaire",
            "detail": "Calcul du gap de liquidité, du BPV et des ratios LCR/NSFR. Stress tests taux pour le comité.",
            "data_used": ["PortfolioPositionsDaily", "FactPrice"],
        },
    ]
    return all_scenarios


def _get_quick_actions(role: str) -> list:
    """Actions rapides selon le rôle."""
    common = [
        {"label": "Voir mes portefeuilles",    "url": "/portfolio/",      "icon": "pie-chart"},
        {"label": "Dashboard performance",     "url": "/performance/",    "icon": "trophy"},
        {"label": "Monitoring technique",      "url": "/monitoring/",     "icon": "activity"},
    ]
    role_specific = {
        "ASSET_MANAGER": [
            {"label": "Créer un portefeuille", "url": "/portfolio/wizard/start", "icon": "plus-lg"},
            {"label": "Rapport Power BI",      "url": "/performance/powerbi",   "icon": "bar-chart-line"},
        ],
        "TRADER": [
            {"label": "Carnet des trades",     "url": "/trading/",              "icon": "graph-up-arrow"},
            {"label": "Risk & VaR",            "url": "/risk/",                 "icon": "shield-exclamation"},
        ],
        "RISK_ANALYST": [
            {"label": "Métriques risque",      "url": "/risk/",                 "icon": "shield-exclamation"},
            {"label": "Stress tests ALM",      "url": "/alm/",                  "icon": "bank"},
        ],
        "QUANT": [
            {"label": "Explorateur STOOQ",     "url": "/quant/",                "icon": "cpu"},
            {"label": "Nouveau portefeuille",  "url": "/portfolio/wizard/start","icon": "plus-lg"},
        ],
        "ALM_OFFICER": [
            {"label": "Gap de liquidité",      "url": "/alm/",                  "icon": "bank"},
            {"label": "Risk dashboard",        "url": "/risk/",                 "icon": "shield-exclamation"},
        ],
        "DATA_ANALYST": [
            {"label": "Explorateur STOOQ",     "url": "/quant/",                "icon": "cpu"},
            {"label": "Power BI",              "url": "/performance/powerbi",   "icon": "bar-chart-line"},
        ],
        "ADMIN": [
            {"label": "Monitoring système",    "url": "/monitoring/",           "icon": "activity"},
            {"label": "Créer un portefeuille", "url": "/portfolio/wizard/start","icon": "plus-lg"},
        ],
    }
    return (role_specific.get(role, []) + common)[:5]


# ── Erreurs globales ─────────────────────────────────────────
@app.errorhandler(404)
def not_found(e):
    return render_template("error.html", code=404,
                           msg="Page introuvable."), 404


@app.errorhandler(500)
def server_error(e):
    return render_template("error.html", code=500,
                           msg=f"Erreur interne : {e}"), 500


# ── Démarrage ────────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 60)
    print("  KHL Bank CIB Platform - Demarrage")
    print("=" * 60)
    print("  Initialisation de la base de donnees...")
    try:
        db.init_db()
        db.app_log("app", "STARTUP", detail="Flask app started")
        print("  [OK] Base de donnees initialisee")
    except Exception as e:
        print(f"  [WARN] Erreur init DB : {e}")

    print("  [OK] Blueprints enregistres")
    print("  --> URL : http://localhost:5000")
    print("=" * 60)

    app.run(
        host="0.0.0.0",
        port=5000,
        debug=config.DEBUG,
        use_reloader=True,
    )
