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

Les fichiers XML Nasdaq demeurent toutefois la source RAW originale et la source de provenance.

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
* de la conformité avec les résultats Python V0.6.

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

La validation du dataset V0.6 a démontré qu'une représentation booléenne du statut de clôture ne permettait pas de conserver correctement les épisodes multi-jours.

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

Cette représentation préserve la sémantique du pipeline Python V0.6. Pour les épisodes multi-jours, le statut de clôture ne doit pas être réduit à une valeur booléenne au niveau de l'épisode.

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

Cette clé naturelle a été validée sur le dataset V0.6 existant :

```text
Lignes                         : 744
Clés naturelles dupliquées    : 0
```

Les champs constituant cette clé naturelle sont obligatoires dans le modèle PostgreSQL actuel.

La table RAW structurée conserve également le nom du fichier source chargé dans `source_file`.

Dans l'architecture cible, cette provenance devra permettre de relier les données structurées aux fichiers XML RAW Nasdaq originaux.

### Table CORE

```text
core.nasdaq_halt_episode
```

Chaque épisode est relié à un événement RAW par :

```text
trade_halt_id
```

La contrainte `UNIQUE` sur `trade_halt_id` impose actuellement une relation 1:1 entre un événement RAW et un épisode CORE.

Cette relation a été validée sur les 744 événements du dataset V0.6 actuel. Elle devra être revalidée lors du chargement de l'historique complet de cinq ans.

Le champ :

```text
collector_episode_id
```

conserve l'identifiant généré par le pipeline V0.6 à des fins de traçabilité. Il ne constitue pas la clé primaire PostgreSQL.

Le champ :

```text
halt_close_status
```

conserve l'état de clôture calculé par le pipeline V0.6.

Distribution validée sur le dataset actuel :

```text
YES       : 15
NO        : 697
UNKNOWN   : 2
MULTI_DAY : 30
TOTAL     : 744
```

Les timestamps fractionnaires provenant du Nasdaq sont préservés dans PostgreSQL.

La chaîne complète suivante a été validée :

```text
Nasdaq
-> CSV V0.6
-> parser Python
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

## 9. Loader PostgreSQL de validation

Le loader actuel se trouve sous :

```text
collectors/nasdaq_halts/src/load_postgresql.py
```

Il charge les fichiers V0.6 suivants :

```text
data/processed/tradehalts.csv
data/processed/halt_episodes.csv
```

vers :

```text
raw.nasdaq_trade_halt
core.nasdaq_halt_episode
```

Ce loader constitue un mécanisme transitoire de validation et de migration. Il permet de valider le modèle PostgreSQL à partir du dataset V0.6 connu.

Il ne représente pas le pipeline de production cible.

### Validation du chargement

Premier chargement :

```text
RAW inserted   : 744
RAW existing   : 0
CORE inserted  : 744
CORE existing  : 0
```

Second chargement du même dataset :

```text
RAW inserted   : 0
RAW existing   : 744
CORE inserted  : 0
CORE existing  : 744
```

Ce second chargement confirme l'idempotence du loader sur le dataset V0.6.

Le chargement RAW et CORE est exécuté dans une transaction PostgreSQL commune. Une erreur pendant le traitement provoque l'annulation de la transaction plutôt qu'un chargement partiel.

### Architecture cible

Le pipeline de production ne doit pas dépendre des CSV intermédiaires.

L'architecture cible est :

```text
Nasdaq Web / RSS
        |
        v
Nasdaq Halt Collector
        |
        +--> XML RAW conservé
        |
        v
Parsing / normalisation
        |
        v
PostgreSQL RAW
        |
        v
Transformation
        |
        v
PostgreSQL CORE
        |
        v
Analytics
```

Les CSV demeurent utiles comme exports, outils de diagnostic et références de non-régression, mais ne constituent pas la couche d'intégration de production entre le collecteur et PostgreSQL.

L'intégration directe du collecteur avec PostgreSQL demeure donc une étape à réaliser.

---

## 10. Requêtes SQL

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

Ces fichiers sont destinés à faciliter l'exploration, la validation et la consultation des données sans intégrer des requêtes ad hoc dans le code applicatif.

L'environnement DEV utilise également l'extension PostgreSQL de Visual Studio Code pour explorer les objets PostgreSQL, exécuter les fichiers SQL sauvegardés et visualiser les résultats.

---

## 11. Analytics

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

Avant leur création définitive, les calculs PostgreSQL devront être comparés aux résultats du pipeline Python V0.6.

Le calendrier de marché devra être modélisé afin d'éviter de considérer les fins de semaine et jours fériés comme des jours de marché.

La logique des épisodes multi-jours et du statut de clôture devra également être reproduite sans perte de sémantique.

La métrique `halts_per_market_day` demeure différée tant que le dénominateur fondé sur les jours de marché n'est pas correctement modélisé.

---

## 12. Sauvegardes

L'environnement Azure DEV utilise actuellement la sauvegarde gérée par Azure avec une rétention de 7 jours.

Une procédure QuantLab complète de sauvegarde et restauration devra être définie séparément, incluant éventuellement :

```text
pg_dump
pg_restore
```

Cette activité est suivie séparément dans le backlog QuantLab.

---

## 13. Sécurité

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
