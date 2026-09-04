# QuantLab — Nasdaq Halt Collector

## ARCHITECTURE.md

**Version : V1.1**  
**Statut : Architecture de référence du collecteur Nasdaq Halts**  
**Dernière mise à jour : 2026-09-04**

---

## 1. Objectif

Ce document décrit l’architecture spécifique du composant Nasdaq Halts de QuantLab.

L’architecture générale de la plateforme est documentée dans :

```text
../../../docs/architecture.md
```

Le composant Nasdaq Halts assure actuellement :

- la collecte historique et live des Nasdaq Trading Halts;
- la conservation des fichiers XML RAW;
- la collecte historique robuste et reprenable par plage de dates;
- le parsing et la normalisation;
- la déduplication;
- la construction des épisodes HALT;
- la persistance PostgreSQL RAW et CORE;
- la production de datasets CSV de validation;
- le calcul des métriques;
- les tests de non-régression et d’intégration.

L’état V1.1 correspond à la première validation du modèle CORE permettant à un épisode de regrouper plusieurs événements RAW.

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

## 3. Architecture logique

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
unique_events
     |
     +----> PostgreSQL RAW
     |
     v
nasdaq_episodes.py
     |
     v
CORE episodes
     |
     +----> PostgreSQL CORE
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
unique_events
    |
    +----> PostgreSQL RAW
    |
    v
nasdaq_episodes.py
    |
    v
CORE episodes
    |
    +----> PostgreSQL CORE
    |
    v
live_tradehalts.csv
```

PostgreSQL ne dépend pas des CSV processed. Les CSV sont des sorties dérivées destinées notamment à la validation, au diagnostic et à l’export.

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

Valeurs par défaut :

```text
delay-seconds       : 5
max-retries         : 3
retry-delay-seconds : 10
```

Un RSS XML valide contenant zéro HALT est considéré comme une acquisition valide.

---

## 5. RAW et provenance

Les XML historiques et les snapshots live horodatés sont les artefacts RAW de provenance.

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

Dans PostgreSQL, `raw.nasdaq_trade_halt.source_file` conserve actuellement le premier snapshot ayant créé l’événement structuré.

Le modèle N snapshots → 1 événement RAW n’est pas encore matérialisé par une table de provenance distincte.

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

---

## 7. Déduplication

Module :

```text
src/nasdaq_deduplication.py
```

Clé logique Python actuelle :

```text
symbol
halt_start
resumption_date
resumption_trade_time
reason_code
```

Clé naturelle PostgreSQL RAW :

```text
symbol
halt_date
halt_time
reason_code
market
```

Clé naturelle PostgreSQL CORE V1.1 :

```text
symbol
market
reason_code
halt_start
```

Les deux niveaux de clé ne sont donc pas identiques et doivent rester explicitement documentés.

---

## 8. Construction des épisodes

Module :

```text
src/nasdaq_episodes.py
```

La construction des épisodes :

- regroupe les événements par symbole;
- trie chronologiquement;
- fusionne les périodes selon la logique validée;
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

Les identifiants `H00000001`, etc., sont des identifiants de calcul et non des identités métier durables.

### Cardinalité V1.1

La validation historique complète montre :

```text
RAW events uniques : 68 170
CORE episodes      : 68 035
CORE -> RAW        : 68 170 relations
CORE avec >1 RAW   : 90
RAW avec >1 CORE   : 0
```

Le modèle correct est donc :

```text
1 CORE episode -> N RAW events
```

avec, sur le dataset validé :

```text
1 RAW event -> 1 CORE episode
```

Cette dernière propriété est protégée par validation applicative et non par une contrainte UNIQUE sur `core.nasdaq_halt_episode.trade_halt_id`.

---

## 9. Persistance PostgreSQL V1.1

Module :

```text
src/nasdaq_postgresql.py
```

Le chemin de production est :

```text
XML
 -> parsing
 -> déduplication
 -> épisodes
 -> PostgreSQL RAW
 -> PostgreSQL CORE
```

La persistance RAW + CORE + relations CORE→RAW est exécutée dans une transaction commune.

La V1.1 utilise une stratégie batch pour les opérations CORE :

- staging temporaire;
- INSERT massif;
- UPDATE massif;
- suppression des relations obsolètes;
- insertion des relations manquantes;
- validation relationnelle.

Les opérations réelles sur les tables CORE ne sont pas effectuées individuellement par épisode.

---

## 10. Clé naturelle CORE V1.1

La clé naturelle est :

```text
symbol
market
reason_code
halt_start
```

Migration :

```text
database/migrations/004_update_nasdaq_core_natural_key_v1_1.sql
```

Cette clé est nécessaire notamment parce que les tests historiques ont identifié :

```text
CANF / 2026-03-04 09:38:41
CVM  / 2020-02-26 15:02:49
```

avec plusieurs événements différenciés par `reason_code`.

La clé `symbol + halt_start` seule est donc insuffisante.

---

## 11. Sémantique CORE V1.1

Un CORE episode représente une période continue de HALT.

Plusieurs événements RAW peuvent appartenir au même épisode lorsque la logique de construction les fusionne.

Les relations sont stockées dans :

```text
core.nasdaq_halt_episode_event
```

Le modèle est :

```text
core.nasdaq_halt_episode
        |
        +---- raw event
        +---- raw event
        +---- raw event
```

La relation est reconstruite à chaque persistance à partir des groupes d’événements produits par la même logique de regroupement que `nasdaq_episodes.py`.

Le writer refuse :

- un épisode sans RAW;
- un RAW affecté à plusieurs CORE;
- une divergence entre les groupes Python et les épisodes produits;
- une relation manquante après persistance.

---

## 12. Mise à jour RAW

Une observation ultérieure du même événement naturel peut enrichir la ligne RAW.

Règles :

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

`source_file` conserve le premier snapshot ayant créé la ligne.

---

## 13. Mise à jour CORE

Les champs CORE enrichissables comprennent notamment :

```text
issue_name
market
reason_code
halt_end
duration_minutes
halt_close_status
```

Les valeurs NULL entrantes n’effacent pas les valeurs connues.

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

Une nouvelle valeur finale non-UNKNOWN peut corriger une valeur finale existante.

`collector_episode_id` est conservé après insertion initiale.

---

## 14. Transaction

La persistance est atomique :

```text
BEGIN
  RAW
  CORE
  CORE -> RAW relationships
COMMIT
```

Toute erreur provoque :

```text
ROLLBACK
```

Le test historique V1.1 en mode dry-run confirme le rollback complet.

---

## 15. Validation historique complète

Plage :

```text
2020-01-01 -> 2026-08-28
```

Fichiers XML :

```text
2 432
```

Résultats Python :

```text
Événements RAW parser : 69 186
Événements uniques    : 68 170
CORE episodes         : 68 035
Durées calculables    : 67 997

HALT close YES        : 1 780
HALT close NO         : 62 917
HALT UNKNOWN          : 33
HALT MULTI_DAY        : 3 305
```

Validation PostgreSQL en dry-run :

```text
RAW inserted          : 58 701
RAW updated           : 0
RAW unchanged         : 9 469

CORE inserted         : 68 035
CORE updated          : 0
CORE unchanged        : 0

CORE classified       : 68 035
CORE expected         : 68 035

CORE rows observed    : 68 035
CORE -> RAW relations : 68 170
RAW expected          : 68 170

RAW with >1 CORE      : 0
CORE with >1 RAW      : 90

HISTORICAL VALIDATION : PASS
ROLLBACK              : PASS
```

Performance observée :

```text
Parsing               : 5.636 s
Déduplication         : 0.081 s
CORE construction     : 0.225 s
PostgreSQL total      : 47.140 s
TOTAL                 : 53.087 s
```

Le temps PostgreSQL inclut le chargement RAW et CORE ainsi que les validations correspondantes.

---

## 16. Correction du modèle V1.1

La V1.1 corrige une hypothèse V1.0 devenue fausse à volume historique réel :

### Ancienne hypothèse

```text
1 RAW -> 1 CORE
```

avec :

```text
UNIQUE(core.trade_halt_id)
```

### Modèle V1.1

```text
1 CORE -> N RAW
```

avec une table de relation :

```text
core.nasdaq_halt_episode_event
```

et validation que chaque RAW appartient à au plus un CORE.

La suppression de la contrainte :

```text
uq_nasdaq_halt_episode_trade_halt
```

est donc nécessaire.

La contrainte naturelle CORE V1.1 est :

```text
UNIQUE (
    symbol,
    market,
    reason_code,
    halt_start
)
```

---

## 17. Données processed

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
- inspection.

Ils ne constituent pas la source d’intégration PostgreSQL.

---

## 18. Métriques

Les définitions métier sont maintenues dans :

```text
docs/METRICS_SPECIFICATION.md
```

Les objets analytics PostgreSQL restent différés jusqu’à validation complète :

- du calendrier de marché;
- des épisodes multi-jours;
- des statuts de clôture;
- de la cardinalité RAW→CORE;
- de l’équivalence Python/PostgreSQL.

---

## 19. Concurrence

La V1.1 est validée pour l’exécution séquentielle.

Le writer utilise une logique batch et des contraintes PostgreSQL pour protéger l’intégrité.

La concurrence entre plusieurs instances n’est pas encore considérée comme un scénario de production validé.

Avant orchestration concurrente, une stratégie explicite `ON CONFLICT`, verrouillage ou équivalent devra être définie et testée.

---

## 20. Limites restantes

Avant certification PROD :

1. valider l’intégrité complète des 2 432 XML;
2. valider la complétude exacte de la période historique;
3. valider la clé naturelle RAW sur tout l’historique;
4. confirmer la sémantique temporelle et le fuseau Nasdaq;
5. valider le calendrier officiel des jours de marché;
6. analyser les épisodes multi-jours;
7. analyser les 90 CORE comportant plusieurs RAW;
8. vérifier les événements présents dans plusieurs snapshots;
9. définir si une provenance N snapshots → 1 RAW doit être matérialisée;
10. tester les corrections réelles de données live;
11. tester la concurrence avant orchestration multi-instance;
12. valider les performances à volume de production;
13. définir la période historique cinq ans officielle.

---

## 21. Gouvernance documentaire

| Changement | Document |
|---|---|
| Flux, scripts, architecture | `ARCHITECTURE.md` |
| Tables, colonnes, relations | `DATA_MODEL.md` |
| Définitions de métriques | `METRICS_SPECIFICATION.md` |
| Utilisation | `README.md` |
| PostgreSQL transversal | `../../../docs/database.md` |
| Architecture plateforme | `../../../docs/architecture.md` |

Toute modification de logique ou de modèle doit être documentée avec le code correspondant.

---

## 22. État

```text
V1.1 — HISTORICAL CORE LOAD VALIDATED
```

La V1.1 est validée en DEV sur l’historique chargé :

```text
2 432 XML
68 170 RAW uniques
68 035 CORE episodes
68 170 relations CORE→RAW
90 CORE multi-RAW
0 RAW multi-CORE
```

La validation a été exécutée en transaction et terminée par rollback.

Le modèle est donc prêt pour le prochain checkpoint Git et pour la poursuite de l’analyse des données historiques avant stabilisation PROD.
