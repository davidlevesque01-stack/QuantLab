# QuantLab — Nasdaq Halt Collector

## ARCHITECTURE.md

**Version : V0.7**
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

- la collecte des données Nasdaq Trading Halts;
- la conservation des fichiers XML RAW;
- le parsing et la normalisation;
- la déduplication;
- la construction des épisodes HALT;
- la persistance PostgreSQL RAW et CORE;
- la production de datasets CSV de validation;
- le calcul des métriques;
- les tests de non-régression.

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
|   |       +-- latest_tradehalts.xml
|   |
|   +-- processed/
|       +-- tradehalts.csv
|       +-- halt_episodes.csv
|       +-- ticker_halt_daily.csv
|       +-- ticker_halt_metrics.csv
|       +-- ticker_halt_reason_metrics.csv
|
+-- docs/
|   +-- ARCHITECTURE.md
|   +-- DATA_MODEL.md
|   +-- METRICS_SPECIFICATION.md
|
+-- src/
    +-- calculate_halt_metrics.py
    +-- load_postgresql.py
    +-- nasdaq_halt_collector.py
    +-- nasdaq_historical_collector.py
    +-- nasdaq_historical_test.py
    +-- nasdaq_postgresql.py
```

Les répertoires de données RAW, processed et logs sont locaux et exclus de Git.

---

## 3. Architecture logique V0.7

Le flux actuellement validé pour le traitement historique est :

```text
                  NASDAQ TRADER
                       |
                       | XML
                       v
              +-------------------+
              |     COLLECTE      |
              | historical        |
              | collector         |
              +---------+---------+
                        |
                        v
              data/raw/nasdaq/
                 historical/
                        |
                        | XML RAW
                        | provenance
                        v
              +-------------------+
              | PARSING /         |
              | NORMALISATION     |
              | DEDUPLICATION     |
              +---------+---------+
                        |
                        v
                  unique_events
                   /          \
                  /            \
                 v              v
       PostgreSQL RAW      CSV tradehalts
                 |
                 v
        Construction des
        HALT Episodes
                 |
                 v
             episodes
            /        \
           /          \
          v            v
 PostgreSQL CORE   CSV halt_episodes
                       |
                       v
              Daily / Metrics
                       |
          +------------+-------------+
          |            |             |
          v            v             v
       daily        ticker        reason
       CSV          metrics       metrics
```

Le chemin PostgreSQL ne dépend pas des CSV processed.

Les CSV sont conservés comme sorties secondaires pour :

- validation;
- diagnostic;
- non-régression;
- comparaison;
- export;
- inspection manuelle.

---

## 4. Couche de collecte

### `nasdaq_historical_collector.py`

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

Les fichiers historiques sont destinés à être conservés afin de permettre la reconstruction des données structurées.

### `nasdaq_halt_collector.py`

Ce script constitue le chemin de collecte courante/live existant.

Il doit encore être revu dans le cadre de l'intégration PostgreSQL complète du collecteur.

En particulier, les points suivants doivent être validés avant de considérer ce chemin comme production-ready :

- format exact des champs XML courants;
- cohérence de `Market` versus `Mkt`;
- stratégie de nommage et conservation des snapshots courants;
- intégration avec la persistance PostgreSQL V0.7;
- provenance des fichiers courants;
- idempotence lors de collectes répétées.

La validation actuelle V0.7 concerne principalement le traitement des XML historiques.

---

## 5. Couche RAW — provenance

Répertoire historique principal :

```text
data/raw/nasdaq/historical/
```

Les XML téléchargés depuis Nasdaq constituent les fichiers RAW originaux de provenance.

Règles :

1. ne pas modifier manuellement les XML;
2. ne pas remplacer un fichier historique valide sans raison documentée;
3. conserver les données historiques après traitement;
4. considérer les données structurées PostgreSQL comme reconstruisibles à partir des XML;
5. considérer les CSV comme des données dérivées et reconstruisibles.

Cette approche permet de modifier ultérieurement le modèle ou les métriques sans devoir recollecter les données Nasdaq lorsque les XML originaux sont disponibles.

### Provenance PostgreSQL

Lors du parsing V0.7, chaque événement reçoit :

```text
source_file
```

correspondant au nom du fichier XML d'origine.

Cette valeur est persistée dans :

```text
raw.nasdaq_trade_halt.source_file
```

Exemple :

```text
tradehalts_2026-08-03.xml
```

PostgreSQL ne contient pas actuellement le contenu XML complet.

Le fichier XML original demeure dans la couche RAW du filesystem.

---

## 6. Couche de transformation

### `calculate_halt_metrics.py`

Version de référence actuelle :

```text
V0.7
```

Responsabilités :

1. lire les XML historiques;
2. normaliser les champs Nasdaq;
3. conserver `source_file`;
4. dédupliquer les événements;
5. construire les HALT Episodes;
6. calculer les durées;
7. traiter les épisodes multi-day;
8. déterminer les HALT actifs à la clôture;
9. déclencher la persistance PostgreSQL RAW et CORE;
10. produire les données CSV quotidiennes;
11. calculer les métriques par ticker;
12. calculer les métriques par raison;
13. exécuter les tests de non-régression.

Le script importe la persistance PostgreSQL depuis :

```text
collectors/nasdaq_halts/src/nasdaq_postgresql.py
```

### Exécution de référence

Depuis la racine du monorepo :

```powershell
python -m collectors.nasdaq_halts.src.calculate_halt_metrics
```

L'exécution directe du fichier Python par son chemin n'est pas l'invocation de référence.

### Dépendance PostgreSQL actuelle

Dans V0.7, la persistance PostgreSQL est appelée directement par le pipeline.

L'exécution nécessite donc actuellement :

- les variables d'environnement PostgreSQL;
- Psycopg;
- un accès réseau au serveur PostgreSQL;
- les privilèges applicatifs nécessaires.

Une erreur PostgreSQL provoque l'échec de l'exécution plutôt qu'un contournement silencieux de la persistance.

Si un mode de calcul explicitement offline ou sans base de données devient nécessaire, il devra être conçu comme un mode d'exécution distinct et documenté.

---

## 7. Persistance PostgreSQL V0.7

### `nasdaq_postgresql.py`

Ce module contient la logique PostgreSQL spécifique au Nasdaq Halt Collector.

Il réutilise la connexion générique QuantLab définie sous :

```text
shared/database/
```

Responsabilités :

- persister les événements RAW;
- persister les épisodes CORE;
- gérer la clé naturelle RAW;
- récupérer les identifiants des RAW existants;
- préserver `source_file`;
- valider `halt_close_status`;
- assurer l'idempotence;
- valider la relation RAW→CORE;
- utiliser une transaction PostgreSQL commune.

### Flux de persistance

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

La clé naturelle PostgreSQL actuelle est :

```text
symbol
halt_date
halt_time
reason_code
market
```

Elle est protégée par une contrainte UNIQUE.

Le writer utilise cette clé pour distinguer :

- un nouvel événement;
- un événement déjà présent.

### Idempotence

Une réexécution du même dataset ne doit pas créer de doublons.

Comportement V0.7 validé :

```text
Première persistance

RAW inserted   : 744
RAW existing   : 0
CORE inserted  : 744
CORE existing  : 0
```

Puis :

```text
Réexécution

RAW inserted   : 0
RAW existing   : 744
CORE inserted  : 0
CORE existing  : 744
```

---

## 8. Relation RAW → CORE

Le modèle PostgreSQL actuel impose :

```text
1 RAW event -> 1 CORE episode
```

par la contrainte UNIQUE appliquée à :

```text
core.nasdaq_halt_episode.trade_halt_id
```

Cette relation est valide sur le dataset V0.7 actuel de 744 événements.

Cependant, l'algorithme Python de construction des épisodes peut théoriquement fusionner plusieurs événements RAW lorsque leurs périodes se chevauchent.

Pour éviter une association incorrecte, `nasdaq_postgresql.py` applique une validation stricte.

Un épisode doit correspondre sans ambiguïté à exactement un événement RAW sous le modèle actuel.

Dans le cas contraire, le traitement échoue explicitement.

Le code ne doit pas sélectionner arbitrairement un événement RAW.

La relation 1:1 devra être revalidée sur l'historique complet de cinq ans.

---

## 9. Déduplication

La déduplication Python V0.7 utilise actuellement une clé logique qui n'est pas identique à la clé naturelle PostgreSQL.

La clé PostgreSQL est :

```text
symbol
halt_date
halt_time
reason_code
market
```

Le dataset de validation actuel contient :

```text
744 événements bruts
744 événements uniques
0 collision de clé naturelle PostgreSQL
```

Aucune divergence n'est observée sur le baseline actuel.

Cette équivalence doit toutefois être testée sur l'historique complet avant stabilisation définitive du modèle.

---

## 10. Couche PROCESSED

Répertoire :

```text
data/processed/
```

Les fichiers processed ne constituent plus la couche d'intégration PostgreSQL.

Ils demeurent des datasets dérivés utiles pour la validation et l'analyse.

### `tradehalts.csv`

Événements Nasdaq nettoyés et dédupliqués.

### `halt_episodes.csv`

Épisodes HALT logiques avec notamment :

- début;
- fin;
- durée;
- raison;
- statut de clôture.

### `ticker_halt_daily.csv`

Une ligne par ticker et par journée où au moins un HALT est présent selon la logique actuelle.

### `ticker_halt_metrics.csv`

Métriques consolidées par ticker.

Exemples :

- nombre total d'épisodes;
- nombre de jours HALT;
- HALT par jour avec HALT;
- HALT par jour de marché;
- jours HALT à la clôture;
- durée moyenne;
- durée médiane.

### `ticker_halt_reason_metrics.csv`

Métriques regroupées par :

```text
symbol + reason_code
```

Les définitions officielles des métriques appartiennent à :

```text
docs/METRICS_SPECIFICATION.md
```

---

## 11. Loader CSV transitoire

Le module :

```text
src/load_postgresql.py
```

a été créé pour valider la fondation PostgreSQL à partir des fichiers CSV V0.6 connus.

Il a permis de valider notamment :

- la connexion applicative;
- les permissions;
- le schéma RAW;
- le schéma CORE;
- la transaction;
- la clé naturelle;
- l'idempotence;
- les timestamps fractionnaires.

Il demeure disponible comme outil de validation et de migration.

Il ne constitue pas le chemin PostgreSQL V0.7 privilégié.

Le chemin privilégié est :

```text
XML RAW
-> parsing Python
-> PostgreSQL RAW
-> PostgreSQL CORE
```

---

## 12. Configuration

La configuration doit être séparée du code autant que possible.

### `config/config.json`

Contient les paramètres non sensibles nécessaires au collecteur.

Les secrets ne doivent pas y être stockés.

### Configuration PostgreSQL

La connexion PostgreSQL est fournie par les variables d'environnement QuantLab :

```text
QUANTLAB_DB_HOST
QUANTLAB_DB_PORT
QUANTLAB_DB_NAME
QUANTLAB_DB_USER
QUANTLAB_DB_PASSWORD
```

Le mot de passe ne doit jamais être versionné.

### État de collecte historique

Le collecteur historique utilise un mécanisme de progression permettant de suivre notamment :

```text
last_completed_date
successful_days
failed_days
```

La gestion de cet état appartient à la couche d'acquisition historique et non au modèle PostgreSQL analytique.

---

## 13. Principes d'architecture

### 13.1 Provenance

```text
XML RAW original = provenance / reconstruction
PostgreSQL RAW   = représentation structurée de référence
PostgreSQL CORE  = représentation métier normalisée
CSV              = sortie dérivée / validation / export
```

### 13.2 Reproductibilité

Une même collection de XML, traitée avec la même version du pipeline et le même modèle de données, doit produire des résultats équivalents.

### 13.3 Idempotence

Une réexécution des mêmes données ne doit pas créer de doublons PostgreSQL.

### 13.4 Fail-fast

Une ambiguïté de modèle ou de relation RAW→CORE doit provoquer une erreur explicite plutôt qu'une association arbitraire.

### 13.5 Séparation des responsabilités

```text
Collecte              -> acquisition des XML
RAW filesystem        -> fichiers originaux
Transformation        -> parsing / normalisation / épisodes
nasdaq_postgresql.py  -> persistance Nasdaq spécifique
shared/database       -> connexion PostgreSQL générique
PostgreSQL RAW        -> événements structurés
PostgreSQL CORE       -> épisodes métier
data/processed        -> validation / exports dérivés
docs                  -> documentation
```

### 13.6 Traçabilité

Les modifications de logique, de modèle ou de métriques doivent être versionnées et documentées.

---

## 14. Validation V0.7

Jeu de validation actuel :

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

Statuts de clôture :

```text
YES                    : 15
NO                     : 697
UNKNOWN                : 2
MULTI_DAY              : 30
TOTAL                  : 744
```

### QVCG

```text
2 épisodes
2 jours HALT
2 jours HALT à la clôture
TEST PASS
```

### BCARU

```text
12 épisodes
5 jours HALT
1 jour HALT à la clôture
TEST PASS
```

### PostgreSQL

Chargement direct validé :

```text
RAW inserted           : 744
RAW existing           : 0
CORE inserted          : 744
CORE existing          : 0
```

Réexécution :

```text
RAW inserted           : 0
RAW existing           : 744
CORE inserted          : 0
CORE existing          : 744
```

Les timestamps fractionnaires sont préservés.

La provenance XML `source_file` est également validée sur les 744 lignes RAW.

---

## 15. Limites actuellement connues

Les éléments suivants doivent être validés ou améliorés avant stabilisation complète :

1. historique cinq ans non encore chargé;
2. clé de déduplication Python différente de la clé naturelle PostgreSQL;
3. relation 1 RAW → 1 CORE validée uniquement sur le baseline actuel;
4. possibilité théorique de fusion de plusieurs RAW dans un épisode Python;
5. `collector_episode_id` séquentiel et non garanti comme identité durable;
6. fuseau horaire Nasdaq à confirmer;
7. calendrier de marché actuel non encore basé sur un calendrier officiel;
8. comportement multi-day à revalider sur l'historique complet;
9. provenance à revoir si un même événement naturel apparaît dans plusieurs XML;
10. chemin live/current du collecteur non encore intégré complètement à PostgreSQL.

Ces limites doivent être traitées explicitement et non masquées par le pipeline.

---

## 16. Analytics

La logique analytique PostgreSQL est volontairement différée.

Avant de créer les objets du schéma :

```text
analytics
```

il faut valider :

- le calendrier officiel des jours de marché;
- les épisodes multi-jours;
- les statuts de clôture;
- la cardinalité RAW→CORE;
- l'équivalence avec les résultats Python V0.7.

La future migration est réservée sous :

```text
database/migrations/003_create_nasdaq_halts_analytics.sql
```

La métrique :

```text
halts_per_market_day
```

ne doit pas être portée dans la couche analytique PostgreSQL avant modélisation correcte du dénominateur de jours de marché.

---

## 17. Documentation du composant

### `ARCHITECTURE.md`

Décrit comment le composant Nasdaq Halts est construit.

### `METRICS_SPECIFICATION.md`

Décrit les métriques et leurs règles de calcul.

### `DATA_MODEL.md`

Décrit les données, champs et relations.

### `README.md`

Sert de point d'entrée pour le composant.

La documentation générale PostgreSQL se trouve dans :

```text
../../../docs/database.md
```

La procédure générale d'installation se trouve dans :

```text
../../../docs/installation.md
```

---

## 18. Gouvernance documentaire

Lorsqu'une modification est apportée au composant :

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

## 19. État actuel

```text
V0.7 — PERSISTANCE POSTGRESQL HISTORIQUE VALIDÉE
```

La baseline fonctionnelle V0.6 a été préservée lors du passage à V0.7.

La V0.7 ajoute notamment :

- provenance `source_file`;
- writer PostgreSQL spécifique au Nasdaq;
- persistance directe RAW;
- persistance directe CORE;
- idempotence PostgreSQL;
- validation stricte RAW→CORE;
- conservation des résultats de non-régression existants.

La validation actuelle couvre le traitement des XML historiques du dataset de référence.

Elle ne constitue pas encore la validation complète du chemin live/current.

---

## 20. Prochaines étapes

### Étape immédiate

Revoir le chemin :

```text
nasdaq_halt_collector.py
```

afin de l'aligner avec l'architecture PostgreSQL V0.7.

Cette revue doit notamment déterminer :

- le schéma XML courant réel;
- la stratégie de snapshots RAW;
- l'utilisation de `nasdaq_postgresql.py`;
- l'idempotence;
- la provenance;
- la gestion des erreurs.

### Étape historique suivante

Après validation suffisante du chemin PostgreSQL :

> Construire, charger et valider l'historique Nasdaq HALT sur cinq ans.

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
