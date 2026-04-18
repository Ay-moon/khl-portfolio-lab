"""
Build / Refresh stg.stg_ticker_lookup
======================================
Ce script pre-agrège stg_bourso_price_history (60 000+ lignes) en une
table légère stg.stg_ticker_lookup (1 ligne par ticker, ~10-15k lignes).

Gain de performance :
  AVANT  → api_securities() → GROUP BY sur 60k lignes à chaque recherche
  APRÈS  → api_securities() → SELECT sur index clustered de 10-15k lignes

Lancement manuel :
    .venv/Scripts/python.exe scripts/build_ticker_lookup.py

Lancement depuis Monitoring :
    Bouton "Rafraîchir lookup tickers" → run_job("build_ticker_lookup")
"""
import sys, os, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'webapp'))
import db, config

DDL_CREATE = """
IF OBJECT_ID('stg.stg_ticker_lookup', 'U') IS NULL
BEGIN
    CREATE TABLE stg.stg_ticker_lookup (
        ticker          NVARCHAR(50)  NOT NULL,
        asset_class     NVARCHAR(30)  NOT NULL DEFAULT 'Autre',
        nb_cot          INT           NOT NULL DEFAULT 0,
        last_price      FLOAT         NULL,
        date_debut      DATE          NULL,
        date_fin        DATE          NULL,
        updated_at      DATETIME      NOT NULL DEFAULT GETDATE(),
        CONSTRAINT PK_ticker_lookup PRIMARY KEY CLUSTERED (ticker)
    );
    -- Index pour recherche LIKE 'prefix%' (sargable)
    CREATE INDEX IX_ticker_lookup_ticker ON stg.stg_ticker_lookup (ticker);
    PRINT 'TABLE stg_ticker_lookup creee';
END
ELSE
    PRINT 'TABLE stg_ticker_lookup deja existante — truncate + reload';
"""

INSERT_LOOKUP = """
TRUNCATE TABLE stg.stg_ticker_lookup;

INSERT INTO stg.stg_ticker_lookup (ticker, nb_cot, last_price, date_debut, date_fin)
SELECT
    libelle                                                             AS ticker,
    COUNT(*)                                                            AS nb_cot,
    MAX(CASE WHEN TRY_CAST(dernier AS FLOAT) IS NOT NULL
             THEN TRY_CAST(dernier AS FLOAT) END)                      AS last_price,
    CAST(MIN(date_extraction) AS DATE)                                  AS date_debut,
    CAST(MAX(date_extraction) AS DATE)                                  AS date_fin
FROM stg.stg_bourso_price_history WITH (NOLOCK)
WHERE libelle IS NOT NULL AND LEN(libelle) >= 2
GROUP BY libelle;
"""

UPDATE_ASSET_CLASS = """
-- Actions US : '*.US'
UPDATE stg.stg_ticker_lookup
SET asset_class = 'Action US'
WHERE ticker LIKE '%.US';

-- Indices : '^*'
UPDATE stg.stg_ticker_lookup
SET asset_class = 'Indice'
WHERE ticker LIKE '^%';

-- Obligations : '*.B'
UPDATE stg.stg_ticker_lookup
SET asset_class = 'Obligation'
WHERE ticker LIKE '%.B' AND asset_class = 'Autre';

-- Forex / Matières premières
UPDATE stg.stg_ticker_lookup
SET asset_class = 'Forex/Matière première'
WHERE asset_class = 'Autre'
  AND (ticker LIKE '%USD%' OR ticker LIKE '%EUR%' OR ticker LIKE '%GBP%'
       OR ticker LIKE '%JPY%' OR ticker LIKE '%AUD%' OR ticker LIKE '%CHF%'
       OR ticker LIKE '%CAD%');
"""


def main():
    t0 = time.time()
    print("=" * 60)
    print("  stg_ticker_lookup — Build / Refresh")
    print("=" * 60)

    with db.db_cursor(database=config.SQL_DB_STG, autocommit=True) as cur:

        # 1. Créer la table si absente
        print("\n[1/3] Création / vérification de la table...")
        cur.execute(DDL_CREATE)

        # 2. Recalculer depuis la source
        print("[2/3] Insertion groupée depuis stg_bourso_price_history...")
        cur.execute(INSERT_LOOKUP)
        cur.execute("SELECT COUNT(*) FROM stg.stg_ticker_lookup")
        nb = cur.fetchone()[0]
        print(f"      >> {nb:,} tickers charges")

        # 3. Mettre à jour asset_class
        print("[3/3] Classification par asset_class...")
        cur.execute(UPDATE_ASSET_CLASS)
        cur.execute("""
            SELECT asset_class, COUNT(*) as n
            FROM stg.stg_ticker_lookup
            GROUP BY asset_class ORDER BY n DESC
        """)
        for r in cur.fetchall():
            print(f"      {r[0]:<30} {r[1]:>6,}")

    elapsed = round(time.time() - t0, 1)
    print(f"\n  [OK] Lookup prêt en {elapsed}s — {nb:,} tickers indexés.")
    print("=" * 60)


if __name__ == "__main__":
    main()
