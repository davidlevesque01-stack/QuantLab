# QuantLab — Base de données

## 1. Objectif

La base de données PostgreSQL constitue la source structurée partagée de QuantLab.

Elle permet notamment :

- le stockage centralisé des données structurées;
- l'accès partagé aux mêmes données;
- l'ingestion historique et incrémentale;
- la conservation d'observations sources pertinentes;
- l'enrichissement des événements déjà connus;
- la construction d'un modèle métier normalisé;
- l'automatisation future des traitements;
- une persistance idempotente;
- la protection de l'intégrité référentielle;
- le contrôle des écritures concurrentes coopérantes.

Les fichiers XML Nasdaq demeurent la provenance RAW primaire permettant de reconstruire les données structurées.

Les CSV produits par le pipeline sont des artefacts de validation, diagnostic, non-régression ou export. Ils ne constituent pas la couche d'intégration de production entre le collecteur et PostgreSQL.

---

## 2. Environnement DEV

L'environnement PostgreSQL de référence est hébergé dans Microsoft Azure.

Configuration actuelle :

- Service : Azure Database for PostgreSQL Flexible Server
- Environnement : DEV
- Région : Canada Central
- PostgreSQL : 17
- Compute : Burstable B1ms
- vCPU : 1
- Mémoire : 2 GiB
- Stockage : 32 GiB
- Haute disponibilité : désactivée
- Rétention des sauvegardes : 7 jours
- Accès réseau : public restreint par pare-feu Azure
- TLS : requis
- Authentification : PostgreSQL

Serveur :

```text
quantlab-postgres-dev.postgres.database.azure.com
```

Port :

```text
5432
```

Base principale :

```text
quantlab
```

Aucun mot de passe ou secret ne doit être stocké dans Git, GitHub, la documentation ou les fichiers de configuration versionnés.

---

## 3. Organisation logique

La base `quantlab` utilise trois schémas principaux.

### `raw`

Contient les représentations structurées proches des données sources.

Objets Nasdaq actuels :

```text
raw.nasdaq_trade_halt
raw.nasdaq_resumption
```

### `core`

Contient les objets métier normalisés.

Objets Nasdaq actuels :

```text
core.nasdaq_halt_episode
core.nasdaq_halt_episode_event
```

### `analytics`

Réservé aux vues, vues matérialisées et datasets analytiques dérivés.

Les objets analytiques Nasdaq Halts ne sont pas encore créés.

---

## 4. Version actuelle du modèle

Le modèle PostgreSQL Nasdaq Halt actuel est :

```text
Data Model V1.3
```

La persistance applicative correspondante est :

```text
PostgreSQL Persistence V1.3.2
```

Le modèle distingue explicitement :

```text
observation Nasdaq
HALT RAW canonique
épisode CORE
```

Cette distinction a été rendue nécessaire par la validation de l'historique complet.

---

## 5. Historique des migrations

Fichiers actuels :

```text
001_create_nasdaq_halts_schema.sql
002_core_episode_event.sql
002_fix_nasdaq_halt_close_status.sql
003_update_nasdaq_raw_natural_key_v1_1.sql
004_update_nasdaq_core_natural_key_v1_1.sql
005_create_nasdaq_resumption.sql
006_nasdaq_persistence_v1_2.sql
007_nasdaq_resumption_reason_v1_3.sql
008_create_sec_warrant_xbrl_schema.sql
009_create_sec_shares_outstanding_schema.sql
010_create_sec_8k_warrant_exhibit_schema.sql
011_create_nasdaq_symbol_directory_schema.sql
012_create_sec_8k_warrant_text_extraction_schema.sql
```

### 5.1 Anomalie historique de numérotation

Deux migrations utilisent historiquement le préfixe `002`.

Cette anomalie est documentée et les fichiers ne doivent pas être renommés rétroactivement.

Les futures migrations doivent utiliser un nouveau numéro libre.

### 5.2 Migration 001

Crée les schémas de base et les premières tables Nasdaq.

### 5.3 Migration 002 — relation épisode / RAW

`002_core_episode_event.sql` crée :

```text
core.nasdaq_halt_episode_event
```

afin de représenter la cardinalité :

```text
1 CORE -> N RAW
```

### 5.4 Migration 002 — statut de clôture

`002_fix_nasdaq_halt_close_status.sql` remplace :

```text
halt_at_close BOOLEAN
```

par :

```text
halt_close_status VARCHAR(20)
```

Valeurs supportées :

```text
YES
NO
UNKNOWN
MULTI_DAY
```

### 5.5 Migration 003

`003_update_nasdaq_raw_natural_key_v1_1.sql` correspond à l'évolution intermédiaire RAW V1.1.

### 5.6 Migration 004

`004_update_nasdaq_core_natural_key_v1_1.sql` correspond à l'identité CORE V1.1 :

```text
symbol
market
reason_code
halt_start
```

### 5.7 Migration 005

`005_create_nasdaq_resumption.sql` crée :

```text
raw.nasdaq_resumption
```

### 5.8 Migration 006

`006_nasdaq_persistence_v1_2.sql` aligne le schéma sur le modèle V1.2 validé.

Elle :

- consolide les doublons RAW selon la clé V1.2;
- protège et réoriente les relations CORE → RAW;
- applique la clé naturelle RAW V1.2;
- applique la clé naturelle CORE V1.2;
- déduplique les observations de reprise;
- applique `UNIQUE NULLS NOT DISTINCT`;
- exécute des validations d'intégrité;
- utilise le verrou Nasdaq QuantLab `(716203, 1)`;
- s'exécute dans une transaction.

### 5.9 Migration 007

`007_nasdaq_resumption_reason_v1_3.sql` introduit la séparation V1.3 entre motif du HALT et motif/action de reprise.

Elle :

- ajoute `raw.nasdaq_resumption.resumption_reason_code VARCHAR(20)`;
- rend `raw.nasdaq_resumption.reason_code` nullable;
- remplace l'identité d'observation par une identité à neuf champs;
- conserve `reason_code` et `resumption_reason_code` comme contextes distincts;
- utilise `UNIQUE NULLS NOT DISTINCT`;
- reconstruit l'index de rapprochement HALT sur `(symbol, market, halt_date, halt_time)`;
- ajoute un index sur `resumption_reason_code`;
- valide l'absence de doublons selon la nouvelle identité;
- valide qu'une observation ne possède pas simultanément les deux reason fields à `NULL`.

La migration 007 a été appliquée avec succès en DEV le 2026-09-06.

### 5.10 Migration 008

`008_create_sec_warrant_xbrl_schema.sql` crée :

```text
raw.sec_warrant_xbrl_fact
```

Capture RAW immuable des faits XBRL us-gaap dont le concept commence par
`ClassOfWarrantOrRight` (exercise price, quantité, etc.), retournés par
l'API SEC EDGAR company-facts pour un CIK donné — première brique du
pipeline SEC-natif de découverte des warrants (SEC-06). Ne couvre que les
émetteurs qui balisent leurs warrants dimensionnellement en XBRL
(typiquement les ex-SPAC) ; le repli sur le texte des filings pour les
émetteurs non taggués reste un travail de suivi distinct.

Elle :

- utilise `UNIQUE NULLS NOT DISTINCT` (les faits « instant » n'ont pas de
  `period_start`, qui doit tout de même participer à l'identité de
  l'observation);
- réutilise le verrou QuantLab `(716203, 3)` côté écrivain Python
  (`warrants_postgresql.persist_sec_warrant_xbrl_facts`), sans verrou dans
  la migration elle-même (simple création de table, aucune donnée
  existante à migrer).

La migration 008 a été appliquée avec succès en DEV le 2026-09-11.

### 5.11 Migration 009

`009_create_sec_shares_outstanding_schema.sql` crée :

```text
raw.sec_shares_outstanding_fact
```

Même structure que `raw.sec_warrant_xbrl_fact` (§5.10), mais pour le fait
`dei:EntityCommonStockSharesOutstanding` (SEC-01 / SEC-02) — présent sur la
page de couverture de tout déposant 10-K/10-Q, donc une couverture
attendue bien plus large que les warrants. Réutilise le même verrou
QuantLab, avec un `objid` distinct : `(716203, 4)`.

### 5.12 Migration 010

`010_create_sec_8k_warrant_exhibit_schema.sql` crée :

```text
raw.sec_8k_warrant_exhibit
```

Découverte (pas encore extraction) des exhibits de 8-K probablement liés à
un warrant (SEC-09) — le repli pour les warrants invisibles au pipeline
XBRL de la migration 008, parce qu'un 8-K annonçant un placement privé ne
porte presque jamais de balisage `ClassOfWarrantOrRight`. Capture le lien
direct vers l'exhibit (ex. « FORM OF PRE-FUNDED WARRANT »), pas encore les
modalités numériques extraites de son texte légal — travail de suivi
distinct.

Cas réel validé (TNON, 2026-09-11) : le warrant d'août 2026 vu sur
DilutionTracker (exercise price $5.02, 1 058 517 unités, expiration
2031-08-27) est absent de `raw.sec_warrant_xbrl_fact` mais son exhibit
source (8-K du 2026-08-31, `EX-4.1`) est désormais capturé ici.

Réutilise le même verrou QuantLab, avec un `objid` distinct : `(716203, 5)`.

### 5.13 Migration 011

`011_create_nasdaq_symbol_directory_schema.sql` crée :

```text
raw.nasdaq_symbol_directory
```

Capture point-in-time des deux fichiers annuaire quotidiens de Nasdaq
Trader (`nasdaqlisted.txt`, `otherlisted.txt`, ~13 000 titres au total) —
l'univers de référence des sociétés/titres à suivre (SEC-03). Nasdaq
Trader n'apporte que l'identité/le listing, jamais les modalités de
warrants.

Elle :

- insère un nouveau snapshot horodaté à chaque exécution plutôt que de
  mettre à jour en place (principe point-in-time du projet) ;
- conserve le payload JSONB brut de chaque ligne, les deux fichiers
  n'ayant pas le même jeu de colonnes ;
- réutilise le même verrou QuantLab, avec un `objid` distinct :
  `(716203, 6)`.

### 5.14 Migration 012

`012_create_sec_8k_warrant_text_extraction_schema.sql` crée :

```text
raw.sec_8k_warrant_text_extraction
```

Extraction heuristique par expressions régulières des modalités de
warrants (quantité, prix d'exercice, expiration) trouvées dans le texte
du **corps** du 8-K (SEC-10) — découverte importante lors de la
validation TNON : les exhibits « FORM OF ... WARRANT » (capturés par
SEC-09) sont des **gabarits vides** (`[*]`, `______`), les vraies
valeurs vivent dans le récit de l'Item 1.01. Validé sur ce cas réel :
« Series A warrants to purchase up to an aggregate of 1,058,517 shares
... exercise price of $5.02 per share ... will expire five (5) years
from issuance » — correspond exactement à DilutionTracker.

Elle :

- conserve `raw_snippet` (le texte source exact) sur chaque ligne —
  cette extraction est heuristique, jamais une valeur canonique sans
  vérification humaine ;
- contrainte `kind` à `share_quantity` / `exercise_price` /
  `expiration_years` (`CHECK`) ;
- réutilise le même verrou QuantLab, avec un `objid` distinct :
  `(716203, 7)`.

---

## 6. Exécution des migrations

Les migrations sont stockées sous :

```text
database/migrations/
```

Elles doivent être :

1. versionnées dans Git;
2. revues;
3. testées en DEV;
4. documentées;
5. exécutées dans l'ordre historique approprié;
6. conservées sans modification rétroactive après application.

Commande de référence :

```powershell
psql "host=quantlab-postgres-dev.postgres.database.azure.com port=5432 dbname=quantlab user=quantlab_admin sslmode=require" `
    -v ON_ERROR_STOP=1 `
    -f .\database\migrations\<migration>.sql
```

La migration 006 a été validée intégralement dans une copie de test terminée par `ROLLBACK`.

---

## 7. Modèle RAW canonique

### Table

```text
raw.nasdaq_trade_halt
```

Cette table représente un HALT Nasdaq canonique.

### Clé primaire

```text
id BIGINT
```

### Clé naturelle V1.2

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

### Sémantique

Plusieurs observations Nasdaq peuvent représenter le même HALT naturel.

Le modèle applique donc :

```text
N observations Nasdaq
        |
        v
1 raw.nasdaq_trade_halt
```

Les champs de reprise de la ligne canonique sont sélectionnés selon la politique V1.2 décrite plus bas.

---

## 8. Observations RAW de reprise

### Table

```text
raw.nasdaq_resumption
```

Cette table conserve les observations de reprise distinctes.

### Identité de l'observation

```text
symbol
market
halt_date
halt_time
reason_code
resumption_reason_code
resumption_date
resumption_quote_time
resumption_trade_time
```

Contrainte :

```text
uq_nasdaq_resumption_observation
```

Elle utilise PostgreSQL :

```sql
UNIQUE NULLS NOT DISTINCT
```

Cette règle est nécessaire parce que `resumption_quote_time` et `resumption_trade_time` peuvent être `NULL`.

Sans `NULLS NOT DISTINCT`, plusieurs observations identiques contenant des `NULL` pourraient être réinsérées.

Les observations invalides ou partielles ne sont pas supprimées simplement parce qu'elles ne sont pas choisies comme reprise canonique.

---

## 9. Déduplication Python et clé RAW

La déduplication Python représente des observations Nasdaq distinctes.

Elle n'est pas équivalente à la clé naturelle PostgreSQL de `raw.nasdaq_trade_halt`.

Cette différence est intentionnelle.

```text
unique_events
    |
    +----> raw.nasdaq_resumption
    |       observations distinctes
    |
    v
agrégation par clé RAW V1.2
    |
    v
raw.nasdaq_trade_halt
```

L'historique complet a confirmé que plusieurs observations distinctes peuvent appartenir au même HALT RAW.

---

## 10. Politique de reprise canonique

Les champs de reprise du HALT canonique sont sélectionnés à partir d'une seule observation.

Ils ne sont pas combinés artificiellement entre plusieurs observations.

### Rang 2 — complète valide

Une reprise est considérée complète et valide lorsque le `halt_end` construit respecte :

```text
halt_end >= halt_start
```

### Rang 1 — partielle admissible

L'observation contient une information de reprise utile mais ne permet pas encore de construire une reprise complète.

### Rang 0 — non exploitable ou invalide

Inclut :

- absence de reprise exploitable;
- reprise temporellement impossible;
- `halt_end < halt_start`.

### Sélection

La meilleure observation disponible est sélectionnée.

Lorsqu'il existe plusieurs observations complètes valides, la plus tardive est choisie de manière déterministe.

Les champs `resumption_date`, `resumption_quote_time` et `resumption_trade_time` sont toujours pris atomiquement depuis la même observation.

### Cas entièrement invalides

Si toutes les observations disponibles sont invalides, la ligne `raw.nasdaq_trade_halt` conserve ses champs de reprise canoniques à `NULL`.

Les observations sources demeurent toutefois dans `raw.nasdaq_resumption`.

Cinq cas historiques entièrement invalides ont été validés selon cette règle.

---

## 11. Modèle CORE V1.2

### Table

```text
core.nasdaq_halt_episode
```

### Identité naturelle

```text
symbol
market
halt_start
```

Contrainte :

```text
uq_nasdaq_halt_episode_natural_key
```

### `reason_code`

En V1.2, `reason_code` est descriptif.

Il ne fait plus partie de l'identité CORE.

Cette règle a notamment été validée avec BCARU le 12 janvier 2026, où plusieurs `reason_code` peuvent se rapporter au même `halt_start`.

---

## 12. Relation CORE → RAW

La relation explicite est stockée dans :

```text
core.nasdaq_halt_episode_event
```

Elle permet :

```text
1 épisode CORE -> N événements RAW
```

La paire suivante est unique :

```text
episode_id
trade_halt_id
```

Le champ `core.nasdaq_halt_episode.trade_halt_id` reste présent comme référence associée, mais la table de relation représente la cardinalité complète.

---

## 13. Statut de clôture

Champ :

```text
halt_close_status
```

Valeurs supportées :

```text
YES
NO
UNKNOWN
MULTI_DAY
```

Les statuts finaux `YES`, `NO` et `MULTI_DAY` sont protégés contre une régression ultérieure vers `UNKNOWN`.

Une correction entrante finale peut toutefois remplacer une valeur finale lorsque la nouvelle observation est considérée valide.

---

## 14. Provenance

Les fichiers XML historiques utilisent notamment :

```text
tradehalts_YYYY-MM-DD.xml
```

Les collectes live utilisent :

```text
tradehalts_live_YYYYMMDDTHHMMSSZ.xml
```

`latest_tradehalts.xml` peut exister comme copie pratique, mais n'est pas la provenance immuable.

`source_file` permet de conserver une référence vers le fichier source structuré.

Les observations de reprise conservent également leur provenance lorsque disponible.

---

## 15. Précision temporelle

Les timestamps fractionnaires Nasdaq sont préservés à travers :

```text
Nasdaq XML
-> Python
-> PostgreSQL
```

Les colonnes CORE utilisent actuellement `TIMESTAMP` sans fuseau horaire.

La sémantique précise du fuseau horaire Nasdaq reste à formaliser avant certaines utilisations analytiques avancées.

---

## 16. Persistance PostgreSQL V1.3

Module :

```text
collectors/nasdaq_halts/src/nasdaq_postgresql.py
```

Version :

```text
VERSION = "1.3.2"
```

Utilisé notamment par :

```text
calculate_halt_metrics.py
nasdaq_halt_collector.py
```

Flux :

```text
XML RAW
   |
   v
Parsing / Normalisation
   |
   v
Observations distinctes
   |
   +--------------------------+
   |                          |
   v                          v
RAW HALT canonique       Observations de reprise
raw.nasdaq_trade_halt    raw.nasdaq_resumption
   |
   v
Construction des épisodes
   |
   v
core.nasdaq_halt_episode
   |
   v
core.nasdaq_halt_episode_event
```

Les CSV ne sont pas utilisés comme intermédiaires PostgreSQL de production.

---

## 17. Writer RAW V1.2

Le writer RAW :

- agrège les observations par clé naturelle RAW;
- sélectionne la reprise canonique;
- recherche les lignes existantes;
- distingue `inserted`, `updated`, `unchanged`;
- protège les valeurs connues contre les NULL entrants;
- conserve l'identifiant PostgreSQL;
- conserve la provenance appropriée;
- retourne les identifiants RAW nécessaires à CORE.

Réexécution complète validée :

```text
RAW inserted  : 0
RAW updated   : 0
RAW unchanged : 68072
```

---

## 18. Writer RESUMPTION V1.3

Le writer `raw.nasdaq_resumption` :

- conserve les observations distinctes;
- accepte un contexte HALT `reason_code` optionnel;
- accepte un contexte de reprise `resumption_reason_code` optionnel;
- exige qu'au moins un des deux contextes de raison soit présent;
- ignore les événements sans `resumption_date`;
- déduplique en mémoire;
- utilise `ON CONFLICT` sur l'identité V1.3 à neuf champs;
- s'appuie sur `UNIQUE NULLS NOT DISTINCT`;
- conserve les observations invalides comme provenance.

Le chemin dédié `persist_nasdaq_resumptions()` acquiert le même advisory lock que la persistance HALT,
persiste les observations `resumedate`, puis enrichit les HALTs RAW et épisodes CORE existants.
Il ne crée pas un HALT à partir du seul flux `resumedate` et ne remplace jamais le `reason_code` du HALT.

Réexécution complète validée :

```text
RESUMPTION inserted : 0
RESUMPTION existing : 68147
```

---

## 19. Writer CORE V1.2

Le writer CORE :

- applique l'identité `(symbol, market, halt_start)`;
- traite `reason_code` comme descriptif;
- insère les épisodes absents;
- enrichit les épisodes existants;
- protège les valeurs connues;
- protège les statuts finaux;
- maintient la relation CORE → RAW;
- valide l'intégrité relationnelle.

Réexécution complète validée :

```text
CORE inserted  : 0
CORE updated   : 0
CORE unchanged : 68017
```

---

## 20. Transaction

RAW, RESUMPTION, CORE et relations sont persistés dans une transaction commune :

```text
BEGIN
  |
  +-- advisory lock
  +-- RAW
  +-- RESUMPTION
  +-- CORE
  +-- relations CORE -> RAW
  |
COMMIT
```

En cas d'erreur :

```text
ROLLBACK
```

Une erreur tardive ne doit pas laisser une opération partielle considérée comme réussie.

---

## 21. Concurrence

La persistance V1.2 acquiert :

```sql
pg_advisory_xact_lock(716203, 1)
```

Clé réservée :

```text
(716203, 1)
```

Le verrou est transactionnel.

Il est acquis avant les lectures/écritures Nasdaq et libéré automatiquement au `COMMIT` ou au `ROLLBACK`.

La migration 006 utilise le même verrou.

Le composant warrants réserve `(716203, 3)` (`classid` partagé, `objid`
distinct) pour la capture RAW des faits XBRL de warrants (voir §5.10), et
`(716203, 4)` pour la capture RAW des shares outstanding (§5.11), et
`(716203, 5)` pour la découverte d'exhibits de 8-K liés à des warrants
(§5.12), et `(716203, 6)` pour la capture de l'annuaire Nasdaq (§5.13), et
`(716203, 7)` pour l'extraction texte des modalités de warrants (§5.14).
`objid = 2` est réservé à la capture RAW DilutionTracker (à venir), afin
de conserver un registre cohérent des verrous entre les sources.

Un test avec deux connexions PostgreSQL indépendantes a validé qu'une seconde transaction attend la libération du verrou.

Résultat de référence :

```text
holder: lock acquired
holder: transaction completed
waiter: lock acquired after 5.03 seconds
waiter: transaction completed
```

Les contraintes PostgreSQL restent la protection d'intégrité finale.

---

## 22. Validation historique complète

Période :

```text
2020-01-01 -> 2026-08-28
```

Fichiers XML :

```text
2432
```

Jours de marché observés :

```text
1738
```

Résultats :

```text
Événements bruts       : 69186
Événements uniques     : 68170
HALT RAW canoniques    : 68072
HALT Episodes CORE     : 68017
Tickers différents     : 9718
Lignes quotidiennes    : 50000
Durées calculables     : 67983
```

Statuts :

```text
YES       : 1777
NO        : 62902
UNKNOWN   : 34
```

---

## 23. Validation des identités

Résultats structurels :

```text
Observations Python uniques : 68170
Clés RAW V1.2               : 68072
CORE episodes               : 68017
```

La différence entre observations Python et RAW est attendue.

Elle correspond notamment aux HALTs comportant plusieurs observations partielles ou complètes pour une même clé RAW.

---

## 24. Idempotence V1.2

Réexécution complète de référence :

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

---

## 25. BCARU

Le test BCARU utilise désormais un fixture historique fixe jusqu'au :

```text
2026-08-27
```

Il valide :

```text
21 épisodes CORE
13 dates historiques
```

Il vérifie également le statut de clôture pour BCARU au 2026-08-03.

Les données BCARU ont confirmé :

- plusieurs observations partielles et complètes pour un même HALT;
- plusieurs HALTs le même jour;
- T1/T2/T3 sur un même `halt_start`;
- la nécessité de retirer `reason_code` de l'identité CORE.

---

## 26. Observations invalides

Cinq clés historiques où toutes les observations de reprise étaient invalides ont été validées.

La représentation canonique dans `raw.nasdaq_trade_halt` conserve les champs de reprise à `NULL`.

Les observations sources invalides restent présentes dans `raw.nasdaq_resumption`.

Cette séparation garantit à la fois une représentation canonique exploitable et la fidélité à la source.

---

## 27. Intégrité référentielle

Les validations suivantes retournent zéro anomalie :

```text
broken_episode_raw_refs        : 0
broken_relation_episode_refs   : 0
broken_relation_raw_refs       : 0
duplicate episode/raw pairs    : 0
```

La migration 006 contient également des validations correspondantes avant `COMMIT`.

---

## 28. Accès applicatif

Rôle :

```text
quantlab_collector
```

Type :

```text
NOLOGIN
```

Compte DEV :

```text
quantlab_collector_dev
```

La connectivité commune est centralisée sous :

```text
shared/database/
```

Dépendance :

```text
psycopg[binary]>=3.3,<4
```

Variables :

```text
QUANTLAB_DB_HOST
QUANTLAB_DB_PORT
QUANTLAB_DB_NAME
QUANTLAB_DB_USER
QUANTLAB_DB_PASSWORD
```

Aucun secret ne doit être versionné.

---

## 29. Loader CSV transitoire

Le loader demeure disponible :

```text
collectors/nasdaq_halts/src/load_postgresql.py
```

Il a servi à la validation initiale de PostgreSQL.

Il est conservé comme outil de migration/validation.

Il n'est pas le chemin de production.

Chemin de référence :

```text
XML
-> Python
-> PostgreSQL RAW
-> PostgreSQL CORE
```

avec conservation séparée des observations de reprise.

---

## 30. Requêtes SQL

Répertoire :

```text
database/queries/
```

Sous-répertoire Nasdaq :

```text
database/queries/nasdaq_halts/
```

Ces requêtes servent à l'exploration, la validation, le diagnostic, les contrôles d'intégrité et la provenance.

---

## 31. Analytics

Les objets analytiques PostgreSQL Nasdaq ne sont pas encore créés.

Objets conceptuels :

```text
analytics.ticker_halt_daily
analytics.ticker_halt_metrics
analytics.ticker_halt_reason_metrics
```

Les calculs PostgreSQL devront être comparés aux métriques Python validées.

Le calendrier officiel de marché doit être correctement modélisé avant la certification de métriques dépendantes du nombre de jours de marché.

Aucun numéro de migration analytics n'est actuellement réservé.

---

## 32. Sauvegardes

L'environnement Azure DEV utilise actuellement une rétention gérée de 7 jours.

Une procédure QuantLab complète doit encore être définie et testée pour :

```text
pg_dump
pg_restore
restauration
validation post-restauration
```

---

## 33. Sécurité

Principes :

- TLS requis;
- pare-feu Azure;
- aucun secret dans Git;
- compte administrateur réservé aux opérations administratives;
- rôle applicatif distinct;
- compte DEV applicatif distinct;
- variables d'environnement pour les paramètres sensibles.

Avant PROD, QuantLab devra définir la gestion centralisée des secrets, la rotation des identifiants, le réseau PROD, l'audit des privilèges et les procédures de restauration.

---

## 34. Encodage

Le dépôt contient :

```text
.editorconfig
```

avec :

```text
charset = utf-8
```

Sous PowerShell 5.1, `Set-Content -Encoding utf8` peut écrire un BOM UTF-8.

Pour les fichiers nécessitant UTF-8 sans BOM, notamment les migrations SQL, utiliser un writer explicite :

```powershell
$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
```

PowerShell 7 sera évalué séparément après stabilisation de ce checkpoint.

---

## 35. État actuel

État validé :

```text
Data Model V1.3
PostgreSQL Persistence V1.3.2
Migration 007 appliquée en DEV
```

Le backfill historique `resumedate` 2020-2026 est terminé au 2026-09-06.

Checkpoint du corpus complémentaire :

```text
Fichiers XML             : 2 435
Observations XML         : 69 211
Identités V1.3 uniques   : 68 195
Observations dupliquées  : 1 016
```

État DEV après backfill et non-régression :

```text
raw.nasdaq_trade_halt          : 68107
raw.nasdaq_resumption          : 136365
core.nasdaq_halt_episode       : 68017
core.nasdaq_halt_episode_event : 68072
```

`raw.nasdaq_resumption` contient les contextes HALT historiques et RESUMPTION du corpus `resumedate`; son total n'est donc pas un nombre d'épisodes CORE.

Validations :

```text
Historique complet                 : PASS
RAW V1.2 identity                  : PASS
RESUMPTION observations            : PASS
CORE V1.2 identity                 : PASS
CORE -> RAW relationships          : PASS
Referential integrity              : PASS
Sequential idempotence             : PASS
Concurrency advisory lock          : PASS
Migration 006 rollback test        : PASS
Canonical resumption policy        : PASS
Invalid-resumption preservation    : PASS
QVCG regression                    : PASS
BCARU historical fixture           : PASS
Fractional timestamps              : PASS
Historical resumedate backfill        : PASS
V1.3 resumption idempotence           : PASS
V1.3 SQL non-regression               : PASS
V1.3.1 normal loader rollback         : PASS
GPUS integration                      : PASS
Analytics tests                       : 69/69 PASS
Complete test suite                   : 70/70 PASS
```

Travaux encore ouverts :

- calendrier officiel de marché;
- analytics PostgreSQL;
- sauvegarde / restauration;
- orchestration centralisée;
- exécution planifiée et à la demande;
- préparation TEST / PROD;
- stratégie de gestion des secrets;
- formalisation complète de la timezone Nasdaq.

Le champ `core.nasdaq_halt_episode.market` reste physiquement nullable, même si les données validées actuelles ne contiennent pas de `NULL`.

Comme `market` participe à l'identité CORE V1.2, un futur durcissement vers `NOT NULL` pourra être envisagé par migration dédiée après validation explicite.


---

## 36. Cas de référence GPUS — V1.3

GPUS valide la nécessité de séparer les deux contextes de raison :

```text
symbol                  : GPUS
market RAW              : A
market CORE             : AMEX
halt_start              : 2026-08-14 14:15:13.698
HALT reason_code        : H11
resumption_reason_code  : T3
halt_end                : 2026-08-25 09:00:00
halt_close_status       : MULTI_DAY
CORE episodes           : 1
```

Le flux `haltdate` fournissait le HALT H11 sans reprise.
Le flux complémentaire `resumedate` a fourni la reprise T3.
La persistance V1.3.2 a enrichi le RAW et le CORE existants sans modifier le motif H11 et sans créer un second épisode.

---

## 37. Limitation historique connue — reason_code final

Certains snapshots historiques `haltdate` peuvent contenir l'état/action final observé plutôt que le motif HALT initial. Certains épisodes CORE historiques portent donc notamment `T3` dans `reason_code`.

Ces épisodes sont conservés. V1.3 ne lance pas de reconstruction globale des motifs HALT historiques; cette reconstruction constitue un chantier distinct.

Règle analytique V1.3 :

```text
ALL = tous les épisodes CORE admissibles
```

Lorsque `ALL` est sélectionné, aucun prédicat `reason_code` ne doit être appliqué. Les épisodes historiques portant `T3` restent donc inclus dans les analyses globales.
