# Inventaire Modules et Traitements

Ce document donne une vue detaillee de:
- chaque script/module,
- son role,
- ses inputs/outputs,
- la techno utilisee,
- l'endroit ou il est execute/installe.

## 1) Installation et emplacements

| Element | Valeur |
|---|---|
| Racine projet | `d:\ATELIER_IT\PROJETS_PYTHON\khl-portfolio-lab` |
| Environnement Python | `.venv` |
| Dependances Python | `requirements.txt` (`pyodbc`) |
| Config | `.env` (template: `infra/secrets-template.env`) |
| Base SQL cible | `SQL_DATABASE` (ex: `SmartAssetAdvicedb`) |
| Schema cible | `dbo` |
| Base SQL source staging | `SQL_DATABASE_STG` (ex: `KHLWorldInvest`) |
| Schema source staging | `stg` |

## 2) Scripts d'orchestration (jobs)

| Script | Role | Input | Output | Tech | Execution |
|---|---|---|---|---|---|
| `scripts/bootstrap_local.ps1` | Bootstrap local Windows | template env, `requirements.txt` | `.env`, `.venv`, deps installees, seed lance | PowerShell | Poste dev Windows |
| `scripts/bootstrap_local.sh` | Bootstrap local Linux/macOS | template env, `requirements.txt` | `.env`, `.venv`, deps installees, seed lance | Bash | Linux/macOS |
| `scripts/seed_demo_data.py` | Initialise DB (DDL/DML) | `.env`, SQL files DDL/DML | Tables/vues creees, donnees seedees | Python + `pyodbc` | Local -> SQL Server |
| `scripts/load_factprice_from_stg.py` | Ingestion prix reels staging -> Gold | `stg.stg_bourso_price_history` | `DimDate`, `DimSecurity`, `FactPrice` | Python + `pyodbc` | Local -> SQL Server |
| `scripts/validate_sql.py` | Validation statique SQL pour CI | fichiers SQL sous `data-platform/sql` | rapport OK/FAIL CI | Python | GitHub Actions / local |
| `trading-sim/engine/run_mvp.py` | Simulation trading et chargement SQL | params run, pricing, strategy | `FactTrades`, `PortfolioPositionsDaily` | Python + `pyodbc` | Local -> SQL Server |
| `analytics/performance_risk_mvp.py` | Calcul perf/risk journalier | `FactTrades`, `PortfolioPositionsDaily`, `FactPrice` | `PortfolioPnLDaily`, `RiskMetricsDaily` | Python + `pyodbc` | Local -> SQL Server |
| `ai-assistant/app/main.py` | Orchestrateur IA MVP | Gold views/tables + args CLI | ecrit AI_* (hors dry-run) | Python + `pyodbc` | Local -> SQL Server |

## 3) SQL Data Platform

| Fichier SQL | Objet installe | Input | Output |
|---|---|---|---|
| `data-platform/sql/ddl/001_create_gold_tables.sql` | Dimensions, facts, tables AI, index, contraintes | Schema cible vide ou partiel | Modele Gold + tables AI disponibles |
| `data-platform/sql/ddl/002_create_gold_views.sql` | Vues de consommation (trades, positions, dashboard, latest recos) | Tables Gold/AI | Vues SQL pretes pour BI/IA |
| `data-platform/sql/dml/001_seed_gold_data.sql` | Jeu de donnees demo | Tables existantes | Donnees initiales pour demo/tests |

## 4) Trading Simulation (details implementation)

| Module | Comment c'est implemente | Input | Output |
|---|---|---|---|
| `trading-sim/engine/models.py` | Dataclasses metier + regles `apply_buy`/`apply_sell` + validations | Ordres + etat position | Etats de position coherents + objets execution |
| `trading-sim/engine/pricing.py` | Generation jours ouvres + random walk controle des prix | `tickers`, `start_date`, `days` | `calendar`, grille `prices[date][ticker]` |
| `trading-sim/engine/simulator.py` | Execution ordre market avec frais/slippage, snapshots poids/PnL latent | Ordre, prix, position | `ExecutedTrade`, `PositionSnapshot` |
| `trading-sim/strategies/rotation_strategy.py` | Strategie rotation simple selon jour/index et positions | prix du jour, positions | Liste `MarketOrder` |
| `trading-sim/engine/run_mvp.py` | Orchestration end-to-end + insertion SQL + purge re-run | args CLI + modules ci-dessus | Ecrit en base `FactTrades` et `PortfolioPositionsDaily` |

## 5) Analytics Performance & Risk (details implementation)

| Module | Comment c'est implemente | Input | Output |
|---|---|---|---|
| `analytics/performance_risk_mvp.py` | Rebuild NAV via cash-flow trades + market value positions, calcule Vol20d/Drawdown/VaR95/Sharpe, purge plage puis insert | `FactTrades`, `PortfolioPositionsDaily`, `FactPrice` | `PortfolioPnLDaily`, `RiskMetricsDaily` |

## 6) Assistant IA MVP (details implementation)

| Module | Etat | Comment c'est implemente | Input | Output |
|---|---|---|---|---|
| `ai-assistant/app/config.py` | Implemente | Charge `.env`, valide provider et variables SQL | `.env` | `AssistantConfig` |
| `ai-assistant/app/db.py` | Implemente | Connexion SQL, parse date, resolve portfolio/date, ensure `DimDate` | config + args | `connection`, `portfolio_key`, `date_key` |
| `ai-assistant/rag/context_schema.py` | Implemente | Dataclasses contexte (headline, positions, latest recos) | donnees SQL | `ContextPack` structure |
| `ai-assistant/rag/retriever.py` | Implemente | Requetes sur `vw_PortfolioDashboardDaily`, `vw_PositionSnapshot`, `vw_AI_LatestRecommendations` | portfolio/date | `ContextPack` |
| `ai-assistant/outputs/schemas.py` | Implemente | Schemas typed + validations (actions, confidence, target weight) | objets IA | objets valides/erreurs |
| `ai-assistant/rules/constraints.py` | Implemente | Guardrails metier (langage auto-trading interdit, limites concentration) | sortie IA | liste d'issues |
| `ai-assistant/rules/postcheck.py` | Implemente | Controle qualite final (doublons, longueur reasoning, etc.) | sortie IA | liste d'issues/erreur |
| `ai-assistant/outputs/writers.py` | Implemente | Ecriture SQL `AI_DailyBriefing`, `AI_Recommendations`, `AI_WhatIf`, `AI_AuditLog` | sortie validee + keys | rows ecrites en base |
| `ai-assistant/app/main.py` | Implemente | CLI `daily-briefing`, `recommendations`, `what-if`; pipeline `retrieve -> mock generate -> validate -> constraints -> postcheck -> write` | args CLI + SQL | JSON preview (`--dry-run`) ou ecriture AI_* |
| `ai-assistant/prompts/*.md` | Placeholder simple | Fichiers de prompts presents mais minimalistes | texte prompt | base pour futur provider reel |

## 7) Frameworks, libs, runtime

| Composant | Utilise |
|---|---|
| Langage principal | Python |
| DB driver | `pyodbc` |
| Tests | `unittest` |
| Scripts shell | PowerShell / Bash |
| Base de donnees | SQL Server |
| CI/CD | GitHub Actions (CI Python + CI SQL + release operationnels) |
| Conteneurisation | Docker compose (placeholder) |

## 8) Tests existants

| Test | Couvre |
|---|---|
| `trading-sim/tests/test_simulator.py` | Execution ordres, frais/slippage, snapshots |
| `analytics/tests/test_performance_risk_mvp.py` | Formules PnL/risk |
| `scripts/tests/test_load_factprice_from_stg.py` | Parsing FR, dedup, mapping ticker |
| `scripts/tests/test_validate_sql.py` | Qualite statique des scripts SQL |
| `ai-assistant/tests/test_schemas_and_rules.py` | Validation schemas + contraintes/postcheck IA |

## 9) Ce qui reste a implementer (roadmap courte)

| Zone | Reste a faire |
|---|---|
| AI provider reel | Brancher `openai` dans `ai-assistant/app/main.py` (actuellement mock only) |
| Prompts IA | Enrichir `ai-assistant/prompts/*.md` avec prompts metier complets |
| Docker | Definir stack reelle dans `docker/docker-compose.yml` |

## 10) Commandes utiles (operation)

```bash
# Bootstrap
scripts/bootstrap_local.ps1

# Ingestion prix reels
python scripts/load_factprice_from_stg.py

# Simulation trading
python trading-sim/engine/run_mvp.py --portfolio-code MAIN

# Performance & risk
python analytics/performance_risk_mvp.py --portfolio-code MAIN --initial-nav 100000

# IA MVP (dry-run)
python ai-assistant/app/main.py daily-briefing --portfolio-code MAIN --provider mock --dry-run
python ai-assistant/app/main.py recommendations --portfolio-code MAIN --provider mock --dry-run
python ai-assistant/app/main.py what-if --portfolio-code MAIN --provider mock --dry-run
```
