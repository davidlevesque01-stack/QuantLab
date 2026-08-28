\# QuantLab – Nasdaq Halt Collector



\## Modèle de données PostgreSQL



\*\*Version :\*\* V1.0

\*\*Statut :\*\* Conception initiale

\*\*Date :\*\* 2026-08-28



\---



\## 1. Objectif



Ce document définit le modèle de données PostgreSQL utilisé par le module \*\*QuantLab – Nasdaq Halt Collector\*\*.



Le modèle vise à :



\* conserver les événements Nasdaq Trade Halt sous une forme structurée;

\* assurer la déduplication des événements lors des chargements historiques et quotidiens;

\* représenter les épisodes de suspension de négociation;

\* permettre le traitement correct des épisodes couvrant plusieurs jours;

\* fournir des données analytiques par symbole, journée et raison de suspension;

\* permettre la reconstruction des métriques analytiques à partir des données de base;

\* supporter le chargement initial de plusieurs années d'historique ainsi que les mises à jour quotidiennes futures.



Les fichiers XML Nasdaq conservés dans `data/raw/nasdaq/` demeurent la source originale de provenance des données externes.



PostgreSQL constitue la source structurée et interrogeable de QuantLab.



\---



\## 2. Principes du modèle



Le modèle est organisé en trois couches PostgreSQL :



```text

raw

│

└── nasdaq\_trade\_halt



core

│

└── nasdaq\_halt\_episode



analytics

│

├── ticker\_halt\_daily

├── ticker\_halt\_metrics

└── ticker\_halt\_reason\_metrics

```



\### 2.1 Couche `raw`



La couche `raw` contient les événements normalisés provenant directement des données Nasdaq.



Elle doit rester aussi près que raisonnablement possible de la donnée source tout en appliquant les conversions de types nécessaires.



\### 2.2 Couche `core`



La couche `core` contient les objets métier reconstruits à partir des événements bruts.



Pour le Nasdaq Halt Collector, l'objet principal est l'épisode de suspension de négociation.



\### 2.3 Couche `analytics`



La couche `analytics` contient les données dérivées utilisées pour les analyses, métriques et interfaces de consultation.



Ces données doivent pouvoir être reconstruites à partir de la couche `core`.



\---



\# 3. Table `raw.nasdaq\_trade\_halt`



Cette table contient les événements Nasdaq Trade Halt normalisés.



\## Colonnes



| Colonne                 | Type PostgreSQL | Contraintes                               |

| ----------------------- | --------------- | ----------------------------------------- |

| `id`                    | BIGINT          | PRIMARY KEY, GENERATED ALWAYS AS IDENTITY |

| `symbol`                | VARCHAR(20)     | NOT NULL                                  |

| `issue\_name`            | TEXT            |                                           |

| `market`                | VARCHAR(10)     |                                           |

| `reason\_code`           | VARCHAR(20)     | NOT NULL                                  |

| `halt\_date`             | DATE            | NOT NULL                                  |

| `halt\_time`             | TIME            |                                           |

| `resumption\_date`       | DATE            |                                           |

| `resumption\_quote\_time` | TIME            |                                           |

| `resumption\_trade\_time` | TIME            |                                           |

| `pause\_threshold\_price` | NUMERIC(18,6)   |                                           |

| `source\_file`           | TEXT            |                                           |

| `loaded\_at`             | TIMESTAMPTZ     | NOT NULL, DEFAULT now()                   |



\## Clé naturelle



La clé naturelle retenue est :



```text

symbol

halt\_date

halt\_time

reason\_code

market

```



Une contrainte UNIQUE doit empêcher le chargement répété du même événement.



Cette clé a été validée sur le dataset V0.6 :



```text

Événements analysés       : 744

Clés naturelles dupliquées: 0

```



Cette validation devra être répétée sur l'historique complet avant de considérer cette hypothèse comme définitive.



\---



\# 4. Table `core.nasdaq\_halt\_episode`



Cette table représente les épisodes de suspension reconstruits à partir des événements Nasdaq.



\## Colonnes



| Colonne                | Type PostgreSQL | Contraintes                                    |

| ---------------------- | --------------- | ---------------------------------------------- |

| `id`                   | BIGINT          | PRIMARY KEY, GENERATED ALWAYS AS IDENTITY      |

| `trade\_halt\_id`        | BIGINT          | référence vers `raw.nasdaq\_trade\_halt.id`      |

| `collector\_episode\_id` | VARCHAR(20)     | identifiant généré par le collector, optionnel |

| `symbol`               | VARCHAR(20)     | NOT NULL                                       |

| `issue\_name`           | TEXT            |                                                |

| `market`               | VARCHAR(10)     |                                                |

| `reason\_code`          | VARCHAR(20)     |                                                |

| `halt\_start`           | TIMESTAMP       | NOT NULL                                       |

| `halt\_end`             | TIMESTAMP       |                                                |

| `duration\_minutes`     | NUMERIC(12,3)   |                                                |

| `halt\_at\_close`        | BOOLEAN         |                                                |



\## Identifiant



Les identifiants actuels du collector :



```text

H00000001

H00000002

...

```



ne constituent pas la clé primaire PostgreSQL.



Ils peuvent changer lors d'une reconstruction complète du dataset.



PostgreSQL utilise donc une clé technique générée automatiquement.



L'identifiant du collector peut être conservé dans `collector\_episode\_id` à des fins de diagnostic et de traçabilité.



\## Relation avec les événements



Le dataset V0.6 contient :



```text

Trade Halt Events : 744

Halt Episodes     : 744

```



Les 744 `episode\_id` sont uniques.



La relation observée actuellement est donc 1:1.



Cette hypothèse devra également être validée sur l'historique complet.



\---



\# 5. Épisodes multi-jours



Un épisode peut couvrir plus d'une journée de marché.



Par conséquent :



```text

nombre d'épisodes

```



et :



```text

nombre de jours affectés

```



représentent deux concepts distincts.



Exemple observé dans V0.6 :



```text

Symbol              : ABVC

Total halt episodes : 1

Halt days           : 2

```



Le modèle doit conserver cette distinction.



La table `core.nasdaq\_halt\_episode` représente l'épisode complet tandis que la couche analytique peut représenter individuellement chaque journée affectée.



\---



\# 6. Objet `analytics.ticker\_halt\_daily`



Cet objet représente l'activité de suspension quotidienne par symbole.



\## Colonnes



| Colonne         | Type PostgreSQL |

| --------------- | --------------- |

| `symbol`        | VARCHAR(20)     |

| `date`          | DATE            |

| `halt\_present`  | BOOLEAN         |

| `episode\_count` | INTEGER         |

| `halt\_at\_close` | BOOLEAN         |



Clé logique :



```text

PRIMARY KEY (symbol, date)

```



Cet objet est entièrement dérivable de `core.nasdaq\_halt\_episode`.



Il devrait donc préférablement être implémenté sous forme de \*\*vue matérialisée\*\* plutôt que comme une table indépendante alimentée par le collector.



\---



\# 7. Objet `analytics.ticker\_halt\_metrics`



Cet objet contient les métriques consolidées par symbole.



\## Colonnes



| Colonne                        | Type PostgreSQL |

| ------------------------------ | --------------- |

| `symbol`                       | VARCHAR(20)     |

| `total\_halt\_episodes`          | INTEGER         |

| `halt\_days`                    | INTEGER         |

| `halt\_days\_at\_close`           | INTEGER         |

| `halt\_at\_close\_pct`            | NUMERIC(8,4)    |

| `halts\_per\_halt\_day`           | NUMERIC(12,6)   |

| `halts\_per\_market\_day`         | NUMERIC(12,6)   |

| `avg\_halt\_duration\_minutes`    | NUMERIC(12,3)   |

| `median\_halt\_duration\_minutes` | NUMERIC(12,3)   |

| `min\_halt\_duration\_minutes`    | NUMERIC(12,3)   |

| `max\_halt\_duration\_minutes`    | NUMERIC(12,3)   |

| `first\_halt\_date`              | DATE            |

| `last\_halt\_date`               | DATE            |



Clé logique :



```text

symbol

```



Cet objet est dérivé de `core.nasdaq\_halt\_episode` et des journées de marché considérées par la période analytique.



Une vue matérialisée est privilégiée.



\---



\# 8. Objet `analytics.ticker\_halt\_reason\_metrics`



Cet objet contient les métriques par symbole et par code de raison Nasdaq.



\## Colonnes



| Colonne                | Type PostgreSQL |

| ---------------------- | --------------- |

| `symbol`               | VARCHAR(20)     |

| `reason\_code`          | VARCHAR(20)     |

| `halt\_episodes`        | INTEGER         |

| `avg\_duration\_minutes` | NUMERIC(12,3)   |

| `min\_duration\_minutes` | NUMERIC(12,3)   |

| `max\_duration\_minutes` | NUMERIC(12,3)   |



Clé logique :



```text

PRIMARY KEY (symbol, reason\_code)

```



Cet objet est dérivé de `core.nasdaq\_halt\_episode`.



Une vue matérialisée est privilégiée.



\---



\# 9. Index



Les index suivants sont prévus initialement.



\## `raw.nasdaq\_trade\_halt`



```text

UNIQUE (symbol, halt\_date, halt\_time, reason\_code, market)



INDEX (symbol)

INDEX (halt\_date)

INDEX (reason\_code)

INDEX (symbol, halt\_date)

```



\## `core.nasdaq\_halt\_episode`



```text

INDEX (trade\_halt\_id)

INDEX (symbol)

INDEX (halt\_start)

INDEX (reason\_code)

INDEX (symbol, halt\_start)

```



Les index supplémentaires devront être ajoutés en fonction des requêtes réelles plutôt que par anticipation.



\---



\# 10. Gestion des valeurs booléennes



Les fichiers CSV V0.6 utilisent notamment :



```text

YES

NO

UNKNOWN

```



PostgreSQL doit utiliser autant que possible le type natif :



```text

BOOLEAN

```



avec :



```text

YES     → TRUE

NO      → FALSE

UNKNOWN → NULL

```



Cette convention s'applique notamment à `halt\_at\_close`.



\---



\# 11. Gestion du temps



Les fichiers sources contiennent des dates et heures séparées alors que les épisodes utilisent des timestamps reconstruits.



La couche `raw` conserve cette structure proche de la source :



```text

halt\_date

halt\_time

resumption\_date

resumption\_quote\_time

resumption\_trade\_time

```



La couche `core` utilise :



```text

halt\_start

halt\_end

```



Les règles relatives au fuseau horaire Nasdaq devront être documentées explicitement avant le chargement historique complet.



Aucune conversion implicite de fuseau horaire ne doit être introduite sans validation.



\---



\# 12. Provenance



Les fichiers XML téléchargés depuis Nasdaq demeurent conservés dans :



```text

collectors/nasdaq\_halts/data/raw/nasdaq/

```



Ils constituent la donnée externe originale permettant de reconstruire les datasets PostgreSQL.



Chaque événement PostgreSQL doit pouvoir conserver une référence à son fichier source au moyen de :



```text

source\_file

```



Le contenu RAW ne doit pas être supprimé après ingestion réussie.



\---



\# 13. Reconstruction des données



L'architecture doit permettre le flux suivant :



```text

Nasdaq XML

&#x20;   ↓

RAW XML local

&#x20;   ↓

raw.nasdaq\_trade\_halt

&#x20;   ↓

core.nasdaq\_halt\_episode

&#x20;   ↓

analytics.\*

```



Les objets analytiques ne doivent pas être considérés comme des sources de vérité indépendantes.



Ils doivent pouvoir être supprimés et reconstruits à partir des données `core`.



\---



\# 14. Chargement incrémental



Le chargement quotidien devra :



1\. télécharger les nouvelles données Nasdaq;

2\. conserver le fichier RAW;

3\. normaliser les événements;

4\. insérer uniquement les nouveaux événements;

5\. reconstruire ou mettre à jour les épisodes affectés;

6\. rafraîchir les objets analytiques nécessaires;

7\. enregistrer le résultat de l'exécution;

8\. pouvoir être relancé sans créer de doublons.



L'ingestion doit donc être \*\*idempotente\*\*.



\---



\# 15. Validation V0.6



Le modèle initial a été dérivé du dataset V0.6 existant.



Résultats de validation :



```text

Trade Halt rows             : 744

Duplicate natural keys      : 0



Halt Episode rows           : 744

Duplicate episode IDs       : 0

Unique episode IDs          : 744

```



Tests de non-régression existants :



```text

QVCG : PASS

BCARU: PASS

```



Ces résultats constituent la baseline avant intégration PostgreSQL.



\---



\# 16. Points à valider sur l'historique cinq ans



Le chargement de cinq années de données devra notamment confirmer :



\* unicité réelle de la clé naturelle des événements;

\* relation entre événements et épisodes;

\* gestion des épisodes multi-jours;

\* valeurs possibles de `market`;

\* valeurs possibles de `reason\_code`;

\* valeurs et formats de `pause\_threshold\_price`;

\* présence de valeurs manquantes;

\* cas où aucune reprise n'est disponible;

\* cohérence des timestamps;

\* gestion des changements de symbole;

\* performance des index;

\* volume réel de données.



Le schéma pourra être ajusté avant d'être considéré comme stable pour PROD.



\---



\# 17. Statut



Le présent modèle constitue le \*\*PostgreSQL Data Model V1.0 initial\*\* du Nasdaq Halt Collector.



Il est suffisamment défini pour permettre la création de la première migration SQL :



```text

database/migrations/001\_create\_nasdaq\_halts\_schema.sql

```



La validation définitive du modèle sera effectuée après chargement et analyse de l'historique complet.



