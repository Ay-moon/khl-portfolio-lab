"""
Module ALM — Asset & Liability Management
─────────────────────────────────────────────────────────────
Qui est concerné : ALM_OFFICER, RISK_ANALYST
Ce que ça fait :
  • Gap de liquidité (actif vs passif)
  • Sensibilité taux (duration, BPV)
  • Scénarios de stress taux (+100bp / -100bp)
  • Ratios réglementaires LCR / NSFR
"""
from flask import Blueprint, render_template
from auth.routes import login_required
import db

alm_bp = Blueprint("alm", __name__, url_prefix="/alm")


@alm_bp.route("/")
@login_required
def index():
    # Données simulées pour la démo ALM
    # En production, ces données viendraient de tables ALM dédiées
    gap_data = [
        {"bucket": "0–1 mois",  "actifs": 12500000, "passifs": 15000000},
        {"bucket": "1–3 mois",  "actifs": 8000000,  "passifs": 7500000},
        {"bucket": "3–6 mois",  "actifs": 15000000, "passifs": 12000000},
        {"bucket": "6–12 mois", "actifs": 20000000, "passifs": 18000000},
        {"bucket": "1–3 ans",   "actifs": 35000000, "passifs": 30000000},
        {"bucket": "3–5 ans",   "actifs": 25000000, "passifs": 22000000},
        {"bucket": "> 5 ans",   "actifs": 18000000, "passifs": 14000000},
    ]

    stress_scenarios = [
        {"name": "Choc +100bp",  "impact_actifs": -4.2, "impact_passifs": -3.8, "impact_net": -0.4},
        {"name": "Choc +200bp",  "impact_actifs": -8.1, "impact_passifs": -7.2, "impact_net": -0.9},
        {"name": "Choc -100bp",  "impact_actifs":  4.1, "impact_passifs":  3.7, "impact_net":  0.4},
        {"name": "Choc -200bp",  "impact_actifs":  8.5, "impact_passifs":  7.9, "impact_net":  0.6},
        {"name": "Crise 2008",   "impact_actifs":-15.3, "impact_passifs": -8.2, "impact_net": -7.1},
        {"name": "COVID 2020",   "impact_actifs":-22.1, "impact_passifs": -9.5, "impact_net":-12.6},
    ]

    ratios = {
        "lcr":   {"value": 142.5, "min": 100, "label": "LCR (Liquidity Coverage Ratio)"},
        "nsfr":  {"value": 118.3, "min": 100, "label": "NSFR (Net Stable Funding Ratio)"},
        "lvr":   {"value":  8.2,  "min":   3, "label": "Levier (Leverage Ratio CRR2)"},
    }

    duration_data = {
        "duration_actifs":  5.8,
        "duration_passifs": 6.2,
        "gap_duration":    -0.4,
        "bpv_actifs":    -58000,
        "bpv_passifs":    62000,
        "bpv_net":         4000,
    }

    return render_template(
        "modules/alm/index.html",
        gap_data=gap_data,
        stress_scenarios=stress_scenarios,
        ratios=ratios,
        duration=duration_data,
    )
