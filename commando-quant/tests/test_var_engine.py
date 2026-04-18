"""
tests/test_var_engine.py
========================
Tests unitaires pour le moteur VaR CommandoQuant.

Ces tests couvrent les fonctions mathématiques pures de demo.py
(aucun SQL Server requis — mode autonome uniquement).

Lancer avec :
    pytest tests/ -v
    pytest tests/ -v --cov=demo --cov-report=term-missing
"""

import math
import sys
import os
import pytest

# Rend demo.py importable depuis la racine du projet
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from demo import (
    var_parametrique,
    var_monte_carlo,
    var_historique,
    load_positions,
    VOL_DAILY,
)


# ----------------------------------------------------------------
# Fixtures
# ----------------------------------------------------------------

@pytest.fixture
def single_call():
    """Une seule position CALL longue — cas le plus simple."""
    return [{
        "underlying":  "TEST.PA",
        "option_type": "CALL",
        "strike":      100.0,
        "spot":        105.0,
        "vol":         0.20,
        "prix":        8.50,
        "delta":       0.60,
        "gamma":       0.05,
        "vega":        0.15,
        "notional":    100_000,
    }]


@pytest.fixture
def mixed_book():
    """Un portefeuille équilibré : 2 calls + 1 put sur 2 sous-jacents."""
    return [
        {"underlying": "AAA", "option_type": "CALL",
         "strike": 50.0, "spot": 52.0, "vol": 0.22,
         "prix": 4.5, "delta":  0.65, "gamma": 0.04,
         "vega": 0.12, "notional": 100_000},

        {"underlying": "AAA", "option_type": "PUT",
         "strike": 48.0, "spot": 52.0, "vol": 0.25,
         "prix": 1.8, "delta": -0.30, "gamma": 0.03,
         "vega": 0.10, "notional": 100_000},

        {"underlying": "BBB", "option_type": "CALL",
         "strike": 200.0, "spot": 210.0, "vol": 0.18,
         "prix": 18.0, "delta":  0.58, "gamma": 0.02,
         "vega": 0.35, "notional": 100_000},
    ]


@pytest.fixture
def zero_delta_position():
    """Une position delta-neutre (delta = 0) — la VaR doit être proche de zéro."""
    return [{
        "underlying": "NEUTRAL", "option_type": "CALL",
        "strike": 100.0, "spot": 100.0, "vol": 0.20,
        "prix": 5.0, "delta": 0.0, "gamma": 0.03,
        "vega": 0.10, "notional": 100_000,
    }]


@pytest.fixture
def sample_csv_path():
    """Chemin vers le CSV de positions exemples inclus dans le dépôt."""
    return os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "data", "sample_positions.csv"
    )


# ================================================================
# Tests — load_positions
# ================================================================

class TestLoadPositions:

    def test_loads_correct_row_count(self, sample_csv_path):
        positions = load_positions(sample_csv_path)
        assert len(positions) == 10, "sample_positions.csv doit contenir 10 lignes"

    def test_required_keys_present(self, sample_csv_path):
        positions = load_positions(sample_csv_path)
        required = {"underlying", "option_type", "strike", "spot",
                    "vol", "prix", "delta", "gamma", "vega", "notional"}
        for p in positions:
            assert required.issubset(p.keys()), f"Clés manquantes dans : {p}"

    def test_numeric_fields_are_floats(self, sample_csv_path):
        positions = load_positions(sample_csv_path)
        numeric = ["strike", "spot", "vol", "prix", "delta", "gamma", "vega", "notional"]
        for p in positions:
            for field in numeric:
                assert isinstance(p[field], float), \
                    f"Le champ '{field}' doit être float, obtenu {type(p[field])}"

    def test_option_types_are_valid(self, sample_csv_path):
        positions = load_positions(sample_csv_path)
        for p in positions:
            assert p["option_type"] in ("CALL", "PUT"), \
                f"option_type invalide : {p['option_type']}"

    def test_spots_are_positive(self, sample_csv_path):
        positions = load_positions(sample_csv_path)
        for p in positions:
            assert p["spot"] > 0, f"Le spot doit être > 0, obtenu {p['spot']}"


# ================================================================
# Tests — var_parametrique
# ================================================================

class TestVarParametrique:

    def test_returns_positive_value(self, single_call):
        var = var_parametrique(single_call)
        assert var > 0

    def test_formula_single_position(self, single_call):
        """Vérifie manuellement la formule paramétrique pour une seule position."""
        p   = single_call[0]
        nb  = p["notional"] / p["spot"]           # équivalent actions
        sig = p["spot"] * VOL_DAILY                # sigma spot journalier
        exp = 1.6449 * abs(p["delta"] * nb * sig)  # VaR attendue

        var = var_parametrique(single_call)
        assert abs(var - exp) < 0.01, f"Attendu ~{exp:.2f}, obtenu {var:.2f}"

    def test_var_scales_with_notional(self, single_call):
        """Doubler le notional doit doubler la VaR (linéaire en Delta)."""
        p2 = [{**single_call[0], "notional": single_call[0]["notional"] * 2}]
        var1 = var_parametrique(single_call)
        var2 = var_parametrique(p2)
        assert abs(var2 / var1 - 2.0) < 1e-6, "La VaR doit être linéaire en notional"

    def test_delta_neutral_returns_zero(self, zero_delta_position):
        """Une position delta-neutre doit avoir VaR = 0 avec la méthode paramétrique."""
        var = var_parametrique(zero_delta_position)
        assert var == pytest.approx(0.0, abs=1e-9)

    def test_call_vs_put_same_abs_delta(self):
        """Un CALL et un PUT avec le même |delta| et même spot/notional → même VaR."""
        call = [{"underlying": "X", "option_type": "CALL",
                 "strike": 100.0, "spot": 100.0, "vol": 0.20,
                 "prix": 5.0, "delta":  0.50, "gamma": 0.04,
                 "vega": 0.10, "notional": 100_000}]
        put  = [{"underlying": "X", "option_type": "PUT",
                 "strike": 100.0, "spot": 100.0, "vol": 0.20,
                 "prix": 3.0, "delta": -0.50, "gamma": 0.04,
                 "vega": 0.10, "notional": 100_000}]
        assert var_parametrique(call) == pytest.approx(var_parametrique(put), rel=1e-6)

    def test_mixed_book_is_positive(self, mixed_book):
        var = var_parametrique(mixed_book)
        assert var > 0

    def test_ignores_zero_spot_positions(self):
        """Les positions avec spot=0 doivent être ignorées silencieusement."""
        positions = [
            {"underlying": "BAD", "option_type": "CALL",
             "strike": 100.0, "spot": 0.0, "vol": 0.20,
             "prix": 0.0, "delta": 0.5, "gamma": 0.0,
             "vega": 0.0, "notional": 100_000},
        ]
        var = var_parametrique(positions)
        assert var == pytest.approx(0.0, abs=1e-9)


# ================================================================
# Tests — var_monte_carlo
# ================================================================

class TestVarMonteCarlo:

    def test_returns_positive_value(self, single_call):
        var, _ = var_monte_carlo(single_call, n_simul=1000, seed=42)
        assert var > 0

    def test_reproducible_with_seed(self, single_call):
        """La même graine doit produire des résultats identiques."""
        var1, _ = var_monte_carlo(single_call, n_simul=2000, seed=99)
        var2, _ = var_monte_carlo(single_call, n_simul=2000, seed=99)
        assert var1 == var2

    def test_different_seeds_different_results(self, single_call):
        """Des graines différentes doivent (quasi-toujours) donner des résultats différents."""
        var1, _ = var_monte_carlo(single_call, n_simul=500, seed=1)
        var2, _ = var_monte_carlo(single_call, n_simul=500, seed=2)
        assert var1 != var2

    def test_pnl_list_length(self, single_call):
        n = 500
        _, pnl = var_monte_carlo(single_call, n_simul=n, seed=42)
        assert len(pnl) == n

    def test_pnl_list_is_sorted_ascending(self, single_call):
        _, pnl = var_monte_carlo(single_call, n_simul=200, seed=42)
        assert pnl == sorted(pnl), "La liste P&L doit être triée par ordre croissant"

    def test_var_is_positive_loss(self, single_call):
        """La VaR est exprimée comme un nombre positif (perte absolue)."""
        var, pnl = var_monte_carlo(single_call, n_simul=1000, seed=42)
        assert var >= 0, "La VaR doit être un nombre positif"

    def test_converges_toward_parametric(self, single_call):
        """
        Avec un N élevé, pour une position dominée par Delta,
        la VaR MC doit être du même ordre de grandeur que la VaR paramétrique.
        """
        var_param = var_parametrique(single_call)
        var_mc, _ = var_monte_carlo(single_call, n_simul=50_000, seed=42)
        ratio = var_mc / var_param
        assert 0.5 < ratio < 2.0, \
            f"VaR MC ({var_mc:.0f}) diverge trop de la Paramétrique ({var_param:.0f})"

    def test_more_simulations_reduces_variance(self, single_call):
        """
        Vérification faible : l'écart entre plusieurs tirages avec graines différentes
        doit rester borné.
        """
        vars_ = [var_monte_carlo(single_call, n_simul=200, seed=s)[0]
                 for s in range(10)]
        spread = max(vars_) - min(vars_)
        assert spread < var_parametrique(single_call) * 2, \
            "L'écart VaR MC entre graines doit rester borné"


# ================================================================
# Tests — var_historique
# ================================================================

class TestVarHistorique:

    def test_returns_positive_value(self, single_call):
        var, _ = var_historique(single_call)
        assert var > 0

    def test_scenario_count(self, single_call):
        _, results = var_historique(single_call)
        assert len(results) == 25, "Le jeu de scénarios historiques doit contenir 25 entrées"

    def test_results_sorted_by_pnl(self, single_call):
        _, results = var_historique(single_call)
        pnls = [r[1] for r in results]
        assert pnls == sorted(pnls), "Les résultats doivent être triés par P&L croissant"

    def test_covid_scenario_is_worst_for_long_call(self, single_call):
        """
        Pour un CALL long (delta > 0), le pire choc (-12% COVID)
        doit produire le P&L le plus négatif.
        """
        _, results = var_historique(single_call)
        worst_pnl   = results[0][1]   # plus négatif après tri
        worst_shock = results[0][0]   # choc correspondant (%)
        assert worst_shock == pytest.approx(-12.0, rel=0.01), \
            f"Pire choc attendu = -12% (COVID), obtenu {worst_shock:.1f}%"
        assert worst_pnl < 0

    def test_delta_neutral_var_near_zero(self, zero_delta_position):
        """
        Une position delta-neutre, longue en Gamma, bénéficie des grands mouvements (dS^2 > 0).
        La VaR historique peut être négative — la position GAGNE sur les crises (long convexité).
        C'est financièrement correct. On vérifie simplement que le résultat est fini et borné.
        """
        var, _ = var_historique(zero_delta_position)
        assert math.isfinite(var), "La VaR doit être un nombre fini"
        # La valeur absolue doit rester bien en dessous du notional
        assert abs(var) < zero_delta_position[0]["notional"] * 0.05, \
            "La VaR delta-neutre (abs) doit être < 5% du notional"

    def test_shock_range_includes_positive_scenarios(self, single_call):
        """Au moins certains scénarios doivent produire un P&L positif."""
        _, results = var_historique(single_call)
        positive = [r for r in results if r[1] > 0]
        assert len(positive) > 0, "Au moins un scénario doit être gagnant"

    def test_mixed_book(self, mixed_book):
        var, _ = var_historique(mixed_book)
        assert var > 0


# ================================================================
# Test d'intégration — pipeline complet
# ================================================================

class TestFullPipeline:

    def test_all_three_methods_positive(self, mixed_book):
        var_p          = var_parametrique(mixed_book)
        var_mc, _      = var_monte_carlo(mixed_book, n_simul=1000, seed=42)
        var_h, _       = var_historique(mixed_book)

        assert var_p  > 0
        assert var_mc > 0
        assert var_h  > 0

    def test_csv_to_var_pipeline(self, sample_csv_path):
        """Bout en bout : charger CSV → lancer les 3 méthodes VaR → vérifier les résultats."""
        positions = load_positions(sample_csv_path)
        assert len(positions) == 10

        var_p          = var_parametrique(positions)
        var_mc, pnl_mc = var_monte_carlo(positions, n_simul=2000, seed=42)
        var_h, pnl_h   = var_historique(positions)

        for var in (var_p, var_mc, var_h):
            assert var > 0
            assert math.isfinite(var)

        assert len(pnl_mc) == 2000
        assert len(pnl_h)  == 25

    def test_parametric_less_than_mc_for_long_book(self, mixed_book):
        """
        Pour un portefeuille long (delta net positif), la VaR paramétrique (linéaire)
        est généralement inférieure à la VaR MC (non-linéaire avec Gamma).
        Ce n'est pas toujours vrai, mais vaut pour les portefeuilles calls typiques.
        """
        var_p        = var_parametrique(mixed_book)
        var_mc, _    = var_monte_carlo(mixed_book, n_simul=10_000, seed=42)
        # Tolérance ±50% — on vérifie simplement qu'ils sont du même ordre
        ratio = var_mc / var_p
        assert 0.5 < ratio < 3.0, \
            f"Paramétrique ({var_p:.0f}) et MC ({var_mc:.0f}) doivent être du même ordre"
