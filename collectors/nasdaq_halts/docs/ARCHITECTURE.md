# QuantLab — Nasdaq Halt Collector

## ARCHITECTURE.md

**Version : V0.8**
**Statut : Architecture de référence du collecteur Nasdaq Halts**
**Dernière mise à jour : 2026-08-28**

---

## 1. Objectif

Ce document décrit l'architecture spécifique du composant Nasdaq Halts de QuantLab.

L'architecture générale de la plateforme est documentée dans :

```text
../../../docs/architecture.md
```

Le composant Nasdaq Halts assure actuellement :

- la collecte historique et live des données Nasdaq Trading Halts;
- la conservation des fichiers XML RAW;
- la création de snapshots live XML immuables;
- le parsing et la normalisation via un parser commun;
- la déduplication;
- la construction des épisodes HALT via un module commun;
- la persistance directe PostgreSQL RAW et CORE;
- l'enrichissement des HALT live lorsque Nasdaq complète l'information;
- la protection contre la régression de données déjà connues;
- la production de datasets CSV dérivés;
- le calcul des métriques historiques;
- les tests de non-régression;
- les tests d'intégration PostgreSQL.

---

## 2. Emplacement dans le monorepo

Le composant est situé sous :

```text
C:\QuantLab\QuantLab\collectors\nasdaq_halts
```

Arborescence de référence :

```text
collectors/nasdaq_halts/
|
+-- README.md
|
+-- config/
|   +-- config.json
|
+-- data/
|   +-- raw/
|   |   +-- nasdaq/
|   |       +-- historical/
|   |       |   +-- tradehalts_YYYY-MM-DD.xml
|   |       |
|   |       +-- live/
|   |       |   +-- tradehalts_live_YYYYMMDDTHHMMSSZ.xml
|   |       |
|   |       +-- latest_tradehalts.xml
|   |
|   +-- processed/
|       +-- tradehalts.csv
|       +-- halt_episodes.csv
|       +-- ticker_halt_daily.csv
|       +-- ticker_halt_metrics.csv
|       +-- ticker_halt_reason_metrics.csv
|       +-- live_tradehalts.csv
|
+-- docs/
|   +-- ARCHITECTURE.md
|   +-- DATA_MODEL.md
|   +-- METRICS_SPECIFICATION.md
|
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

Le test d'intégration PostgreSQL live se trouve sous :

```text
tests/integration/test_nasdaq_postgresql_live_update.py
```

Les répertoires de données RAW, processed et logs sont locaux et exclus de Git.

---

## 3. Architecture logique V0.8

La V0.8 utilise maintenant des composants communs pour les chemins historique et live.

Architecture générale :

```text
                         NASDAQ TRADER
                        /             \
                       /               \
                      v                 v
             Historical Source       Live RSS
                      |                 |
                      v                 v
             Historical Collector   Live Collector
                      |                 |
                      v                 v
             Historical RAW XML     Immutable Live
                                    RAW Snapshot
                      \                 /
                       \               /
                        v             v
                       Shared XML Parser
                              |
                              v
                         Normalized
                           Events
                              |
                              v
                    Shared Deduplication
                              |
                              v
                        unique_events
                         /         \
                        /           \
                       v             v
              PostgreSQL RAW     Derived CSV
                       |
                       v
               Shared Episode Builder
                       |
                       v
                    episodes
                    /     \
                   /       \
                  v         v
         PostgreSQL CORE   Historical
                           Daily / Metrics
```

Le chemin PostgreSQL ne dépend pas des CSV processed.

Les CSV sont des sorties secondaires utilisées pour :

- validation;
- diagnostic;
- non-régression;
- comparaison;
- export;
- inspection manuelle.

---

## 4. Couche de collecte

### 4.1 `nasdaq_historical_collector.py`

Responsabilités :

- interroger la source historique Nasdaq;
- télécharger les données journée par journée;
- sauvegarder un fichier XML par date;
- éviter de télécharger inutilement un fichier déjà présent;
- gérer les erreurs de collecte;
- permettre une reprise après interruption;
- utiliser un délai entre les requêtes;
- maintenir l'état de progression de la collecte.

Format historique :

```text
tradehalts_YYYY-MM-DD.xml
```

Exemple :

```text
tradehalts_2026-08-10.xml
```

Les fichiers historiques sont conservés afin de permettre la reconstruction des données structurées.

### 4.2 `nasdaq_halt_collector.py`

Le chemin live est intégré à l'architecture PostgreSQL depuis la V0.8.

Responsabilités :

1. télécharger le flux RSS Nasdaq courant;
2. conserver un snapshot XML immuable horodaté;
3. mettre à jour une copie pratique `latest_tradehalts.xml`;
4. parser le snapshot avec le parser commun;
5. dédupliquer les événements;
6. construire les HALT Episodes;
7. persister directement RAW et CORE dans PostgreSQL;
8. produire un CSV live optionnel;
9. afficher les compteurs de persistance.

Exécution de référence :

```powershell
python -m collectors.nasdaq_halts.src.nasdaq_halt_collector
```

Le CSV live ne constitue pas un intermédiaire de persistance.

---

## 5. Couche RAW — provenance

### 5.1 Historique

Répertoire :

```text
data/raw/nasdaq/historical/
```

Format :

```text
tradehalts_YYYY-MM-DD.xml
```

### 5.2 Live

Répertoire :

```text
data/raw/nasdaq/live/
```

Chaque collecte live crée un snapshot immuable :

```text
tradehalts_live_YYYYMMDDTHHMMSSZ.xml
```

Le timestamp du nom de fichier est UTC.

Exemple validé :

```text
tradehalts_live_20260828T205115Z.xml
```

Le collecteur maintient également :

```text
data/raw/nasdaq/latest_tradehalts.xml
```

Ce fichier est une copie pratique du dernier flux reçu.

Il n'est pas le fichier de provenance immuable.

### 5.3 Règles RAW

1. ne pas modifier manuellement les XML;
2. ne pas remplacer un fichier historique valide sans raison documentée;
3. conserver les snapshots live horodatés;
4. conserver les données RAW après traitement;
5. considérer PostgreSQL comme la représentation structurée de référence;
6. considérer les données structurées comme reconstruisibles à partir des XML;
7. considérer les CSV comme des données dérivées.

### 5.4 Provenance PostgreSQL

Chaque événement normalisé reçoit :

```text
source_file
```

Cette valeur est persistée dans :

```text
raw.nasdaq_trade_halt.source_file
```

Pour un événement historique :

```text
tradehalts_2026-08-03.xml
```

Pour un événement live :

```text
tradehalts_live_20260828T205115Z.xml
```

Dans la V0.8, `source_file` conserve le **premier snapshot ayant créé l'événement RAW**.

Une observation ultérieure du même événement peut enrichir les données PostgreSQL sans remplacer ce `source_file`.

Les snapshots XML immuables demeurent la provenance primaire.

Un futur modèle de provenance pourra représenter explicitement :

```text
N snapshots -> 1 RAW event
```

PostgreSQL ne contient pas actuellement le contenu XML complet.

---

## 6. Parser XML commun

Module :

```text
src/nasdaq_xml.py
```

La V0.8 centralise le parsing historique et live.

Responsabilités :

- parsing XML;
- extraction des champs Nasdaq;
- normalisation des valeurs;
- construction de `halt_start`;
- construction de `halt_end`;
- conservation de `source_file`;
- préservation des fractions de seconde.

Le parser supporte la différence observée entre :

```text
Historical XML : Mkt
Live XML       : Market
```

La validation du flux live réel a confirmé l'utilisation de :

```text
Market
```

Les timestamps fractionnaires sont préservés.

Exemple :

```text
15:55:18.200
```

devient :

```text
2026-08-28 15:55:18.200000
```

---

## 7. Déduplication commune

Module :

```text
src/nasdaq_deduplication.py
```

La logique actuelle reproduit volontairement la déduplication historique V0.7 validée.

Clé logique actuelle :

```text
symbol
halt_start
resumption_date
resumption_trade_time
reason_code
```

Cette clé n'est pas identique à la clé naturelle PostgreSQL.

La clé PostgreSQL est :

```text
symbol
halt_date
halt_time
reason_code
market
```

Baseline historique :

```text
744 événements bruts
744 événements uniques
0 collision de clé naturelle PostgreSQL
```

Un snapshot live réel a également été vérifié :

```text
35 événements
35 clés naturelles PostgreSQL
0 clé naturelle dupliquée
```

Les doublons apparents observés sur la présentation Web Nasdaq n'étaient donc pas présents comme doublons de clé naturelle dans le RSS XML validé.

Si plusieurs observations d'un même HALT naturel apparaissent un jour dans un seul snapshot RSS, la stratégie de déduplication live devra être revue explicitement.

---

## 8. Construction commune des épisodes

Module :

```text
src/nasdaq_episodes.py
```

La V0.8 centralise la construction des HALT Episodes.

Responsabilités :

- regrouper les événements par symbole;
- trier chronologiquement;
- appliquer la logique de fusion historique validée;
- déterminer `halt_start`;
- déterminer `halt_end`;
- calculer `duration_minutes`;
- déterminer le statut de clôture;
- produire les statistiques d'épisodes.

Statuts possibles :

```text
YES
NO
UNKNOWN
MULTI_DAY
```

Les identifiants :

```text
H00000001
H00000002
...
```

sont des identifiants séquentiels de calcul.

Ils ne sont pas considérés comme des identités métier durables.

---

## 9. Pipeline historique

### `calculate_halt_metrics.py`

Version fonctionnelle actuelle :

```text
V0.7
```

Le pipeline historique utilise désormais les composants communs V0.8.

Responsabilités :

1. lire les XML historiques;
2. parser via `nasdaq_xml.py`;
3. conserver `source_file`;
4. dédupliquer via `nasdaq_deduplication.py`;
5. construire les épisodes via `nasdaq_episodes.py`;
6. déclencher la persistance PostgreSQL V0.8;
7. produire les données CSV;
8. calculer les métriques;
9. exécuter les tests de non-régression.

Exécution de référence :

```powershell
python -m collectors.nasdaq_halts.src.calculate_halt_metrics
```

L'exécution nécessite actuellement :

- les variables d'environnement PostgreSQL;
- Psycopg;
- un accès réseau au serveur PostgreSQL;
- les privilèges applicatifs nécessaires.

Une erreur PostgreSQL provoque l'échec de l'exécution plutôt qu'un contournement silencieux.

---

## 10. Pipeline live V0.8

Le pipeline live validé est :

```text
Nasdaq RSS
    |
    v
Download
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
episodes
    |
    +----> PostgreSQL CORE
    |
    v
live_tradehalts.csv
```

Le CSV est généré après la persistance PostgreSQL.

Il n'est pas requis par PostgreSQL.

---

## 11. Persistance PostgreSQL V0.8

### `nasdaq_postgresql.py`

Ce module contient la logique PostgreSQL spécifique au Nasdaq Halt Collector.

Il réutilise la connexion générique QuantLab :

```text
shared/database/
```

Responsabilités :

- persister les événements RAW;
- persister les épisodes CORE;
- gérer la clé naturelle RAW;
- récupérer les identifiants RAW;
- enrichir les événements déjà connus;
- protéger les informations connues contre des observations incomplètes;
- préserver le premier `source_file`;
- valider `halt_close_status`;
- assurer l'idempotence;
- valider strictement la relation RAW→CORE;
- utiliser une transaction commune RAW + CORE;
- retourner des compteurs `inserted / updated / unchanged`.

### Flux

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

### Clé naturelle RAW

```text
symbol
halt_date
halt_time
reason_code
market
```

Cette clé est protégée par une contrainte UNIQUE.

---

## 12. Sémantique d'UPDATE V0.8

La V0.8 doit supporter l'évolution naturelle d'un HALT live.

Exemple :

```text
Snapshot T1
HALT connu
resumption_trade_time = NULL

Snapshot T2
même HALT
resumption_trade_time = 10:05:00
```

Le second snapshot doit enrichir la ligne existante et non créer un doublon.

### Règles générales

```text
DB NULL + incoming NULL
-> unchanged

DB NULL + incoming value
-> UPDATE

DB value + incoming NULL
-> preserve DB value

DB value A + incoming A
-> unchanged

DB value A + incoming value B
-> UPDATE avec B
```

Cette dernière règle permet de prendre en compte une correction Nasdaq non-NULL.

### Champs RAW enrichissables

Actuellement :

- `issue_name`;
- `resumption_date`;
- `resumption_quote_time`;
- `resumption_trade_time`;
- `pause_threshold_price`.

Les champs constituant l'identité naturelle ne sont pas modifiés par cette logique.

### `source_file`

Lors d'un conflit sur la clé naturelle :

```text
source_file
```

n'est pas remplacé.

Il conserve le premier snapshot ayant créé l'événement structuré.

---

## 13. Sémantique CORE V0.8

Les informations CORE peuvent être enrichies lorsque le HALT évolue.

Champs concernés notamment :

- `issue_name`;
- `market` si précédemment NULL;
- `reason_code` si précédemment NULL;
- `halt_end`;
- `duration_minutes`;
- `halt_close_status`.

Une valeur NULL entrante n'efface pas une valeur connue.

### Protection du statut

Si PostgreSQL contient un statut final :

```text
YES
NO
MULTI_DAY
```

une observation entrante :

```text
UNKNOWN
```

ne remplace pas le statut final.

Une nouvelle valeur finale non-UNKNOWN peut toutefois remplacer une ancienne valeur finale lorsqu'elle représente une correction Nasdaq.

### `collector_episode_id`

L'identifiant séquentiel du calculateur n'est pas considéré comme une identité métier stable.

Après l'insertion initiale, il n'est donc pas remplacé lors d'une mise à jour.

---

## 14. Relation RAW → CORE

Le modèle actuel impose :

```text
1 RAW event -> 1 CORE episode
```

via la contrainte UNIQUE sur :

```text
core.nasdaq_halt_episode.trade_halt_id
```

Cette relation est validée sur :

```text
744 événements historiques
744 épisodes historiques
```

et sur le snapshot live validé :

```text
35 événements
35 épisodes
```

Cependant, l'algorithme de construction des épisodes peut théoriquement fusionner plusieurs événements RAW lorsque leurs périodes se chevauchent.

`nasdaq_postgresql.py` conserve donc une validation stricte.

Un épisode doit correspondre sans ambiguïté à exactement un événement RAW.

Dans le cas contraire, le traitement échoue explicitement.

Le code ne doit pas sélectionner arbitrairement un événement RAW.

Cette relation devra être revalidée sur l'historique complet de cinq ans.

---

## 15. Transaction PostgreSQL

La persistance :

```text
RAW
+
CORE
```

est exécutée dans une transaction PostgreSQL commune.

Principe :

```text
RAW réussi
CORE réussi
    |
    v
COMMIT
```

En cas d'erreur :

```text
RAW ou CORE en erreur
    |
    v
ROLLBACK
```

Le système évite ainsi de valider silencieusement une persistance partielle.

---

## 16. Couche PROCESSED

Répertoire :

```text
data/processed/
```

Les fichiers processed ne constituent pas la couche d'intégration PostgreSQL.

Ils sont dérivés.

### Historique

```text
tradehalts.csv
halt_episodes.csv
ticker_halt_daily.csv
ticker_halt_metrics.csv
ticker_halt_reason_metrics.csv
```

### Live

```text
live_tradehalts.csv
```

Le CSV live représente le dernier lot normalisé exporté.

Il est destiné à :

- inspection;
- diagnostic;
- validation;
- export.

Il n'est pas utilisé pour alimenter PostgreSQL.

Les définitions officielles des métriques historiques appartiennent à :

```text
docs/METRICS_SPECIFICATION.md
```

---

## 17. Loader CSV transitoire

Module :

```text
src/load_postgresql.py
```

Ce module a été créé pour valider la fondation PostgreSQL à partir des CSV V0.6 connus.

Il a permis de valider :

- connexion applicative;
- permissions;
- schéma RAW;
- schéma CORE;
- transaction;
- clé naturelle;
- idempotence;
- timestamps fractionnaires.

Il demeure disponible comme outil de validation et de migration.

Il n'est pas le chemin de production.

Le chemin privilégié est :

```text
XML RAW
-> parsing Python
-> PostgreSQL RAW
-> PostgreSQL CORE
```

---

## 18. Configuration

### `config/config.json`

Contient les paramètres non sensibles nécessaires au collecteur.

Les secrets ne doivent pas y être stockés.

### PostgreSQL

Variables d'environnement :

```text
QUANTLAB_DB_HOST
QUANTLAB_DB_PORT
QUANTLAB_DB_NAME
QUANTLAB_DB_USER
QUANTLAB_DB_PASSWORD
```

Le mot de passe ne doit jamais être versionné.

### État historique

Le collecteur historique maintient notamment :

```text
last_completed_date
successful_days
failed_days
```

Cet état appartient à la couche d'acquisition.

---

## 19. Principes d'architecture

### 19.1 Provenance

```text
XML RAW original = provenance / reconstruction
PostgreSQL RAW   = représentation structurée de référence
PostgreSQL CORE  = représentation métier normalisée
CSV              = sortie dérivée / validation / export
```

### 19.2 Immutabilité RAW

Les fichiers historiques et snapshots live horodatés ne doivent pas être modifiés après acquisition.

### 19.3 Reproductibilité

Une même collection de XML, traitée avec la même version du pipeline et le même modèle, doit produire des résultats équivalents.

### 19.4 Idempotence

Une réexécution des mêmes données ne doit pas créer de doublons ni provoquer de mises à jour inutiles.

### 19.5 Enrichissement

Une nouvelle observation peut compléter ou corriger un événement existant.

### 19.6 Non-régression des données

Une observation incomplète ne doit pas supprimer une information déjà connue.

### 19.7 Fail-fast

Une ambiguïté RAW→CORE doit provoquer une erreur explicite.

### 19.8 Séparation des responsabilités

```text
Historical Collector   -> acquisition historique
Live Collector         -> acquisition live + orchestration du flux live
RAW filesystem         -> provenance XML
nasdaq_xml.py           -> parsing / normalisation
nasdaq_deduplication.py -> déduplication
nasdaq_episodes.py      -> construction des épisodes
nasdaq_postgresql.py    -> persistance Nasdaq
shared/database         -> connexion PostgreSQL générique
PostgreSQL RAW          -> événements structurés
PostgreSQL CORE         -> épisodes métier
data/processed          -> sorties dérivées
docs                    -> documentation
```

### 19.9 Traçabilité

Les modifications de logique, de modèle ou de métriques doivent être versionnées et documentées.

---

## 20. Validation historique

Jeu de référence :

```text
Fichiers XML           : 15
Événements bruts       : 744
Événements uniques     : 744
HALT Episodes          : 744
Tickers différents     : 235
Lignes quotidiennes    : 322
Jours de marché        : 10
Durées calculables     : 742
```

Statuts :

```text
YES                    : 15
NO                     : 697
UNKNOWN                : 2
MULTI_DAY              : 30
TOTAL                  : 744
```

Tests :

```text
QVCG : PASS
BCARU: PASS
```

Après passage de la persistance à V0.8 :

```text
RAW inserted           : 0
RAW updated            : 0
RAW unchanged          : 744

CORE inserted          : 0
CORE updated           : 0
CORE unchanged         : 744
```

Cette validation confirme que la V0.8 ne modifie pas la baseline historique lorsque les données sont identiques.

---

## 21. Validation contrôlée de l'évolution live

Test :

```text
tests/integration/test_nasdaq_postgresql_live_update.py
```

Le test utilise une transaction PostgreSQL puis effectue un rollback.

Scénarios validés :

### HALT ouvert

```text
RAW  inserted / updated / unchanged : 1 / 0 / 0
CORE inserted / updated / unchanged : 1 / 0 / 0
```

### Même HALT complété

```text
RAW  inserted / updated / unchanged : 0 / 1 / 0
CORE inserted / updated / unchanged : 0 / 1 / 0
```

### Réexécution identique

```text
RAW  inserted / updated / unchanged : 0 / 0 / 1
CORE inserted / updated / unchanged : 0 / 0 / 1
```

### Observation régressive

```text
RAW  inserted / updated / unchanged : 0 / 0 / 1
CORE inserted / updated / unchanged : 0 / 0 / 1
```

Le test valide notamment :

- `NULL -> valeur`;
- protection `valeur -> NULL`;
- protection `NO -> UNKNOWN`;
- conservation du premier `source_file`;
- idempotence.

Après rollback, la base a été vérifiée :

```text
RAW QLV08TEST  : 0
CORE QLV08TEST : 0
```

---

## 22. Validation live réelle

Un flux RSS Nasdaq réel a été traité par le pipeline V0.8.

Premier passage :

```text
Événements bruts       : 35
Événements uniques     : 35
HALT Episodes          : 35
Durées calculables     : 23

Clôture YES            : 2
Clôture NO             : 17
Clôture UNKNOWN        : 12
Clôture MULTI_DAY      : 4
```

Persistance :

```text
RAW inserted           : 35
RAW updated            : 0
RAW unchanged          : 0

CORE inserted          : 35
CORE updated           : 0
CORE unchanged         : 0
```

Une deuxième collecte du même flux a produit :

```text
RAW inserted           : 0
RAW updated            : 0
RAW unchanged          : 35

CORE inserted          : 0
CORE updated           : 0
CORE unchanged         : 35
```

Cette deuxième collecte valide l'idempotence live réelle.

Le snapshot a également été analysé selon la clé naturelle PostgreSQL :

```text
Events                 : 35
Natural keys           : 35
Duplicate natural keys : 0
```

---

## 23. Limites actuellement connues

Les éléments suivants doivent encore être validés avant stabilisation complète :

1. historique cinq ans non encore chargé;
2. clé de déduplication Python différente de la clé naturelle PostgreSQL;
3. relation 1 RAW → 1 CORE validée seulement sur les datasets actuels;
4. possibilité théorique de fusion de plusieurs RAW dans un épisode;
5. `collector_episode_id` séquentiel et non durable;
6. fuseau horaire Nasdaq à confirmer;
7. calendrier de marché non encore basé sur un calendrier officiel;
8. comportement multi-day à revalider sur cinq ans;
9. `source_file` ne représente actuellement que le premier snapshot structurant un RAW;
10. modèle N snapshots → 1 RAW non encore matérialisé en PostgreSQL;
11. évolution live naturelle `HALT ouvert → HALT complété` validée par test contrôlé, mais doit également être observée et confirmée sur des snapshots Nasdaq réels;
12. corrections Nasdaq de valeur connue A → valeur connue B à observer sur données réelles;
13. présence éventuelle de plusieurs observations du même HALT naturel dans un seul RSS à surveiller.

Ces limites doivent être traitées explicitement et non masquées par le pipeline.

---

## 24. Analytics

La logique analytique PostgreSQL demeure volontairement différée.

Avant de créer les objets du schéma :

```text
analytics
```

il faut valider :

- calendrier officiel des jours de marché;
- épisodes multi-jours;
- statuts de clôture;
- cardinalité RAW→CORE;
- équivalence avec les résultats Python.

Migration future réservée :

```text
database/migrations/003_create_nasdaq_halts_analytics.sql
```

La métrique :

```text
halts_per_market_day
```

ne doit pas être portée dans PostgreSQL Analytics avant modélisation correcte du dénominateur des jours de marché.

---

## 25. Documentation du composant

### `ARCHITECTURE.md`

Architecture technique et flux du composant.

### `METRICS_SPECIFICATION.md`

Définitions et règles des métriques.

### `DATA_MODEL.md`

Données, champs, relations et sémantique PostgreSQL.

### `README.md`

Point d'entrée du composant.

Documentation générale PostgreSQL :

```text
../../../docs/database.md
```

Installation :

```text
../../../docs/installation.md
```

---

## 26. Gouvernance documentaire

| Modification | Documentation |
|---|---|
| Nouvelle métrique ou changement de calcul | `METRICS_SPECIFICATION.md` |
| Nouveau script ou changement de flux | `ARCHITECTURE.md` |
| Nouvelle table, fichier, colonne ou relation | `DATA_MODEL.md` |
| Changement d'installation ou d'utilisation | `README.md` et/ou `../../../docs/installation.md` |
| Changement PostgreSQL transversal | `../../../docs/database.md` |
| Changement d'architecture plateforme | `../../../docs/architecture.md` |

La documentation doit évoluer en même temps que le code.

---

## 27. État actuel

```text
V0.8 — PIPELINE POSTGRESQL HISTORIQUE ET LIVE VALIDÉ
```

La baseline historique reste reproductible.

La V0.8 ajoute notamment :

- parser XML commun;
- support `Mkt` / `Market`;
- déduplication commune;
- construction commune des épisodes;
- snapshots live XML immuables;
- persistance live directe PostgreSQL;
- enrichissement des HALT existants;
- protection contre les observations régressives;
- compteurs `inserted / updated / unchanged`;
- test transactionnel d'évolution live;
- validation live réelle;
- idempotence historique et live.

---

## 28. Prochaines étapes

### Étape immédiate

Finaliser le checkpoint V0.8 :

- mettre à jour la documentation associée;
- versionner le test d'intégration;
- effectuer les contrôles Git;
- committer et pousser la V0.8;
- documenter le checkpoint dans GitHub Issue #8.

Après cette validation, l'intégration PostgreSQL du chemin live peut être considérée complétée pour le périmètre V0.8 actuel.

### Étape historique suivante

Construire, charger et valider l'historique Nasdaq HALT sur cinq ans.

La validation cinq ans devra notamment couvrir :

- complétude de la collecte;
- clés naturelles;
- déduplication;
- cardinalité RAW→CORE;
- épisodes fusionnés;
- provenance;
- timestamps;
- fuseaux horaires;
- multi-day;
- calendrier de marché;
- idempotence à volume complet.

La définition des métriques ne doit pas être modifiée silencieusement pendant cette validation.
