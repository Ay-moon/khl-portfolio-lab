# Architecture Technique Globale - KHL Portfolio Lab

## 1) Objectif et perimetre

Ce document decrit l'architecture complete du projet, avec une vue claire de:
- modules applicatifs,
- traitements de donnees,
- serveurs et bases,
- workflows d'execution,
- points de controle (qualite, audit, re-run).

Le projet couvre un flux "lab" de gestion de portefeuille:
1. charger/normaliser des donnees,
2. simuler du trading,
3. calculer performance et risque,
4. exposer des vues pour reporting,
5. preparer la couche assistant IA (encore partiellement en TODO).

## 2) Vue d'ensemble (System Landscape)

```text
                          +-----------------------+
                          |   Poste Developpeur   |
                          |  (PowerShell / Bash)  |
                          +-----------+-----------+
                                      |
                                      | scripts/*.py
                                      v
                      +---------------+------------------+
                      |         Python Runtime           |
                      |     (.venv + pyodbc driver)      |
                      +---+---------------+--------------+
                          |               |
          SQL read/write  |               | SQL read (source prices)
                          v               v
     +--------------------+----+     +----+----------------------+
     | SQL Server cible        |     | SQL Server source data    |
     | SmartAssetAdvicedb      |     | KHLWorldInvest            |
     | schema dbo (Gold + AI)  |     | schema stg                |
     +-----------+-------------+     +---------------------------+
                 |
                 | views / tables
                 v
     +-----------+-------------+
     | Reporting (Power BI)    |
     | (structure presente)    |
     +-------------------------+
```

## 3) Modules et responsabilites

### 3.1 Data Platform (SQL)
- DDL Gold model: `data-platform/sql/ddl/001_create_gold_tables.sql`
- Vues metier: `data-platform/sql/ddl/002_create_gold_views.sql`
- Seed demo: `data-platform/sql/dml/001_seed_gold_data.sql`

Role:
- definir le schema de reference (dimensions, faits, tables IA),
- fournir les vues de consommation analytics/reporting.

### 3.2 Scripts d'initialisation et ingestion
- Bootstrap local: `scripts/bootstrap_local.ps1`, `scripts/bootstrap_local.sh`
- Seed DB + execution DDL/DML: `scripts/seed_demo_data.py`
- Ingestion prix reels depuis staging: `scripts/load_factprice_from_stg.py`

Role:
- rendre l'environnement reproductible,
- alimenter `FactPrice` avec donnees de marche nettoyees.

### 3.3 Moteur Trading Simulation MVP
- Modeles domaine: `trading-sim/engine/models.py`
- Generation de prix: `trading-sim/engine/pricing.py`
- Execution ordres + snapshots: `trading-sim/engine/simulator.py`
- Strategie MVP: `trading-sim/strategies/rotation_strategy.py`
- Orchestration run + insertion SQL: `trading-sim/engine/run_mvp.py`

Role:
- simuler des ordres BUY/SELL avec frais/slippage,
- produire des positions journalieres en base.

### 3.4 Analytics Performance & Risk MVP
- Calcul metriques: `analytics/performance_risk_mvp.py`

Role:
- recalculer NAV/PnL journaliers,
- calculer risque (volatilite 20j, drawdown, VaR95, Sharpe),
- charger `PortfolioPnLDaily` et `RiskMetricsDaily`.

### 3.5 Assistant IA (etat actuel)
- Dossiers: `ai-assistant/app`, `ai-assistant/rag`, `ai-assistant/outputs`, `ai-assistant/rules`
- Prompts presents: `ai-assistant/prompts/*.md`
- Implementation Python: majoritairement TODO.

Role cible:
- construire un contexte,
- generer briefing/recommandations/what-if,
- ecrire en tables AI_* avec audit.

## 4) Serveurs, bases et schemas

### 4.1 Cible principale (Gold)
- Serveur SQL (configurable): `SQL_SERVER`
- Base cible: `SQL_DATABASE` (ex: `SmartAssetAdvicedb`)
- Schema principal: `dbo`

Tables principales:
- Dimensions: `DimDate`, `DimSecurity`, `DimPortfolio`
- Faits: `FactPrice`, `FactTrades`, `PortfolioPositionsDaily`, `PortfolioPnLDaily`, `RiskMetricsDaily`
- IA/Audit: `AI_DailyBriefing`, `AI_Recommendations`, `AI_WhatIf`, `AI_AuditLog`

### 4.2 Source marche (staging existant)
- Base source: `SQL_DATABASE_STG` (ex: `KHLWorldInvest`)
- Schema source: `SQL_SCHEMA_STG` (ex: `stg`)
- Table source: `stg_bourso_price_history`

## 5) Workflows de traitement

## Workflow A - Bootstrap environnement + schema

```text
bootstrap_local.(ps1|sh)
        |
        +--> cree .env depuis template (si absent)
        +--> cree .venv
        +--> installe requirements.txt
        +--> lance scripts/seed_demo_data.py
                       |
                       +--> applique DDL (tables + vues)
                       +--> applique DML (seed demo)
                       +--> healthcheck table
```

Sortie:
- base cible prete avec model Gold + jeu de demo.

## Workflow B - Ingestion FactPrice depuis staging

```text
stg.stg_bourso_price_history
        |
        +--> parse numeriques FR (prix/volume)
        +--> canonicalisation nom instrument
        +--> dedup (date, instrument) latest load_ts/stg_id
        +--> ensure DimDate
        +--> match/create DimSecurity
        +--> MERGE dbo.FactPrice (insert/update)
```

Sortie:
- `FactPrice` alimente avec donnees utilisables.

## Workflow C - Simulation trading vers Gold

```text
run_mvp.py
   |
   +--> genere calendrier + prix synthetiques
   +--> construit ordres (RotationStrategy)
   +--> execute ordres (frais/slippage)
   +--> met a jour positions
   +--> calcule snapshots quotidiens
   +--> ecrit FactTrades + PortfolioPositionsDaily
```

Sortie:
- historique trades et positions journalieres.

## Workflow D - Performance & Risk

```text
Sources:
  FactTrades + PortfolioPositionsDaily + FactPrice
        |
        +--> verification prix manquants (guardrail)
        +--> calcul cash flows et market value
        +--> reconstruction NAV / PnL journalier
        +--> calcul metriques risque
        +--> purge plage dates
        +--> insert PortfolioPnLDaily + RiskMetricsDaily
```

Sortie:
- metriques pretes pour dashboards et analyses.

## Workflow E - Reporting (etat)

```text
vw_PortfolioDashboardDaily
vw_PositionSnapshot
vw_FactTradesEnriched
vw_AI_LatestRecommendations
        |
        +--> consommation Power BI (structure en place)
```

Etat:
- vues SQL operationnelles,
- artefacts Power BI non versionnes a ce stade.

## Workflow F - AI Assistant (cible)

```text
Gold tables + prompts
       |
       +--> build context (RAG)
       +--> LLM call (mock/real provider)
       +--> post-check constraints
       +--> write AI outputs + audit log
```

Etat:
- workflow defini dans la conception,
- implementation Python encore majoritairement TODO.

## 6) Diagramme de flux global de donnees

```text
 [STG Market Data] ---> [load_factprice_from_stg.py] ----+
                                                         |
 [Pricing+Strategy] ---> [trading run_mvp.py] ----------+--> [SQL Gold Tables]
                                                         |        |
                                                         |        +--> [analytics/performance_risk_mvp.py]
                                                         |                    |
                                                         |                    +--> PortfolioPnLDaily / RiskMetricsDaily
                                                         |
                                                         +--> [Gold Views] ---> [Power BI]
                                                         |
                                                         +--> [AI tables] <--- (future ai-assistant runtime)
```

## 7) Orchestration recommandee (ordre d'execution)

1. `scripts/bootstrap_local.ps1` ou `scripts/bootstrap_local.sh`
2. `python scripts/load_factprice_from_stg.py` (optionnel mais recommande pour data reelle)
3. `python trading-sim/engine/run_mvp.py --portfolio-code MAIN`
4. `python analytics/performance_risk_mvp.py --portfolio-code MAIN --initial-nav 100000`
5. Consommation via vues SQL / Power BI

## 8) Qualite, controles et tests

Tests unitaires existants:
- `trading-sim/tests/test_simulator.py`
- `analytics/tests/test_performance_risk_mvp.py`
- `scripts/tests/test_load_factprice_from_stg.py`

Controles metier implementes:
- validation side BUY/SELL et quantites > 0,
- impossibilite de vendre plus que la position,
- guardrail prix manquants avant calcul PnL/Risk,
- comportement re-runnable (purge plage cible puis reinsert).

CI/CD:
- workflows GitHub presents mais encore placeholder (`TODO`).

## 9) Securite et configuration

Configuration via `.env`:
- connexion SQL Server (`SQL_SERVER`, `SQL_DATABASE`, `SQL_USER`, `SQL_PASSWORD`, `SQL_DRIVER`),
- references plateformes (`SQL_DATABASE_STG`, etc.),
- cle IA optionnelle (`OPENAI_API_KEY`).

Pratiques deja en place:
- separation config / code,
- seed reproductible,
- tables d'audit IA prevues dans le schema.

## 10) Etat d'avancement architectural

Parties operationnelles:
- schema Gold + vues,
- seed/bootstrap,
- ingestion prix staging -> FactPrice,
- simulation trading -> tables de faits,
- calcul Performance & Risk -> tables metriques,
- tests unitaires coeur de logique.

Parties en construction:
- runtime complet `ai-assistant`,
- industrialisation Docker,
- pipelines CI/CD effectifs,
- livrables Power BI versionnes.

## 11) Matrice composant -> entrees/sorties

| Composant | Entrees | Sorties |
|---|---|---|
| `seed_demo_data.py` | `.env`, SQL DDL/DML files | schema + donnees demo |
| `load_factprice_from_stg.py` | `stg_bourso_price_history` | `DimDate`, `DimSecurity`, `FactPrice` |
| `run_mvp.py` | params run + pricing + strategy | `FactTrades`, `PortfolioPositionsDaily` |
| `performance_risk_mvp.py` | `FactTrades`, `PortfolioPositionsDaily`, `FactPrice` | `PortfolioPnLDaily`, `RiskMetricsDaily` |
| SQL Views | tables Gold/AI | datasets de consommation |
| `ai-assistant/*` (cible) | Gold views/tables + prompts | AI_* + logs audit |
