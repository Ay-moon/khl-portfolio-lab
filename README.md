<div align="center">

# KHL Bank CIB Platform

**Plateforme de gestion de portefeuille bancaire — Front to Back**

[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white)](https://python.org)
[![Flask](https://img.shields.io/badge/Flask-3.x-000000?logo=flask&logoColor=white)](https://flask.palletsprojects.com)
[![SQL Server](https://img.shields.io/badge/SQL_Server-2019+-CC2927?logo=microsoftsqlserver&logoColor=white)](https://www.microsoft.com/sql-server)
[![Bootstrap](https://img.shields.io/badge/Bootstrap-5.3-7952B3?logo=bootstrap&logoColor=white)](https://getbootstrap.com)
[![Power BI](https://img.shields.io/badge/Power_BI-Tabular_Model-F2C811?logo=powerbi&logoColor=black)](https://powerbi.microsoft.com)
[![License](https://img.shields.io/badge/License-MIT-green)](LICENSE)

*Simulation · Performance & Risk · ALM · Quant Lab · AI Assistant · Power BI*

---

</div>

## Vue d'ensemble

**KHL Bank CIB Platform** est une plateforme bancaire de démonstration couvrant l'intégralité du cycle front-to-back d'une salle des marchés. Elle simule les flux réels d'une banque d'investissement : décisions d'allocation, exécution des ordres, comptabilisation, contrôle des risques et reporting.

> Projet portfolio démontrant la maîtrise de l'architecture data bancaire, du développement full-stack et des outils quantitatifs.

---

## Architecture globale

```
┌─────────────────────────────────────────────────────────────────────┐
│                        SOURCES DE DONNÉES                           │
│  Boursorama STG  │  ESMA DLTINS  │  Stooq (prix)  │  CommandoQuant │
└────────┬─────────┴───────┬───────┴───────┬─────────┴───────┬────────┘
         │                 │               │                 │
         ▼                 ▼               ▼                 ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     DATA PLATFORM — SQL Server                      │
│                                                                     │
│   STG Layer (KHLWorldInvest)                                        │
│   stg_bourso_price_history · stg_ticker_lookup · ESMA_DLTINS_WIDE  │
│                         │                                           │
│                         ▼                                           │
│   GOLD Layer (SmartAssetAdvicedb)                                   │
│   DimDate · DimSecurity · DimPortfolio                              │
│   FactPrice · FactTrades · PortfolioPositionsDaily                  │
│   PortfolioPnLDaily · RiskMetricsDaily                              │
│   AI_DailyBriefing · AI_Recommendations · AI_WhatIf                │
└──────────────────────────┬──────────────────────────────────────────┘
                           │
         ┌─────────────────┼──────────────────┐
         ▼                 ▼                  ▼
┌─────────────┐   ┌─────────────────┐  ┌───────────────┐
│  WEBAPP     │   │  ANALYTICS      │  │  POWER BI     │
│  Flask App  │   │  Engine Python  │  │  Tabular Model│
│  8 modules  │   │  PnL·VaR·Sharpe │  │  DirectQuery  │
└─────────────┘   └─────────────────┘  └───────────────┘
```

---

## Stack technique

| Composant | Technologie | Rôle |
|---|---|---|
| **Backend** | Flask 3.x (Python) | API + rendu templates — blueprints modulaires |
| **Base de données** | SQL Server 2019+ | Gold layer, staging, auth — Windows Auth |
| **Frontend** | Bootstrap 5.3 + Chart.js | UI responsive — zéro framework JS |
| **Auth** | SHA-256 + salt maison | Session Flask, table `AppUsers` |
| **Config** | `AppSettings` (clé/valeur SQL) | Config persistante sans fichier |
| **Data Pipeline** | pyodbc + scripts Python | ETL STG → Gold |
| **Trading Engine** | Python custom | Simulation ordres, fees, slippage |
| **Quant** | pandas, numpy, scipy | VaR, Sharpe, drawdown, backtesting |
| **Power BI** | Modèle tabulaire TMDL | Import Dims + DirectQuery Facts |
| **AI** | Anthropic Claude API | Briefings, recommandations, what-if |
| **VBA / Excel** | CommandoQuant.xlsm | Pricing options, greeks |

---

## Modules applicatifs

### Front Office

| Module | Rôle métier |
|---|---|
| **Création Portefeuille** | Wizard 6 étapes : profil risque, allocation, validation |
| **Trading Desk** | Carnet d'ordres BUY/SELL, historique, export VBA Excel |
| **Quant / Data Lab** | Explorateur Stooq, backtesting stratégies, séries temporelles |

### Middle Office

| Module | Rôle métier |
|---|---|
| **Risk Management** | VaR 95/99%, drawdown, volatilité, alertes limites |
| **Performance** | NAV quotidien, PnL cumulé, Sharpe ratio, attribution |
| **ALM** | Gap de liquidité, duration, ratios LCR/NSFR |

### Back Office

| Module | Rôle métier |
|---|---|
| **Comptabilité** | Journal en partie double, balance CIB, rapprochements EOD |
| **Monitoring** | Logs applicatifs, jobs, santé système |
| **Power BI** | Rapports embarqués depuis service Power BI |

### Transverse

| Module | Rôle |
|---|---|
| **AI Assistant** | Briefing quotidien, recommandations, scénarios what-if (Claude API) |
| **Documentation** | Wiki interne, workflows métier, changelog |
| **Admin** | Gestion utilisateurs, config Power BI, logs |

---

## Structure du projet

```
khl-portfolio-lab/
│
├── webapp/                          # Application Flask principale
│   ├── app.py                       # Point d'entrée, enregistrement blueprints
│   ├── config.py                    # Connexion SQL, rôles, modules
│   ├── db.py                        # Couche DB : cursor, settings, logs
│   ├── auth/routes.py               # Login / logout / reset password
│   └── modules/
│       ├── portfolio/               # Wizard création portefeuille
│       ├── trading/                 # Carnet d'ordres
│       ├── risk/                    # VaR, drawdown, alertes
│       ├── performance/             # PnL, NAV, Sharpe
│       ├── alm/                     # Gap liquidité, LCR/NSFR
│       ├── quant/                   # Backtesting, Stooq explorer
│       ├── accounting/              # Journal comptable
│       ├── monitoring/              # Logs, jobs
│       └── docs/                   # Wiki interne + changelog
│
├── data-platform/
│   ├── sql/ddl/                     # DDL Gold (tables, vues, indexes)
│   ├── sql/dml/                     # Seeds, migrations
│   ├── bronze/ silver/ gold/        # Couches data lake (scripts)
│   └── pipelines/                   # Orchestration ETL
│
├── trading-sim/
│   └── engine/                      # Simulateur d'ordres (models, run_mvp)
│
├── analytics/
│   └── performance_risk_mvp.py      # Calcul PnL, VaR, Sharpe, drawdown
│
├── ai-assistant/
│   ├── app/main.py                  # CLI : daily-briefing, recommendations
│   ├── prompts/                     # Templates prompts Claude
│   └── rules/                       # Règles métier pour les recommandations
│
├── commando-quant/
│   ├── CommandoQuant.xlsm           # Outil Excel VBA pricing options/greeks
│   └── var_engine.py                # Moteur VaR Python pour les greeks
│
├── powerbi/
│   ├── model/                       # Modèle tabulaire TMDL
│   └── theme/                       # Thème JSON KHL
│
├── scripts/
│   ├── seed_demo_data.py            # Données de démonstration complètes
│   ├── create_demo_users.py         # 7 comptes de démonstration
│   ├── load_factprice_from_stg.py   # Pipeline prix STG → Gold
│   └── validate_sql.py             # Validation qualité SQL
│
├── docs/                            # Documentation HTML statique
├── docker/                          # Containerisation (WIP)
├── .github/workflows/               # CI/CD GitHub Actions
├── requirements.txt
└── START_WEBAPP.bat                 # Lancement rapide Windows
```

---

## Démarrage rapide

### Prérequis

- Python 3.11+
- SQL Server 2019+ (Windows Auth)
- ODBC Driver 17 for SQL Server

### Installation

```bash
# 1. Cloner le repo
git clone https://github.com/Ay-moon/khl-portfolio-lab.git
cd khl-portfolio-lab

# 2. Environnement virtuel
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # Linux/macOS

# 3. Dépendances
pip install -r requirements.txt

# 4. Variables d'environnement
cp infra/secrets-template.env .env
# Editer .env avec vos paramètres SQL Server
```

### Base de données

```bash
# Créer les tables Gold (idempotent)
python -c "from webapp.db import init_db; init_db()"

# Données de démonstration (portefeuilles, titres, trades, prix)
python scripts/seed_demo_data.py

# Créer les comptes utilisateurs de démo
python scripts/create_demo_users.py
```

### Lancer l'application

```bash
# Option A — Script Windows
START_WEBAPP.bat

# Option B — Commande Python
python webapp/app.py
```

Ouvrir : **http://localhost:5000**

---

## Comptes de démonstration

| Rôle | Login | Office |
|---|---|---|
| Administrateur | `admin` | Système |
| Asset Manager | `assetmanager` | Front Office |
| Trader | `trader` | Front Office |
| Quant | `quant` | Front Office |
| Risk Analyst | `riskanalyst` | Middle Office |
| Comptable | `comptable` | Back Office |
| Data Analyst | `dataanalyst` | Back Office |

---

## Pipeline de données

```
Boursorama HTML ──► stg.stg_bourso_price_history (111M lignes)
                              │
                    load_factprice_from_stg.py
                              │
                    ┌─────────▼────────┐
                    │  dbo.DimSecurity │◄── ESMA DLTINS (ISIN / CFI)
                    │  dbo.FactPrice   │◄── stg_ticker_lookup (61k tickers)
                    └─────────┬────────┘
                              │
                   trading-sim/engine/run_mvp.py
                              │
                    ┌─────────▼────────────────┐
                    │  dbo.FactTrades           │
                    │  dbo.PortfolioPositions   │
                    └─────────┬────────────────┘
                              │
                   analytics/performance_risk_mvp.py
                              │
                    ┌─────────▼──────────────┐
                    │  dbo.PortfolioPnLDaily  │
                    │  dbo.RiskMetricsDaily   │
                    └─────────┬──────────────┘
                              │
                         Power BI / Webapp
```

---

## Modèle de données Gold

```
DimDate ──────┐
              ├──► FactPrice
DimSecurity ──┤
              ├──► FactTrades ──► PortfolioPositionsDaily
DimPortfolio ─┘                        │
                                        └──► PortfolioPnLDaily
                                        └──► RiskMetricsDaily

AI_DailyBriefing · AI_Recommendations · AI_WhatIf · AI_AuditLog
AppUsers · AppSettings · AppLog · PasswordResetTokens
```

---

## Hiérarchie des accès (Chinese Wall)

```
                    ADMIN
                      │
        ┌─────────────┼──────────────┐
        │             │              │
   FRONT OFFICE  MIDDLE OFFICE  BACK OFFICE
   ─────────────  ─────────────  ──────────
   Asset Manager  Risk Analyst   Comptable
   Trader         ALM Officer    Data Analyst
   Quant
   
   Règle : Qui DÉCIDE ≠ Qui EXÉCUTE ≠ Qui COMPTABILISE
```

---

## CI/CD

| Workflow | Déclencheur | Action |
|---|---|---|
| `ci-python.yml` | Push `*.py` | Lint + compile check |
| `ci-sql.yml` | Push `*.sql` | Validation SQL qualité |
| `release.yml` | Tag `v*` | Package release |

---

## Données de marché

- **Stooq** — cotations historiques (104M lignes, indices + actions US)
- **Boursorama STG** — actions françaises (scraping structuré)
- **ESMA DLTINS** — référentiel instruments européens (ISIN, CFI, MIC)
- **STG ticker lookup** — 61 608 tickers référencés

---

## License

[MIT](LICENSE) — Aymen Jebabli
