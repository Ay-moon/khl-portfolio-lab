"""
Module Portfolio — Création & Simulation de Portefeuille
─────────────────────────────────────────────────────────────
Qui est concerné : ASSET_MANAGER, QUANT, ADMIN
Ce que ça fait :
  • Wizard 6 étapes pour paramétrer un portefeuille professionnel
  • Exploration de l'univers investissable (STOOQ + Bourso)
  • Instanciation dans DimPortfolio + lancement de la simulation
  • Liste et gestion des portefeuilles existants
"""
import json
from datetime import date
from flask import (
    Blueprint, render_template, request, redirect,
    url_for, session, flash, jsonify
)
from auth.routes import login_required
import db, config

portfolio_bp = Blueprint("portfolio", __name__, url_prefix="/portfolio")

# ── Cache mémoire pour les top instruments (évite GROUP BY 60k lignes à chaque GET) ──
_TOP_INSTRUMENTS_CACHE: dict = {}   # {"top_us": [...], "top_indices": [...]}


def _get_top_instruments() -> dict:
    """Retourne les top instruments depuis le cache. Calcul unique au premier appel."""
    global _TOP_INSTRUMENTS_CACHE
    if _TOP_INSTRUMENTS_CACHE:
        return _TOP_INSTRUMENTS_CACHE
    try:
        with db.db_cursor(database=config.SQL_DB_STG) as cur:
            cur.execute("""
                SELECT TOP 20 libelle,
                       COUNT(*) as nb_cot,
                       MAX(CASE WHEN TRY_CAST(dernier AS FLOAT) IS NOT NULL
                                THEN TRY_CAST(dernier AS FLOAT) END) as last_price
                FROM [stg].[stg_bourso_price_history] WITH (NOLOCK)
                WHERE produit_type = 'STOOQ' AND libelle LIKE '%.US'
                GROUP BY libelle ORDER BY nb_cot DESC
            """)
            top_us = [{"ticker": r[0], "nb_cot": r[1],
                       "last_price": round(float(r[2]), 2) if r[2] else None}
                      for r in cur.fetchall()]

            cur.execute("""
                SELECT TOP 10 libelle,
                       COUNT(*) as nb_cot,
                       MAX(CASE WHEN TRY_CAST(dernier AS FLOAT) IS NOT NULL
                                THEN TRY_CAST(dernier AS FLOAT) END) as last_price
                FROM [stg].[stg_bourso_price_history] WITH (NOLOCK)
                WHERE produit_type = 'STOOQ' AND libelle LIKE '^%'
                GROUP BY libelle ORDER BY nb_cot DESC
            """)
            top_indices = [{"ticker": r[0], "nb_cot": r[1],
                            "last_price": round(float(r[2]), 2) if r[2] else None}
                           for r in cur.fetchall()]

        _TOP_INSTRUMENTS_CACHE = {"top_us": top_us, "top_indices": top_indices}
    except Exception:
        _TOP_INSTRUMENTS_CACHE = {"top_us": [], "top_indices": []}
    return _TOP_INSTRUMENTS_CACHE


# ── Liste des portefeuilles ──────────────────────────────────

@portfolio_bp.route("/")
@login_required
def index():
    portfolios = []
    try:
        with db.db_cursor() as cur:
            cur.execute("""
                SELECT p.PortfolioCode, p.PortfolioName, p.BaseCurrency,
                       p.RiskProfile, p.InceptionDate, p.IsActive,
                       COUNT(DISTINCT t.SecurityKey) as nb_positions,
                       SUM(CASE WHEN t.Side='BUY' THEN t.Quantity ELSE -t.Quantity END) as net_qty
                FROM dbo.DimPortfolio p
                LEFT JOIN dbo.FactTrades t ON t.PortfolioKey = p.PortfolioKey
                GROUP BY p.PortfolioCode, p.PortfolioName, p.BaseCurrency,
                         p.RiskProfile, p.InceptionDate, p.IsActive
                ORDER BY p.PortfolioCode
            """)
            for r in cur.fetchall():
                portfolios.append({
                    "code":        r[0], "name":        r[1],
                    "currency":    r[2], "risk":        r[3],
                    "inception":   str(r[4])[:10] if r[4] else "—",
                    "active":      r[5],
                    "nb_positions":r[6] or 0,
                })
    except Exception as e:
        flash(f"Erreur chargement portefeuilles : {e}", "danger")

    return render_template("modules/portfolio/index.html", portfolios=portfolios)


# ── Wizard ───────────────────────────────────────────────────

@portfolio_bp.route("/wizard/start")
@login_required
def wizard_start():
    """Lance le wizard en nettoyant tout draft précédent."""
    session.pop("pf_draft", None)
    session["pf_draft"] = {"step": 1}
    return redirect(url_for("portfolio.wizard_step", step=1))


@portfolio_bp.route("/wizard/<int:step>", methods=["GET", "POST"])
@login_required
def wizard_step(step):
    draft = session.get("pf_draft", {"step": 1})

    if request.method == "POST":
        # Sauvegarder les données de l'étape
        form_data = {k: v for k, v in request.form.items() if k != "csrf_token"}
        # Gérer les listes (checkboxes multiples)
        for key in request.form.to_dict(flat=False):
            vals = request.form.getlist(key)
            if len(vals) > 1:
                form_data[key] = vals
        draft.update(form_data)
        draft["step"] = max(draft.get("step", 1), step + 1)
        session["pf_draft"] = draft
        session.modified = True

        if step == 6:
            return redirect(url_for("portfolio.wizard_confirm"))
        return redirect(url_for("portfolio.wizard_step", step=step + 1))

    # GET — préparer les données pour l'étape
    context = _build_step_context(step, draft)
    return render_template(
        f"modules/portfolio/wizard_step{step}.html",
        step=step, draft=draft, **context
    )


@portfolio_bp.route("/wizard/confirm", methods=["GET", "POST"])
@login_required
def wizard_confirm():
    draft = session.get("pf_draft", {})

    if request.method == "POST":
        action = request.form.get("action")
        if action == "create":
            try:
                _create_portfolio(draft)
                db.app_log(
                    "portfolio",
                    f"CREATE PORTFOLIO {draft.get('portfolio_code','?')}",
                    detail=json.dumps({k: v for k, v in draft.items() if k != "step"})[:500],
                    username=session.get("username"),
                    rows_affected=1
                )
                session.pop("pf_draft", None)
                flash(f"Portefeuille {draft.get('portfolio_code')} créé avec succès !", "success")
                return redirect(url_for("portfolio.index"))
            except Exception as e:
                flash(f"Erreur lors de la création : {e}", "danger")
        elif action == "back":
            return redirect(url_for("portfolio.wizard_step", step=6))

    return render_template("modules/portfolio/wizard_confirm.html", draft=draft)


@portfolio_bp.route("/api/securities")
@login_required
def api_securities():
    """
    Recherche d'instruments dans STOOQ pour le wizard étape 2.
    Utilise stg_ticker_lookup (table pré-agrégée) si disponible,
    sinon fallback sur stg_bourso_price_history avec GROUP BY.
    """
    q         = request.args.get("q", "").strip()
    asset_cls = request.args.get("class", "")
    limit     = min(int(request.args.get("limit", 50)), 100)

    if not q and not asset_cls:
        return jsonify([])
    if q and len(q) < 2:
        return jsonify([])

    results = []
    try:
        with db.db_cursor(database=config.SQL_DB_STG) as cur:
            # Vérifier si la table lookup est disponible
            cur.execute("""
                SELECT 1 FROM INFORMATION_SCHEMA.TABLES
                WHERE TABLE_SCHEMA='stg' AND TABLE_NAME='stg_ticker_lookup'
            """)
            use_lookup = cur.fetchone() is not None

            if use_lookup:
                results = _search_lookup(cur, q, asset_cls, limit)
            else:
                results = _search_raw(cur, q, asset_cls, limit)

    except Exception as e:
        return jsonify({"error": str(e)}), 500

    return jsonify(results)


def _search_lookup(cur, q: str, asset_cls: str, limit: int) -> list:
    """Recherche rapide dans stg_ticker_lookup (table pré-agrégée, indexée)."""
    where  = ["1=1"]
    params = []

    if q:
        # Deux patterns : préfixe exact 'ABC%' et suffixe '.ABC%' (sargables sur index)
        where.append("(ticker LIKE ? OR ticker LIKE ?)")
        params += [f"{q.upper()}%", f"%.{q.upper()}%"]

    if asset_cls == "indices":
        where.append("ticker LIKE '^%'")
    elif asset_cls == "us_stocks":
        where.append("ticker LIKE '%.US'")
    elif asset_cls == "forex":
        where.append("asset_class = 'Forex/Matière première'")
    elif asset_cls == "bonds":
        where.append("ticker LIKE '%.B'")
    elif asset_cls == "fr_stocks":
        where.append("asset_class = 'Action FR'")

    sql = f"""
        SELECT TOP {limit}
            ticker, asset_class, nb_cot, last_price,
            date_debut, date_fin
        FROM stg.stg_ticker_lookup
        WHERE {' AND '.join(where)}
        ORDER BY nb_cot DESC
    """
    cur.execute(sql, *params)
    rows = []
    for r in cur.fetchall():
        rows.append({
            "ticker":      str(r[0]),
            "name":        str(r[0]),
            "debut":       str(r[4])[:10] if r[4] else "—",
            "fin":         str(r[5])[:10] if r[5] else "—",
            "nb_cot":      r[2],
            "last_price":  round(float(r[3]), 2) if r[3] else None,
            "asset_class": r[1] or _classify_ticker(str(r[0])),
        })
    return rows


def _search_raw(cur, q: str, asset_cls: str, limit: int) -> list:
    """Fallback : GROUP BY sur stg_bourso_price_history (lent, ~2-5s)."""
    where  = ["produit_type = 'STOOQ'"]
    params = []

    if q:
        where.append("(libelle LIKE ? OR libelle LIKE ?)")
        params += [f"{q.upper()}%", f"%.{q.upper()}%"]

    if asset_cls == "indices":
        where.append("libelle LIKE '^%'")
    elif asset_cls == "us_stocks":
        where.append("libelle LIKE '%.US'")
    elif asset_cls == "forex":
        where.append("(libelle LIKE '%USD%' OR libelle LIKE '%EUR%' OR libelle LIKE '%GBP%' OR libelle LIKE '%JPY%')")
    elif asset_cls == "bonds":
        where.append("libelle LIKE '%.B'")
    elif asset_cls == "fr_stocks":
        where.append("produit_type = 'ACTION'")

    sql = f"""
        SELECT TOP {limit}
            libelle,
            MIN(date_extraction) as debut,
            MAX(date_extraction) as fin,
            COUNT(*)             as nb_cot,
            MAX(CASE WHEN TRY_CAST(dernier AS FLOAT) IS NOT NULL
                     THEN TRY_CAST(dernier AS FLOAT) END) as last_price
        FROM [stg].[stg_bourso_price_history] WITH (NOLOCK)
        WHERE {' AND '.join(where)}
        GROUP BY libelle
        ORDER BY nb_cot DESC
    """
    cur.execute(sql, *params)
    rows = []
    for r in cur.fetchall():
        ticker = str(r[0])
        rows.append({
            "ticker":      ticker,
            "name":        ticker,
            "debut":       str(r[1])[:10] if r[1] else "—",
            "fin":         str(r[2])[:10] if r[2] else "—",
            "nb_cot":      r[3],
            "last_price":  round(float(r[4]), 2) if r[4] else None,
            "asset_class": _classify_ticker(ticker),
        })
    return rows


@portfolio_bp.route("/view/<code>")
@login_required
def view(code):
    """Vue détaillée d'un portefeuille."""
    portfolio = None
    positions = []
    pnl_history = []

    try:
        with db.db_cursor() as cur:
            cur.execute("""
                SELECT PortfolioKey, PortfolioCode, PortfolioName, BaseCurrency,
                       RiskProfile, InceptionDate, IsActive
                FROM dbo.DimPortfolio WHERE PortfolioCode = ?
            """, code)
            row = cur.fetchone()
            if not row:
                flash(f"Portefeuille {code} introuvable.", "warning")
                return redirect(url_for("portfolio.index"))
            portfolio = {
                "key": row[0], "code": row[1], "name": row[2],
                "currency": row[3], "risk": row[4],
                "inception": str(row[5])[:10] if row[5] else "—",
                "active": row[6]
            }

            # Positions actuelles
            cur.execute("""
                SELECT s.Ticker, s.SecurityName, p.Quantity, p.AvgCost,
                       p.MarketValue, p.UnrealizedPnL, p.WeightPct,
                       d.FullDate
                FROM dbo.PortfolioPositionsDaily p
                JOIN dbo.DimSecurity s ON s.SecurityKey = p.SecurityKey
                JOIN dbo.DimDate d ON d.DateKey = p.DateKey
                WHERE p.PortfolioKey = ?
                  AND p.DateKey = (
                    SELECT MAX(DateKey) FROM dbo.PortfolioPositionsDaily WHERE PortfolioKey = ?
                  )
                ORDER BY p.WeightPct DESC
            """, portfolio["key"], portfolio["key"])
            for r in cur.fetchall():
                positions.append({
                    "ticker": r[0], "name": r[1],
                    "qty": r[2], "avg_cost": round(float(r[3] or 0), 2),
                    "market_value": round(float(r[4] or 0), 2),
                    "unrealized_pnl": round(float(r[5] or 0), 2),
                    "weight_pct": round(float(r[6] or 0), 2),
                    "date": str(r[7])[:10],
                })

            # Historique PnL (30 derniers jours)
            cur.execute("""
                SELECT TOP 30 d.FullDate, pl.Nav, pl.DailyPnL, pl.CumPnL, pl.ReturnPct
                FROM dbo.PortfolioPnLDaily pl
                JOIN dbo.DimDate d ON d.DateKey = pl.DateKey
                WHERE pl.PortfolioKey = ?
                ORDER BY d.FullDate ASC
            """, portfolio["key"])
            for r in cur.fetchall():
                pnl_history.append({
                    "date": str(r[0])[:10],
                    "nav":  round(float(r[1] or 0), 2),
                    "daily_pnl": round(float(r[2] or 0), 2),
                    "cum_pnl":   round(float(r[3] or 0), 2),
                    "return_pct":round(float(r[4] or 0), 4),
                })

    except Exception as e:
        flash(f"Erreur : {e}", "danger")

    return render_template(
        "modules/portfolio/view.html",
        portfolio=portfolio, positions=positions, pnl_history=pnl_history
    )


# ── Helpers privés ───────────────────────────────────────────

def _build_step_context(step: int, draft: dict) -> dict:
    ctx = {}
    if step == 2:
        # Lecture depuis le cache mémoire — pas de requête SQL bloquante au GET
        top = _get_top_instruments()
        ctx["top_us"]      = top.get("top_us", [])
        ctx["top_indices"] = top.get("top_indices", [])
    return ctx


def _create_portfolio(draft: dict):
    """Instancie le portefeuille dans DimPortfolio."""
    code      = draft.get("portfolio_code", "PF001").upper().strip()
    name      = draft.get("portfolio_name", f"Portfolio {code}")
    currency  = draft.get("base_currency", "EUR")
    risk      = draft.get("risk_profile", "BALANCED")
    inception = draft.get("inception_date") or str(date.today())

    with db.db_cursor() as cur:
        # Vérif unicité
        cur.execute("SELECT COUNT(*) FROM dbo.DimPortfolio WHERE PortfolioCode = ?", code)
        if cur.fetchone()[0] > 0:
            raise ValueError(f"Le code {code} existe déjà.")
        cur.execute("""
            INSERT INTO dbo.DimPortfolio (PortfolioCode, PortfolioName, BaseCurrency, RiskProfile, InceptionDate)
            VALUES (?, ?, ?, ?, ?)
        """, code, name, currency, risk, inception)


def _classify_ticker(ticker: str) -> str:
    if ticker.startswith("^"):
        return "Indice"
    if ticker.endswith(".US"):
        return "Action US"
    if ticker.endswith(".B"):
        return "Obligation"
    if any(x in ticker for x in ["USD","EUR","GBP","JPY","AUD","CHF","CAD"]):
        return "Forex/Matière première"
    return "Autre"
