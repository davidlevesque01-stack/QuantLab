# QuantLab — Nasdaq Halt Collector

## METRICS_SPECIFICATION.md

**Version : V0.7**  
**Statut : Référence officielle des métriques HALT**  
**Dernière mise à jour : 2026-09-04**

---

## 1. Objectif

Ce document définit les structures de données et les métriques officielles utilisées par QuantLab pour les Nasdaq Trading Halts.

La V0.7 met à jour la représentation du statut de clôture afin de l’aligner avec le modèle CORE V1.1.

Les définitions métier des métriques existantes sont conservées.

---

## 2. Architecture des données

```text
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

Les XML sont conservés comme source de provenance et permettent le recalcul complet des datasets dérivés.

Le pipeline PostgreSQL suit parallèlement :

```text
Nasdaq XML
    ↓
RAW
    ↓
CORE episodes
    ↓
analytics future
```

Les CSV restent des sorties dérivées de validation, diagnostic et export.

---

## 3. Niveaux de données

### Niveau 1 — `tradehalts.csv`

Événements Nasdaq dédupliqués.

Champs principaux :

- symbol
- issue_name
- market
- reason_code
- halt_date
- halt_time
- resumption_date
- resumption_quote_time
- resumption_trade_time
- pause_threshold_price

### Niveau 2 — `halt_episodes.csv`

Un épisode représente une période continue de HALT.

Champs :

- episode_id
- symbol
- issue_name
- market
- reason_code
- halt_start
- halt_end
- duration_minutes
- halt_close_status

`halt_at_close` n’est plus le champ de référence.

### Niveau 3 — `ticker_halt_daily.csv`

Une ligne = un ticker + une journée de marché comportant au moins un HALT.

Champs :

- symbol
- date
- halt_present
- episode_count
- halt_close_status

### Niveau 4 — `ticker_halt_metrics.csv`

---

## 4. Métriques officielles

| Colonne | Définition |
|---|---|
| `total_halt_episodes` | Nombre total d’épisodes |
| `halt_days` | Jours avec ≥1 HALT |
| `halt_days_at_close` | Jours où le HALT est actif à 16:00 |
| `halt_at_close_pct` | `halt_days_at_close / halt_days × 100` |
| `halts_per_halt_day` | `total_halt_episodes / halt_days` |
| `halts_per_market_day` | `total_halt_episodes / jours de marché observés` |
| `avg_halt_duration_minutes` | Durée moyenne |
| `median_halt_duration_minutes` | Durée médiane |
| `min_halt_duration_minutes` | Durée minimale |
| `max_halt_duration_minutes` | Durée maximale |
| `first_halt_date` | Première date observée |
| `last_halt_date` | Dernière date observée |

Les définitions de calcul n’ont pas été modifiées par la V0.7.

---

## 5. Niveau 5 — `ticker_halt_reason_metrics.csv`

Regroupement par :

```text
symbol
reason_code
```

Métriques :

- nombre d’épisodes;
- durée moyenne;
- durée minimale;
- durée maximale.

---

## 6. Définitions officielles

### HALT Day

Nombre de journées de marché pendant lesquelles un ticker possède au moins un HALT.

Plusieurs HALT durant la même journée comptent pour **1 seul halt_day**.

### HALT at Close

Un HALT est actif à la clôture lorsque :

```text
effective_start ≤ 16:00:00 ≤ effective_end
```

La référence est la clôture régulière Nasdaq à 16:00 ET.

Si le statut de l’épisode est :

```text
UNKNOWN
```

la situation ne doit pas être transformée silencieusement en YES ou NO.

### HALT multi-day

Un épisode peut couvrir plusieurs journées de marché.

Exemple :

```text
Début : vendredi 09:23
Fin   : lundi 09:00
```

Résultat :

```text
1 épisode
2 halt_days
1 journée à la clôture
```

Le calcul de `halt_days` pour un épisode multi-jours doit utiliser un calendrier de marché validé, et non une simple séquence de dates calendaires.

---

## 7. Contrôles de cohérence

Le pipeline doit vérifier :

```text
episodes >= halt_days
halt_days_at_close <= halt_days
0 <= halt_at_close_pct <= 100
duration_minutes >= 0
```

Pour PostgreSQL Analytics, ces contrôles seront appliqués lors de l’implémentation de la couche analytique.

---

## 8. Cas de validation officiels

### QVCG

```text
2 épisodes
2 halt_days
2 halt_days_at_close
100 %
```

### BCARU

```text
12 épisodes
5 halt_days
1 halt_day_at_close
20 %
```

Ces deux tickers constituent les tests de non-régression officiels.

---

## 9. Statut de clôture

La représentation de référence est maintenant :

```text
halt_close_status
```

Valeurs :

```text
YES
NO
UNKNOWN
MULTI_DAY
```

La valeur :

```text
MULTI_DAY
```

indique qu’un épisode traverse plusieurs journées et doit être traité avec la logique dédiée des épisodes multi-jours.

Les métriques `halt_days_at_close` et `halt_at_close_pct` doivent être dérivées de l’activité réelle de l’épisode sur les journées de marché concernées.

---

## 10. Versionnement

- **V0.5.1** : logique des épisodes et HALT à la clôture validée.
- **V0.6** : ajout des métriques `halts_per_halt_day`, `halts_per_market_day` et `median_halt_duration_minutes`.
- **V0.7** : alignement documentaire avec `halt_close_status` et le modèle CORE V1.1; aucune définition métier existante n’est volontairement modifiée.

Toute modification d’une définition de métrique doit créer une nouvelle version de cette spécification.
