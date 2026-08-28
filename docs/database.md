# QuantLab — Base de données

## 1. Objectif

La base de données PostgreSQL constitue la source structurée partagée de QuantLab.

Elle doit permettre :

- le stockage centralisé des données structurées;
- l'accès aux mêmes données par les différents utilisateurs de QuantLab;
- l'exécution des collecteurs et traitements analytiques;
- l'ingestion historique et incrémentale;
- l'enrichissement des événements déjà connus;
- la reconstruction des jeux de données analytiques à partir des données sources;
- l'automatisation future des mises à jour et traitements.

Les fichiers RAW originaux, notamment les fichiers XML du Nasdaq Halt Collector, demeurent la source de provenance permettant de reconstruire les données structurées.

Les fichiers CSV générés par le pipeline Nasdaq sont des artefacts de validation, de diagnostic, de non-régression ou d'export.

Ils ne constituent pas la couche d'intégration entre le traitement Nasdaq et PostgreSQL.

---

## 2. Environnement DEV

Le premier environnement PostgreSQL QuantLab est hébergé dans Microsoft Azure.

### Configuration

- Service : Azure Database for PostgreSQL Flexible Server
- Environnement : DEV
- Région Azure : Canada Central
- Version PostgreSQL : 17
- Type de calcul : Burstable
- Compute : B1ms
- vCPU : 1
- Mémoire : 2 GiB
- Stockage : 32 GiB
- Haute disponibilité : désactivée
- Rétention des sauvegardes : 7 jours
- Accès réseau : public restreint par règle de pare-feu
- Chiffrement en transit : TLS
- Authentification : PostgreSQL

### Serveur

Nom du serveur :

```text
quantlab-postgres-dev
```

Point de terminaison :

```text
quantlab-postgres-dev.postgres.database.azure.com
```

Port PostgreSQL :

```text
5432
```

Base de données principale :

```text
quantlab
```

Le mot de passe administrateur et les autres secrets ne doivent jamais être stockés dans Git, GitHub, les fichiers Markdown ou les fichiers de configuration versionnés.

---

## 3. Organisation logique

La base `quantlab` utilise actuellement trois schémas PostgreSQL.

### `raw`

Contient les données structurées les plus proches possible des données sources.

Objet initial :

```text
raw.nasdaq_trade_halt
```

Les fichiers XML Nasdaq demeurent la source RAW originale et la source de provenance.

### `core`

Contient les données métier normalisées et les objets dérivés nécessaires aux traitements QuantLab.

Objet initial :

```text
core.nasdaq_halt_episode
```

### `analytics`

Réservé aux objets analytiques : vues, vues matérialisées et autres datasets dérivés.

Le schéma existe depuis la migration initiale, mais les premiers objets analytiques seront créés dans une migration ultérieure après validation :

- du calendrier de marché;
- des épisodes multi-jours;
- de la logique `halt_close_status`;
- de la cardinalité RAW→CORE;
- de la conformité avec les résultats Python validés.

La future migration consacrée aux objets analytiques Nasdaq Halts est réservée comme migration `003`.

---

## 4. Version du modèle

Le modèle PostgreSQL Nasdaq Halt actuel demeure :

```text
Data Model V1.1
```

Le passage du pipeline à V0.8 n'a nécessité aucune modification physique du schéma PostgreSQL.

La V0.8 modifie principalement :

- la logique de persistance;
- la gestion des événements existants;
- l'enrichissement des HALT live;
- la protection contre les observations incomplètes;
- la gestion de provenance des snapshots live;
- les compteurs de résultat de persistance.

Aucune nouvelle migration n'est donc requise pour ce checkpoint.

---

## 5. Migrations Nasdaq Halts

### Migration 001 — schéma initial

Migration :

```text
database/migrations/001_create_nasdaq_halts_schema.sql
```

Cette migration crée :

```text
raw.nasdaq_trade_halt
core.nasdaq_halt_episode
```

ainsi que les index et contraintes nécessaires.

Elle a été validée sur PostgreSQL 17 dans l'environnement Azure DEV.

Une migration déjà appliquée n'est pas modifiée rétroactivement.

Toute évolution du schéma doit être réalisée par une nouvelle migration versionnée.

### Migration 002 — statut de clôture des épisodes

Migration :

```text
database/migrations/002_fix_nasdaq_halt_close_status.sql
```

La validation du dataset initial a démontré qu'une représentation booléenne du statut de clôture ne permettait pas de conserver correctement les épisodes multi-jours.

La migration `002` remplace :

```text
halt_at_close BOOLEAN
```

par :

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

La migration `002` a été appliquée et validée dans l'environnement PostgreSQL DEV.

### Migration 003 — réservée

La migration :

```text
database/migrations/003_create_nasdaq_halts_analytics.sql
```

est réservée aux futurs objets analytiques.

Elle n'est pas encore implémentée.

---

## 6. Connexion avec psql

Le client PostgreSQL utilisé sur le poste Windows de développement est `psql` version 17.

Exemple de connexion administrative :

```powershell
psql "host=quantlab-postgres-dev.postgres.database.azure.com port=5432 dbname=quantlab user=quantlab_admin sslmode=require"
```

Le mot de passe est demandé de manière interactive.

Il ne doit pas être intégré directement dans la commande, dans un script versionné ou dans l'historique Git.

Le compte administrateur est réservé au provisionnement, aux migrations et aux opérations nécessitant explicitement des privilèges administratifs.

---

## 7. Exécution des migrations

Depuis une session `psql` connectée à la base `quantlab`, les migrations sont exécutées dans l'ordre numérique.

Migration initiale :

```sql
\i 'C:/QuantLab/QuantLab/database/migrations/001_create_nasdaq_halts_schema.sql'
```

Migration de correction du statut de clôture :

```sql
\i 'C:/QuantLab/QuantLab/database/migrations/002_fix_nasdaq_halt_close_status.sql'
```

Les migrations doivent être :

1. versionnées dans Git;
2. revues avant exécution;
3. testées dans l'environnement DEV;
4. documentées;
5. exécutées dans l'ordre numérique;
6. conservées sans modification rétroactive après leur application.

---

## 8. Modèle Nasdaq Halt RAW

### Table

```text
raw.nasdaq_trade_halt
```

La table utilise une clé primaire technique `BIGINT`.

### Clé naturelle

La clé naturelle unique est :

```text
symbol
halt_date
halt_time
reason_code
market
```

Ces champs sont obligatoires dans le modèle PostgreSQL actuel.

Validation historique :

```text
Lignes                      : 744
Clés naturelles dupliquées : 0
```

Validation d'un snapshot live réel :

```text
Événements                  : 35
Clés naturelles             : 35
Clés naturelles dupliquées  : 0
```

La clé devra être revalidée sur l'historique complet de cinq ans.

### Provenance RAW historique

Les fichiers historiques utilisent notamment :

```text
tradehalts_2026-08-03.xml
tradehalts_2026-08-04.xml
tradehalts_2026-08-05.xml
```

Le champ :

```text
source_file
```

conserve le nom du fichier ayant créé l'événement structuré.

### Provenance RAW live

Chaque collecte live crée un snapshot immuable :

```text
tradehalts_live_YYYYMMDDTHHMMSSZ.xml
```

Exemple :

```text
tradehalts_live_20260828T205115Z.xml
```

Ces fichiers sont conservés sous la couche RAW locale du collecteur.

Lorsqu'un événement existe déjà selon la clé naturelle, une observation ultérieure peut enrichir sa ligne PostgreSQL.

Dans la V0.8 :

```text
source_file
```

n'est pas remplacé lors de cet enrichissement.

Il représente le premier snapshot ayant créé l'enregistrement RAW structuré.

Le stockage XML immuable demeure la provenance primaire.

Le modèle PostgreSQL ne représente pas encore explicitement :

```text
N snapshots -> 1 RAW event
```

Une future table de provenance ou d'observation pourra être ajoutée si cette traçabilité devient nécessaire.

---

## 9. Déduplication Python et PostgreSQL

La déduplication Python utilise actuellement :

```text
symbol
halt_start
resumption_date
resumption_trade_time
reason_code
```

La clé naturelle PostgreSQL utilise :

```text
symbol
halt_date
halt_time
reason_code
market
```

Ces deux clés ne sont donc pas identiques.

Sur le baseline historique :

```text
Événements bruts            : 744
Événements uniques          : 744
Clés PostgreSQL dupliquées  : 0
```

Sur le snapshot live validé :

```text
Événements                  : 35
Clés PostgreSQL             : 35
Clés PostgreSQL dupliquées  : 0
```

Aucune divergence n'est actuellement observée.

Cette équivalence doit être revalidée à plus grande échelle.

---

## 10. Modèle Nasdaq Halt CORE

### Table

```text
core.nasdaq_halt_episode
```

Chaque épisode est relié à un événement RAW par :

```text
trade_halt_id
```

La contrainte `UNIQUE` impose actuellement :

```text
1 événement RAW -> 1 épisode CORE
```

Cette relation est validée sur :

```text
744 événements historiques
35 événements du lot live validé
```

Elle devra être revalidée lors du chargement de l'historique complet.

### Validation stricte

Le pipeline Python peut théoriquement fusionner certains événements RAW lorsque leurs périodes se chevauchent.

Le writer PostgreSQL ne tente pas de résoudre arbitrairement une telle situation.

Un épisode doit pouvoir être associé sans ambiguïté à exactement un événement RAW sous le modèle actuel.

Une absence de correspondance ou plusieurs correspondances provoquent une erreur explicite.

### Identifiant du collecteur

Le champ :

```text
collector_episode_id
```

conserve l'identifiant généré par le pipeline Python.

Il ne constitue pas la clé primaire PostgreSQL.

L'identifiant est séquentiel et ne doit pas être considéré comme une identité métier durable.

Une mise à jour V0.8 d'un épisode existant ne remplace pas son `collector_episode_id`.

---

## 11. Statut de clôture

Le champ :

```text
halt_close_status
```

supporte :

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

### Protection V0.8

Les statuts :

```text
YES
NO
MULTI_DAY
```

sont considérés comme des statuts finaux pour la protection contre une observation incomplète.

Ainsi :

```text
final -> UNKNOWN
```

ne provoque pas de régression de la valeur stockée.

Une nouvelle valeur finale non-UNKNOWN peut toutefois remplacer une autre valeur finale lorsqu'elle représente une correction entrante.

---

## 12. Précision temporelle

Les timestamps fractionnaires provenant du Nasdaq sont préservés dans PostgreSQL.

Chaîne validée :

```text
Nasdaq XML
-> parser Python
-> PostgreSQL
```

Exemples :

```text
2026-08-03 08:52:20.892
2026-08-28 15:55:18.200
```

Les colonnes temporelles CORE utilisent actuellement :

```text
TIMESTAMP
```

sans fuseau horaire.

Cette décision permet de préserver les valeurs sources telles qu'elles sont actuellement interprétées par le pipeline.

La sémantique exacte du fuseau horaire Nasdaq devra être explicitement validée avant certification de l'historique complet.

---

## 13. Accès applicatif PostgreSQL

QuantLab applique le principe du moindre privilège.

Rôle applicatif :

```text
quantlab_collector
```

Ce rôle est défini avec :

```text
NOLOGIN
```

Compte de connexion DEV :

```text
quantlab_collector_dev
```

Ce compte est membre de :

```text
quantlab_collector
```

Le collecteur ne doit pas utiliser le compte administrateur pour ses opérations normales.

### Connectivité Python

La connectivité PostgreSQL commune est centralisée sous :

```text
shared/database/
```

Le module utilise Psycopg 3.

Dépendance :

```text
psycopg[binary]>=3.3,<4
```

Variables d'environnement :

```text
QUANTLAB_DB_HOST
QUANTLAB_DB_PORT
QUANTLAB_DB_NAME
QUANTLAB_DB_USER
QUANTLAB_DB_PASSWORD
```

Aucun secret ne doit être versionné dans Git.

La connexion Python avec le compte applicatif DEV a été validée avec TLS.

---

## 14. Persistance PostgreSQL V0.8

La persistance Nasdaq est implémentée dans :

```text
collectors/nasdaq_halts/src/nasdaq_postgresql.py
```

Elle est utilisée par :

```text
collectors/nasdaq_halts/src/calculate_halt_metrics.py
collectors/nasdaq_halts/src/nasdaq_halt_collector.py
```

Le premier traite le pipeline historique.

Le second traite le pipeline live.

### Flux

```text
XML RAW
   |
   v
Parsing / Normalisation
   |
   v
Deduplication
   |
   v
unique_events
   |
   +------> raw.nasdaq_trade_halt
   |
   v
Episode Construction
   |
   v
episodes
   |
   +------> core.nasdaq_halt_episode
```

Les CSV ne sont pas utilisés comme intermédiaires PostgreSQL.

---

## 15. Writer RAW V0.8

Le writer RAW :

- valide les champs nécessaires à la clé naturelle;
- recherche un événement existant;
- insère les nouveaux événements;
- enrichit les événements existants;
- protège les valeurs connues contre les NULL entrants;
- conserve le premier `source_file`;
- récupère l'identifiant PostgreSQL RAW;
- construit la correspondance nécessaire à CORE;
- retourne les compteurs de persistance.

### Champs enrichissables

Actuellement :

```text
issue_name
resumption_date
resumption_quote_time
resumption_trade_time
pause_threshold_price
```

### Règles

```text
DB NULL + incoming NULL
-> unchanged

DB NULL + incoming value
-> updated

DB value + incoming NULL
-> preserve DB value

DB value A + incoming A
-> unchanged

DB value A + incoming value B
-> updated avec B
```

Cette logique permet notamment :

```text
HALT ouvert
-> HALT complété
```

sans créer une nouvelle ligne RAW.

---

## 16. Writer CORE V0.8

Le writer CORE :

- recherche le RAW correspondant;
- exige une correspondance unique;
- insère les nouveaux épisodes;
- enrichit les épisodes existants;
- protège les valeurs connues contre les NULL entrants;
- protège les statuts finaux contre `UNKNOWN`;
- conserve `collector_episode_id`;
- retourne les compteurs de persistance.

Champs enrichissables :

```text
issue_name
market
reason_code
halt_end
duration_minutes
halt_close_status
```

Pour un épisode existant :

```text
symbol
halt_start
```

doivent rester structurellement cohérents.

Une incohérence provoque une erreur explicite.

---

## 17. Normalisation numérique

Les colonnes PostgreSQL de type :

```text
NUMERIC
```

sont retournées sous forme décimale par le driver PostgreSQL.

La V0.8 normalise les valeurs numériques entrantes avant comparaison.

Cette règle évite de générer une mise à jour lorsque les valeurs sont sémantiquement identiques mais représentées par des types Python différents.

Cette correction a notamment été validée pour :

```text
duration_minutes
```

Après normalisation, la réexécution historique produit :

```text
CORE updated   : 0
CORE unchanged : 744
```

---

## 18. Transaction RAW + CORE

RAW et CORE sont persistés dans une transaction commune.

```text
BEGIN
  |
  +-- RAW
  |
  +-- CORE
  |
COMMIT
```

En cas d'erreur :

```text
ROLLBACK
```

Une erreur CORE ne doit donc pas laisser une opération partielle considérée comme réussie.

---

## 19. Validation historique V0.8

Baseline :

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

Tests :

```text
QVCG  : PASS
BCARU : PASS
```

Après conversion de la persistance à V0.8 :

```text
RAW inserted          : 0
RAW updated           : 0
RAW unchanged         : 744

CORE inserted         : 0
CORE updated          : 0
CORE unchanged        : 744
```

La baseline historique demeure donc inchangée.

---

## 20. Validation contrôlée du cycle live

Test :

```text
tests/integration/test_nasdaq_postgresql_live_update.py
```

Scénarios :

```text
1. HALT ouvert
   RAW  : 1 inserted
   CORE : 1 inserted

2. même HALT complété
   RAW  : 1 updated
   CORE : 1 updated

3. réexécution identique
   RAW  : 1 unchanged
   CORE : 1 unchanged

4. observation incomplète ultérieure
   RAW  : 1 unchanged
   CORE : 1 unchanged
```

Le test valide notamment :

- `NULL -> valeur`;
- protection `valeur -> NULL`;
- protection d'un statut final contre `UNKNOWN`;
- conservation du premier `source_file`;
- idempotence.

Le test utilise une transaction puis effectue un rollback.

Après exécution :

```text
QLV08TEST RAW rows  : 0
QLV08TEST CORE rows : 0
```

Aucune donnée synthétique n'est conservée.

---

## 21. Validation live réelle

Premier passage V0.8 :

```text
Événements bruts      : 35
Événements uniques    : 35
HALT Episodes         : 35
Durées calculables    : 23

YES                   : 2
NO                    : 17
UNKNOWN               : 12
MULTI_DAY             : 4
```

Persistance :

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
CORE updated          : 0
CORE unchanged        : 35
```

Cette validation confirme l'idempotence du pipeline live sur un flux Nasdaq réel.

Le snapshot validé contenait également :

```text
35 événements
35 clés naturelles PostgreSQL
0 clé naturelle dupliquée
```

---

## 22. Loader CSV transitoire

Le loader reste disponible sous :

```text
collectors/nasdaq_halts/src/load_postgresql.py
```

Il a servi à valider initialement :

- la connectivité PostgreSQL;
- le modèle de données;
- les permissions;
- la transaction RAW/CORE;
- les clés naturelles;
- l'idempotence;
- la précision temporelle.

Il est conservé comme outil de validation et de migration.

Il ne constitue pas le chemin de persistance de production.

Le chemin actuel est :

```text
XML RAW
-> Python
-> PostgreSQL RAW
-> PostgreSQL CORE
```

---

## 23. Requêtes SQL

Les requêtes SQL réutilisables sont conservées sous :

```text
database/queries/
```

Les requêtes Nasdaq Halt se trouvent sous :

```text
database/queries/nasdaq_halts/
```

Fichiers actuels :

```text
explore_halt_episodes.sql
get_halts_per_symbol_and_date.sql
visualize_halts_table.sql
```

Ils servent notamment à :

- l'exploration;
- la validation;
- la consultation;
- le diagnostic;
- la vérification de provenance.

Exemple :

```sql
SELECT DISTINCT
    source_file
FROM raw.nasdaq_trade_halt
ORDER BY source_file;
```

L'environnement DEV utilise également l'extension PostgreSQL de Visual Studio Code.

---

## 24. Analytics

Les objets analytiques Nasdaq Halts ne sont pas encore créés dans PostgreSQL.

Migration future :

```text
database/migrations/003_create_nasdaq_halts_analytics.sql
```

Objets conceptuels :

```text
analytics.ticker_halt_daily
analytics.ticker_halt_metrics
analytics.ticker_halt_reason_metrics
```

Avant leur création, les calculs PostgreSQL devront être comparés aux résultats du pipeline Python validé.

Le calendrier de marché devra être modélisé afin d'éviter de considérer incorrectement les fins de semaine et jours fériés comme des jours de marché.

La logique des épisodes multi-jours et du statut de clôture devra être reproduite sans perte de sémantique.

La métrique :

```text
halts_per_market_day
```

demeure différée tant que le dénominateur fondé sur les jours de marché n'est pas correctement modélisé.

---

## 25. Concurrence

La persistance V0.8 est validée pour une exécution séquentielle.

Le writer utilise actuellement une logique conceptuelle :

```text
SELECT
puis
INSERT ou UPDATE
```

Les contraintes UNIQUE protègent l'intégrité du modèle.

Cependant, deux instances concurrentes pourraient entrer en compétition entre la lecture et l'insertion.

Avant l'activation d'une exécution centralisée permettant potentiellement plusieurs instances simultanées, une stratégie explicite devra être choisie, par exemple :

```text
INSERT ... ON CONFLICT
```

ou un mécanisme de verrouillage approprié.

---

## 26. Points à revalider sur l'historique cinq ans

Avant de considérer le modèle Nasdaq Halt comme stabilisé, le chargement historique complet devra notamment valider :

1. l'unicité de la clé naturelle RAW;
2. la compatibilité entre la déduplication Python et la clé naturelle PostgreSQL;
3. la relation actuelle 1 RAW → 1 CORE;
4. les éventuels épisodes construits à partir de plusieurs événements RAW;
5. la stabilité et l'utilité de `collector_episode_id`;
6. la présence d'un même événement naturel dans plusieurs fichiers XML;
7. la stratégie de provenance si plusieurs fichiers contiennent le même événement;
8. la précision des timestamps;
9. la sémantique du fuseau horaire Nasdaq;
10. la logique des épisodes multi-jours;
11. le calendrier officiel des jours de marché;
12. l'idempotence sur le volume historique complet;
13. les valeurs possibles de `market`;
14. les valeurs possibles de `reason_code`;
15. les cas sans reprise;
16. les changements de symbole;
17. les corrections de valeurs déjà connues;
18. les événements pouvant apparaître plusieurs fois dans un même snapshot.

Une divergence observée doit conduire à une évolution explicite du modèle plutôt qu'à une correction silencieuse.

---

## 27. Sauvegardes

L'environnement Azure DEV utilise actuellement la sauvegarde gérée par Azure avec une rétention de 7 jours.

Une procédure QuantLab complète de sauvegarde et restauration devra être définie séparément, incluant éventuellement :

```text
pg_dump
pg_restore
```

Cette activité est suivie séparément dans le backlog QuantLab.

---

## 28. Sécurité

Principes actuels :

- accès PostgreSQL uniquement par TLS;
- accès réseau restreint par le pare-feu Azure;
- aucun secret dans Git;
- aucun mot de passe dans la documentation;
- compte administrateur réservé au provisionnement et aux opérations administratives;
- rôle applicatif distinct du compte administrateur;
- compte de connexion DEV utilisant les privilèges du rôle applicatif;
- paramètres de connexion applicatifs fournis par variables d'environnement.

Avant PROD, QuantLab devra notamment définir :

- la gestion centralisée des secrets;
- la stratégie réseau PROD;
- la rotation des informations d'authentification;
- les rôles spécifiques nécessaires aux différents services;
- les procédures d'audit des privilèges;
- les procédures de sauvegarde et restauration validées.

---

## 29. État actuel

Le modèle PostgreSQL Nasdaq Halt est actuellement :

```text
Data Model V1.1
```

avec le pipeline :

```text
Collector Integration V0.8
```

Validations actuelles :

```text
Historique baseline       : PASS
QVCG                      : PASS
BCARU                     : PASS
Historique idempotence    : PASS
Live PostgreSQL           : PASS
Live idempotence          : PASS
Live update controlled    : PASS
Transaction rollback test : PASS
Fractional timestamps     : PASS
```

Aucune migration de schéma supplémentaire n'est nécessaire pour le checkpoint V0.8.

La prochaine validation structurante du modèle sera le chargement et la certification de l'historique Nasdaq Halt de cinq ans.
