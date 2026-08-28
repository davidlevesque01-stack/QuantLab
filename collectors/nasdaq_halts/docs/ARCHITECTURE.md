# QuantLab — Nasdaq Halt Collector

## ARCHITECTURE.md

**Version : V0.8**
**Statut : Architecture de référence du collecteur Nasdaq Halts**
**Dernière mise à jour : 2026-08-29**

---

## 1. Objectif

Ce document décrit l'architecture spécifique du composant Nasdaq Halts de QuantLab.

L'architecture générale de la plateforme est documentée dans :

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
- les tests de non-régression et d'intégration.

La version d'intégration globale actuelle est :

```text
V0.8
```

La version actuelle du collecteur historique est :

```text
V0.4
```

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
|   |       +-- live/
|   |       |   +-- tradehalts_live_YYYYMMDDTHHMMSSZ.xml
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
+-- logs/
|   +-- historical_progress_STARTDATE_ENDDATE.json
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

Les répertoires de données RAW, processed et logs sont locaux et exclus de Git.

---

## 3. Architecture logique

### 3.1 Historique

```text
                  NASDAQ TRADER
                       |
                       | RSS XML historique
                       v
              +-------------------+
              | Historical        |
              | Collector V0.4    |
              +---------+---------+
                        |
              +---------+---------+
              |                   |
              v                   v
       RAW XML historique     Checkpoint
       immutable              par plage
              |
              v
        nasdaq_xml.py
              |
              v
   nasdaq_deduplication.py
              |
              v
         unique_events
          /          \
         v            v
 PostgreSQL RAW    CSV tradehalts
         |
         v
  nasdaq_episodes.py
         |
         v
       episodes
      /        \
     v          v
PostgreSQL    CSV
   CORE       halt_episodes
                |
                v
         Daily / Metrics
                |
       +--------+--------+
       |        |        |
       v        v        v
     daily    ticker   reason
      CSV     metrics   metrics
```

### 3.2 Live

```text
Nasdaq RSS
    |
    v
Live Collector V0.8
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

Le chemin PostgreSQL ne dépend pas des CSV processed.

Les CSV sont conservés comme sorties secondaires pour :

- validation;
- diagnostic;
- non-régression;
- comparaison;
- export;
- inspection manuelle.

---

## 4. Couche de collecte historique V0.4

Module :

```text
src/nasdaq_historical_collector.py
```

Version :

```text
V0.4
```

Le collecteur historique est exclusivement responsable de l'acquisition des XML RAW.

Il ne persiste pas directement les événements dans PostgreSQL.

Responsabilités :

- recevoir une plage de dates explicite;
- interroger la source historique Nasdaq;
- télécharger les données journée par journée;
- sauvegarder un fichier XML par date;
- détecter les fichiers RAW déjà présents;
- éviter les téléchargements inutiles;
- valider syntaxiquement le XML reçu;
- écrire les XML de façon atomique;
- gérer les tentatives de reprise réseau;
- arrêter la collecte sur une date en échec;
- maintenir un checkpoint spécifique à la plage;
- écrire le checkpoint de façon atomique;
- reprendre une collecte interrompue;
- protéger contre une date de fin future.

### 4.1 Interface de commande

Exécution :

```powershell
python -m collectors.nasdaq_halts.src.nasdaq_historical_collector `
  --start-date YYYY-MM-DD `
  --end-date YYYY-MM-DD
```

Paramètres obligatoires :

```text
--start-date
--end-date
```

Paramètres optionnels :

```text
--delay-seconds
--max-retries
--retry-delay-seconds
```

Valeurs par défaut actuelles :

```text
delay-seconds       : 5
max-retries         : 3
retry-delay-seconds : 10
```

### 4.2 Format RAW historique

```text
tradehalts_YYYY-MM-DD.xml
```

Exemple :

```text
tradehalts_2026-08-17.xml
```

Répertoire :

```text
data/raw/nasdaq/historical/
```

### 4.3 Validation XML

Un nouveau téléchargement doit :

1. contenir des données;
2. être un document XML bien formé;
3. passer la validation XML avant d'être accepté comme RAW.

Un RSS Nasdaq bien formé contenant zéro HALT est valide.

Le nombre d'événements n'est donc pas utilisé comme critère de succès de l'acquisition.

Cette distinction permet de traiter correctement :

- fins de semaine;
- jours sans HALT;
- autres dates où Nasdaq retourne un RSS valide sans événement.

### 4.4 Écriture atomique

Un nouveau XML est d'abord écrit dans un fichier temporaire :

```text
*.xml.tmp
```

puis remplacé vers son nom définitif uniquement après validation.

Le checkpoint utilise le même principe :

```text
*.json.tmp
```

puis remplacement atomique.

Le système évite ainsi de considérer une écriture partielle comme un artefact complété.

### 4.5 Fichiers existants

Lorsqu'un fichier historique existe déjà pour une date :

- aucune nouvelle requête Nasdaq n'est effectuée pour cette date;
- le fichier n'est pas remplacé;
- la date est comptabilisée comme existante;
- le checkpoint peut avancer.

Le fichier existant est actuellement considéré comme un RAW déjà acquis.

Son intégrité complète sera vérifiée indépendamment lors de la validation cinq ans.

---

## 5. Checkpoint historique V0.4

Chaque plage de collecte possède son propre checkpoint.

Format :

```text
logs/historical_progress_STARTDATE_ENDDATE.json
```

Exemple :

```text
historical_progress_2026-08-03_2026-08-05.json
```

Cette stratégie évite qu'un ancien checkpoint associé à une autre plage provoque un saut incorrect de dates.

### 5.1 Structure

Le checkpoint contient :

```text
version
start_date
end_date
last_completed_date
successful_days
existing_days
failed_days
failed_dates
```

Exemple conceptuel :

```json
{
    "version": "0.4",
    "start_date": "2026-08-03",
    "end_date": "2026-08-05",
    "last_completed_date": "2026-08-05",
    "successful_days": 0,
    "existing_days": 3,
    "failed_days": 0,
    "failed_dates": []
}
```

### 5.2 Sémantique

`successful_days` :

```text
nombre de nouvelles dates téléchargées avec succès
```

`existing_days` :

```text
nombre de dates dont le RAW existait déjà lorsque la plage a été parcourue
```

`failed_days` :

```text
compteur cumulatif des échecs de collecte
```

`failed_dates` :

```text
liste des dates actuellement considérées en échec
```

Lorsqu'une date précédemment en échec réussit ultérieurement, elle est retirée de `failed_dates`.

Le compteur `failed_days` demeure cumulatif.

### 5.3 Reprise

Si :

```text
last_completed_date = 2026-08-17
```

la prochaine date est :

```text
2026-08-18
```

Si cette prochaine date dépasse `end_date`, le collecteur termine avec :

```text
COLLECTE DÉJÀ COMPLÈTE
```

et aucune nouvelle requête Nasdaq n'est effectuée.

### 5.4 Gestion des échecs

Une date en échec :

- est enregistrée dans le checkpoint;
- incrémente le compteur cumulatif;
- interrompt le traitement de la plage;
- n'est pas dépassée silencieusement.

Le système évite ainsi de créer artificiellement une plage déclarée complète contenant un trou connu.

---

## 6. Stratégie de retry historique

Pour chaque date nécessitant un téléchargement, le collecteur peut effectuer plusieurs tentatives.

Valeur par défaut :

```text
3 tentatives
```

Le délai de retry est progressif.

Avec :

```text
retry-delay-seconds = 10
```

les délais après échec sont notamment :

```text
tentative 1 -> 10 secondes
tentative 2 -> 20 secondes
```

Après la dernière tentative infructueuse, la date est déclarée en échec.

Le collecteur ne poursuit pas automatiquement vers la date suivante.

---

## 7. Couche RAW — provenance

### 7.1 Historique

Répertoire :

```text
data/raw/nasdaq/historical/
```

Les XML historiques constituent les artefacts RAW originaux permettant la reconstruction des données structurées.

### 7.2 Live

Répertoire :

```text
data/raw/nasdaq/live/
```

Chaque collecte live crée un snapshot immuable :

```text
tradehalts_live_YYYYMMDDTHHMMSSZ.xml
```

Le collecteur maintient également :

```text
data/raw/nasdaq/latest_tradehalts.xml
```

Ce fichier est une copie pratique du dernier flux reçu.

Il n'est pas le fichier de provenance immuable.

### 7.3 Règles RAW

1. ne pas modifier manuellement les XML;
2. ne pas remplacer un fichier historique valide sans raison documentée;
3. conserver les snapshots live horodatés;
4. conserver les données RAW après traitement;
5. considérer PostgreSQL comme la représentation structurée de référence;
6. considérer les données structurées comme reconstruisibles à partir des XML;
7. considérer les CSV comme des données dérivées.

### 7.4 Provenance PostgreSQL

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
tradehalts_2026-08-17.xml
```

Pour un événement live :

```text
tradehalts_live_20260828T205115Z.xml
```

Dans la V0.8, `source_file` conserve le premier snapshot ayant créé l'événement RAW.

Une observation ultérieure du même événement peut enrichir les données PostgreSQL sans remplacer ce `source_file`.

Les snapshots XML immuables demeurent la provenance primaire.

Un futur modèle de provenance pourra représenter explicitement :

```text
N snapshots -> 1 RAW event
```

PostgreSQL ne contient pas actuellement le contenu XML complet.

---

## 8. Parser XML commun

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

Les timestamps fractionnaires sont préservés.

---

## 9. Déduplication commune

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

Baseline historique initiale :

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

La collecte historique du 17 août 2026 a montré que le RSS historique peut contenir une représentation consolidée d'un HALT là où l'affichage Web Nasdaq présente plusieurs états.

La validation observée ne justifie pas de fusionner des événements ayant des `reason_code` différents.

La clé naturelle PostgreSQL continue donc d'inclure :

```text
reason_code
```

Cette hypothèse devra être revalidée statistiquement sur les cinq ans.

---

## 10. Construction commune des épisodes

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

## 11. Pipeline historique de traitement

### `calculate_halt_metrics.py`

Version fonctionnelle actuelle :

```text
V0.7
```

Le pipeline historique utilise les composants communs V0.8.

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

Exécution :

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

## 12. Pipeline live V0.8

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

## 13. Persistance PostgreSQL V0.8

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

## 14. Sémantique d'UPDATE V0.8

La V0.8 supporte l'évolution naturelle d'un HALT live.

Exemple :

```text
Snapshot T1
HALT connu
resumption_trade_time = NULL

Snapshot T2
même HALT
resumption_trade_time = 10:05:00
```

Le second snapshot enrichit la ligne existante au lieu de créer un doublon.

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

## 15. Sémantique CORE V0.8

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

## 16. Relation RAW → CORE

Le modèle actuel impose :

```text
1 RAW event -> 1 CORE episode
```

via la contrainte UNIQUE sur :

```text
core.nasdaq_halt_episode.trade_halt_id
```

Cette relation a été validée sur :

```text
744 événements historiques
744 épisodes historiques
```

et sur le snapshot live de référence :

```text
35 événements
35 épisodes
```

Cependant, l'algorithme de construction des épisodes peut théoriquement fusionner plusieurs événements RAW lorsque leurs périodes se chevauchent.

`nasdaq_postgresql.py` conserve donc une validation stricte.

Un épisode doit correspondre sans ambiguïté à exactement un événement RAW.

Dans le cas contraire, le traitement échoue explicitement.

Cette relation devra être revalidée sur l'historique complet de cinq ans.

---

## 17. Transaction PostgreSQL

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

## 18. Couche PROCESSED

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

Le CSV live est destiné à :

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

## 19. Loader CSV transitoire

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

## 20. Configuration

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

### Acquisition historique

Les dates de collecte ne sont plus codées en dur.

Elles sont fournies explicitement par :

```text
--start-date
--end-date
```

Le délai entre dates et la stratégie de retry peuvent également être contrôlés par la ligne de commande.

---

## 21. Principes d'architecture

### 21.1 Provenance

```text
XML RAW original = provenance / reconstruction
PostgreSQL RAW   = représentation structurée de référence
PostgreSQL CORE  = représentation métier normalisée
CSV              = sortie dérivée / validation / export
```

### 21.2 Immutabilité RAW

Les fichiers historiques et snapshots live horodatés ne doivent pas être modifiés après acquisition.

### 21.3 Reproductibilité

Une même collection de XML, traitée avec la même version du pipeline et le même modèle, doit produire des résultats équivalents.

### 21.4 Idempotence

Une réexécution des mêmes données ne doit pas créer de doublons ni provoquer de mises à jour inutiles.

### 21.5 Reprise

Une collecte historique interrompue doit pouvoir reprendre à partir de son checkpoint sans recommencer la plage complète.

### 21.6 Enrichissement

Une nouvelle observation peut compléter ou corriger un événement structuré existant.

### 21.7 Non-régression des données

Une observation incomplète ne doit pas supprimer une information déjà connue.

### 21.8 Fail-fast

Une ambiguïté RAW→CORE ou une date historique dont l'acquisition échoue doit provoquer un état explicite plutôt qu'être masquée.

### 21.9 Séparation des responsabilités

```text
Historical Collector   -> acquisition historique / checkpoint
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

### 21.10 Traçabilité

Les modifications de logique, de modèle ou de métriques doivent être versionnées et documentées.

---

## 22. Validation historique de référence

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

## 23. Validation du collecteur historique V0.4

La V0.4 a été testée avant le lancement de la collecte cinq ans.

### 23.1 Plage contenant des RAW existants

Plage :

```text
2026-08-03 -> 2026-08-05
```

Résultat :

```text
Nouveaux téléchargements : 0
Fichiers déjà présents   : 3
Échecs                    : 0
Dernière date             : 2026-08-05
```

Le checkpoint spécifique à la plage a été créé correctement.

### 23.2 Date sans HALT

Date testée :

```text
2026-08-16
```

Le RSS reçu était un XML valide.

Taille observée :

```text
448 octets
```

Le parser commun a produit :

```text
Événements : 0
```

Le cas RSS valide sans HALT est donc accepté correctement.

### 23.3 Date historique avec données

Date testée :

```text
2026-08-17
```

Le téléchargement a réussi à la première tentative.

Taille observée :

```text
102547 octets
```

Le parser commun a produit :

```text
Événements : 67
Premier symbole : EYPT
```

Une inspection ciblée a confirmé la présence de timestamps fractionnaires et d'informations de reprise complétées dans le RSS historique.

### 23.4 Consolidation historique observée

Pour un HALT `EJH` observé le 17 août 2026, le XML historique contenait directement :

```text
ReasonCode          : LUDP
HaltTime            : 15:34:38.020
ResumptionDate      : 08/17/2026
ResumptionQuoteTime : 15:34:38
ResumptionTradeTime : 15:39:38
```

L'affichage Web Nasdaq pouvait présenter plusieurs états du même HALT.

Le RSS historique testé contenait l'information consolidée finale pour cet exemple.

Cette observation doit être considérée comme une caractéristique constatée sur le cas testé, et non comme une garantie universelle avant validation des cinq ans.

Les `reason_code` distincts demeurent des événements distincts selon la clé naturelle PostgreSQL.

### 23.5 Reprise/idempotence

Une seconde exécution de la plage :

```text
2026-08-17 -> 2026-08-17
```

a produit :

```text
COLLECTE DÉJÀ COMPLÈTE
Aucune nouvelle requête effectuée.
```

Le comportement de reprise par checkpoint est donc validé sur le cas contrôlé.

---

## 24. Validation contrôlée de l'évolution live

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

Après rollback :

```text
RAW QLV08TEST  : 0
CORE QLV08TEST : 0
```

---

## 25. Validation live réelle

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

## 26. Limites actuellement connues

Les éléments suivants doivent encore être validés avant stabilisation complète :

1. historique cinq ans non encore chargé;
2. complétude et intégrité de tous les XML historiques à valider;
3. les fichiers RAW déjà présents sont actuellement considérés comme valides par le collecteur sans revalidation;
4. clé de déduplication Python différente de la clé naturelle PostgreSQL;
5. relation 1 RAW → 1 CORE validée seulement sur les datasets actuels;
6. possibilité théorique de fusion de plusieurs RAW dans un épisode;
7. `collector_episode_id` séquentiel et non durable;
8. fuseau horaire Nasdaq à confirmer;
9. calendrier de marché non encore basé sur un calendrier officiel;
10. comportement multi-day à revalider sur cinq ans;
11. `source_file` ne représente actuellement que le premier snapshot structurant un RAW;
12. modèle N snapshots → 1 RAW non encore matérialisé en PostgreSQL;
13. évolution live naturelle `HALT ouvert → HALT complété` à continuer d'observer sur des snapshots Nasdaq réels;
14. corrections Nasdaq de valeur connue A → valeur connue B à observer sur données réelles;
15. présence éventuelle de plusieurs observations du même HALT naturel dans un seul RSS à surveiller;
16. comportement de collecte cinq ans à valider à volume complet;
17. la politique exacte de période cinq ans doit être définie avant le lancement définitif.

Ces limites doivent être traitées explicitement et non masquées par le pipeline.

---

## 27. Analytics

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

## 28. Documentation du composant

### `ARCHITECTURE.md`

Architecture technique et flux du composant.

### `METRICS_SPECIFICATION.md`

Définitions et règles des métriques.

### `DATA_MODEL.md`

Données, champs, relations et sémantique PostgreSQL.

### `README.md`

Point d'entrée du composant et procédures d'exécution.

Documentation générale PostgreSQL :

```text
../../../docs/database.md
```

Installation :

```text
../../../docs/installation.md
```

---

## 29. Gouvernance documentaire

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

## 30. État actuel

```text
V0.8 — PIPELINE POSTGRESQL HISTORIQUE ET LIVE VALIDÉ
V0.4 — COLLECTEUR HISTORIQUE ROBUSTE VALIDÉ POUR LE BACKFILL
```

La baseline historique reste reproductible.

La V0.8 fournit notamment :

- parser XML commun;
- support `Mkt` / `Market`;
- déduplication commune;
- construction commune des épisodes;
- snapshots live XML immuables;
- persistance directe PostgreSQL;
- enrichissement des HALT existants;
- protection contre les observations régressives;
- compteurs `inserted / updated / unchanged`;
- test transactionnel d'évolution live;
- validation live réelle;
- idempotence historique et live.

La V0.4 du collecteur historique fournit :

- plages de dates explicites;
- checkpoints spécifiques à chaque plage;
- reprise automatique;
- détection des RAW existants;
- retry réseau;
- validation XML;
- écriture atomique XML;
- écriture atomique checkpoint;
- suivi des échecs;
- arrêt fail-fast sur une date non acquise;
- protection contre les dates futures.

---

## 30. V0.9-B — Optimisation de performance PostgreSQL

La V0.9-B optimise la persistance PostgreSQL introduite en V0.8, sans modifier sa sémantique fonctionnelle.

Les principes fonctionnels sont inchangés :

- idempotence;
- clé naturelle RAW;
- relation RAW → CORE;
- conservation des valeurs existantes;
- protection contre les valeurs NULL régressives;
- compteurs inserted / updated / unchanged;
- transaction PostgreSQL commune.

La V0.9-B remplace les opérations CORE individuelles par des opérations batch afin de réduire fortement le nombre d'allers-retours entre Python et PostgreSQL.

### Performance observée

Sur le dataset de validation de 1 065 événements :

- V0.8 : environ 55 secondes;
- optimisation RAW batch : environ 28,5 secondes;
- V0.9-B : environ 1,36 seconde;
- gain V0.9-B vs V0.8 : environ 20,9x.

### Validation

La validation fonctionnelle V0.9-B a produit les mêmes résultats que la version précédente :

- RAW : 0 inserted / 0 updated / 1 065 unchanged;
- CORE : 0 inserted / 0 updated / 1 065 unchanged;
- QVCG : PASS;
- BCARU : PASS;
- événements bruts : 1 065;
- épisodes HALT : 1 065;
- durées calculables : 1 063.

La V0.9-B est donc une optimisation interne de performance et ne modifie pas la définition métier des données.

---

## 31. Prochaines étapes

### Étape immédiate

Créer le checkpoint Git de la V0.4 du collecteur historique et de sa documentation.

### Étape suivante — historique cinq ans

Définir précisément la plage historique cinq ans, puis lancer la collecte contrôlée.

La validation cinq ans devra couvrir au minimum :

- complétude des dates;
- intégrité XML;
- parseabilité de tous les fichiers;
- distribution des événements par date;
- clés naturelles;
- déduplication;
- cardinalité RAW→CORE;
- épisodes fusionnés;
- provenance;
- timestamps;
- fuseaux horaires;
- multi-day;
- calendrier de marché;
- idempotence à volume complet;
- comparaison des résultats Python et PostgreSQL.

La définition des métriques ne doit pas être modifiée silencieusement pendant cette validation.
