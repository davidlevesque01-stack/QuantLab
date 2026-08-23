# QuantLab --- Nasdaq Halt Collector

## METRICS_SPECIFICATION.md

**Version : V0.6 (Figée)**

Statut : Référence officielle des métriques HALT

------------------------------------------------------------------------

## Objectif

Ce document définit les structures de données et les métriques
officielles utilisées par QuantLab pour la base historique des Nasdaq
Trading Halts.

------------------------------------------------------------------------

## Architecture

``` text
Nasdaq XML
    ↓
tradehalts.csv
    ↓
halt_episodes.csv
    ↓
ticker_halt_daily.csv
    ↓
ticker_halt_metrics.csv
    ↓
ticker_halt_reason_metrics.csv
```

Les fichiers XML sont conservés comme source de vérité afin de permettre
le recalcul complet des métriques.

------------------------------------------------------------------------

## Niveaux de données

### Niveau 1 --- `tradehalts.csv`

Événements Nasdaq dédupliqués.

Champs principaux :

-   symbol
-   issue_name
-   market
-   reason_code
-   halt_date
-   halt_time
-   resumption_date
-   resumption_quote_time
-   resumption_trade_time
-   pause_threshold_price

### Niveau 2 --- `halt_episodes.csv`

Un épisode représente une période continue de HALT.

Champs :

-   episode_id
-   symbol
-   issue_name
-   market
-   reason_code
-   halt_start
-   halt_end
-   duration_minutes
-   halt_at_close

### Niveau 3 --- `ticker_halt_daily.csv`

Une ligne = un ticker + une journée de marché comportant au moins un
HALT.

Champs :

-   symbol
-   date
-   halt_present
-   episode_count
-   halt_at_close

### Niveau 4 --- `ticker_halt_metrics.csv`

## Métriques officielles V0.6

  -----------------------------------------------------------------------
  Colonne                             Définition
  ----------------------------------- -----------------------------------
  total_halt_episodes                 Nombre total d'épisodes

  halt_days                           Jours avec ≥1 HALT

  halt_days_at_close                  Jours où le HALT est actif à 16:00

  halt_at_close_pct                   halt_days_at_close / halt_days ×
                                      100

  halts_per_halt_day                  total_halt_episodes / halt_days

  halts_per_market_day                total_halt_episodes / jours de
                                      marché observés

  avg_halt_duration_minutes           Durée moyenne

  median_halt_duration_minutes        Durée médiane

  min_halt_duration_minutes           Durée minimale

  max_halt_duration_minutes           Durée maximale

  first_halt_date                     Première date observée

  last_halt_date                      Dernière date observée
  -----------------------------------------------------------------------

### Niveau 5 --- `ticker_halt_reason_metrics.csv`

Regroupement par :

-   symbol
-   reason_code

Métriques :

-   nombre d'épisodes
-   durée moyenne
-   durée minimale
-   durée maximale

------------------------------------------------------------------------

## Définitions officielles

### HALT Day

Nombre de journées de marché pendant lesquelles un ticker possède au
moins un HALT.

Plusieurs HALT durant la même journée comptent pour **1 seul halt_day**.

### HALT at Close

Un HALT est actif à la clôture lorsque :

``` text
effective_start ≤ 16:00:00 ≤ effective_end
```

La référence est la clôture régulière du Nasdaq (16:00 ET).

### HALT multi-day

Un épisode peut couvrir plusieurs journées de marché.

Exemple :

-   Début : vendredi 09:23
-   Fin : lundi 09:00

Résultat :

-   1 épisode
-   2 halt_days
-   1 journée à la clôture (vendredi)

------------------------------------------------------------------------

## Contrôles de cohérence

Le pipeline doit toujours vérifier :

``` text
episodes >= halt_days
halt_days_at_close <= halt_days
0 <= halt_at_close_pct <= 100
duration_minutes >= 0
```

------------------------------------------------------------------------

## Cas de validation

### QVCG

-   2 épisodes
-   2 halt_days
-   2 halt_days_at_close
-   100 %

### BCARU

-   12 épisodes
-   5 halt_days
-   1 halt_day_at_close
-   20 %

Ces deux tickers constituent les tests de non-régression officiels.

------------------------------------------------------------------------

## Versionnement

-   **V0.5.1** : logique des épisodes et HALT à la clôture validée.
-   **V0.6** : ajout des métriques `halts_per_halt_day`,
    `halts_per_market_day` et `median_halt_duration_minutes`.

Toute modification d'une définition doit créer une nouvelle version de
cette spécification.
