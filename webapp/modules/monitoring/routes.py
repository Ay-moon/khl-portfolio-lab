"""
Module Monitoring Technique
─────────────────────────────────────────────────────────────
Qui est concerné : ADMIN, DATA_ANALYST, QUANT
Ce que ça fait :
  • Affiche le statut de toutes les tables (row counts, dernière maj)
  • Affiche les logs applicatifs en temps réel (AppLog)
  • Montre les stats de la staging (KHLWorldInvest)
  • Permet de lancer les jobs Python depuis l'interface
"""
import subprocess, sys, os
from flask import Blueprint, render_template, jsonify, request, session
from auth.routes import login_required
import db, config

monitoring_bp = Blueprint("monitoring", __name__, url_prefix="/monitoring")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@monitoring_bp.route("/")
@login_required
def index():
    table_stats = db.get_table_stats()
    stg_stats   = db.get_stg_stats()

    # Derniers logs (50 lignes)
    logs = []
    try:
        with db.db_cursor() as cur:
            cur.execute("""
                SELECT TOP 100
                    FORMAT(log_ts, 'HH:mm:ss') as ts,
                    level, module, action, detail,
                    username, duration_ms, rows_affected
                FROM dbo.AppLog
                ORDER BY log_id DESC
            """)
            for r in cur.fetchall():
                logs.append({
                    "ts":      r[0] or "",
                    "level":   r[1] or "INFO",
                    "module":  r[2] or "",
                    "action":  r[3] or "",
                    "detail":  r[4] or "",
                    "user":    r[5] or "",
                    "dur_ms":  r[6],
                    "rows":    r[7],
                })
    except Exception as e:
        logs = [{"ts":"--","level":"ERROR","module":"monitoring","action":str(e),"detail":"","user":"","dur_ms":None,"rows":None}]

    # Portfolios existants
    portfolios = []
    try:
        with db.db_cursor() as cur:
            cur.execute("""
                SELECT PortfolioCode, PortfolioName, BaseCurrency, RiskProfile,
                       InceptionDate, IsActive
                FROM dbo.DimPortfolio ORDER BY PortfolioCode
            """)
            for r in cur.fetchall():
                portfolios.append({
                    "code": r[0], "name": r[1], "currency": r[2],
                    "risk": r[3], "inception": str(r[4])[:10] if r[4] else "—",
                    "active": r[5]
                })
    except Exception:
        pass

    return render_template(
        "modules/monitoring/index.html",
        table_stats=table_stats,
        stg_stats=stg_stats,
        logs=logs,
        portfolios=portfolios,
        jobs=_get_job_definitions(),
    )


@monitoring_bp.route("/api/table-stats")
@login_required
def api_table_stats():
    """Endpoint JSON pour rafraîchissement temps réel (polling)."""
    return jsonify(db.get_table_stats())


@monitoring_bp.route("/api/logs")
@login_required
def api_logs():
    """50 derniers logs pour rafraîchissement AJAX."""
    logs = []
    try:
        with db.db_cursor() as cur:
            cur.execute("""
                SELECT TOP 50
                    FORMAT(log_ts, 'yyyy-MM-dd HH:mm:ss') as ts,
                    level, module, action, detail, username, duration_ms, rows_affected
                FROM dbo.AppLog ORDER BY log_id DESC
            """)
            for r in cur.fetchall():
                logs.append({
                    "ts": r[0], "level": r[1], "module": r[2],
                    "action": r[3], "detail": r[4], "user": r[5],
                    "dur_ms": r[6], "rows": r[7]
                })
    except Exception as e:
        logs = [{"ts":"--","level":"ERROR","module":"monitoring","action":str(e)}]
    return jsonify(logs)


@monitoring_bp.route("/run-job/eod-reco", methods=["POST"])
@login_required
def run_eod_reco():
    """Contrôle EOD comptable : vérifie Débit = Crédit dans FactAccountingMovement."""
    result = db.run_debit_credit_control(checked_by=session.get("username", "SYSTEM"))
    db.app_log(
        "monitoring", "EOD RECO DEBIT_CREDIT",
        detail=result.get("comment", ""),
        level="INFO" if result["status"] == "OK" else "WARN",
        username=session.get("username"),
    )
    return jsonify({
        "ok":     result["status"] in ("OK",),
        "status": result["status"],
        "diff":   result["difference"],
        "output": result.get("comment", ""),
    })


@monitoring_bp.route("/run-job/<job_id>", methods=["POST"])
@login_required
def run_job(job_id):
    """Lance un job Python et retourne le résultat."""
    jobs = {j["id"]: j for j in _get_job_definitions()}
    if job_id not in jobs:
        return jsonify({"ok": False, "msg": "Job inconnu"}), 404

    job = jobs[job_id]
    # Chemin absolu si fourni (ex: commando), relatif sinon
    raw_script = job["script"]
    script_path = raw_script if os.path.isabs(raw_script) else os.path.join(BASE_DIR, raw_script)
    # Python : venv du projet KHL par défaut, sauf si le job spécifie son propre python
    python_exe = job.get("python_exe") or os.path.join(BASE_DIR, ".venv", "Scripts", "python.exe")

    if not os.path.exists(script_path):
        return jsonify({"ok": False, "msg": f"Script introuvable : {script_path}"}), 400

    try:
        result = subprocess.run(
            [python_exe, script_path] + job.get("args", []),
            capture_output=True, text=True, timeout=120,
            cwd=BASE_DIR
        )
        ok = result.returncode == 0
        output = (result.stdout or "") + (result.stderr or "")
        db.app_log(
            "monitoring", f"RUN JOB {job_id}",
            detail=f"rc={result.returncode} | {output[:500]}",
            level="INFO" if ok else "ERROR",
            username=session.get("username")
        )
        return jsonify({"ok": ok, "output": output[-2000:], "rc": result.returncode})
    except subprocess.TimeoutExpired:
        return jsonify({"ok": False, "msg": "Timeout (>120s)"}), 408
    except Exception as e:
        return jsonify({"ok": False, "msg": str(e)}), 500


def _get_job_definitions():
    return [
        {
            "id":      "seed",
            "label":   "Seed Demo Data",
            "desc":    "Initialise les tables Gold avec des données de démonstration",
            "script":  "scripts/seed_demo_data.py",
            "args":    [],
            "icon":    "database-fill-add",
            "danger":  False,
        },
        {
            "id":      "load_prices",
            "label":   "Charger les Prix (Bourso → Gold)",
            "desc":    "Ingère stg_bourso_price_history → DimDate, DimSecurity, FactPrice",
            "script":  "scripts/load_factprice_from_stg.py",
            "args":    [],
            "icon":    "arrow-repeat",
            "danger":  False,
        },
        {
            "id":      "trading_sim",
            "label":   "Simulation Trading (60j)",
            "desc":    "Lance le moteur de simulation trading pour le portefeuille MAIN",
            "script":  "trading-sim/engine/run_mvp.py",
            "args":    ["--portfolio-code", "MAIN"],
            "icon":    "graph-up-arrow",
            "danger":  True,
        },
        {
            "id":      "perf_risk",
            "label":   "Calcul Performance & Risk",
            "desc":    "Calcule PnL, VaR, Sharpe, Drawdown → PortfolioPnLDaily + RiskMetricsDaily",
            "script":  "analytics/performance_risk_mvp.py",
            "args":    ["--portfolio-code", "MAIN", "--initial-nav", "100000"],
            "icon":    "shield-check",
            "danger":  False,
        },
        {
            "id":      "var_commando",
            "label":   "VaR Dérivés — CommandoQuant",
            "desc":    "Lit tbl_Greeks (CommandoQuant DB) → calcule VaR Paramétrique + Monte Carlo + Historique → génère commando-quant/var_results.xlsx",
            "script":  "commando-quant/var_engine.py",
            "args":    [],
            "icon":    "lightning-charge",
            "danger":  False,
        },
        {
            "id":      "build_ticker_lookup",
            "label":   "Rafraîchir lookup tickers",
            "desc":    "Recrée stg.stg_ticker_lookup depuis stg_bourso_price_history — accélère la recherche dans le wizard portefeuille (GROUP BY calculé 1 seule fois)",
            "script":  "scripts/build_ticker_lookup.py",
            "args":    [],
            "icon":    "search",
            "danger":  False,
        },
        {
            "id":      "create_demo_users",
            "label":   "Recréer comptes de démonstration",
            "desc":    "Supprime tous les utilisateurs non-admin et recrée les 7 comptes de démo (admin, trader, assetmanager, quant, riskanalyst, comptable, dataanalyst)",
            "script":  "scripts/create_demo_users.py",
            "args":    [],
            "icon":    "people-fill",
            "danger":  True,
        },
    ]
