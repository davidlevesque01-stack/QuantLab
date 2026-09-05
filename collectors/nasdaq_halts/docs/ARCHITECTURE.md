# QuantLab — Nasdaq Halt Collector

## ARCHITECTURE.md

**Version : V1.2**
**Statut : Architecture de référence du collecteur Nasdaq Halts**  
**Dernière mise à jour : 2026-09-05**

---

## 1. Objectif

Ce document décrit l’architecture spécifique du composant Nasdaq Halts de QuantLab.

L’architecture générale de la plateforme est documentée dans :

```text
../../../docs/architecture.md
```

Le composant Nasdaq Halts assure actuellement :

- la collecte historique et live des Nasdaq Trading Halts;
- la conservation des fichiers XML RAW immuables;
- la collecte historique robuste et reprenable par plage de dates;
- le parsing et la normalisation;
- la déduplication des observations Nasdaq;
- la construction des épisodes HALT;
- la persistance PostgreSQL des HALTs RAW canoniques;
- la conservation PostgreSQL des observations de reprise;
- la persistance des épisodes CORE;
- la conservation des relations CORE → RAW;
- la sélection d’une reprise canonique selon des règles de qualité explicites;
- la production de datasets CSV dérivés;
- le calcul des métriques;
- les tests de non-régression, d’intégrité, d’idempotence et de concurrence.

La V1.2 stabilise la distinction entre :

```text
observation Nasdaq
HALT RAW canonique
épisode CORE
```

et remplace les hypothèses provisoires V1.1 qui ne tenaient pas compte de toutes les observations de reprise et de la sémantique finale de l’identité CORE.

---

## 2. Emplacement dans le monorepo

```text
C:\QuantLab\QuantLab\collectors\nasdaq_halts
```

Arborescence fonctionnelle :

```text
collectors/nasdaq_halts/
|
+-- README.md
+-- config/
+-- data/
|   +-- raw/
|   +-- processed/
+-- logs/
+-- docs/
|   +-- ARCHITECTURE.md
|   +-- DATA_MODEL.md
|   +-- METRICS_SPECIFICATION.md
+-- src/
    +-- calculate_halt_metrics.py
    +-- load_postgresql.py
    +-- nasdaq_deduplication.py
    +-- nasdaq_episodes.py
    +-- nasdaq_halt_collector.py
    +-- nasdaq_historical_collector.py
    +-- nasdaq_historical_test.py
    +-- nasdaq_postgresql.py
    +-- nasdaq_xml.py
```

Les données RAW, processed et logs sont locales et exclues de Git.

---

## 3. Architecture logique V1.2

### 3.1 Historique

```text
NASDAQ TRADER
     |
     v
Historical Collector
     |
     +----> Immutable RAW XML
     |
     v
nasdaq_xml.py
     |
     v
nasdaq_deduplication.py
     |
     v
Distinct Nasdaq Observations
     |
     +------------------------------+
     |                              |
     v                              v
Canonical RAW HALT             RAW Resumption Observations
raw.nasdaq_trade_halt          raw.nasdaq_resumption
     |
     v
nasdaq_episodes.py
     |
     v
CORE Episodes
core.nasdaq_halt_episode
     |
     v
core.nasdaq_halt_episode_event
     |
     +----> CSV derived datasets
```

### 3.2 Live

```text
Nasdaq RSS
    |
    v
Live Collector
    |
    v
Immutable XML Snapshot
    |
    +----> latest_tradehalts.xml
    |
    v
nasdaq_xml.py
    |
    v
nasdaq_deduplication.py
    |
    v
Distinct Nasdaq Observations
    |
    +------------------------------+
    |                              |
    v                              v
Canonical RAW HALT             RAW Resumption Observations
raw.nasdaq_trade_halt          raw.nasdaq_resumption
    |
    v
nasdaq_episodes.py
    |
    v
CORE Episodes
    |
    +----> PostgreSQL CORE
    |
    +----> live_tradehalts.csv
```

PostgreSQL ne dépend pas des CSV processed.

Les CSV sont des sorties dérivées destinées notamment à la validation, au diagnostic, à la comparaison et à l’export.

---

## 4. Collecte historique

Module :

```text
src/nasdaq_historical_collector.py
```

Responsabilités :

- recevoir une plage de dates explicite;
- télécharger les XML journée par journée;
- éviter les téléchargements inutiles pour les fichiers déjà présents;
- valider le XML reçu;
- écrire les fichiers de manière atomique;
- gérer les retries;
- maintenir un checkpoint spécifique à la plage;
- reprendre une collecte interrompue;
- arrêter le traitement sur une date en échec;
- empêcher une date de fin future.

Commande :

```powershell
python -m collectors.nasdaq_halts.src.nasdaq_historical_collector `
  --start-date YYYY-MM-DD `
  --end-date YYYY-MM-DD
```

Valeurs de référence :

```text
delay-seconds       : 5
max-retries         : 3
retry-delay-seconds : 10
```

Un RSS XML valide contenant zéro HALT est considéré comme une acquisition valide.

---

## 5. RAW XML et provenance

Les XML historiques et les snapshots live horodatés sont les artefacts RAW immuables de provenance.

Historique :

```text
data/raw/nasdaq/historical/tradehalts_YYYY-MM-DD.xml
```

Live :

```text
data/raw/nasdaq/live/tradehalts_live_YYYYMMDDTHHMMSSZ.xml
```

Le fichier :

```text
latest_tradehalts.xml
```

est une copie pratique du dernier flux et n’est pas la provenance immuable.

Les XML RAW ne doivent pas être modifiés manuellement.

Dans PostgreSQL :

```text
raw.nasdaq_trade_halt
```

représente le HALT structuré canonique.

La table :

```text
raw.nasdaq_resumption
```

conserve les observations de reprise distinctes et leur `source_file` lorsque disponible.

La provenance XML complète demeure reconstruisible depuis les fichiers RAW immuables.

---

## 6. Parser et normalisation

Module :

```text
src/nasdaq_xml.py
```

Responsabilités :

- parsing XML;
- extraction des champs Nasdaq;
- normalisation;
- construction de `halt_start` et `halt_end`;
- conservation de `source_file`;
- préservation des fractions de seconde;
- support des différences `Mkt` / `Market`.

Les timestamps fractionnaires sont préservés à travers :

```text
Nasdaq XML
-> Python
-> PostgreSQL
```

---

## 7. Déduplication des observations

Module :

```text
src/nasdaq_deduplication.py
```

Clé logique Python des observations :

```text
symbol
halt_start
resumption_date
resumption_trade_time
reason_code
```

Cette identité sert à distinguer les observations Nasdaq.

Elle n’est volontairement pas identique à la clé naturelle du HALT RAW canonique.

### Clé naturelle RAW V1.2

```text
symbol
market
halt_date
halt_time
reason_code
```

### Clé naturelle CORE V1.2

```text
symbol
market
halt_start
```

`reason_code` est descriptif au niveau CORE et ne participe plus à l’identité de l’épisode.

Le pipeline distingue donc explicitement :

```text
unique_events
        |
        +----> observations de reprise
        |
        v
agrégation par clé RAW
        |
        v
HALT RAW canonique
```

Cette distinction évite de perdre des observations partielles ou complètes différentes pour un même HALT.

---

## 8. Modèle PostgreSQL V1.2

Objets principaux :

```text
raw.nasdaq_trade_halt
raw.nasdaq_resumption
core.nasdaq_halt_episode
core.nasdaq_halt_episode_event
```

### 8.1 HALT RAW canonique

`raw.nasdaq_trade_halt` contient une ligne par clé :

```text
symbol
market
halt_date
halt_time
reason_code
```

Contrainte :

```text
uq_nasdaq_trade_halt_natural_key
```

Le modèle est :

```text
N observations Nasdaq -> 1 HALT RAW canonique
```

### 8.2 Observations de reprise

`raw.nasdaq_resumption` conserve les observations distinctes ayant une `resumption_date`.

Identité :

```text
symbol
market
halt_date
halt_time
reason_code
resumption_date
resumption_quote_time
resumption_trade_time
```

Contrainte :

```text
uq_nasdaq_resumption_observation
```

La contrainte utilise :

```sql
UNIQUE NULLS NOT DISTINCT
```

afin que les observations contenant des heures de reprise `NULL` restent idempotentes.

### 8.3 Épisode CORE

`core.nasdaq_halt_episode` représente l’épisode métier.

Identité V1.2 :

```text
symbol
market
halt_start
```

Contrainte :

```text
uq_nasdaq_halt_episode_natural_key
```

### 8.4 Relation CORE → RAW

`core.nasdaq_halt_episode_event` représente :

```text
1 CORE episode -> N RAW events
```

La paire :

```text
episode_id
trade_halt_id
```

est unique.

---

## 9. Construction des épisodes

Module :

```text
src/nasdaq_episodes.py
```

La construction des épisodes :

- regroupe les événements selon la logique métier validée;
- trie chronologiquement;
- fusionne les périodes lorsque requis;
- calcule `halt_start`;
- calcule `halt_end`;
- calcule `duration_minutes`;
- détermine le statut de clôture.

Statuts :

```text
YES
NO
UNKNOWN
MULTI_DAY
```

Les identifiants tels que :

```text
H00000001
```

sont des identifiants de calcul et non des identités métier durables.

La persistance CORE utilise l’identité naturelle V1.2 plutôt que `collector_episode_id`.

---

## 10. Sémantique CORE V1.2

Un CORE episode représente un épisode métier identifié par :

```text
symbol
market
halt_start
```

`reason_code` est un attribut descriptif.

Plusieurs observations ou événements RAW peuvent contribuer au même épisode.

Le cas BCARU du 12 janvier 2026 a confirmé qu’un même `halt_start` peut être observé avec :

```text
T1
T2
T3
```

Ces codes ne doivent donc pas créer trois identités CORE distinctes.

La relation complète est reconstruite dans :

```text
core.nasdaq_halt_episode_event
```

Le writer valide notamment :

- qu’un épisode possède des RAW associés;
- que les relations référencent des objets existants;
- qu’une paire épisode/RAW n’est pas dupliquée;
- que la relation persistée correspond aux groupes calculés.

---

## 11. Persistance PostgreSQL V1.2

Module :

```text
src/nasdaq_postgresql.py
```

Version :

```text
VERSION = "1.2"
```

Chemin de production :

```text
XML
 -> parsing / normalisation
 -> déduplication des observations
 -> canonicalisation RAW
 -> observations RESUMPTION
 -> construction CORE
 -> PostgreSQL
```

La persistance complète est exécutée dans une transaction commune.

Compteurs produits :

```text
RAW inserted
RAW updated
RAW unchanged

RESUMPTION inserted
RESUMPTION existing

CORE inserted
CORE updated
CORE unchanged
```

---

## 12. Canonicalisation RAW

Plusieurs observations Python peuvent partager la même clé RAW V1.2.

Le writer les agrège avant persistance.

Les champs de reprise canoniques sont sélectionnés à partir d’une seule observation et ne sont jamais recombinés artificiellement entre plusieurs observations.

### Rang 2 — reprise complète valide

Une observation est complète et valide lorsque le `halt_end` calculé respecte :

```text
halt_end >= halt_start
```

### Rang 1 — reprise partielle admissible

L’observation contient une information de reprise utile sans permettre encore une reprise complète.

### Rang 0 — reprise non exploitable ou invalide

Inclut notamment :

- aucune information de reprise exploitable;
- reprise temporellement impossible;
- `halt_end < halt_start`.

Lorsqu’il existe plusieurs observations complètes valides, la reprise valide la plus tardive est choisie de manière déterministe.

---

## 13. Préservation des observations invalides

Une observation de reprise invalide ne doit pas contaminer le HALT RAW canonique.

Elle n’est toutefois pas supprimée de la provenance structurée.

Elle demeure dans :

```text
raw.nasdaq_resumption
```

Lorsque toutes les observations de reprise d’une clé RAW sont invalides :

```text
raw.nasdaq_trade_halt.resumption_date
raw.nasdaq_trade_halt.resumption_quote_time
raw.nasdaq_trade_halt.resumption_trade_time
```

restent `NULL`.

Cinq cas historiques entièrement invalides ont été validés :

```text
NCNA
QFTA.W
TPC
PBR.A
LSEAW
```

Leur représentation canonique RAW ne contient aucune reprise invalide, tandis que leurs observations sources demeurent conservées.

---

## 14. Mise à jour RAW

Une observation ultérieure du même HALT naturel peut enrichir la ligne RAW.

Règles générales :

```text
DB NULL + incoming NULL
-> unchanged

DB NULL + incoming value
-> update

DB value + incoming NULL
-> preserve DB value

DB value A + incoming A
-> unchanged

DB value A + incoming B
-> update avec B
```

Les règles de reprise canonique ont priorité sur une simple logique champ-par-champ afin d’éviter de mélanger plusieurs observations.

`source_file` est préservé selon la politique de provenance du writer.

---

## 15. Mise à jour CORE

Les champs CORE enrichissables comprennent notamment :

```text
issue_name
market
reason_code
halt_end
duration_minutes
halt_close_status
```

Les valeurs `NULL` entrantes n’effacent pas les valeurs connues.

Pour `halt_close_status` :

```text
UNKNOWN
```

ne remplace pas :

```text
YES
NO
MULTI_DAY
```

Une nouvelle valeur finale non-`UNKNOWN` peut corriger une valeur finale existante.

`collector_episode_id` est conservé après insertion initiale.

---

## 16. Transaction et concurrence

La persistance est atomique :

```text
BEGIN
  |
  +-- PostgreSQL advisory lock
  +-- RAW HALT
  +-- RESUMPTION observations
  +-- CORE episodes
  +-- CORE -> RAW relationships
  |
COMMIT
```

Toute erreur provoque :

```text
ROLLBACK
```

### Verrou Nasdaq QuantLab

Avant toute lecture ou écriture de persistance Nasdaq, le writer acquiert :

```sql
pg_advisory_xact_lock(716203, 1)
```

Clé réservée :

```text
(716203, 1)
```

Le verrou est conservé pendant toute la transaction et libéré automatiquement au `COMMIT` ou au `ROLLBACK`.

La migration V1.2 utilise le même verrou.

### Validation de concurrence

Deux connexions PostgreSQL indépendantes ont été testées.

Résultat :

```text
holder: lock acquired
holder: transaction completed
waiter: lock acquired after 5.03 seconds
waiter: transaction completed
concurrency test completed
```

La seconde transaction attend donc correctement la libération du verrou.

Les contraintes PostgreSQL restent la protection d’intégrité finale pour les writers externes qui n’utilisent pas ce verrou.

---

## 17. Migrations PostgreSQL

Migrations actuelles :

```text
001_create_nasdaq_halts_schema.sql
002_core_episode_event.sql
002_fix_nasdaq_halt_close_status.sql
003_update_nasdaq_raw_natural_key_v1_1.sql
004_update_nasdaq_core_natural_key_v1_1.sql
005_create_nasdaq_resumption.sql
006_nasdaq_persistence_v1_2.sql
```

Deux migrations historiques portent le préfixe `002`.

Cette anomalie est conservée et documentée; les fichiers ne doivent pas être renommés rétroactivement.

### Migration 006

```text
database/migrations/006_nasdaq_persistence_v1_2.sql
```

Elle :

- consolide les doublons RAW V1.2;
- préserve et réoriente les relations CORE → RAW;
- installe la clé naturelle RAW V1.2;
- installe la clé naturelle CORE V1.2;
- déduplique les observations de reprise;
- installe `UNIQUE NULLS NOT DISTINCT`;
- valide l’intégrité référentielle;
- utilise le verrou `(716203, 1)`.

La migration requiert PostgreSQL 15+ pour `UNIQUE NULLS NOT DISTINCT`.

Une copie de test de la migration a été exécutée complètement en DEV avec `ROLLBACK` final.

---

## 18. Validation historique complète V1.2

Plage :

```text
2020-01-01 -> 2026-08-28
```

Fichiers XML :

```text
2 432
```

Jours de marché observés :

```text
1 738
```

Résultats :

```text
Événements bruts       : 69 186
Événements uniques     : 68 170
HALT RAW canoniques    : 68 072
CORE episodes          : 68 017
Tickers différents     : 9 718
Lignes quotidiennes    : 50 000
Durées calculables     : 67 983
```

Statuts de clôture :

```text
YES       : 1 777
NO        : 62 902
UNKNOWN   : 34
```

Le corpus historique complet a permis de remplacer plusieurs hypothèses V1.1 par les règles V1.2 actuellement validées.

---

## 19. Idempotence V1.2

Réexécution historique complète de référence :

```text
RAW inserted          : 0
RAW updated           : 0
RAW unchanged         : 68072

RESUMPTION inserted   : 0
RESUMPTION existing   : 68147

CORE inserted         : 0
CORE updated          : 0
CORE unchanged        : 68017
```

Tests :

```text
QVCG TEST  : PASS
BCARU TEST : PASS
```

Ce résultat constitue le checkpoint d’idempotence séquentielle V1.2.

---

## 20. BCARU — fixture historique

Le test BCARU ne repose plus sur un total cumulatif susceptible de changer avec les nouvelles collectes.

Il utilise un fixture historique fixe jusqu’au :

```text
2026-08-27
```

Le fixture valide :

```text
21 épisodes CORE
13 dates historiques
```

Répartition attendue :

```text
2026-01-12 : 1
2026-07-28 : 1
2026-07-29 : 2
2026-07-30 : 1
2026-07-31 : 1
2026-08-03 : 1
2026-08-07 : 2
2026-08-10 : 7
2026-08-11 : 1
2026-08-14 : 1
2026-08-21 : 1
2026-08-25 : 1
2026-08-27 : 1
```

Le 2026-08-03 est également validé comme :

```text
halt_at_close = YES
```

Les données officielles BCARU ont confirmé :

- des observations partielles et complètes pour un même HALT;
- plusieurs HALTs distincts le même jour;
- les reason codes T1/T2/T3 sur un même `halt_start`;
- la sémantique CORE V1.2.

---

## 21. Intégrité référentielle

Après la persistance V1.2, les validations suivantes retournent zéro anomalie :

```text
broken_episode_raw_refs        : 0
broken_relation_episode_refs   : 0
broken_relation_raw_refs       : 0
duplicate episode/raw pairs    : 0
```

Ces validations sont également intégrées à la migration 006.

---

## 22. Données processed

Les CSV restent dérivés :

```text
tradehalts.csv
halt_episodes.csv
ticker_halt_daily.csv
ticker_halt_metrics.csv
ticker_halt_reason_metrics.csv
live_tradehalts.csv
```

Ils servent à :

- validation;
- diagnostic;
- comparaison;
- export;
- inspection;
- non-régression.

Ils ne constituent pas la source d’intégration PostgreSQL.

---

## 23. Métriques

Les définitions métier sont maintenues dans :

```text
docs/METRICS_SPECIFICATION.md
```

Les objets analytics PostgreSQL restent différés jusqu’à validation du calendrier officiel de marché et comparaison avec les métriques Python validées.

Objets conceptuels :

```text
analytics.ticker_halt_daily
analytics.ticker_halt_metrics
analytics.ticker_halt_reason_metrics
```

La métrique :

```text
halts_per_market_day
```

doit utiliser un calendrier de marché correctement défini.

---

## 24. Loader CSV transitoire

Module :

```text
src/load_postgresql.py
```

Le loader CSV a servi à la validation initiale de PostgreSQL.

Il est conservé comme outil de migration ou de diagnostic.

Il ne constitue pas le chemin de production.

Le chemin de référence est :

```text
XML
-> Python
-> PostgreSQL RAW
-> PostgreSQL CORE
```

avec conservation séparée des observations de reprise.

---

## 25. Encodage

Le dépôt contient :

```text
.editorconfig
```

avec encodage UTF-8.

Sous Windows PowerShell 5.1 :

```powershell
Set-Content -Encoding utf8
```

peut écrire un BOM UTF-8.

Pour les migrations SQL et autres fichiers devant être écrits sans BOM, utiliser explicitement :

```powershell
$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
```

Cette règle a été ajoutée après qu’un BOM a provoqué une erreur de syntaxe lors d’un test `psql`.

---

## 26. Limites et travaux restants

La persistance V1.2 est stabilisée en DEV.

Les principaux travaux restant avant certification PROD sont :

1. formaliser la sémantique temporelle et le fuseau Nasdaq;
2. valider et modéliser le calendrier officiel des jours de marché;
3. construire les objets analytics PostgreSQL;
4. comparer les analytics PostgreSQL aux métriques Python validées;
5. définir et tester la stratégie de sauvegarde/restauration;
6. mettre en place l’orchestration centralisée;
7. mettre en place l’exécution planifiée et à la demande;
8. préparer les environnements TEST et PROD;
9. définir la gestion centralisée des secrets;
10. poursuivre les validations de données live réelles;
11. envisager le durcissement `NOT NULL` de certains champs participant aux identités, notamment `core.nasdaq_halt_episode.market`, après validation dédiée;
12. décider si une provenance explicite N snapshots → 1 RAW doit être matérialisée à l’avenir.

Les validations de l’historique 2020-2026, de l’identité RAW V1.2, de l’identité CORE V1.2, de l’idempotence et de la concurrence ne sont plus des travaux futurs : elles sont complétées.

---

## 27. Gouvernance documentaire

| Changement | Document |
|---|---|
| Flux, scripts, architecture du collecteur | `ARCHITECTURE.md` |
| Tables, colonnes, relations | `DATA_MODEL.md` |
| Définitions de métriques | `METRICS_SPECIFICATION.md` |
| Utilisation | `README.md` |
| PostgreSQL transversal | `../../../docs/database.md` |
| Architecture plateforme | `../../../docs/architecture.md` |
| Installation et environnement | `../../../docs/installation.md` |

Toute modification de logique ou de modèle doit être documentée avec le code correspondant.

---

## 28. État

```text
V1.2 — POSTGRESQL PERSISTENCE STABILIZED
```

Checkpoint validé :

```text
2 432 XML
69 186 événements bruts
68 170 observations uniques
68 072 HALTs RAW canoniques
68 147 observations RESUMPTION persistées
68 017 épisodes CORE
QVCG PASS
BCARU PASS
Intégrité référentielle PASS
Idempotence séquentielle PASS
Concurrence advisory lock PASS
Migration 006 rollback test PASS
```

La V1.2 constitue désormais l’architecture de référence du collecteur Nasdaq Halts en DEV.

Les prochaines étapes portent principalement sur la couche analytics, le calendrier de marché, l’exploitation centralisée et la préparation des environnements futurs.
