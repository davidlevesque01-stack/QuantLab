# QuantLab — Nasdaq Halt Collector

## DATA_MODEL.md

**Version : V1.1**  
**Statut : Modèle DEV implémenté et validé sur l’historique complet chargé**  
**Date : 2026-09-04**

---

## 1. Objectif

Ce document définit le modèle PostgreSQL du composant QuantLab — Nasdaq Halt Collector.

Le modèle distingue :

```text
raw
core
analytics
```

Les XML Nasdaq restent les données externes originales de provenance. PostgreSQL constitue la représentation structurée partagée et interrogeable.

---

## 2. Organisation

```text
raw
 |
 +-- nasdaq_trade_halt

core
 |
 +-- nasdaq_halt_episode
 +-- nasdaq_halt_episode_event

analytics
 |
 +-- objets futurs
```

---

## 3. Table `raw.nasdaq_trade_halt`

| Colonne | Type | Contraintes |
|---|---|---|
| `id` | BIGINT | PRIMARY KEY, identity |
| `symbol` | VARCHAR(20) | NOT NULL |
| `issue_name` | TEXT | |
| `market` | VARCHAR(10) | NOT NULL |
| `reason_code` | VARCHAR(20) | NOT NULL |
| `halt_date` | DATE | NOT NULL |
| `halt_time` | TIME | NOT NULL |
| `resumption_date` | DATE | |
| `resumption_quote_time` | TIME | |
| `resumption_trade_time` | TIME | |
| `pause_threshold_price` | NUMERIC(18,6) | |
| `source_file` | TEXT | |
| `loaded_at` | TIMESTAMPTZ | DEFAULT CURRENT_TIMESTAMP |

### Clé naturelle RAW

```text
symbol
halt_date
halt_time
reason_code
market
```

Cette clé est protégée par une contrainte UNIQUE.

La clé naturelle RAW doit encore être revalidée statistiquement sur l’ensemble historique avant certification PROD.

---

## 4. Provenance RAW

`source_file` contient actuellement le premier snapshot ayant créé la ligne structurée.

Exemples :

```text
tradehalts_2026-08-17.xml
tradehalts_live_20260828T205115Z.xml
```

Le filesystem conserve les snapshots XML immuables.

Le modèle PostgreSQL ne matérialise pas encore :

```text
N snapshots -> 1 RAW event
```

Une table de provenance/observations pourra être ajoutée ultérieurement si nécessaire.

---

## 5. Déduplication

La clé Python actuelle :

```text
symbol
halt_start
resumption_date
resumption_trade_time
reason_code
```

est différente de la clé PostgreSQL RAW :

```text
symbol
halt_date
halt_time
reason_code
market
```

Cette différence est volontaire et doit être contrôlée par validation.

---

## 6. Table `core.nasdaq_halt_episode`

| Colonne | Type | Contraintes |
|---|---|---|
| `id` | BIGINT | PRIMARY KEY, identity |
| `trade_halt_id` | BIGINT | NOT NULL, FK RAW |
| `collector_episode_id` | VARCHAR(20) | optionnel |
| `symbol` | VARCHAR(20) | NOT NULL |
| `issue_name` | TEXT | |
| `market` | VARCHAR(10) | |
| `reason_code` | VARCHAR(20) | |
| `halt_start` | TIMESTAMP | NOT NULL |
| `halt_end` | TIMESTAMP | |
| `duration_minutes` | NUMERIC(12,3) | |
| `halt_close_status` | VARCHAR(20) | CHECK |

### Important — V1.1

`trade_halt_id` **n’est pas UNIQUE**.

La relation CORE→RAW est maintenant représentée par :

```text
core.nasdaq_halt_episode_event
```

La contrainte de clé naturelle CORE est :

```text
UNIQUE (
    symbol,
    market,
    reason_code,
    halt_start
)
```

Cette contrainte est implémentée par :

```text
uq_nasdaq_halt_episode_natural_key
```

---

## 7. Table `core.nasdaq_halt_episode_event`

Cette table matérialise l’appartenance des événements RAW aux épisodes CORE.

Conceptuellement :

```text
CORE episode
     |
     +---- RAW event
     +---- RAW event
     +---- RAW event
```

Colonnes :

```text
episode_id
trade_halt_id
```

avec :

```text
episode_id -> core.nasdaq_halt_episode.id
trade_halt_id -> raw.nasdaq_trade_halt.id
```

La V1.1 exige que chaque couple :

```text
episode_id + trade_halt_id
```

soit unique.

La validation applicative exige également qu’un `trade_halt_id` n’appartienne pas à plusieurs épisodes CORE.

Cette dernière propriété est validée sur l’historique complet chargé :

```text
RAW avec >1 CORE : 0
```

---

## 8. Cardinalité

Le modèle V1.1 est :

```text
CORE 1 ---- N RAW
```

Sur l’historique chargé :

```text
RAW uniques           : 68 170
CORE episodes         : 68 035
relations             : 68 170
CORE avec >1 RAW      : 90
RAW avec >1 CORE      : 0
```

Donc :

- un CORE peut représenter plusieurs RAW;
- un RAW ne doit pas être partagé par plusieurs CORE.

Cette distinction est essentielle pour les épisodes fusionnés.

---

## 9. Clé naturelle CORE

La clé naturelle est :

```text
symbol
market
reason_code
halt_start
```

Une clé basée uniquement sur :

```text
symbol
halt_start
```

est insuffisante.

Cas identifiés :

```text
CANF / 2026-03-04 09:38:41
CVM  / 2020-02-26 15:02:49
```

Ces cas comportent plusieurs `reason_code` et démontrent pourquoi `reason_code` doit faire partie de l’identité naturelle CORE.

---

## 10. `collector_episode_id`

Exemples :

```text
H00000001
H00000002
...
```

Il s’agit d’un identifiant de calcul.

Il n’est pas une identité métier durable.

Une reconstruction complète peut produire une numérotation différente.

Après insertion initiale, sa valeur n’est pas remplacée par une mise à jour ordinaire.

---

## 11. Statut de clôture

Le champ officiel CORE est :

```text
halt_close_status
```

Valeurs autorisées :

```text
YES
NO
UNKNOWN
MULTI_DAY
```

Le champ historique :

```text
halt_at_close BOOLEAN
```

n’est plus le modèle CORE V1.1.

### Règle de protection

Un `UNKNOWN` entrant ne remplace pas :

```text
YES
NO
MULTI_DAY
```

Une nouvelle valeur finale non-UNKNOWN peut corriger une valeur finale existante.

---

## 12. Épisodes multi-jours

Un épisode peut couvrir plusieurs journées.

Le CORE conserve l’épisode continu :

```text
halt_start
halt_end
```

Le nombre de journées affectées est un concept analytique distinct.

Un calendrier de marché officiel est requis avant de matérialiser définitivement les métriques quotidiennes PostgreSQL.

---

## 13. Gestion du temps

RAW conserve les composantes :

```text
halt_date
halt_time
resumption_date
resumption_quote_time
resumption_trade_time
```

CORE utilise :

```text
halt_start
halt_end
```

Les fractions de seconde sont conservées.

Les timestamps CORE sont actuellement :

```text
TIMESTAMP
```

sans conversion implicite de fuseau.

La sémantique exacte du fuseau Nasdaq reste à confirmer avant certification PROD.

---

## 14. Mise à jour RAW

Règles :

```text
NULL + NULL -> unchanged
NULL + value -> update
value + NULL -> preserve existing
value A + A  -> unchanged
value A + B  -> update
```

`source_file` conserve le premier snapshot créateur.

---

## 15. Mise à jour CORE

Champs enrichissables :

```text
issue_name
market
reason_code
halt_end
duration_minutes
halt_close_status
```

Une valeur NULL entrante n’efface pas une valeur connue.

Les valeurs numériques sont normalisées avant comparaison afin d’éviter des mises à jour artificielles dues aux différences de types Python/NUMERIC.

---

## 16. Persistance V1.1

La persistance est réalisée par :

```text
collectors/nasdaq_halts/src/nasdaq_postgresql.py
```

La V1.1 utilise :

```text
temporary staging
bulk INSERT
bulk UPDATE
bulk relation DELETE
bulk relation INSERT
relational validation
```

Les opérations CORE sont ainsi traitées en masse plutôt qu’un épisode à la fois.

---

## 17. Transaction

```text
BEGIN
  RAW
  CORE
  CORE -> RAW
COMMIT
```

En cas d’erreur :

```text
ROLLBACK
```

Le test historique dry-run a confirmé :

```text
HISTORICAL VALIDATION : PASS
ROLLBACK              : PASS
```

---

## 18. Validation historique

Période :

```text
2020-01-01 -> 2026-08-28
```

```text
XML                     : 2 432
RAW parser events       : 69 186
RAW uniques             : 68 170
CORE episodes           : 68 035
Durées calculables      : 67 997

YES                     : 1 780
NO                      : 62 917
UNKNOWN                 : 33
MULTI_DAY               : 3 305
```

PostgreSQL :

```text
RAW inserted            : 58 701
RAW updated             : 0
RAW unchanged           : 9 469

CORE inserted           : 68 035
CORE updated            : 0
CORE unchanged          : 0

CORE -> RAW relations   : 68 170
RAW >1 CORE              : 0
CORE >1 RAW              : 90
```

Le test s’est terminé par rollback.

---

## 19. Contraintes V1.1

Le modèle CORE ne doit plus contenir :

```text
UNIQUE (trade_halt_id)
```

La contrainte précédente :

```text
uq_nasdaq_halt_episode_trade_halt
```

a été supprimée.

La contrainte actuelle est :

```text
uq_nasdaq_halt_episode_natural_key
UNIQUE (
    symbol,
    market,
    reason_code,
    halt_start
)
```

Migration :

```text
004_update_nasdaq_core_natural_key_v1_1.sql
```

---

## 20. Analytics future

Les objets suivants restent conceptuels :

```text
analytics.ticker_halt_daily
analytics.ticker_halt_metrics
analytics.ticker_halt_reason_metrics
```

Ils ne doivent pas être implémentés avant validation de :

- calendrier de marché;
- multi-day;
- sémantique de clôture;
- équivalence avec Python;
- volume et performance.

---

## 21. Limites restantes

1. clé naturelle RAW à valider sur tout l’historique;
2. intégrité de tous les XML;
3. complétude exacte de la période;
4. fuseau horaire;
5. calendrier de marché officiel;
6. analyse détaillée des 90 CORE multi-RAW;
7. provenance N snapshots → 1 RAW;
8. corrections live réelles;
9. concurrence;
10. certification PROD.

---

## 22. Migrations

```text
001_create_nasdaq_halts_schema.sql
002_fix_nasdaq_halt_close_status.sql
003_create_nasdaq_halts_analytics.sql  # réservé / non implémenté
004_update_nasdaq_core_natural_key_v1_1.sql
```

Les migrations déjà appliquées ne doivent pas être modifiées rétroactivement.

---

## 23. Statut

```text
DATA MODEL V1.1
```

État :

```text
DEV implémenté
historique chargé en dry-run
68 170 RAW uniques
68 035 CORE
68 170 relations
90 CORE multi-RAW
0 RAW multi-CORE
validation PASS
rollback PASS
non certifié PROD
```
