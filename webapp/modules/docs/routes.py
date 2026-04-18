"""
Module Documentation — Wiki interne de la plateforme KHL Bank CIB
─────────────────────────────────────────────────────────────────
Qui est concerné : tous les utilisateurs connectés
Ce que ça fait :
  • Index des pages de documentation
  • Workflow création de portefeuille (SQL + process métier)
  • Workflow achat/vente dans un portefeuille
  • Matrice des rôles (qui voit quoi)
  • Journal des corrections/évolutions (changelog auto depuis AppLog)
"""
from flask import Blueprint, render_template, session, send_file
from auth.routes import login_required
import db, os

docs_bp = Blueprint("docs", __name__, url_prefix="/docs")

# ── Entrées du changelog : corrections et features ajoutées ──────────
CHANGELOG = [
    {
        "date":    "2026-04-17",
        "version": "3.3",
        "type":    "bugfix",
        "title":   "Fix cinématique trade — OrderKey absent de FactTrades Gold",
        "desc":    "La route /trading/trade/<id> crashait (trade=None) car la requête SQL référençait "
                   "t.OrderKey inexistant dans le schéma Gold FactTrades. Corrigé : OrderKey récupéré "
                   "depuis FactTradeLifecycle. Ajout redirect+flash dans le except pour éviter tout "
                   "render avec trade=None. Config.py rendu paramétrable via env vars KHL_* et "
                   "lecture automatique du .env existant. db.py : message d'erreur de connexion enrichi.",
        "author":  "ADMIN",
    },
    {
        "date": "2026-04-16",
        "version": "3.2",
        "type": "feature",
        "title": "Architecture Graphique Dynamique — diagrammes animés Chart.js",
        "desc": "Nouvelle page /docs/graphical : 6 sections avec diagrammes dynamiques animés. "
                "Diag. 1 : flux de centralisation sources→plateforme→use cases avec particules animées. "
                "Diag. 2 : grille des 10 modules par office (Front/Middle/Back) avec hover effects. "
                "Diag. 3 : cinématique trade 10 étapes avec animation séquentielle auto-play + barre de progression. "
                "Diag. 4 : pipeline 4 couches (Sources→Lookup→Gold→Analytics) avec flèches animées. "
                "Diag. 5 : matrice rôles/modules couleur-codée. "
                "Diag. 6 : 4 charts Chart.js (donut offices, donut tables SQL, bar lifecycle log scale, bar rôles). "
                "Compteurs animés (61 608 tickers, 10 modules, etc.) déclenchés au scroll. "
                "Route Flask /docs/graphical sert le fichier docs/graphical_arch.html via send_file(). "
                "Lien ajouté dans /docs index et dans docs/index.html sidebar.",
        "author": "ADMIN",
    },
    {
        "date": "2026-04-16",
        "version": "3.1",
        "type": "feature",
        "title": "Cinématique trade — workflow complet Front→Middle→Back avec SWIFT simulé",
        "desc": "Nouvelle table DimBroker (6 brokers CIB : BNP, SG, GS, JPM, BofA, Exane avec BIC SWIFT). "
                "Nouvelle table FactTradeLifecycle : 10 statuts horodatés par trade "
                "(PRE_TRADE_CHECK → RECONCILED), références SWIFT simulées (MT515/541/543/544/546). "
                "Chaque order_new() génère automatiquement le cycle de vie complet. "
                "Nouvelle page /trading/trade/<id> : timeline verticale, carte broker, messages SWIFT ISO 15022, "
                "journal comptable CIB, graphique phases Chart.js (échelle log). "
                "Tableau trading/index enrichi : colonne statut lifecycle + bouton cinématique par ligne.",
        "author": "ADMIN",
    },
    {
        "date": "2026-04-16",
        "version": "3.0",
        "type": "feature",
        "title": "Mode Investisseur Retail — portefeuilles dès 500 €, guide débutant",
        "desc": "Nouveau type de client 'Particulier — Investisseur Retail' dans le wizard étape 1 : "
                "capital dès 500 € (vs 10 000 € avant), profil risque Modéré pré-sélectionné, "
                "bannière guidée avec conseil taille de position selon le capital. "
                "Étape 2 adaptée : badges Recommandé/Avancé sur les classes d'actifs, "
                "section 'Starter kit débutant' avec 5 ETF mondiaux (SPY, QQQ, IWDA, EEM, GSPC), "
                "conseil diversification automatique selon le capital saisi. "
                "Le mode pro reste inchangé pour les rôles institutionnels.",
        "author": "ADMIN",
    },
    {
        "date": "2026-04-16",
        "version": "2.9",
        "type": "feature",
        "title": "Lookup tickers pré-agrégé — recherche wizard portefeuille x10 plus rapide",
        "desc": "Création de stg.stg_ticker_lookup : table pré-agrégée (1 ligne/ticker, ~10-15k lignes) "
                "générée par scripts/build_ticker_lookup.py depuis stg_bourso_price_history (60k lignes). "
                "api_securities() utilise automatiquement le lookup si disponible, "
                "fallback transparent sur GROUP BY sinon. "
                "Job 'Rafraîchir lookup tickers' ajouté dans Monitoring. "
                "Gain estimé : 2-5s → <100ms par recherche.",
        "author": "ADMIN",
    },
    {
        "date": "2026-04-16",
        "version": "2.8",
        "type": "feature",
        "title": "Comptes de démonstration — 7 utilisateurs par rôle métier",
        "desc": "Script scripts/create_demo_users.py : supprime tous les comptes non-admin, "
                "crée/met à jour 7 comptes (admin, trader, assetmanager, quant, riskanalyst, comptable, dataanalyst). "
                "Mots de passe documentés dans ce changelog et dans CLAUDE.md. "
                "Job 'Recréer comptes de démonstration' ajouté dans Monitoring. "
                "Optimisation wizard étape 2 : cache mémoire Python pour top_us/top_indices, "
                "WITH (NOLOCK) sur staging, debounce 400ms, minimum 2 chars, LIKE sargable.",
        "author": "ADMIN",
    },
    {
        "date": "2026-04-14",
        "version": "2.7",
        "type": "feature",
        "title": "Cloisonnement Front/Middle/Back — badges sidebar + page accès refusé percutante",
        "desc": "Sidebar restructurée avec sections FRONT / MIDDLE / BACK colorées par office. "
                "Rôle + badge office affiché pour chaque utilisateur connecté. "
                "Nouveau rôle COMPTABLE (Back Office, niveau 2). "
                "role_required() rend access_denied.html : identité utilisateur, module tenté, "
                "qui peut y accéder, liens vers ses propres modules. "
                "Hiérarchie ROLE_HIERARCHY + OFFICE_META dans config.py. "
                "MODULE_ROLES généré automatiquement.",
        "author": "ADMIN",
    },
    {
        "date": "2026-04-14",
        "version": "2.6",
        "type": "feature",
        "title": "Cloisonnement Front/Middle/Back Office — séparation des tâches",
        "desc": "Refonte complète de la matrice des rôles. "
                "TRADER (Front) : trading, risk, quant — exécute, ne comptabilise PAS. "
                "ASSET_MANAGER (Front) : portfolio, performance, risk, powerbi — décide, n'exécute PAS. "
                "QUANT (Front) : quant, portfolio, risk — recherche uniquement. "
                "RISK_ANALYST (Middle) : risk, performance, alm, powerbi — contrôle, ne touche ni ordres ni compta. "
                "ALM_OFFICER (Middle) : alm, risk, performance. "
                "DATA_ANALYST (Back) : accounting, monitoring, performance, powerbi — comptabilise, n'exécute PAS. "
                "Route /trading/order/new verrouillée TRADER+ADMIN uniquement. "
                "Route /accounting verrouillée DATA_ANALYST+RISK_ANALYST+ADMIN.",
        "author": "ADMIN",
    },
    {
        "date": "2026-04-14",
        "version": "2.5",
        "type": "feature",
        "title": "Plan CIB complet — DimAccountInternal + FactAccountingEvent/Movement",
        "desc": "Implémentation complète du plan de comptes CIB (ref 12_CONTEXTE_CIBLE_CIB_COMPTA.md) : "
                "25 comptes CIB (120100 Titres, 140200 Dettes brokers, 110100 Cash Nostro, 510100 Courtage…). "
                "Remplacement des codes maison par le plan normé. "
                "FactAccountingEvent (header EventType/Status/CorrelationId) + FactAccountingMovement "
                "(DebitAmount/CreditAmount séparés + AmountSigned computed). "
                "FactSettlementMovement (PENDING J+2 à chaque ordre). "
                "FactReconciliationControl (contrôle EOD Débit=Crédit). "
                "AppLog enrichi : correlation_id, before_payload, after_payload. "
                "Contrôle pre-trade risk dans order_new (BLOCKED si breach max_order_notional). "
                "Job EOD Monitoring. Module Comptabilité mis à jour.",
        "author": "ADMIN",
    },
    {
        "date": "2026-04-14",
        "version": "2.3",
        "type": "feature",
        "title": "Comptabilité — Journal en partie double (/accounting)",
        "desc": "Nouveau module /accounting : journal comptable complet avec écritures en partie double. "
                "Chaque ordre (BUY/SELL) génère 2 écritures dans dbo.JournalEntries "
                "(510 Titres / 512 Espèces + 615 Frais). Balance des comptes par portefeuille. "
                "Accessible ASSET_MANAGER, TRADER, RISK_ANALYST, ADMIN. "
                "Lien direct depuis le formulaire d'ordre Trading.",
        "author": "ADMIN",
    },
    {
        "date": "2026-04-14",
        "version": "2.2",
        "type": "feature",
        "title": "Trading Desk — Saisie manuelle d'ordres BUY/SELL",
        "desc": "Formulaire de saisie d'ordre dans Trading Desk : portefeuille, ticker, côté BUY/SELL, "
                "quantité, prix d'exécution, frais (bps), type d'ordre (MARKET/LIMIT), notes. "
                "Enregistrement simultané dans dbo.Orders (carnet), dbo.FactTrades (historique) "
                "et dbo.JournalEntries (comptabilité). Slippage 0.5 bps estimé automatiquement. "
                "Accessible TRADER, ASSET_MANAGER, QUANT, ADMIN.",
        "author": "ADMIN",
    },
    {
        "date": "2026-04-14",
        "version": "2.1",
        "type": "feature",
        "title": "Documentation — Cycle de vie d'une transaction (Front/Middle/Back)",
        "desc": "Nouvelle page /docs/transaction-lifecycle : pipeline visuel Front→Middle→Back, "
                "tableau détaillé des 10 étapes avec rôles, modules et tables SQL archivées, "
                "cartographie complète SQL Server (KHLWorldInvest + CommandoQuant), "
                "matrice résumée qui-fait-quoi par rôle.",
        "author": "ADMIN",
    },
    {
        "date": "2026-04-14",
        "version": "2.0",
        "type": "feature",
        "title": "CommandoQuant — Migration complète Access → SQL Server",
        "desc": "Création de la base CommandoQuant sur PERSO-AJE-DELL\\BFASERVER01 avec table tbl_Greeks "
                "(colonnes Vol/Prix + computed aliases ImpliedVol/Price pour compatibilité var_engine.py). "
                "VBA patché via win32com : CDatabase, CBlotter, BtnGreeks_, BtnPnLSim_ → connexions SQLOLEDB "
                "avec Trusted_Connection Windows Auth. SET DATEFORMAT ymd ajouté pour compatibilité locale française. "
                "Suppression de toute dépendance Access (.accdb). "
                "Macro déplacée dans commando-quant/ (projet unifié). "
                "OUTPUT_PATH de var_engine.py rendu portable (os.path.dirname).",
        "author": "ADMIN",
    },
    {
        "date": "2026-04-14",
        "version": "1.9",
        "type": "feature",
        "title": "CommandoQuant — VBA chemins génériques + ouverture inplace",
        "desc": "CommandoQuant.xlsm intégré dans commando-quant/ avec var_engine.py. "
                "Tous les chemins VBA hardcodés remplacés par ThisWorkbook.Path et Environ('LOCALAPPDATA') "
                "via patch_vba_commando.py (win32com). "
                "Ouverture depuis le portail Trading Desk via os.startfile() (pas de téléchargement). "
                "Job 'VaR Dérivés' ajouté dans Monitoring pour lancer var_engine.py depuis l'interface.",
        "author": "ADMIN",
    },
    {
        "date": "2026-04-14",
        "version": "1.8",
        "type": "feature",
        "title": "Tooltips financiers Risk + Quant + Trading, gestion admin utilisateurs",
        "desc": "Tooltips Bootstrap 5 sur tous les KPIs Risk Management (Volatilité, VaR, Sharpe, Drawdown, Beta) "
                "avec formules et seuils. Détection VaR aberrante (warning si valeur hors plage). "
                "Légende tickers dans Quant/Data Lab (^ indice, .US action US, 6L = Forex). "
                "Story-block Trading Desk avec workflow 4 étapes. "
                "Gestion utilisateurs ADMIN : activation/désactivation, changement rôle, reset mot de passe "
                "(/auth/admin-users). Compte ADMIN créé via scripts/create_admin.py.",
        "author": "ADMIN",
    },
    {
        "date": "2026-04-14",
        "version": "1.7",
        "type": "feature",
        "title": "Power BI — formulaire configuration complet",
        "desc": "Page Power BI refondée : formulaire serveur / workspace / login / mot de passe "
                "(avec affichage/masquage). Panneau s'ouvre automatiquement si non configuré. "
                "Rôles RISK_ANALYST et ADMIN ajoutés à l'accès Power BI. "
                "Stockage des 5 clés dans AppSettings.",
        "author": "ADMIN",
    },
    {
        "date": "2026-04-13",
        "version": "1.6",
        "type": "feature",
        "title": "Système Tooltips générique + CLAUDE.md",
        "desc": "Tooltips Bootstrap 5 natifs initialisés globalement dans base.html. "
                "Icône .khl-tip (? bleu) sur tous les champs financiers complexes du wizard étape 1 et 3. "
                "KPIs portefeuille annotés (Market Value, PnL, en-têtes tableau). "
                "CLAUDE.md créé à la racine : guide de dev pour futures sessions LLM.",
        "author": "ADMIN",
    },
    {
        "date": "2026-04-13",
        "version": "1.5",
        "type": "feature",
        "title": "Module Documentation",
        "desc": "Ajout du wiki interne (/docs) : workflows, rôles, changelog.",
        "author": "ADMIN",
    },
    {
        "date": "2026-04-13",
        "version": "1.5",
        "type": "feature",
        "title": "Power BI Service intégré",
        "desc": "L'URL du service Power BI est saisie par l'admin et stockée en base SQL (AppSettings). "
                "Affichage en iframe. Configuration persistée entre redémarrages.",
        "author": "ADMIN",
    },
    {
        "date": "2026-04-13",
        "version": "1.5",
        "type": "feature",
        "title": "Excel VBA — accès par rôle",
        "desc": "Les fichiers VBA/Excel sont téléchargeables depuis le Trading Desk (rôles TRADER, QUANT, ADMIN). "
                "Chemin configurable via AppSettings.",
        "author": "ADMIN",
    },
    {
        "date": "2026-04-13",
        "version": "1.4",
        "type": "bugfix",
        "title": "FactTrades — colonnes SQL incorrectes",
        "desc": "portfolio/routes.py et trading/routes.py référençaient t.TradeType (inexistant), "
                "t.ExecutedPrice (inexistant), t.DateKey (inexistant). "
                "Corrigé en t.Side, t.Price, t.TradeDateKey conformément au DDL 001_create_gold_tables.sql.",
        "author": "ADMIN",
    },
    {
        "date": "2026-04-13",
        "version": "1.3",
        "type": "feature",
        "title": "Récupération / renouvellement de mot de passe",
        "desc": "Ajout des pages /auth/forgot et /auth/reset. Table PasswordResetTokens créée en SQL. "
                "Token 12 caractères, valide 30 min. Affiché à l'écran (app locale, pas d'email).",
        "author": "ADMIN",
    },
]


@docs_bp.route("/graphical")
@login_required
def graphical():
    """Architecture graphique dynamique — diagrammes animés Chart.js."""
    _here = os.path.dirname(os.path.abspath(__file__))
    path = os.path.abspath(os.path.join(_here, "..", "..", "..", "docs", "graphical_arch.html"))
    return send_file(path, mimetype="text/html")


@docs_bp.route("/")
@login_required
def index():
    """Page d'accueil de la documentation."""
    return render_template("modules/docs/index.html", changelog=CHANGELOG[:3])


@docs_bp.route("/transaction-lifecycle")
@login_required
def transaction_lifecycle():
    """Cycle de vie complet d'une transaction — Front / Middle / Back."""
    return render_template("modules/docs/transaction_lifecycle.html")


@docs_bp.route("/portfolio-workflow")
@login_required
def portfolio_workflow():
    """Workflow complet création de portefeuille."""
    return render_template("modules/docs/portfolio_workflow.html")


@docs_bp.route("/trading-workflow")
@login_required
def trading_workflow():
    """Workflow achat/vente dans un portefeuille."""
    return render_template("modules/docs/trading_workflow.html")


@docs_bp.route("/roles")
@login_required
def roles():
    """Matrice complète des rôles."""
    import config
    return render_template("modules/docs/roles.html", roles=config.ROLES, modules=config.MODULES)


@docs_bp.route("/changelog")
@login_required
def changelog():
    """Journal complet des corrections et évolutions."""
    # Récupère aussi les derniers logs applicatifs de type ADMIN
    recent_logs = []
    try:
        with db.db_cursor() as cur:
            cur.execute("""
                SELECT TOP 50
                    FORMAT(log_ts,'yyyy-MM-dd HH:mm') as ts,
                    level, module, action, detail, username
                FROM dbo.AppLog
                WHERE level IN ('INFO','WARN','ERROR')
                ORDER BY log_id DESC
            """)
            for r in cur.fetchall():
                recent_logs.append({
                    "ts": r[0], "level": r[1], "module": r[2],
                    "action": r[3], "detail": r[4], "user": r[5],
                })
    except Exception:
        pass
    return render_template("modules/docs/changelog.html",
                           changelog=CHANGELOG, recent_logs=recent_logs)
