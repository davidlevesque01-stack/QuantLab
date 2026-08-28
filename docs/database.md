# QuantLab — Base de données

## 1. Objectif

La base de données PostgreSQL constitue la source structurée partagée de QuantLab.

Elle doit permettre :

* le stockage centralisé des données structurées ;
* l'accès aux mêmes données par les différents utilisateurs de QuantLab ;
* l'exécution des collecteurs et traitements analytiques ;
* la reconstruction des jeux de données analytiques à partir des données sources ;
* l'automatisation future des mises à jour et traitements.

Les fichiers RAW originaux, notamment les fichiers XML du Nasdaq Halt Collector, demeurent la source de provenance permettant de reconstruire les données structurées.

Les fichiers CSV générés par le pipeline Nasdaq sont des artefacts de validation, de diagnostic, de non-régression ou d'export. Ils ne constituent plus la couche d'intégration entre le traitement Nasdaq et PostgreSQL.

---

## 2. Environnement DEV

Le premier environnement PostgreSQL QuantLab est hébergé dans Microsoft Azure.

### Configuration

* Service : Azure Database for PostgreSQL Flexible Server
* Environnement : DEV
* Région Azure : Canada Central
* Version PostgreSQL : 17
* Type de calcul : Burstable
* Compute : B1ms
* vCPU : 1
* Mémoire : 2 GiB
* Stockage : 32 GiB
* Haute disponibilité : désactivée
* Rétention des sauvegardes : 7 jours
* Accès réseau : public restreint par règle de pare-feu
* Chiffrement en transit : TLS
* Authentification : PostgreSQL

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

* du calendrier de marché ;
* des épisodes multi-jours ;
* de la logique `halt_close_status`, incluant `YES`, `NO`, `UNKNOWN` et `MULTI_DAY` ;
* de la conformité avec les résultats Python V0.7.

La future migration consacrée aux objets analytiques Nasdaq Halts est prévue comme migration `003`, la migration `002` étant utilisée pour la correction du modèle de statut de clôture.

---

## 4. Migrations Nasdaq Halts

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

La migration a été validée sur PostgreSQL 17 dans l'environnement Azure DEV.

Une migration déjà appliquée n'est pas modifiée rétroactivement. Toute évolution du schéma doit être réalisée par une nouvelle migration versionnée.

### Migration 002 — statut de clôture des épisodes

Migration :

```text
database/migrations/002_fix_nasdaq_halt_close_status.sql
```

La validation du dataset initial a démontré qu'une représentation booléenne du statut de clôture ne permettait pas de conserver correctement les épisodes multi-jours.

La migration `002` remplace donc :

```text
halt_at_close BOOLEAN
```

par :

```text
halt_close_status VARCHAR(20)
```

Les valeurs actuellement autorisées sont :

```text
YES
NO
UNKNOWN
MULTI_DAY
```

Cette représentation préserve la sémantique du pipeline Python.

Pour les épisodes multi-jours, le statut de clôture ne doit pas être réduit à une valeur booléenne au niveau de l'épisode.

La migration `002` a été appliquée et validée dans l'environnement PostgreSQL DEV.

---

## 5. Connexion avec psql

Le client PostgreSQL utilisé sur le poste Windows de développement est `psql` version 17.

Exemple de connexion administrative :

```powershell
psql "host=quantlab-postgres-dev.postgres.database.azure.com port=5432 dbname=quantlab user=quantlab_admin sslmode=require"
```

Le mot de passe est demandé de manière interactive.

Il ne doit pas être intégré directement dans la commande, dans un script versionné ou dans l'historique Git.

Le compte administrateur est réservé au provisionnement, aux migrations et aux opérations nécessitant explicitement des privilèges administratifs.

---

## 6. Exécution des migrations

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

1. versionnées dans Git ;
2. revues avant exécution ;
3. testées dans l'environnement DEV ;
4. documentées ;
5. exécutées dans l'ordre numérique ;
6. conservées sans modification rétroactive après leur application.

---

## 7. Modèle Nasdaq Halt

### Table RAW

```text
raw.nasdaq_trade_halt
```

La table utilise une clé primaire technique `BIGINT` et une clé naturelle unique basée sur :

```text
symbol
halt_date
halt_time
reason_code
market
```

Cette clé naturelle a été validée sur le dataset V0.7 actuel :

```text
Lignes                      : 744
Clés naturelles dupliquées : 0
```

Les champs constituant cette clé naturelle sont obligatoires dans le modèle PostgreSQL actuel.

### Provenance RAW

La table RAW structurée conserve le nom du fichier XML source dans :

```text
source_file
```

Exemples :

```text
tradehalts_2026-08-03.xml
tradehalts_2026-08-04.xml
tradehalts_2026-08-05.xml
```

La validation V0.7 contient 744 lignes RAW réparties sur 10 fichiers XML correspondant aux journées de marché du dataset de validation.

PostgreSQL ne stocke pas actuellement le contenu XML complet.

Les fichiers XML originaux demeurent conservés dans le stockage RAW du collecteur et permettent la reconstruction des données structurées.

Le champ `source_file` fournit le lien de provenance entre l'enregistrement structuré et son fichier source.

### Clé de déduplication Python

La clé utilisée actuellement par le pipeline Python V0.7 pour la déduplication des événements n'est pas identique à la clé naturelle PostgreSQL.

Cette différence n'a produit aucune collision sur le dataset actuel de 744 événements.

Elle devra être revalidée sur l'historique complet de cinq ans.

Si cette validation révèle des différences sémantiques, le modèle de déduplication ou le modèle PostgreSQL devra être adapté avant certification de l'historique.

### Table CORE

```text
core.nasdaq_halt_episode
```

Chaque épisode est actuellement relié à un événement RAW par :

```text
trade_halt_id
```

La contrainte `UNIQUE` sur `trade_halt_id` impose actuellement une relation :

```text
1 événement RAW -> 1 épisode CORE
```

Cette relation a été validée sur les 744 événements du dataset V0.7 actuel.

Elle devra être revalidée lors du chargement de l'historique complet de cinq ans.

Le pipeline Python peut théoriquement fusionner certains événements RAW lorsque leurs périodes se chevauchent. Le writer PostgreSQL V0.7 ne tente pas de résoudre arbitrairement une telle situation.

Il exige qu'un épisode puisse être associé sans ambiguïté à exactement un événement RAW sous le modèle actuel.

Une absence de correspondance ou plusieurs correspondances provoquent une erreur explicite afin de signaler que le modèle doit être revu.

### Identifiant du collecteur

Le champ :

```text
collector_episode_id
```

conserve l'identifiant généré par le pipeline Python à des fins de traçabilité.

Il ne constitue pas la clé primaire PostgreSQL.

L'identifiant d'épisode généré actuellement est séquentiel et ne doit pas être considéré comme une identité métier durable tant que son comportement sur un historique étendu n'a pas été validé.

### Statut de clôture

Le champ :

```text
halt_close_status
```

conserve l'état de clôture calculé par le pipeline Python.

Distribution validée sur le dataset V0.7 actuel :

```text
YES       : 15
NO        : 697
UNKNOWN   : 2
MULTI_DAY : 30
TOTAL     : 744
```

### Précision temporelle

Les timestamps fractionnaires provenant du Nasdaq sont préservés dans PostgreSQL.

La chaîne directe suivante a été validée :

```text
Nasdaq XML
-> parser Python V0.7
-> PostgreSQL
```

Des timestamps comportant des fractions de seconde sont présents dans PostgreSQL, par exemple :

```text
2026-08-03 08:52:20.892
```

Les colonnes temporelles du modèle utilisent actuellement `TIMESTAMP` sans fuseau horaire afin de préserver les valeurs temporelles sources telles qu'elles sont fournies et interprétées par le pipeline actuel.

La sémantique exacte du fuseau horaire devra être explicitement validée avant le chargement et la certification de l'historique complet de cinq ans.

---

## 8. Accès applicatif PostgreSQL

QuantLab applique le principe du moindre privilège pour l'accès applicatif.

Le rôle applicatif actuel est :

```text
quantlab_collector
```

Ce rôle est défini avec `NOLOGIN` et reçoit les privilèges nécessaires aux opérations du collecteur sur les objets RAW et CORE concernés.

Le compte de connexion DEV est :

```text
quantlab_collector_dev
```

Ce compte est membre du rôle :

```text
quantlab_collector
```

Le collecteur et les composants applicatifs ne doivent pas utiliser le compte administrateur PostgreSQL pour leurs opérations normales.

### Connectivité Python

La connectivité PostgreSQL commune au monorepo est centralisée sous :

```text
shared/database/
```

Le module actuel utilise Psycopg 3.

La dépendance est déclarée dans :

```text
pyproject.toml
```

avec :

```text
psycopg[binary]>=3.3,<4
```

La connexion applicative lit les paramètres suivants depuis les variables d'environnement :

```text
QUANTLAB_DB_HOST
QUANTLAB_DB_PORT
QUANTLAB_DB_NAME
QUANTLAB_DB_USER
QUANTLAB_DB_PASSWORD
```

Aucune valeur de mot de passe ou autre secret ne doit être versionnée dans Git.

La connexion Python avec le compte applicatif DEV a été validée avec TLS contre la base `quantlab`.

---

## 9. Persistance PostgreSQL V0.7

La persistance PostgreSQL spécifique au Nasdaq Halt Collector est implémentée dans :

```text
collectors/nasdaq_halts/src/nasdaq_postgresql.py
```

Elle est appelée directement par :

```text
collectors/nasdaq_halts/src/calculate_halt_metrics.py
```

Le pipeline V0.7 transmet directement :

```text
unique_events
episodes
```

au writer PostgreSQL.

Il n'est donc plus nécessaire de relire les fichiers CSV traités afin d'alimenter PostgreSQL.

### Flux actuel

```text
XML RAW
   |
   v
Parsing
   |
   v
unique_events
   |
   +------> raw.nasdaq_trade_halt
   |
   v
Episode construction
   |
   v
episodes
   |
   +------> core.nasdaq_halt_episode
```

Les CSV continuent d'être produits comme artefacts secondaires de validation et de non-régression.

### Writer RAW

Le writer RAW :

* valide les champs nécessaires à la clé naturelle ;
* conserve le nom du fichier XML dans `source_file` ;
* insère les nouveaux événements ;
* détecte les événements déjà présents par la contrainte naturelle ;
* récupère l'identifiant PostgreSQL d'un événement existant ;
* construit la correspondance nécessaire à la persistance CORE.

La gestion des conflits repose sur la clé naturelle PostgreSQL :

```text
symbol
halt_date
halt_time
reason_code
market
```

### Writer CORE

Le writer CORE :

* recherche l'événement RAW source correspondant à chaque épisode ;
* exige une correspondance unique sous le modèle 1:1 actuel ;
* récupère le `trade_halt_id` PostgreSQL ;
* conserve le `collector_episode_id` ;
* conserve `halt_close_status` ;
* insère l'épisode CORE ;
* traite une réexécution comme un enregistrement existant plutôt qu'une duplication.

### Transaction

La persistance RAW et CORE est exécutée dans une même connexion transactionnelle PostgreSQL.

Une erreur de persistance empêche l'exécution d'être considérée comme une persistance PostgreSQL réussie.

Le code ne doit pas sélectionner arbitrairement une relation RAW→CORE lorsqu'une ambiguïté est détectée.

---

## 10. Validation de la persistance directe

### Chargement direct après nettoyage DEV

La base DEV a été nettoyée des données précédemment chargées par le loader CSV afin de valider la provenance XML réelle.

Après nettoyage :

```text
RAW  : 0
CORE : 0
```

L'exécution du pipeline V0.7 directement à partir des fichiers XML a produit :

```text
RAW inserted   : 744
RAW existing   : 0
CORE inserted  : 744
CORE existing  : 0
```

Les tests de non-régression sont demeurés conformes :

```text
QVCG  : PASS
BCARU : PASS
```

Les métriques de référence sont également demeurées inchangées.

### Provenance validée

Après le chargement direct, les valeurs de `source_file` correspondent aux fichiers XML historiques réels plutôt qu'au fichier CSV transitoire.

La distribution validée est :

```text
tradehalts_2026-08-03.xml : 93
tradehalts_2026-08-04.xml : 45
tradehalts_2026-08-05.xml : 77
tradehalts_2026-08-06.xml : 93
tradehalts_2026-08-07.xml : 112
tradehalts_2026-08-10.xml : 100
tradehalts_2026-08-11.xml : 60
tradehalts_2026-08-12.xml : 78
tradehalts_2026-08-13.xml : 42
tradehalts_2026-08-14.xml : 44
```

Total :

```text
744
```

### Idempotence

Une exécution du pipeline contre des données déjà présentes a également validé le comportement idempotent :

```text
RAW inserted   : 0
RAW existing   : 744
CORE inserted  : 0
CORE existing  : 744
```

La persistance directe V0.7 est donc idempotente sur le dataset de validation actuel.

Cette propriété devra être revalidée sur l'historique complet de cinq ans.

---

## 11. Loader CSV transitoire

Le loader historique reste disponible sous :

```text
collectors/nasdaq_halts/src/load_postgresql.py
```

Il charge :

```text
data/processed/tradehalts.csv
data/processed/halt_episodes.csv
```

vers :

```text
raw.nasdaq_trade_halt
core.nasdaq_halt_episode
```

Ce loader a servi à valider initialement :

* la connectivité PostgreSQL ;
* le modèle de données ;
* les permissions du rôle applicatif ;
* la transaction RAW/CORE ;
* la gestion des clés naturelles ;
* l'idempotence ;
* la précision temporelle.

Il est conservé comme outil de validation et de migration.

Il ne constitue pas le chemin de persistance de production.

Le chemin V0.7 privilégié est désormais :

```text
XML RAW
-> Python
-> PostgreSQL RAW
-> PostgreSQL CORE
```

---

## 12. Requêtes SQL

Les requêtes SQL réutilisables sont conservées sous :

```text
database/queries/
```

Les requêtes actuelles du Nasdaq Halt Collector se trouvent sous :

```text
database/queries/nasdaq_halts/
```

Elles comprennent actuellement :

```text
explore_halt_episodes.sql
get_halts_per_symbol_and_date.sql
visualize_halts_table.sql
```

Ces fichiers sont destinés à faciliter :

* l'exploration ;
* la validation ;
* la consultation ;
* le diagnostic ;
* la vérification de provenance.

La provenance des fichiers XML peut notamment être inspectée avec :

```sql
SELECT DISTINCT
    source_file
FROM raw.nasdaq_trade_halt
ORDER BY source_file;
```

L'environnement DEV utilise également l'extension PostgreSQL de Visual Studio Code pour explorer les objets PostgreSQL, exécuter les fichiers SQL sauvegardés et visualiser les résultats.

---

## 13. Analytics

Les objets analytiques Nasdaq Halts ne sont pas encore créés dans PostgreSQL.

La future migration analytique est prévue comme :

```text
database/migrations/003_create_nasdaq_halts_analytics.sql
```

Elle pourra notamment créer les équivalents PostgreSQL des datasets :

```text
analytics.ticker_halt_daily
analytics.ticker_halt_metrics
analytics.ticker_halt_reason_metrics
```

Cette migration ne doit pas être créée avant validation complète de la sémantique nécessaire.

Avant leur création définitive, les calculs PostgreSQL devront être comparés aux résultats du pipeline Python V0.7.

Le calendrier de marché devra être modélisé afin d'éviter de considérer incorrectement les fins de semaine et jours fériés comme des jours de marché.

La logique des épisodes multi-jours et du statut de clôture devra également être reproduite sans perte de sémantique.

La métrique :

```text
halts_per_market_day
```

demeure différée tant que le dénominateur fondé sur les jours de marché n'est pas correctement modélisé.

---

## 14. Points à revalider sur l'historique cinq ans

Avant de considérer le modèle Nasdaq Halt comme stabilisé, le chargement historique complet devra notamment valider :

1. l'unicité de la clé naturelle RAW ;
2. la compatibilité entre la déduplication Python et la clé naturelle PostgreSQL ;
3. la relation actuelle 1 RAW → 1 CORE ;
4. les éventuels épisodes construits à partir de plusieurs événements RAW ;
5. la stabilité et l'utilité de `collector_episode_id` ;
6. la présence d'un même événement naturel dans plusieurs fichiers XML ;
7. la stratégie de provenance si plusieurs fichiers contiennent le même événement ;
8. la précision des timestamps ;
9. la sémantique du fuseau horaire Nasdaq ;
10. la logique des épisodes multi-jours ;
11. le calendrier officiel des jours de marché ;
12. l'idempotence sur le volume historique complet.

Une divergence observée pendant cette validation doit conduire à une évolution explicite du modèle plutôt qu'à une correction silencieuse des données.

---

## 15. Sauvegardes

L'environnement Azure DEV utilise actuellement la sauvegarde gérée par Azure avec une rétention de 7 jours.

Une procédure QuantLab complète de sauvegarde et restauration devra être définie séparément, incluant éventuellement :

```text
pg_dump
pg_restore
```

Cette activité est suivie séparément dans le backlog QuantLab.

---

## 16. Sécurité

Principes actuels :

* accès PostgreSQL uniquement par TLS ;
* accès réseau restreint par le pare-feu Azure ;
* aucun secret dans Git ;
* aucun mot de passe dans la documentation ;
* compte administrateur réservé au provisionnement et aux opérations administratives ;
* rôle applicatif distinct du compte administrateur ;
* compte de connexion DEV utilisant les privilèges du rôle applicatif ;
* paramètres de connexion applicatifs fournis par variables d'environnement.

Avant l'environnement PROD, QuantLab devra notamment définir :

* la gestion centralisée des secrets ;
* la stratégie réseau PROD ;
* la rotation des informations d'authentification ;
* les rôles spécifiques nécessaires aux différents services ;
* les procédures d'audit des privilèges ;
* les procédures de sauvegarde et restauration validées.
