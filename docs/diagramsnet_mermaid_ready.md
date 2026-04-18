# Diagrams.net - Texte pret a coller (Mermaid)

## Comment l'utiliser dans app.diagrams.net
1. Ouvrir `https://app.diagrams.net/`
2. Menu `Arrange` -> `Insert` -> `Advanced` -> `Mermaid`
3. Coller un bloc ci-dessous
4. Cliquer `Insert`

---

## 1) Diagramme global complet (application end-to-end)

```mermaid
flowchart LR
    DEV["Poste dev\nPowerShell/Bash"] --> BOOT["bootstrap_local.ps1/.sh"]
    BOOT --> VENV["Python .venv\npyodbc"]

    subgraph SRC["Source data server"]
        STGDB["KHLWorldInvest\nschema stg"]
        STGTBL["stg_bourso_price_history"]
        STGDB --> STGTBL
    end

    subgraph TGT["Target SQL Server"]
        GOLDDB["SmartAssetAdvicedb\ndbo"]

        subgraph DIM["Dimensions"]
            DD["DimDate"]
            DS["DimSecurity"]
            DP["DimPortfolio"]
        end

        subgraph FACT["Facts"]
            FP["FactPrice"]
            FT["FactTrades"]
            POS["PortfolioPositionsDaily"]
            PNL["PortfolioPnLDaily"]
            RISK["RiskMetricsDaily"]
        end

        subgraph AI["AI tables"]
            AIB["AI_DailyBriefing"]
            AIR["AI_Recommendations"]
            AIW["AI_WhatIf"]
            AIL["AI_AuditLog"]
        end

        subgraph VW["SQL Views"]
            V1["vw_FactTradesEnriched"]
            V2["vw_PositionSnapshot"]
            V3["vw_PortfolioDashboardDaily"]
            V4["vw_AI_LatestRecommendations"]
        end
    end

    subgraph APP["Python modules / scripts"]
        SEED["scripts/seed_demo_data.py"]
        LOAD["scripts/load_factprice_from_stg.py"]
        SIM["trading-sim/engine/run_mvp.py"]
        ANL["analytics/performance_risk_mvp.py"]
        AIPOC["ai-assistant/*\n(currently TODO)"]
    end

    VENV --> SEED
    VENV --> LOAD
    VENV --> SIM
    VENV --> ANL
    VENV --> AIPOC

    SEED --> GOLDDB
    STGTBL --> LOAD
    LOAD --> DD
    LOAD --> DS
    LOAD --> FP

    SIM --> FT
    SIM --> POS
    SIM --> DD
    SIM --> DS
    SIM --> DP

    FP --> ANL
    FT --> ANL
    POS --> ANL
    ANL --> PNL
    ANL --> RISK

    FT --> V1
    POS --> V2
    PNL --> V3
    RISK --> V3
    AIR --> V4

    subgraph BI["Reporting"]
        PBI["Power BI dashboards"]
    end

    V1 --> PBI
    V2 --> PBI
    V3 --> PBI
    V4 --> PBI

    AIPOC -. future read/write .-> AIB
    AIPOC -. future read/write .-> AIR
    AIPOC -. future read/write .-> AIW
    AIPOC -. future logging .-> AIL
```

---

## 2) Workflow execution (ordre des traitements)

```mermaid
flowchart TD
    A["1. bootstrap_local.ps1/.sh"] --> B["2. seed_demo_data.py\nDDL + DML"]
    B --> C["3. load_factprice_from_stg.py\n(optional but recommended)"]
    C --> D["4. run_mvp.py\ntrades + positions"]
    D --> E["5. performance_risk_mvp.py\nPnL + Risk"]
    E --> F["6. SQL Views"]
    F --> G["7. Power BI"]
    F --> H["8. AI assistant runtime (future)"]
```

---

## 3) Diagramme detail ingestion FactPrice

```mermaid
flowchart LR
    S["stg_bourso_price_history"] --> P1["Parse FR numbers\nprice/volume"]
    P1 --> P2["Canonical security name"]
    P2 --> P3["Dedup by (date, security)\nkeep latest load_ts/stg_id"]
    P3 --> P4["Ensure DimDate"]
    P4 --> P5["Match/Create DimSecurity"]
    P5 --> P6["MERGE FactPrice\ninsert/update"]
```

---

## 4) Diagramme detail simulation + analytics

```mermaid
flowchart LR
    MKT["Synthetic prices\npricing.py"] --> STRAT["RotationStrategy"]
    STRAT --> EXEC["TradingSimulator\nfees + slippage"]
    EXEC --> TRD["FactTrades"]
    EXEC --> SNAP["PortfolioPositionsDaily"]

    TRD --> PERF["performance_risk_mvp.py"]
    SNAP --> PERF
    PRC["FactPrice"] --> PERF

    PERF --> OUT1["PortfolioPnLDaily"]
    PERF --> OUT2["RiskMetricsDaily"]
```

---

## 5) Diagramme serveurs / environnements

```mermaid
flowchart LR
    DEV["Developer machine\nWindows + .venv"] --> SQL["SQL Server instance"]
    DEV --> GIT["GitHub repository"]
    GIT --> CI["GitHub Actions\n(current placeholder)"]

    SQL --> DB1["SmartAssetAdvicedb\ndbo"]
    SQL --> DB2["KHLWorldInvest\nstg"]
```

