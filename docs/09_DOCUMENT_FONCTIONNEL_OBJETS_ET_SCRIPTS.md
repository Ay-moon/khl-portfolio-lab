# Document fonctionnel - Objets et scripts du projet

## 1. Contexte et objectif metier

Ce projet met en place un **laboratoire de gestion de portefeuille** pour simuler, analyser et expliquer des decisions d'investissement.

Le but metier est de disposer d'un socle unique pour:
- centraliser des donnees de portefeuille dans un modele "Gold";
- simuler des ordres de trading avec des regles simples mais realistes;
- produire des indicateurs de performance et de risque;
- preparer une couche de restitution (Power BI) et une couche d'assistance IA explicable.

Le systeme vise une logique de type **decision support** (aide a la decision), pas de trading automatique.

## 2. Vision fonctionnelle globale

Le fonctionnement attendu est le suivant:
1. Initialiser l'environnement local et la base SQL.
2. Creer les tables/vues metier.
3. Injecter des donnees de demonstration.
4. Executer une simulation de trading sur plusieurs jours.
5. Alimenter les tables de faits (trades, positions) pour exploitation analytique.
6. Exploiter les vues pour reporting et futures sorties IA.

## 3. Objets de donnees crees (SQL) et finalite metier

## 3.1 Dimensions de reference

Fichier: `data-platform/sql/ddl/001_create_gold_tables.sql`

- `dbo.DimDate`
  - Role: calendrier de reference.
  - But metier: aligner tous les calculs sur une granularite journaliere.
- `dbo.DimSecurity`
  - Role: referentiel des instruments (ticker, classe d'actif, devise).
  - But metier: normaliser les actifs utilises dans les trades et les positions.
- `dbo.DimPortfolio`
  - Role: referentiel des portefeuilles.
  - But metier: segmenter les resultats par portefeuille et code de gestion.

## 3.2 Faits de marche, trading, performance et risque

Fichier: `data-platform/sql/ddl/001_create_gold_tables.sql`

- `dbo.FactPrice`
  - Role: prix de cloture par date et instrument.
  - But metier: base de valorisation et d'analyse des mouvements de marche.
- `dbo.FactTrades`
  - Role: execution des ordres (side, qty, prix, frais, slippage, strategie).
  - But metier: tracer les decisions de trading et leur cout reel.
- `dbo.PortfolioPositionsDaily`
  - Role: etat des positions quotidiennes.
  - But metier: connaitre exposition, valeur de marche, poids et PnL latent.
- `dbo.PortfolioPnLDaily`
  - Role: performance journaliere (daily/cum PnL, NAV, rendement).
  - But metier: piloter la performance au niveau portefeuille.
- `dbo.RiskMetricsDaily`
  - Role: metriques de risque quotidiennes (volatilite, drawdown, VaR, beta, sharpe).
  - But metier: mesurer le risque pris vs rendement obtenu.

## 3.3 Tables IA et audit

Fichier: `data-platform/sql/ddl/001_create_gold_tables.sql`

- `dbo.AI_DailyBriefing`
  - Role: stockage des syntheses IA quotidiennes.
  - But metier: industrialiser un "brief" journalier exploitable par un gerant.
- `dbo.AI_Recommendations`
  - Role: recommandations IA structurees (action, confiance, raison).
  - But metier: formaliser des suggestions tracables et controlables.
- `dbo.AI_WhatIf`
  - Role: scenarios de simulation "what-if".
  - But metier: evaluer des hypotheses de reallocation avant execution.
- `dbo.AI_AuditLog`
  - Role: journal technique/fonctionnel des evenements IA.
  - But metier: auditabilite et gouvernance (qui a fait quoi, quand, et statut).

## 4. Vues SQL creees et usage fonctionnel

Fichier: `data-platform/sql/ddl/002_create_gold_views.sql`

- `dbo.vw_FactTradesEnriched`
  - Sert a: rendre les trades lisibles metier (jointure date, portefeuille, instrument).
  - Valeur metier: faciliter controle de l'activite et analyse des couts.
- `dbo.vw_PortfolioDashboardDaily`
  - Sert a: fournir une vue quotidienne portfolio + performance + risque.
  - Valeur metier: alimenter un tableau de bord global en une seule requete.
- `dbo.vw_PositionSnapshot`
  - Sert a: consulter les positions detaillees par date et instrument.
  - Valeur metier: suivi de l'exposition et contribution des lignes.
- `dbo.vw_AI_LatestRecommendations`
  - Sert a: recuperer la recommandation IA la plus recente par couple portefeuille/instrument.
  - Valeur metier: eviter la confusion entre anciennes et nouvelles recommandations.

## 5. Scripts de seed et de bootstrap: utilite metier

## 5.1 Seed SQL de donnees de demonstration

Fichier: `data-platform/sql/dml/001_seed_gold_data.sql`

Ce script insere:
- un calendrier initial;
- des instruments de base (AAPL, MSFT, SPY);
- un portefeuille principal (`MAIN`);
- des exemples de prix, trades, positions, performance, risque;
- des enregistrements IA de demonstration.

But metier:
- disposer rapidement d'un jeu coherent pour demo, tests, QA, et mise en place des dashboards.

## 5.2 Script Python de preparation BDD

Fichier: `scripts/seed_demo_data.py`

Fonctions principales:
- chargement des variables `.env`;
- connexion SQL Server;
- creation de la base si necessaire;
- execution des scripts DDL puis DML;
- creation/verification d'une table de healthcheck.

But metier:
- securiser une initialisation reproductible de l'environnement de travail.

## 5.3 Scripts de bootstrap local (Windows/Linux)

Fichiers:
- `scripts/bootstrap_local.ps1`
- `scripts/bootstrap_local.sh`

Fonctions principales:
- creation du `.env` depuis template;
- creation de l'environnement virtuel Python;
- installation des dependances;
- execution automatique du seed.

But metier:
- reduire le temps d'onboarding et eviter les ecarts de configuration entre postes.

## 6. Composant Trading Simulation MVP: role fonctionnel

## 6.1 Objets de domaine

Fichier: `trading-sim/engine/models.py`

- `MarketOrder`: ordre de marche (BUY/SELL, quantite, date, strategie).
- `PositionState`: etat d'une position (quantite, cout moyen) avec regles d'update.
- `ExecutedTrade`: trace de l'execution avec frais/slippage/cash-flow.
- `PositionSnapshot`: photographie journaliere d'une ligne de portefeuille.

But metier:
- representer clairement les objets manipules par un moteur de simulation.

## 6.2 Generation de prix de marche

Fichier: `trading-sim/engine/pricing.py`

Fonction:
- generation d'une grille de prix pseudo-marche sur jours ouvrables.

But metier:
- permettre des tests et simulations sans dependre d'un fournisseur de data externe.

## 6.3 Moteur de simulation et valorisation

Fichier: `trading-sim/engine/simulator.py`

Fonctions:
- execution d'ordres market avec slippage et frais;
- mise a jour des positions;
- calcul des snapshots quotidiens (valeur, PnL latent, poids).

But metier:
- obtenir un comportement proche de la realite de trading (couts d'execution inclus).

## 6.4 Strategie MVP de demonstration

Fichier: `trading-sim/strategies/rotation_strategy.py`

Fonction:
- creer des ordres simples selon une logique de rotation entre tickers.

But metier:
- disposer d'un flux de trades reproductible pour alimenter la chaine analytique.

## 6.5 Orchestrateur de run vers SQL

Fichier: `trading-sim/engine/run_mvp.py`

Fonctions:
- lecture config `.env`;
- execution simulation sur N jours;
- creation/verification des dimensions necessaires;
- purge des donnees de run precedent sur la plage de dates;
- insertion des trades et positions en base.

But metier:
- transformer une simulation en donnees exploitables dans le modele Gold.

## 7. Tests crees et valeur fonctionnelle

Fichier: `trading-sim/tests/test_simulator.py`

Ce qui est teste:
- calcul execution BUY avec frais + slippage;
- reduction de position en SELL;
- blocage des ventes superieures a la position;
- coherence des poids de portefeuille (somme a 1).

But metier:
- fiabiliser les regles critiques qui impactent directement les resultats de performance.

## 8. Configuration, securite et exploitation

- `infra/secrets-template.env`
  - Sert a: formaliser les variables de connexion et d'environnement.
  - But metier: standardiser la configuration locale et limiter les erreurs manuelles.
- `.gitignore`
  - Sert a: exclure secrets, environnements et artefacts.
  - But metier: proteger les donnees sensibles et garder un repository propre.

## 9. CI/CD, Docker, IA applicative: etat fonctionnel actuel

Objets presents mais encore en squelette:
- `ai-assistant/app/*.py`, `ai-assistant/rag/*.py`, `ai-assistant/outputs/*.py`, `ai-assistant/rules/*.py`
- `docker/docker-compose.yml`
- `.github/workflows/ci-python.yml`, `.github/workflows/ci-sql.yml`, `.github/workflows/release.yml`

Interpretation fonctionnelle:
- le cadre cible est defini (assistant IA, industrialisation, deploiement),
- mais l'implementation metier de ces briques reste a finaliser.

## 10. Benefice metier global deja obtenu

A ce stade, le projet offre deja un socle fonctionnel concret:
- une base Gold structuree et chargeable;
- un moteur de simulation qui produit des donnees de trading/positions;
- des vues metier pretes pour reporting;
- un parcours local reproductible pour lancer des demos et iterations.

En termes metier, cela permet de:
- demontrer rapidement une chaine "donnee -> decision -> mesure";
- tester des hypotheses de gestion avec traces auditables;
- preparer la phase suivante: reporting Power BI et assistant IA explicable.
