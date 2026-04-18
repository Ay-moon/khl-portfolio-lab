# FactPrice from stg_bourso_price_history

## Goal

Load real market prices from:
- `[KHLWorldInvest].[stg].[stg_bourso_price_history]`

into:
- `[SmartAssetAdvicedb].[dbo].[FactPrice]`

with the maximum usable data quality.

## Implemented script

- `scripts/load_factprice_from_stg.py`

## Source and target structures used

Target (`dbo.FactPrice`):
- `DateKey` (int)
- `SecurityKey` (int)
- `ClosePrice` (decimal(19,6))
- `Volume` (bigint)
- `SourceSystem` (nvarchar(50))

Source (`stg.stg_bourso_price_history`):
- identity/metadata: `stg_id`, `date_extraction`, `load_ts`
- instrument labels: `libelle`, `sous_jacent`, `ss_jacent`, `isin`, `produit`
- prices/volumes as text: `dernier`, `volume`
- filter key: `produit_type`

## Functional rules

1. Filter source rows on `produit_type='ACTION'` (the usable subset with prices).
2. Parse French numeric formats:
   - price from `dernier` (ex: `2 034,500`, `158,000 (c)`)
   - volume from `volume`
3. Build canonical security name from:
   - `libelle` (first choice, prefix `SRD ` removed),
   - then `ss_jacent`, `sous_jacent`, `produit`, `isin`.
4. Deduplicate on `(date, canonical_security_name)` and keep the latest `(load_ts, stg_id)`.
5. Ensure `DimDate` rows exist for all source dates.
6. Match/create `DimSecurity`:
   - match on existing `SecurityName`/`Ticker`,
   - create missing securities with generated unique ticker.
7. Upsert into `FactPrice` on `(DateKey, SecurityKey)`:
   - update if exists,
   - insert otherwise.

## Run

```bash
python scripts/load_factprice_from_stg.py
```

Options:
- `--start-date YYYY-MM-DD`
- `--end-date YYYY-MM-DD`
- `--product-type ACTION`
- `--dry-run`

## Current result (latest run)

- Prepared source rows: `8439`
- Deduplicated usable rows: `699`
- Distinct dates loaded: `6`
- Distinct securities loaded: `183`
- Upsert `FactPrice`: `inserted=699`, `updated=0`

