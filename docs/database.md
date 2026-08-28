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
* Authentification initiale : PostgreSQL

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

Le schéma existe dans la migration initiale, mais les premiers objets analytiques seront créés dans une migration ultérieure après validation :

* du calendrier de marché ;
* des épisodes multi-jours ;
* de la logique `halt_at_close` ;
* de la conformité avec les résultats Python V0.6.

---

## 4. Migration initiale

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

---

## 5. Connexion avec psql

Le client PostgreSQL utilisé sur le poste Windows de développement est `psql` version 17.

Exemple de connexion :

```powershell
psql "host=quantlab-postgres-dev.postgres.database.azure.com port=5432 dbname=quantlab user=quantlab_admin sslmode=require"
```

Le mot de passe est demandé de manière interactive.

Il ne doit pas être intégré directement dans la commande, dans un script versionné ou dans l'historique Git.

---

## 6. Exécution d'une migration

Depuis une session `psql` connectée à la base `quantlab` :

```sql
\i 'C:/QuantLab/QuantLab/database/migrations/001_create_nasdaq_halts_schema.sql'
```

Les migrations doivent être :

1. versionnées dans Git ;
2. revues avant exécution ;
3. testées dans l'environnement DEV ;
4. documentées ;
5. exécutées dans l'ordre numérique.

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

Cette clé naturelle a été validée sur le dataset V0.6 existant : aucun doublon n'a été détecté.

### Table CORE

```text
core.nasdaq_halt_episode
```

Chaque épisode est relié à un événement RAW par :

```text
trade_halt_id
```

La relation actuellement imposée est 1:1.

Cette hypothèse devra être revalidée lors du chargement de l'historique complet de cinq ans.

---

## 8. Analytics

Les objets analytiques ne sont pas encore inclus dans la migration `001`.

Une migration ultérieure devra notamment créer :

```text
analytics.ticker_halt_daily
analytics.ticker_halt_metrics
analytics.ticker_halt_reason_metrics
```

Avant leur création définitive, les calculs PostgreSQL devront être comparés aux résultats du pipeline Python V0.6.

Le calendrier de marché devra aussi être modélisé afin d'éviter de considérer les fins de semaine et jours fériés comme des jours de marché.

---

## 9. Sauvegardes

L'environnement Azure DEV utilise actuellement la sauvegarde gérée par Azure avec une rétention de 7 jours.

Une procédure QuantLab complète de sauvegarde et restauration devra être définie séparément, incluant éventuellement :

```text
pg_dump
pg_restore
```

Cette activité est suivie séparément dans le backlog QuantLab.

---

## 10. Sécurité

Principes actuels :

* accès PostgreSQL uniquement par TLS ;
* accès réseau restreint par le pare-feu Azure ;
* aucun secret dans Git ;
* aucun mot de passe dans la documentation ;
* compte administrateur réservé à l'administration initiale.

Avant l'environnement PROD, QuantLab devra définir :

* des comptes applicatifs dédiés ;
* les privilèges minimum requis ;
* la gestion centralisée des secrets ;
* la stratégie réseau PROD ;
* la rotation des informations d'authentification.
