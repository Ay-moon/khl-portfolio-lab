# 12_CONTEXTE_CIBLE_CIB_COMPTA

Date de reference: 2026-04-14
Perimetre: KHL Portfolio Lab (mode Academy + mode Live)

## 1) Decision d architecture (validee)

Decision: conserver une seule application KHL et renforcer le cloisonnement par modules independants.

Pourquoi:
- Simplicite d usage (un seul point d entree).
- Simplicite d installation (repo leger, bootstrap unique).
- Trajectoire claire vers un usage reel (banque CIB) sans casser la base existante.
- Archivage centralise dans SQL Server.

Regle directrice:
- "Simple, cloisonne, auditable".

## 2) Cloisonnement metier cible

Front Office:
- Asset Manager: allocation, objectifs, mandat.
- Quant: recherche, signaux, scenarios, stress.
- Trader: execution des ordres.

Middle Office:
- Risk Manager: controles pre-trade, limites, post-trade, alertes.
- Performance: PnL, attribution, benchmark.

Back Office:
- Settlement: confirmations, statut de reglement, incidents.
- Comptabilite: ecritures en partie double, cloture, rapprochements.
- Controle/Audit: piste complete des actions et validations.

Separation des responsabilites:
- Une meme personne ne doit pas "decider + valider + comptabiliser" la meme transaction.

## 3) Experience utilisateur par role (des la connexion)

A la connexion, afficher une info-bulle obligatoire:
- Votre role.
- Vos missions prioritaires.
- Ce que vous pouvez faire.
- Ce que vous ne pouvez pas faire.
- Les modules visibles.
- Les reportings/KPI obligatoires.

Exigence UX:
- Ecran d accueil cible par role.
- Menu filtre par role.
- Aucun module "bruite" ou inutile pour le role connecte.

## 4) Cycle de vie transaction unique (front -> back)

1. Idee d investissement (Quant/Asset Manager)
2. Controle pre-trade (Risk)
3. Creation ordre (Trader)
4. Validation ou blocage (Risk/Conformite)
5. Execution
6. Allocation portefeuille/book
7. Confirmation
8. Settlement
9. Ecriture comptable
10. Rapprochement et reporting

Statuts minimum obligatoires:
- DRAFT, SUBMITTED, APPROVED, BLOCKED, EXECUTED, ALLOCATED, CONFIRMED, SETTLED, POSTED, RECONCILED, CANCELLED.

## 5) Reference comptable interne CIB (minimum)

Important:
- Ce plan est un plan de comptes interne cible KHL (pilotage et industrialisation).
- Il doit etre aligne ensuite avec les obligations locales (France/UE), normes IFRS et reporting prudentiel.

### 5.1 Plan de comptes interne (noyau minimal)

| Compte | Libelle | Nature | Usage CIB |
|---|---|---|---|
| 110100 | Cash EUR Nostro | Actif | Tresorerie disponible EUR |
| 110200 | Cash USD Nostro | Actif | Tresorerie disponible USD |
| 120100 | Titres de transaction - Actions | Actif | Positions actions de trading |
| 120200 | Titres de transaction - Obligations | Actif | Positions obligataires |
| 130100 | Derives actifs a la juste valeur | Actif | MTM positif derives |
| 130200 | Derives passifs a la juste valeur | Passif | MTM negatif derives |
| 140100 | Creances brokers | Actif | Sommes a recevoir brokers |
| 140200 | Dettes brokers | Passif | Sommes a payer brokers |
| 140300 | Marges initiales deposees | Actif | Collateral verse |
| 140400 | Marges variation a recevoir | Actif | VM positive |
| 140500 | Marges variation a payer | Passif | VM negative |
| 150100 | Frais a payer - execution | Passif | Courtage/frais non regles |
| 150200 | Taxes sur transactions a payer | Passif | Taxes de marche |
| 160100 | Suspens cash | Actif/Passif | Ecart temporaire cash |
| 160200 | Suspens titres | Actif/Passif | Ecart temporaire titres |
| 210100 | Capital / fonds propres internes | Passif | Base de pilotage interne |
| 310100 | Engagements hors bilan - achats | Hors bilan | Ordres/engagements non denoues |
| 310200 | Engagements hors bilan - ventes | Hors bilan | Ordres/engagements non denoues |
| 410100 | PnL realise - trading | Produit/Charge | Resultat realise |
| 410200 | PnL latent - variation juste valeur | Produit/Charge | MTM EOD |
| 510100 | Charges de courtage | Charge | Commissions brokers |
| 510200 | Charges de slippage | Charge | Impact execution |
| 510300 | Charges de financement | Charge | Cout funding |
| 610100 | Produits dividendes | Produit | Flux dividendes |
| 610200 | Produits coupons | Produit | Flux coupons |
| 610300 | Resultat de change | Produit/Charge | Revalo FX |

Convention:
- Prefixe 1xxxxx: bilan actif/passif operationnel.
- Prefixe 3xxxxx: hors bilan engagements.
- Prefixe 4xxxxx: resultat trading (realise/latent).
- Prefixe 5xxxxx: charges d execution/funding.
- Prefixe 6xxxxx: produits financiers.

### 5.2 Ecritures types (minimum)

Achat titre (trade date):
- Debit 120100 Titres de transaction
- Credit 140200 Dettes brokers

Frais achat:
- Debit 510100 Charges de courtage
- Credit 150100 Frais a payer

Settlement achat:
- Debit 140200 Dettes brokers
- Credit 110100 Cash Nostro

MTM derive (gain latent):
- Debit 130100 Derives actifs
- Credit 410200 PnL latent

Variation margin recue:
- Debit 110100 Cash Nostro
- Credit 140400 Marges variation a recevoir

## 6) Tables de fait comptables (minimum d information)

Objectif:
- Tracer chaque mouvement comptable de bout en bout.
- Garder un modele simple mais professionnel.

### 6.1 Dimensions minimales

1. dbo.DimAccountInternal
- AccountKey (PK)
- AccountCode (unique)
- AccountLabel
- AccountType (ASSET/LIABILITY/EQUITY/INCOME/EXPENSE/OFFBALANCE)
- IsActive

2. dbo.DimCounterparty
- CounterpartyKey (PK)
- CounterpartyCode
- CounterpartyName
- CounterpartyType (BROKER/BANK/CCP/CLIENT)

3. dbo.DimBook
- BookKey (PK)
- BookCode
- BookName
- DeskCode

### 6.2 Faits minimaux

1. dbo.FactAccountingEvent (header metier)
- AccountingEventKey (PK)
- EventTs
- EventType (TRADE, FEE, MTM, SETTLEMENT, CORPORATE_ACTION, FX_REVAL)
- SourceSystem (TRADING, RISK, BACKOFFICE)
- PortfolioKey
- BookKey
- TradeKey (nullable)
- Status (DRAFT/POSTED/REVERSED)
- CreatedBy
- CreatedAt

2. dbo.FactAccountingMovement (lignes en partie double)
- AccountingMovementKey (PK)
- AccountingEventKey (FK)
- PostingDateKey
- ValueDateKey
- AccountKey
- CounterpartyKey (nullable)
- CurrencyCode
- AmountSigned
- DebitAmount
- CreditAmount
- ReferenceId (ordre, execution, settlement)
- Narrative
- InsertTs

Regle obligatoire:
- Somme(DebitAmount) = Somme(CreditAmount) pour chaque AccountingEventKey.

3. dbo.FactSettlementMovement (suivi denouement)
- SettlementMovementKey (PK)
- TradeKey
- PortfolioKey
- SecurityKey
- CounterpartyKey
- TradeDateKey
- SettleDateKey
- ExpectedCashAmount
- SettledCashAmount
- ExpectedQty
- SettledQty
- SettlementStatus (PENDING, PARTIAL, SETTLED, FAILED)
- FailureReason
- LastUpdateTs

4. dbo.FactReconciliationControl (controle quotidien)
- RecoKey (PK)
- DateKey
- PortfolioKey
- ControlName (FO_MO_BO, CASH, POSITION, GL_SUBLEDGER)
- ControlStatus (OK, WARNING, BREAK)
- DifferenceAmount
- Comment
- CheckedBy
- CheckedAt

## 7) Archivage total SQL Server (obligatoire)

Tout doit etre archive:
- Login/logout, changements de role/session.
- Creation/modification/validation ordre.
- Resultat pre-trade risk check.
- Execution, allocation, confirmation, settlement.
- Ecritures comptables et corrections.
- Rapprochements, incidents, resolution.

Regles d audit minimales:
- Qui (user/service), quoi (action), quand (timestamp UTC), ou (module), avant/apres (payload), resultat (success/fail), correlation_id.

## 8) Contraintes de simplicite projet

- Un seul repo, bootstrap court, dependances limitees.
- Modules independants mais schema SQL commun.
- Contrats de donnees explicites (tables/vues).
- Pas de microservices inutiles a ce stade.
- Documentation courte et actionnable par role.

## 9) References externes (cadre de reference)

1. France - homologation ANC secteur bancaire (Reglement n 2014-07):
- https://www.legifrance.gouv.fr/jorf/id/JORFTEXT000030006380

2. IFRS (instruments financiers):
- IFRS 9: https://www.ifrs.org/issued-standards/list-of-standards/ifrs-9-financial-instruments/
- IFRS 7: https://www.ifrs.org/issued-standards/list-of-standards/ifrs-7-financial-instruments-disclosures/
- IAS 32: https://www.ifrs.org/issued-standards/list-of-standards/ias-32-financial-instruments-presentation/
- IFRS 13: https://www.ifrs.org/issued-standards/list-of-standards/ifrs-13-fair-value-measurement/

3. Prudential reporting UE:
- EBA reporting frameworks: https://www.eba.europa.eu/risk-and-data-analysis/reporting/reporting-frameworks
- ITS supervisory reporting (EU 2021/451): https://op.europa.eu/en/publication-detail/-/publication/e1d3d9ac-6a06-11ef-a8ba-01aa75ed71a1/language-en

4. Gouvernance data risque:
- BCBS 239: https://www.bis.org/publ/bcbs239.pdf

5. Donnees externes gratuites sans compte (option light):
- ECB Data Portal API: https://data.ecb.europa.eu/help/api
- Stooq (usage a encadrer legalement): https://stooq.com/stooq/

## 10) Definition of Done (minimum)

Le contexte est considere pret quand:
- Le cloisonnement role/module est applique dans l UX.
- Le plan de comptes interne est valide metier.
- Les 4 faits comptables minimaux existent en SQL Server.
- Les controles debit=credit et rapprochements quotidiens tournent.
- Chaque action critique est tracable dans les logs d audit.
