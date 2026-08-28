# QuantLab — Nasdaq Halt Collector

## Modèle de données PostgreSQL

**Version : V1.1**
**Statut : Modèle DEV implémenté et validé sur le baseline V0.7**
**Date : 2026-08-28**

---

## 1. Objectif

Ce document définit le modèle de données PostgreSQL utilisé par le composant **QuantLab — Nasdaq Halt Collector**.

Le modèle vise à :

* conserver les événements Nasdaq Trade Halt sous une forme structurée;
* préserver la provenance vers les fichiers XML originaux;
* assurer la déduplication lors des chargements;
* représenter les épisodes de suspension de négociation;
* préserver correctement les épisodes multi-jours;
* permettre la reconstruction future des données analytiques;
* supporter le chargement historique et les mises à jour futures;
* permettre une ingestion idempotente;
* détecter explicitement les situations incompatibles avec les hypothèses actuelles du modèle.

Les fichiers XML Nasdaq conservés sous :

```text
collectors/nasdaq_halts/data/raw/nasdaq/
```

demeurent les données externes originales de provenance.

PostgreSQL constitue la représentation structurée et interrogeable partagée de QuantLab.

---

## 2. Organisation du modèle

Le modèle est organisé en trois couches PostgreSQL :

```text
raw
 |
 +-- nasdaq_trade_halt

core
 |
 +-- nasdaq_halt_episode

analytics
 |
 +-- objets futurs
```

### 2.1 Couche `raw`

La couche `raw` contient les événements structurés provenant des données Nasdaq.

Elle reste aussi près que raisonnablement possible de la donnée source tout en appliquant les conversions de types nécessaires.

Objet actuel :

```text
raw.nasdaq_trade_halt
```

### 2.2 Couche `core`

La couche `core` contient les objets métier reconstruits à partir des événements RAW.

Objet actuel :

```text
core.nasdaq_halt_episode
```

### 2.3 Couche `analytics`

La couche `analytics` est réservée aux datasets et objets analytiques dérivés.

Le schéma existe, mais les objets analytiques Nasdaq Halts ne sont pas encore implémentés.

Leur création est volontairement différée jusqu'à validation :

* du calendrier officiel des jours de marché;
* des épisodes multi-jours;
* de la cardinalité RAW→CORE;
* de la sémantique des statuts de clôture;
* des résultats sur l'historique complet.

---

## 3. Table `raw.nasdaq_trade_halt`

Cette table contient les événements Nasdaq Trade Halt structurés.

### Colonnes

| Colonne | Type PostgreSQL | Contraintes |
|---|---|---|
| `id` | BIGINT | PRIMARY KEY, GENERATED ALWAYS AS IDENTITY |
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

### Clé naturelle

La clé naturelle PostgreSQL actuelle est :

```text
symbol
halt_date
halt_time
reason_code
market
```

Une contrainte UNIQUE empêche le chargement répété du même événement sous cette clé.

Validation V0.7 :

```text
Événements analysés        : 744
Clés naturelles dupliquées : 0
```

Cette hypothèse devra être revalidée sur l'historique complet de cinq ans.

---

## 4. Provenance RAW

Chaque événement parsé par le pipeline V0.7 contient :

```text
source_file
```

Cette valeur correspond au nom du fichier XML ayant fourni l'événement.

Exemple :

```text
tradehalts_2026-08-03.xml
```

Elle est persistée dans :

```text
raw.nasdaq_trade_halt.source_file
```

La validation directe V0.7 a produit 744 lignes RAW provenant de 10 fichiers XML historiques.

PostgreSQL ne conserve pas actuellement le contenu XML complet.

Le contenu original demeure dans la couche RAW du filesystem.

Le modèle de provenance actuel est donc :

```text
XML original
     |
     | nom du fichier
     v
raw.nasdaq_trade_halt.source_file
```

Si un même événement naturel est découvert dans plusieurs fichiers XML lors de la validation historique complète, ce modèle de provenance devra être réévalué afin de déterminer si une relation distincte entre événements et sources est nécessaire.

---

## 5. Déduplication RAW

Le pipeline Python V0.7 possède sa propre logique de déduplication avant la persistance PostgreSQL.

La clé Python actuelle n'est pas identique à la clé naturelle PostgreSQL.

Sur le dataset V0.7 :

```text
Événements bruts       : 744
Événements uniques     : 744
Clés PostgreSQL dupliquées : 0
```

Aucune divergence n'est observée sur ce baseline.

Cette équivalence ne doit toutefois pas être présumée sur cinq années de données.

La validation historique devra comparer explicitement :

```text
déduplication Python
vs
clé naturelle PostgreSQL
```

Une divergence devra conduire à une décision explicite sur le modèle.

---

## 6. Table `core.nasdaq_halt_episode`

Cette table représente les épisodes de suspension reconstruits par le pipeline Python.

### Colonnes

| Colonne | Type PostgreSQL | Contraintes |
|---|---|---|
| `id` | BIGINT | PRIMARY KEY, GENERATED ALWAYS AS IDENTITY |
| `trade_halt_id` | BIGINT | NOT NULL, FK RAW, UNIQUE |
| `collector_episode_id` | VARCHAR(20) | optionnel |
| `symbol` | VARCHAR(20) | NOT NULL |
| `issue_name` | TEXT | |
| `market` | VARCHAR(10) | |
| `reason_code` | VARCHAR(20) | |
| `halt_start` | TIMESTAMP | NOT NULL |
| `halt_end` | TIMESTAMP | |
| `duration_minutes` | NUMERIC(12,3) | |
| `halt_close_status` | VARCHAR(20) | CHECK |

La contrainte de statut permet actuellement :

```text
YES
NO
UNKNOWN
MULTI_DAY
```

La durée doit être positive ou nulle lorsqu'elle est disponible.

Lorsque `halt_end` est disponible, il ne doit pas précéder `halt_start`.

---

## 7. Relation RAW → CORE

Le modèle actuel impose :

```text
1 RAW event -> 1 CORE episode
```

La contrainte :

```text
UNIQUE (trade_halt_id)
```

empêche plusieurs épisodes CORE de référencer le même événement RAW.

Le baseline V0.7 contient :

```text
RAW events    : 744
CORE episodes : 744
```

Cette relation 1:1 est donc valide sur le dataset actuel.

Elle n'est cependant pas encore considérée comme une propriété universelle des données Nasdaq.

### Risque identifié

L'algorithme Python de construction des épisodes peut théoriquement fusionner plusieurs événements lorsque leurs périodes se chevauchent.

Dans une telle situation :

```text
plusieurs RAW
     |
     v
un épisode logique
```

serait incompatible avec le modèle PostgreSQL 1:1 actuel.

Le writer V0.7 détecte cette situation au lieu de choisir arbitrairement une relation.

La cardinalité devra être revalidée sur l'historique complet avant stabilisation du modèle.

---

## 8. Identifiant d'épisode du collector

Le pipeline génère actuellement des identifiants tels que :

```text
H00000001
H00000002
...
```

Ils sont conservés dans :

```text
collector_episode_id
```

Ils ne constituent pas la clé primaire PostgreSQL.

PostgreSQL utilise :

```text
core.nasdaq_halt_episode.id
```

comme clé technique.

Les identifiants du collector étant actuellement générés séquentiellement, ils peuvent changer lorsqu'un dataset plus large est reconstruit.

Ils ne doivent donc pas être considérés comme des identifiants métier durables tant que leur stabilité n'a pas été explicitement définie.

---

## 9. Statut de clôture

Le modèle initial utilisait :

```text
halt_at_close BOOLEAN
```

Cette représentation s'est révélée insuffisante pour préserver la sémantique des épisodes multi-jours.

La migration :

```text
002_fix_nasdaq_halt_close_status.sql
```

a remplacé ce champ par :

```text
halt_close_status VARCHAR(20)
```

Valeurs autorisées :

```text
YES
NO
UNKNOWN
MULTI_DAY
```

Distribution V0.7 validée :

```text
YES       : 15
NO        : 697
UNKNOWN   : 2
MULTI_DAY : 30
TOTAL     : 744
```

Il ne faut donc pas convertir automatiquement ces valeurs en BOOLEAN au niveau CORE.

En particulier :

```text
MULTI_DAY
```

possède une sémantique distincte qui doit être conservée.

---

## 10. Épisodes multi-jours

Un épisode peut couvrir plus d'une journée.

Par conséquent :

```text
nombre d'épisodes
```

et :

```text
nombre de jours affectés
```

représentent deux concepts différents.

Le modèle CORE représente l'épisode complet.

La future couche analytique pourra représenter séparément les journées affectées, mais cette logique devra utiliser un calendrier de marché validé.

La simple génération de dates calendaires entre `halt_start` et `halt_end` n'est pas suffisante puisqu'elle pourrait inclure :

* fins de semaine;
* jours fériés;
* journées où le marché concerné n'était pas ouvert.

---

## 11. Gestion du temps

La couche RAW conserve les composantes temporelles proches de la source :

```text
halt_date
halt_time
resumption_date
resumption_quote_time
resumption_trade_time
```

La couche CORE utilise :

```text
halt_start
halt_end
```

Les timestamps fractionnaires sont préservés.

Exemple validé :

```text
2026-08-03 08:52:20.892
```

La chaîne suivante a été validée :

```text
Nasdaq XML
-> parser Python V0.7
-> PostgreSQL
```

Les colonnes CORE utilisent actuellement :

```text
TIMESTAMP
```

sans fuseau horaire.

Cette décision permet de préserver les valeurs temporelles interprétées actuellement par le pipeline sans appliquer une conversion implicite.

La sémantique exacte du fuseau horaire Nasdaq devra être validée avant certification de l'historique complet.

---

## 12. Persistance PostgreSQL

La persistance Nasdaq spécifique est implémentée dans :

```text
collectors/nasdaq_halts/src/nasdaq_postgresql.py
```

Le module utilise la connexion PostgreSQL générique définie sous :

```text
shared/database/
```

Le flux actuel est :

```text
unique_events
      |
      v
raw.nasdaq_trade_halt
      |
      | trade_halt_id
      v
core.nasdaq_halt_episode
```

La persistance RAW et CORE est exécutée dans une même connexion transactionnelle.

### Idempotence validée

Premier chargement direct après nettoyage DEV :

```text
RAW inserted   : 744
RAW existing   : 0
CORE inserted  : 744
CORE existing  : 0
```

Réexécution :

```text
RAW inserted   : 0
RAW existing   : 744
CORE inserted  : 0
CORE existing  : 744
```

La persistance est donc idempotente sur le baseline V0.7.

---

## 13. Loader CSV transitoire

Le module :

```text
collectors/nasdaq_halts/src/load_postgresql.py
```

a servi à valider initialement le modèle PostgreSQL à partir des CSV du baseline V0.6.

Il est conservé comme outil de validation et de migration.

Il ne constitue plus le chemin de persistance privilégié.

Le chemin V0.7 est :

```text
XML RAW
-> parsing / normalisation
-> PostgreSQL RAW
-> PostgreSQL CORE
```

Les CSV demeurent des datasets dérivés utiles pour :

* validation;
* diagnostic;
* comparaison;
* non-régression;
* export.

---

## 14. Index

Les index et contraintes actuels doivent principalement répondre aux besoins réels de déduplication, relation et interrogation.

### `raw.nasdaq_trade_halt`

La clé naturelle unique est :

```text
UNIQUE (
    symbol,
    halt_date,
    halt_time,
    reason_code,
    market
)
```

Des index complémentaires sont utilisés pour faciliter les recherches courantes selon les migrations appliquées.

### `core.nasdaq_halt_episode`

La relation RAW est protégée par :

```text
UNIQUE (trade_halt_id)
```

Des index complémentaires facilitent notamment les recherches par symbole, date/heure et raison selon le schéma appliqué.

Les index supplémentaires devront être ajoutés sur la base de requêtes et volumes réels plutôt que par anticipation.

---

## 15. Couche analytique future

Les objets analytiques PostgreSQL ne sont pas encore implémentés.

Les datasets Python/CSV actuels servent de référence fonctionnelle :

```text
ticker_halt_daily.csv
ticker_halt_metrics.csv
ticker_halt_reason_metrics.csv
```

Les objets PostgreSQL futurs pourront éventuellement prendre la forme de vues ou vues matérialisées, mais ce choix n'est pas encore finalisé.

Noms conceptuels envisagés :

```text
analytics.ticker_halt_daily
analytics.ticker_halt_metrics
analytics.ticker_halt_reason_metrics
```

La migration future est réservée comme :

```text
database/migrations/003_create_nasdaq_halts_analytics.sql
```

Elle ne doit pas être créée avant validation de la sémantique analytique.

---

## 16. Calendrier de marché

Le pipeline Python actuel détermine les jours de marché selon une logique qui ne constitue pas encore un calendrier officiel complet.

Avant de reproduire les métriques quotidiennes dans PostgreSQL, QuantLab devra disposer d'une représentation fiable des journées de marché.

Cette exigence concerne notamment :

```text
halt_days
halt_days_at_close
halts_per_market_day
```

La métrique :

```text
halts_per_market_day
```

ne doit pas être considérée comme définitivement modélisée dans PostgreSQL tant que le dénominateur de jours de marché n'est pas validé.

---

## 17. Reconstruction des données

L'architecture vise le flux reconstructible suivant :

```text
Nasdaq XML
     |
     v
RAW XML local
     |
     v
Parsing / normalisation
     |
     v
raw.nasdaq_trade_halt
     |
     v
core.nasdaq_halt_episode
     |
     v
analytics.*
```

Les objets analytiques futurs ne doivent pas devenir des sources indépendantes.

Ils doivent pouvoir être reconstruits à partir des couches de données appropriées.

Les fichiers XML originaux permettent de reconstruire les couches structurées si nécessaire.

---

## 18. Chargement incrémental futur

Le chemin quotidien/live devra éventuellement :

1. télécharger les nouvelles données Nasdaq;
2. conserver une source RAW appropriée;
3. normaliser les événements;
4. insérer uniquement les événements nouveaux;
5. associer correctement les épisodes CORE;
6. mettre à jour les objets analytiques nécessaires;
7. enregistrer le résultat d'exécution;
8. pouvoir être relancé sans créer de doublons.

Le chemin live/current :

```text
nasdaq_halt_collector.py
```

n'est pas encore considéré comme complètement intégré à l'architecture PostgreSQL V0.7.

Il devra notamment être validé pour :

* la structure XML courante;
* `Market` versus `Mkt`;
* la stratégie de snapshots;
* la provenance;
* la persistance;
* l'idempotence.

---

## 19. Validation V0.7

Résultats actuels :

```text
Fichiers XML               : 15
Événements bruts           : 744
Événements uniques         : 744
HALT Episodes              : 744
Tickers différents         : 235
Lignes quotidiennes        : 322
Jours de marché            : 10
Durées calculables         : 742
Clés RAW dupliquées        : 0
```

Statuts :

```text
YES       : 15
NO        : 697
UNKNOWN   : 2
MULTI_DAY : 30
TOTAL     : 744
```

Tests :

```text
QVCG : PASS
BCARU: PASS
```

Persistance directe :

```text
RAW  : 744
CORE : 744
```

Réexécution :

```text
Nouveaux RAW  : 0
Nouveaux CORE : 0
```

Ces résultats constituent le baseline V0.7 avant le chargement de l'historique complet.

---

## 20. Points à valider sur l'historique cinq ans

Le chargement de cinq années devra notamment confirmer :

1. l'unicité réelle de la clé naturelle RAW;
2. la compatibilité entre la déduplication Python et la clé PostgreSQL;
3. la cardinalité RAW→CORE;
4. les cas d'épisodes construits à partir de plusieurs événements;
5. les épisodes multi-jours;
6. les valeurs possibles de `market`;
7. les valeurs possibles de `reason_code`;
8. les formats de `pause_threshold_price`;
9. les valeurs manquantes;
10. les cas sans reprise disponible;
11. la précision des timestamps;
12. la sémantique des fuseaux horaires;
13. les changements de symbole;
14. les événements apparaissant dans plusieurs fichiers source;
15. la stratégie de provenance nécessaire dans ces cas;
16. la performance des index;
17. le volume réel;
18. l'idempotence sur le dataset complet;
19. la validité du calendrier de marché.

Le schéma pourra évoluer par de nouvelles migrations avant d'être considéré comme stable pour PROD.

Les migrations déjà appliquées ne doivent pas être modifiées rétroactivement.

---

## 21. Migrations actuelles

### Migration 001

```text
database/migrations/001_create_nasdaq_halts_schema.sql
```

Elle a créé le modèle initial RAW et CORE.

Elle a été appliquée et validée en DEV.

### Migration 002

```text
database/migrations/002_fix_nasdaq_halt_close_status.sql
```

Elle a remplacé :

```text
halt_at_close BOOLEAN
```

par :

```text
halt_close_status VARCHAR(20)
```

Elle a été appliquée et validée en DEV.

### Migration 003

Réservée pour les futurs objets analytiques :

```text
database/migrations/003_create_nasdaq_halts_analytics.sql
```

Elle n'est pas encore implémentée.

---

## 22. Statut

Le modèle actuel constitue le :

```text
PostgreSQL Data Model V1.1
```

du Nasdaq Halt Collector.

Il est :

```text
implémenté en DEV
validé sur le baseline V0.7 de 744 événements
non encore certifié sur l'historique cinq ans
```

Les hypothèses structurantes, particulièrement la clé naturelle RAW et la relation 1 RAW → 1 CORE, demeurent soumises à la validation historique complète.
