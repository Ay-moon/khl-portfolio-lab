"""
Module Quant / Data Lab
─────────────────────────────────────────────────────────────
Qui est concerné : QUANT, DATA_ANALYST, ADMIN
Ce que ça fait :
  • Explorateur de données STOOQ (recherche, stats, graphique)
  • Backtesting simple de stratégies
  • Stats descriptives sur les instruments
"""
from flask import Blueprint, render_template, request, jsonify
from auth.routes import login_required
import db, config

quant_bp = Blueprint("quant", __name__, url_prefix="/quant")


@quant_bp.route("/")
@login_required
def index():
    # Stats globales STOOQ
    stg_stats = db.get_stg_stats()
    return render_template("modules/quant/index.html", stg_stats=stg_stats)


@quant_bp.route("/api/price-history")
@login_required
def api_price_history():
    """Retourne l'historique de prix d'un ticker STOOQ."""
    ticker = request.args.get("ticker", "").strip()
    limit  = min(int(request.args.get("limit", 252)), 2000)

    if not ticker:
        return jsonify({"error": "ticker requis"}), 400

    rows = []
    try:
        with db.db_cursor(database=config.SQL_DB_STG) as cur:
            cur.execute("""
                SELECT TOP (?)
                    CONVERT(DATE, date_extraction) as dt,
                    TRY_CAST(dernier AS FLOAT)   as close_p,
                    TRY_CAST(ouverture AS FLOAT) as open_p,
                    TRY_CAST(plus_haut AS FLOAT) as high_p,
                    TRY_CAST(plus_bas AS FLOAT)  as low_p,
                    TRY_CAST(volume AS FLOAT)    as vol
                FROM [stg].[stg_bourso_price_history]
                WHERE produit_type = 'STOOQ'
                  AND libelle = ?
                  AND TRY_CAST(dernier AS FLOAT) IS NOT NULL
                ORDER BY date_extraction ASC
            """, limit, ticker)
            for r in cur.fetchall():
                rows.append({
                    "date":  str(r[0])[:10],
                    "close": round(float(r[1]), 4) if r[1] else None,
                    "open":  round(float(r[2]), 4) if r[2] else None,
                    "high":  round(float(r[3]), 4) if r[3] else None,
                    "low":   round(float(r[4]), 4) if r[4] else None,
                    "vol":   int(r[5]) if r[5] else 0,
                })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    if not rows:
        return jsonify({"error": f"Aucune donnée pour {ticker}"}), 404

    # Stats descriptives
    closes = [r["close"] for r in rows if r["close"]]
    if closes:
        import statistics
        returns = [(closes[i]-closes[i-1])/closes[i-1] for i in range(1, len(closes))]
        stats = {
            "nb_points":  len(closes),
            "first_date": rows[0]["date"],
            "last_date":  rows[-1]["date"],
            "min":        round(min(closes), 4),
            "max":        round(max(closes), 4),
            "last":       round(closes[-1], 4),
            "perf_total": round((closes[-1]/closes[0]-1)*100, 2) if closes[0] else None,
            "vol_annualized": round(statistics.stdev(returns) * (252**0.5) * 100, 2) if len(returns) > 1 else None,
        }
    else:
        stats = {}

    return jsonify({"ticker": ticker, "data": rows, "stats": stats})


@quant_bp.route("/api/compare")
@login_required
def api_compare():
    """Compare 2 ou 3 tickers (retours normalisés à 100)."""
    tickers_raw = request.args.get("tickers", "")
    tickers = [t.strip() for t in tickers_raw.split(",") if t.strip()][:3]
    if not tickers:
        return jsonify({"error": "tickers requis"}), 400

    result = {}
    try:
        with db.db_cursor(database=config.SQL_DB_STG) as cur:
            for ticker in tickers:
                cur.execute("""
                    SELECT TOP 252
                        CONVERT(DATE, date_extraction) as dt,
                        TRY_CAST(dernier AS FLOAT) as close_p
                    FROM [stg].[stg_bourso_price_history]
                    WHERE produit_type = 'STOOQ' AND libelle = ?
                      AND TRY_CAST(dernier AS FLOAT) IS NOT NULL
                    ORDER BY date_extraction ASC
                """, ticker)
                rows = [(str(r[0])[:10], float(r[1])) for r in cur.fetchall() if r[1]]
                if rows:
                    base = rows[0][1]
                    result[ticker] = [{"date": d, "val": round(v/base*100, 2)} for d, v in rows]
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    return jsonify(result)
