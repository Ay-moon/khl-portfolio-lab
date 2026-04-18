"""
KHL Bank Platform — Configuration centrale
Connexion Windows Auth (Trusted_Connection) — aucune licence requise

Surcharge par variables d'environnement (ou fichier .env) :
  KHL_SQL_SERVER   → serveur SQL Server  (défaut: PERSO-AJE-DELL\BFASERVER01)
  KHL_SQL_DRIVER   → driver ODBC         (défaut: ODBC Driver 17 for SQL Server)
  KHL_SQL_DB_MAIN  → base Gold/App       (défaut: SmartAssetAdvicedb)
  KHL_SQL_DB_STG   → base staging        (défaut: KHLWorldInvest)
  KHL_SQL_TIMEOUT  → timeout connexion s (défaut: 10)
  KHL_DEBUG        → mode debug Flask    (défaut: True)
  KHL_SECRET_KEY   → clé secrète Flask   (défaut: aléatoire à chaque démarrage)
"""
import os

# ── Chargement optionnel d'un fichier .env (sans dépendance python-dotenv) ──
_env_file = os.path.join(os.path.dirname(__file__), "..", ".env")
if os.path.isfile(_env_file):
    with open(_env_file, encoding="utf-8") as _f:
        for _line in _f:
            _line = _line.strip()
            if _line and not _line.startswith("#") and "=" in _line:
                _k, _v = _line.split("=", 1)
                os.environ.setdefault(_k.strip(), _v.strip())

# ── SQL Server ──────────────────────────────────────────────
# Priorité : KHL_* > SQL_* (legacy .env data-platform) > valeur par défaut
def _e(khl_key: str, legacy_key: str, default: str) -> str:
    return os.environ.get(khl_key) or os.environ.get(legacy_key) or default

SQL_SERVER  = _e("KHL_SQL_SERVER",  "SQL_SERVER",   r"PERSO-AJE-DELL\BFASERVER01")
SQL_DRIVER  = _e("KHL_SQL_DRIVER",  "SQL_DRIVER",   "ODBC Driver 17 for SQL Server")
SQL_DB_MAIN = _e("KHL_SQL_DB_MAIN", "SQL_DATABASE", "SmartAssetAdvicedb")   # Gold + AppUsers + AppLog
SQL_DB_STG  = _e("KHL_SQL_DB_STG",  "SQL_DATABASE_STG", "KHLWorldInvest")  # Cotations staging
SQL_TIMEOUT = int(_e("KHL_SQL_TIMEOUT", "", "10"))

def conn_str(database: str = None) -> str:
    db = database or SQL_DB_MAIN
    return (
        f"DRIVER={{{SQL_DRIVER}}};"
        f"SERVER={SQL_SERVER};"
        f"DATABASE={db};"
        f"Trusted_Connection=yes;"
        f"Connect Timeout={SQL_TIMEOUT};"
    )

# ── Flask ────────────────────────────────────────────────────
SECRET_KEY   = os.environ.get("KHL_SECRET_KEY", None) or os.urandom(32)
SESSION_PERMANENT = False
DEBUG        = os.environ.get("KHL_DEBUG", "True").lower() not in ("false", "0", "no")
PAGE_SIZE    = 50

# ══════════════════════════════════════════════════════════════
# HIÉRARCHIE DES ACCÈS
# ══════════════════════════════════════════════════════════════
#
#   Niveau 1 — ADMIN
#       Supervision globale, accès total
#
#   Niveau 2 — DATA_ANALYST / COMPTABLE
#       Cross-office : reporting, comptabilité, monitoring
#       Voit les résultats des trois offices sans agir sur le marché
#
#   Niveau 3 — Métiers spécialisés (cloisonnés par office)
#       FRONT OFFICE  : TRADER · ASSET_MANAGER · QUANT
#       MIDDLE OFFICE : RISK_ANALYST · ALM_OFFICER
#       BACK OFFICE   : COMPTABLE
#
#   Règle absolue :
#     • Qui DÉCIDE ne EXÉCUTE pas
#     • Qui EXÉCUTE ne COMPTABILISE pas
#     • Qui COMPTABILISE ne DÉCIDE pas
#
# ══════════════════════════════════════════════════════════════

OFFICE_META = {
    "Front Office":  {"color": "#0d6e3b", "badge": "FRONT",  "icon": "graph-up-arrow"},
    "Middle Office": {"color": "#8b1a1a", "badge": "MIDDLE", "icon": "shield-exclamation"},
    "Back Office":   {"color": "#1a3a5c", "badge": "BACK",   "icon": "journal-text"},
    "Système":       {"color": "#2c2c2c", "badge": "ADMIN",  "icon": "gear"},
}

# Hiérarchie numérique (1 = plus de pouvoir)
ROLE_HIERARCHY = {
    "ADMIN":         1,
    "DATA_ANALYST":  2,
    "COMPTABLE":     2,
    "TRADER":        3,
    "ASSET_MANAGER": 3,
    "QUANT":         3,
    "RISK_ANALYST":  3,
    "ALM_OFFICER":   3,
}

# ── Rôles ─────────────────────────────────────────────────────
ROLES = {
    # ── FRONT OFFICE ──────────────────────────────────────────
    "ASSET_MANAGER": {
        "label":  "Asset Manager",
        "icon":   "briefcase",
        "color":  "#1a3a5c",
        "office": "Front Office",
        "hierarchy_level": 3,
        "desc":   "Décide des allocations et de la stratégie portefeuille. "
                  "Donne les instructions au Trader — ne passe PAS d'ordres lui-même, ne comptabilise PAS.",
        "can_do":    "Gérer les portefeuilles · Suivre la performance · Contrôler le risque",
        "cannot_do": "Exécuter des ordres (→ Trader) · Comptabiliser (→ Back Office)",
        "modules": ["portfolio", "performance", "risk", "powerbi"],
    },
    "TRADER": {
        "label":  "Trader / Sales",
        "icon":   "graph-up-arrow",
        "color":  "#0d6e3b",
        "office": "Front Office",
        "hierarchy_level": 3,
        "desc":   "Exécute les ordres sur instruction de l'Asset Manager. "
                  "Accès au carnet d'ordres et aux outils de pricing — ne comptabilise PAS.",
        "can_do":    "Passer des ordres BUY/SELL · Surveiller le Risk · Utiliser les outils Quant/VBA",
        "cannot_do": "Voir la comptabilité (→ Back Office) · Modifier les portefeuilles (→ Asset Manager)",
        "modules": ["trading", "risk", "quant"],
    },
    "QUANT": {
        "label":  "Quant / IT Quant",
        "icon":   "cpu",
        "color":  "#4a1a7a",
        "office": "Front Office",
        "hierarchy_level": 3,
        "desc":   "Modélisation quantitative, backtesting, alpha research. "
                  "Ne passe PAS d'ordres réels, ne comptabilise PAS.",
        "can_do":    "Data Lab · Backtesting · Construction de portefeuilles (simulation)",
        "cannot_do": "Exécuter des ordres réels (→ Trader) · Voir la comptabilité (→ Back Office)",
        "modules": ["quant", "portfolio", "risk"],
    },
    # ── MIDDLE OFFICE ─────────────────────────────────────────
    "RISK_ANALYST": {
        "label":  "Risk Analyst",
        "icon":   "shield-exclamation",
        "color":  "#8b1a1a",
        "office": "Middle Office",
        "hierarchy_level": 3,
        "desc":   "Contrôle indépendant du risque de marché. "
                  "Surveille VaR, drawdown, stress-tests. Ne passe PAS d'ordres.",
        "can_do":    "Métriques risque · Performance · ALM · Reporting Power BI",
        "cannot_do": "Passer des ordres (→ Trader) · Comptabiliser (→ Back Office)",
        "modules": ["risk", "performance", "alm", "powerbi"],
    },
    "ALM_OFFICER": {
        "label":  "ALM Officer",
        "icon":   "bank",
        "color":  "#1a5c5c",
        "office": "Middle Office",
        "hierarchy_level": 3,
        "desc":   "Gestion actif-passif, gap de liquidité, ratios LCR/NSFR. "
                  "Ne passe PAS d'ordres.",
        "can_do":    "ALM · Risk · Performance",
        "cannot_do": "Passer des ordres (→ Trader) · Voir la comptabilité (→ Back Office)",
        "modules": ["alm", "risk", "performance"],
    },
    # ── BACK OFFICE ───────────────────────────────────────────
    "COMPTABLE": {
        "label":  "Comptable / Back Office",
        "icon":   "calculator",
        "color":  "#2c5c1a",
        "office": "Back Office",
        "hierarchy_level": 2,
        "desc":   "Comptabilité en partie double, rapprochements EOD, clôtures. "
                  "Ne passe PAS d'ordres — enregistre CE QUE le Trader a exécuté.",
        "can_do":    "Journal comptable · Balance CIB · Rapprochements · Monitoring",
        "cannot_do": "Passer des ordres (→ Trader) · Décider des allocations (→ Asset Manager)",
        "modules": ["accounting", "monitoring", "performance"],
    },
    "DATA_ANALYST": {
        "label":  "Data Analyst / Ingénieur Data",
        "icon":   "bar-chart-line",
        "color":  "#5c3a1a",
        "office": "Back Office",
        "hierarchy_level": 2,
        "desc":   "Reporting cross-office, pipelines de données, Power BI, monitoring technique. "
                  "Visibilité étendue mais pas d'actions marché.",
        "can_do":    "Comptabilité · Monitoring · Performance · Power BI · Data Lab",
        "cannot_do": "Passer des ordres (→ Trader) · Modifier les portefeuilles (→ Asset Manager)",
        "modules": ["accounting", "monitoring", "performance", "powerbi", "quant"],
    },
    # ── ADMINISTRATION ────────────────────────────────────────
    "ADMIN": {
        "label":  "Administrateur",
        "icon":   "gear",
        "color":  "#2c2c2c",
        "office": "Système",
        "hierarchy_level": 1,
        "desc":   "Supervision globale de la plateforme. Accès complet pour administration.",
        "can_do":    "Tout",
        "cannot_do": "—",
        "modules": ["monitoring", "portfolio", "trading", "accounting",
                    "performance", "risk", "alm", "quant", "powerbi"],
    },
}

# ── Modules — avec tag office ─────────────────────────────────
MODULES = {
    "portfolio":   {"label": "Création Portefeuille",  "icon": "pie-chart",           "route": "portfolio.index",  "office": "Front Office"},
    "trading":     {"label": "Trading Desk",           "icon": "graph-up-arrow",      "route": "trading.index",    "office": "Front Office"},
    "quant":       {"label": "Quant / Data Lab",       "icon": "cpu",                 "route": "quant.index",      "office": "Front Office"},
    "risk":        {"label": "Risk Management",        "icon": "shield-exclamation",  "route": "risk.index",       "office": "Middle Office"},
    "performance": {"label": "Performance",            "icon": "trophy",              "route": "performance.index","office": "Middle Office"},
    "alm":         {"label": "ALM",                    "icon": "bank",                "route": "alm.index",        "office": "Middle Office"},
    "accounting":  {"label": "Comptabilité",           "icon": "journal-text",        "route": "accounting.index", "office": "Back Office"},
    "monitoring":  {"label": "Monitoring Technique",   "icon": "activity",            "route": "monitoring.index", "office": "Back Office"},
    "powerbi":     {"label": "Power BI Reports",       "icon": "bar-chart-line",      "route": "performance.powerbi", "office": "Back Office"},
}

# ── Qui peut accéder à chaque module (pour le message d'accès refusé) ──
MODULE_ROLES = {
    mod: [r for r, info in ROLES.items() if mod in info["modules"]]
    for mod in MODULES
}
