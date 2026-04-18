# Storytelling fonctionnel du modele de donnees et des notions finance

## 1. Le decor: une journee de gestion de portefeuille

Imagine une equipe de gestion qui pilote un portefeuille multi-actifs.
Chaque matin, elle veut repondre a 4 questions metier:

1. Qu'est-ce que je detiens exactement aujourd'hui ?
2. Combien j'ai gagne ou perdu ?
3. Quel risque je porte maintenant ?
4. Quelle decision est la plus defendable pour la suite ?

Le modele de donnees du projet est construit pour repondre a ces 4 questions, tous les jours, avec des traces auditables.

## 2. Acte I - Connaitre l'univers: dates, actifs, portefeuille

Avant de parler performance, il faut un referentiel propre.

- `dbo.DimDate`: calendrier de travail.
- `dbo.DimSecurity`: liste des instruments (AAPL, MSFT, SPY...).
- `dbo.DimPortfolio`: identite du portefeuille (ex: `MAIN`).

Vision metier:
- Sans ces dimensions, on ne peut pas comparer proprement des chiffres dans le temps, par actif, ou par portefeuille.

## 3. Acte II - Observer le marche: les prix

Le marche "donne le ton" via les prix de cloture.

- `dbo.FactPrice` stocke: date, instrument, prix, volume.

Notion finance:
- Le prix est la base de la valorisation.
- Si le prix change, la valeur du portefeuille change, meme sans nouveau trade.

## 4. Acte III - Prendre une decision: ordre d'achat ou de vente

Le gerant (ou la strategie de simulation) decide:
- `BUY` pour augmenter une position.
- `SELL` pour la reduire.

Dans le projet, cette decision est capturee par le moteur de simulation:
- objets metier dans `trading-sim/engine/models.py`;
- logique d'execution dans `trading-sim/engine/simulator.py`;
- scenario de decisions dans `trading-sim/strategies/rotation_strategy.py`.

Puis les executions sont persistees dans:
- `dbo.FactTrades`.

Notions finance cle:
- `Quantity`: nombre de titres.
- `Price`: prix d'execution.
- `FeeAmount`: cout de courtage/transaction.
- `SlippageAmount`: ecart entre prix theorique et prix reel execute.

Lecture metier:
- Un trade n'est pas gratuit.
- Le vrai resultat depend des couts (fees + slippage), pas seulement de la direction du marche.

## 5. Acte IV - Voir le portefeuille en fin de journee

Apres les trades, on photographie les positions:
- `dbo.PortfolioPositionsDaily`.

Chaque ligne repond a:
- combien je detiens (`Quantity`) ?
- quel est mon cout moyen (`AvgCost`) ?
- quelle est la valeur actuelle (`MarketValue`) ?
- quel est le gain/perte latent (`UnrealizedPnL`) ?
- quel est le poids de la ligne (`WeightPct`) ?

Notions finance:
- **PnL latent**: gain/perte non realise tant que la position n'est pas vendue.
- **Poids**: part de chaque actif dans le portefeuille total.

## 6. Acte V - Piloter la performance du portefeuille

Le niveau portefeuille est resume dans:
- `dbo.PortfolioPnLDaily`.

Champs metier importants:
- `DailyPnL`: variation du jour.
- `CumPnL`: performance cumulee depuis le debut.
- `Nav`: valeur nette du portefeuille.
- `ReturnPct`: rendement journalier.

Notions finance:
- **NAV** (Net Asset Value): valeur globale du portefeuille.
- **Return**: performance relative (pas seulement en montant).

Lecture metier:
- Deux portefeuilles peuvent avoir le meme PnL en dollars, mais des rendements differents selon leur taille.

## 7. Acte VI - Mesurer le risque pris pour obtenir ce resultat

La performance seule ne suffit pas. On veut savoir "a quel prix de risque".

Table metier:
- `dbo.RiskMetricsDaily`.

Metriques:
- `Volatility20d`: variabilite recente des rendements.
- `MaxDrawdown`: pire baisse depuis un pic.
- `VaR95`: perte potentielle sous un niveau de confiance 95%.
- `Beta`: sensibilite au marche de reference.
- `SharpeRatio`: rendement ajuste du risque.

Lecture metier:
- Bon portefeuille = pas seulement performant, mais performant avec un risque sous controle.

## 8. Acte VII - Rendre les donnees lisibles pour pilotage

Les vues SQL servent de "langage metier pre-assemble":

- `dbo.vw_FactTradesEnriched`: trades + noms metier (date, portefeuille, ticker).
- `dbo.vw_PositionSnapshot`: etat des positions lisible pour suivi.
- `dbo.vw_PortfolioDashboardDaily`: performance + risque dans un seul flux.
- `dbo.vw_AI_LatestRecommendations`: derniere recommandation IA par actif/portefeuille.

Valeur fonctionnelle:
- Les equipes BI, risque, gestion et IA consomment la meme verite, sans refaire les jointures a chaque fois.

## 9. Acte VIII - Ajouter l'explication IA sans perdre la gouvernance

Le modele prevoit une couche IA orientee aide a la decision:

- `dbo.AI_DailyBriefing`: synthese du jour.
- `dbo.AI_Recommendations`: recommandations structurees.
- `dbo.AI_WhatIf`: simulation de scenarios.
- `dbo.AI_AuditLog`: journal des evenements IA.

Vision metier:
- L'IA propose, le gerant dispose.
- Toute proposition doit etre tracee, explicable, et auditable.

## 10. Fil rouge: un exemple simple de bout en bout

1. Le 2 janvier, AAPL cote 186.
2. Le portefeuille `MAIN` achete 120 AAPL.
3. L'execution enregistre prix, frais et slippage dans `FactTrades`.
4. En fin de journee, `PortfolioPositionsDaily` montre la quantite et le cout moyen.
5. Le lendemain, le prix monte: le `UnrealizedPnL` devient positif.
6. `PortfolioPnLDaily` met a jour `DailyPnL`, `CumPnL`, `Nav`.
7. `RiskMetricsDaily` mesure si la volatilite ou la drawdown devient excessive.
8. Une recommendation IA peut suggerer "BUY/HOLD/REDUCE" avec justification.
9. Tout est historise pour audit et revue de decision.

## 11. Pourquoi ce modele est utile metierement

Ce modele transforme des donnees techniques en decisions pilotables:

- Il relie execution de trades et resultat financier.
- Il distingue performance et risque.
- Il permet de justifier une decision par des faits historises.
- Il prepare une industrialisation BI + IA sans casser la gouvernance.

En pratique, c'est un socle pour passer de:
- "je pense que c'est une bonne decision"
vers
- "je peux demontrer, mesurer, comparer et tracer cette decision".

