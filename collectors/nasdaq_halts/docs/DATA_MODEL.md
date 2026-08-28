# QuantLab — Nasdaq Halt Collector

## Modèle de données PostgreSQL

**Version : V1.1**
**Statut : Modèle DEV implémenté et validé avec le pipeline V0.8**
**Date : 2026-08-28**

---

## 1. Objectif

Ce document définit le modèle de données PostgreSQL utilisé par le composant **QuantLab — Nasdaq Halt Collector**.

Le modèle vise à :

- conserver les événements Nasdaq Trade Halt sous une forme structurée;
- préserver la provenance vers les fichiers XML originaux;
- assurer la déduplication lors des chargements;
- représenter les épisodes de suspension de négociation;
- préserver correctement les épisodes multi-jours;
- supporter les données historiques et live;
- permettre l'enrichissement d'un événement live déjà connu;
- empêcher une observation incomplète d'effacer une information connue;
- permettre une ingestion idempotente;
- permettre la reconstruction future des données analytiques;
- détecter explicitement les situations incompatibles avec les hypothèses actuelles du modèle.

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

- du calendrier officiel des jours de marché;
- des épisodes multi-jours;
- de la cardinalité RAW→CORE;
- de la sémantique des statuts de clôture;
- des résultats sur l'historique complet.

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

Validation historique :

```text
Événements analysés        : 744
Clés naturelles dupliquées : 0
```

Validation live V0.8 sur un snapshot réel :

```text
Événements                 : 35
Clés naturelles            : 35
Clés naturelles dupliquées : 0
```

Cette hypothèse devra être revalidée sur l'historique complet de cinq ans et surveillée sur les futurs flux live.

---

## 4. Provenance RAW

Chaque événement parsé contient :

```text
source_file
```

Cette valeur correspond au nom du fichier XML ayant fourni l'observation utilisée lors de la création de la ligne RAW.

### Historique

Exemple :

```text
tradehalts_2026-08-03.xml
```

### Live

Les snapshots live utilisent :

```text
tradehalts_live_YYYYMMDDTHHMMSSZ.xml
```

Exemple :

```text
tradehalts_live_20260828T205115Z.xml
```

La valeur est persistée dans :

```text
raw.nasdaq_trade_halt.source_file
```

### Sémantique V0.8

Lorsqu'un événement existe déjà selon la clé naturelle, une nouvelle observation peut enrichir ses données.

Cependant :

```text
source_file
```

n'est pas remplacé.

Il représente actuellement le **premier snapshot ayant créé la ligne RAW structurée**.

Le modèle actuel est donc conceptuellement :

```text
Premier XML observé
        |
        v
RAW event
```

alors que la réalité live peut devenir :

```text
Snapshot T1 ----\
Snapshot T2 -----+--> même événement naturel
Snapshot T3 ----/
```

Les snapshots XML immuables restent conservés dans le filesystem.

Le modèle PostgreSQL ne représente pas encore explicitement la relation :

```text
N snapshots -> 1 RAW event
```

Une table de provenance ou d'observation distincte pourra être ajoutée ultérieurement si ce niveau de traçabilité devient nécessaire.

PostgreSQL ne conserve pas actuellement le contenu XML complet.

---

## 5. Déduplication RAW

Le pipeline Python possède une logique de déduplication avant la persistance PostgreSQL.

La clé Python actuelle est :

```text
symbol
halt_start
resumption_date
resumption_trade_time
reason_code
```

Elle n'est pas identique à la clé naturelle PostgreSQL :

```text
symbol
halt_date
halt_time
reason_code
market
```

### Baseline historique

```text
Événements bruts            : 744
Événements uniques          : 744
Clés PostgreSQL dupliquées  : 0
```

### Snapshot live validé

```text
Événements                  : 35
Clés PostgreSQL             : 35
Clés PostgreSQL dupliquées  : 0
```

Aucune divergence n'est observée sur les datasets actuellement validés.

Cette équivalence ne doit toutefois pas être présumée sur cinq années de données ou sur tous les futurs snapshots live.

Une divergence devra conduire à une décision explicite sur la stratégie de déduplication ou le modèle de données.

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

Valeurs autorisées pour `halt_close_status` :

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

### Validation historique

```text
RAW events    : 744
CORE episodes : 744
```

### Validation live

```text
RAW events du lot    : 35
CORE episodes du lot : 35
```

Cette relation est donc valide sur les datasets actuels.

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

Le writer V0.8 détecte cette situation au lieu de choisir arbitrairement une relation.

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

Les identifiants du collector étant générés séquentiellement, ils peuvent changer lorsqu'un dataset plus large est reconstruit.

Ils ne doivent donc pas être considérés comme des identifiants métier durables.

En V0.8, une mise à jour d'un épisode existant ne remplace pas son `collector_episode_id`.

---

## 9. Statut de clôture

Le modèle initial utilisait :

```text
halt_at_close BOOLEAN
```

Cette représentation était insuffisante pour préserver la sémantique des épisodes multi-jours.

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

Distribution historique validée :

```text
YES       : 15
NO        : 697
UNKNOWN   : 2
MULTI_DAY : 30
TOTAL     : 744
```

Il ne faut pas convertir automatiquement ces valeurs en BOOLEAN au niveau CORE.

### Protection V0.8

Les valeurs suivantes sont actuellement considérées comme finales :

```text
YES
NO
MULTI_DAY
```

Une observation entrante :

```text
UNKNOWN
```

ne doit pas remplacer un statut final déjà connu.

Une nouvelle valeur finale peut cependant remplacer une ancienne valeur finale lorsqu'une nouvelle observation apporte une correction non-NULL.

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

- fins de semaine;
- jours fériés;
- journées où le marché concerné n'était pas ouvert.

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

Exemples validés :

```text
2026-08-03 08:52:20.892
2026-08-28 15:55:18.200
```

La chaîne suivante est validée :

```text
Nasdaq XML
-> parser Python
-> PostgreSQL
```

Les colonnes CORE utilisent actuellement :

```text
TIMESTAMP
```

sans fuseau horaire.

Cette décision permet de préserver les valeurs temporelles actuellement interprétées par le pipeline sans appliquer de conversion implicite.

La sémantique exacte du fuseau horaire Nasdaq devra être validée avant certification de l'historique complet.

---

## 12. Persistance PostgreSQL V0.8

La persistance Nasdaq spécifique est implémentée dans :

```text
collectors/nasdaq_halts/src/nasdaq_postgresql.py
```

Le module utilise la connexion PostgreSQL générique :

```text
shared/database/
```

Flux :

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

La persistance RAW et CORE est exécutée dans une transaction commune.

Le writer V0.8 classe chaque traitement dans l'un des états suivants :

```text
inserted
updated
unchanged
```

pour RAW et CORE.

---

## 13. Sémantique de mise à jour RAW

Une observation live peut être incomplète au moment initial du HALT.

Exemple :

```text
T1
resumption_trade_time = NULL

T2
resumption_trade_time = 10:05:00
```

T2 représente le même événement naturel.

Il doit enrichir la ligne existante plutôt que créer une nouvelle ligne.

### Règles

```text
Existing NULL + incoming NULL
-> unchanged

Existing NULL + incoming value
-> update

Existing value + incoming NULL
-> preserve existing value

Existing value A + incoming A
-> unchanged

Existing value A + incoming value B
-> update avec B
```

### Champs RAW enrichissables

Actuellement :

```text
issue_name
resumption_date
resumption_quote_time
resumption_trade_time
pause_threshold_price
```

Les champs de la clé naturelle ne sont pas modifiés par cette logique.

### `source_file`

Le `source_file` existant est conservé.

Une observation ultérieure ne remplace pas le premier fichier source enregistré pour la ligne RAW.

---

## 14. Sémantique de mise à jour CORE

Un épisode CORE existant peut être enrichi lorsque de nouvelles informations deviennent disponibles.

Champs actuellement enrichissables :

```text
issue_name
market
reason_code
halt_end
duration_minutes
halt_close_status
```

Les valeurs NULL entrantes n'effacent pas les valeurs connues.

### Identité structurelle

Pour un épisode existant :

```text
symbol
halt_start
```

doivent rester cohérents avec l'épisode stocké.

Une incohérence structurelle provoque une erreur plutôt qu'une modification silencieuse.

### Statut de clôture

Un `UNKNOWN` entrant ne remplace pas :

```text
YES
NO
MULTI_DAY
```

Une valeur finale non-UNKNOWN peut remplacer une autre valeur finale si l'information entrante constitue une correction.

### `collector_episode_id`

Il est conservé après l'insertion initiale.

---

## 15. Comparaison des valeurs numériques

PostgreSQL retourne les colonnes :

```text
NUMERIC
```

sous forme de valeurs décimales.

La V0.8 normalise les valeurs numériques entrantes avant comparaison.

Cette normalisation évite qu'une valeur sémantiquement identique soit considérée comme différente uniquement en raison d'une comparaison entre types numériques Python différents.

Cette règle a notamment été validée pour :

```text
duration_minutes
```

Après normalisation, une réexécution historique complète produit :

```text
CORE updated   : 0
CORE unchanged : 744
```

---

## 16. Idempotence V0.8

L'idempotence signifie qu'une réexécution des mêmes observations ne doit :

- créer aucun doublon;
- effectuer aucune mise à jour inutile;
- modifier aucune information déjà équivalente.

### Historique

Réexécution V0.8 du baseline :

```text
RAW inserted          : 0
RAW updated           : 0
RAW unchanged         : 744

CORE inserted         : 0
CORE updated          : 0
CORE unchanged        : 744
```

### Live

Premier passage PostgreSQL du lot live validé :

```text
RAW inserted          : 35
RAW updated           : 0
RAW unchanged         : 0

CORE inserted         : 35
CORE updated          : 0
CORE unchanged        : 0
```

Deuxième passage sur le même contenu :

```text
RAW inserted          : 0
RAW updated           : 0
RAW unchanged         : 35

CORE inserted         : 0
CORE updated           : 0
CORE unchanged        : 35
```

L'idempotence est donc validée sur le baseline historique et sur un flux live réel.

---

## 17. Transaction

RAW et CORE sont persistés dans une transaction commune.

Conceptuellement :

```text
BEGIN
  |
  +-- RAW
  |
  +-- CORE
  |
COMMIT
```

Si une erreur survient :

```text
ROLLBACK
```

Une erreur CORE ne doit donc pas laisser silencieusement un chargement RAW partiellement validé dans la transaction courante.

---

## 18. Validation contrôlée du cycle live

Le test :

```text
tests/integration/test_nasdaq_postgresql_live_update.py
```

valide explicitement le cycle de vie d'un HALT.

### Étape 1 — HALT ouvert

```text
RAW  : inserted
CORE : inserted
```

### Étape 2 — même HALT complété

```text
RAW  : updated
CORE : updated
```

Le test confirme notamment :

```text
NULL -> valeur
```

### Étape 3 — observation identique

```text
RAW  : unchanged
CORE : unchanged
```

### Étape 4 — observation régressive

Une observation ultérieure contenant moins d'information ne doit pas effacer les valeurs connues.

Le test confirme notamment :

```text
valeur -> NULL
```

et :

```text
statut final -> UNKNOWN
```

sont protégés.

Le test est exécuté dans une transaction puis effectue :

```text
ROLLBACK
```

La base a été vérifiée après le test :

```text
QLV08TEST RAW rows  : 0
QLV08TEST CORE rows : 0
```

---

## 19. Loader CSV transitoire

Le module :

```text
collectors/nasdaq_halts/src/load_postgresql.py
```

a servi à valider initialement le modèle PostgreSQL à partir des CSV du baseline V0.6.

Il est conservé comme outil de validation et de migration.

Il ne constitue pas le chemin de persistance privilégié.

Le chemin actuel est :

```text
XML RAW
-> parsing / normalisation
-> objets Python
-> PostgreSQL RAW
-> PostgreSQL CORE
```

Les CSV demeurent des datasets dérivés utiles pour :

- validation;
- diagnostic;
- comparaison;
- non-régression;
- export.

---

## 20. Index

Les index et contraintes doivent répondre aux besoins réels de déduplication, relation et interrogation.

### `raw.nasdaq_trade_halt`

Clé naturelle :

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

Relation RAW :

```text
UNIQUE (trade_halt_id)
```

Des index complémentaires facilitent notamment les recherches par symbole, date/heure et raison selon le schéma appliqué.

Les index supplémentaires devront être ajoutés sur la base de requêtes et volumes réels plutôt que par anticipation.

---

## 21. Couche analytique future

Les objets analytiques PostgreSQL ne sont pas encore implémentés.

Les datasets Python/CSV actuels servent de référence fonctionnelle :

```text
ticker_halt_daily.csv
ticker_halt_metrics.csv
ticker_halt_reason_metrics.csv
```

Objets conceptuels futurs :

```text
analytics.ticker_halt_daily
analytics.ticker_halt_metrics
analytics.ticker_halt_reason_metrics
```

Migration réservée :

```text
database/migrations/003_create_nasdaq_halts_analytics.sql
```

Elle ne doit pas être implémentée avant validation de la sémantique analytique.

---

## 22. Calendrier de marché

Le pipeline Python actuel ne constitue pas encore un calendrier officiel complet.

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

ne doit pas être considérée comme définitivement modélisée dans PostgreSQL tant que le dénominateur des jours de marché n'est pas validé.

---

## 23. Reconstruction des données

Architecture reconstructible :

```text
Nasdaq
  |
  v
Immutable RAW XML
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

Ils doivent pouvoir être reconstruits à partir des couches appropriées.

Les fichiers XML originaux permettent de reconstruire les couches structurées si nécessaire.

---

## 24. Ingestion incrémentale live

Le chemin live V0.8 implémente actuellement :

1. téléchargement du flux Nasdaq;
2. création d'un snapshot RAW immuable;
3. parsing et normalisation;
4. déduplication;
5. construction des épisodes;
6. insertion des nouveaux événements;
7. enrichissement des événements existants;
8. protection des valeurs déjà connues;
9. persistance transactionnelle RAW + CORE;
10. production d'un CSV live dérivé;
11. compte rendu `inserted / updated / unchanged`.

Le chemin :

```text
nasdaq_halt_collector.py
```

est donc intégré à PostgreSQL pour le périmètre V0.8 actuel.

Les évolutions futures devront notamment ajouter :

- orchestration centrale;
- planification automatique;
- journalisation d'exécution centralisée;
- gestion explicite de la concurrence si plusieurs instances peuvent s'exécuter simultanément;
- éventuellement un modèle de provenance N snapshots → 1 événement.

---

## 25. Concurrence

La V0.8 est validée pour l'exécution séquentielle actuelle.

Le writer effectue actuellement une logique conceptuelle :

```text
SELECT
puis
INSERT ou UPDATE
```

La contrainte UNIQUE protège l'intégrité de la clé naturelle.

Cependant, deux processus exécutés exactement en parallèle pourraient entrer en compétition entre le SELECT et l'INSERT.

Avant de permettre des exécutions centralisées concurrentes, QuantLab devra définir une stratégie appropriée, par exemple :

```text
ON CONFLICT
```

ou un mécanisme de verrouillage adapté.

Ce point appartient à la future architecture d'orchestration.

---

## 26. Validation V0.8

### Baseline historique

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

Persistance après conversion V0.8 :

```text
RAW inserted          : 0
RAW updated           : 0
RAW unchanged         : 744

CORE inserted         : 0
CORE updated          : 0
CORE unchanged        : 744
```

### Live réel

Premier passage :

```text
Événements uniques    : 35
HALT Episodes         : 35

RAW inserted          : 35
RAW updated           : 0
RAW unchanged         : 0

CORE inserted         : 35
CORE updated          : 0
CORE unchanged        : 0
```

Deuxième passage :

```text
RAW inserted          : 0
RAW updated           : 0
RAW unchanged         : 35

CORE inserted         : 0
CORE updated          : 0
CORE unchanged        : 35
```

Ces résultats valident l'idempotence réelle du pipeline live V0.8.

---

## 27. Points à valider sur l'historique cinq ans

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
19. la validité du calendrier de marché;
20. la présence éventuelle de plusieurs observations du même événement dans un fichier;
21. les cas réels d'évolution `HALT ouvert -> HALT complété`;
22. les corrections Nasdaq de valeurs déjà connues.

Le schéma pourra évoluer par de nouvelles migrations avant d'être considéré comme stable pour PROD.

Les migrations déjà appliquées ne doivent pas être modifiées rétroactivement.

---

## 28. Migrations actuelles

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

Réservée aux futurs objets analytiques :

```text
database/migrations/003_create_nasdaq_halts_analytics.sql
```

Elle n'est pas encore implémentée.

Aucune migration de schéma supplémentaire n'a été nécessaire pour la V0.8.

La V0.8 modifie la logique de persistance et non la structure physique du modèle PostgreSQL V1.1.

---

## 29. Statut

Le modèle actuel demeure :

```text
PostgreSQL Data Model V1.1
```

Il est :

```text
implémenté en DEV
validé sur le baseline historique de 744 événements
validé avec le pipeline PostgreSQL V0.8
validé sur un lot live réel de 35 événements
validé pour l'idempotence historique et live
non encore certifié sur l'historique cinq ans
```

Les hypothèses structurantes, particulièrement :

```text
clé naturelle RAW
relation 1 RAW -> 1 CORE
provenance N snapshots -> 1 RAW
sémantique temporelle
calendrier de marché
```

demeurent soumises aux validations futures.
