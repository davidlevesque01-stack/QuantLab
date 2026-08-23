# QuantLab --- Nasdaq Halt Collector

## ARCHITECTURE.md

**Version : V0.6**\
**Statut : Architecture de référence du collecteur Nasdaq Halts**\
**Dernière mise à jour : 2026-08-22**

------------------------------------------------------------------------

## 1. Objectif

> Ce document décrit l'architecture spécifique du collecteur Nasdaq Halts.
> L'architecture générale de la plateforme QuantLab est documentée dans
> `../../../docs/architecture.md`.

------------------------------------------------------------------------

## 2. Arborescence de référence

``` text
C:\QuantLab\nasdaq_halts\
│
├── README.md
│
├── .venv\
│
├── config\
│   ├── config.json
│   └── checkpoint.json
│
├── data\
│   ├── raw\
│   │   └── nasdaq\
│   │       ├── historical\
│   │       │   ├── tradehalts_2026-08-01.xml
│   │       │   ├── tradehalts_2026-08-02.xml
│   │       │   └── ...
│   │       ├── latest_tradehalts.xml
│   │       └── tradehalts_<timestamp>.xml
│   │
│   └── processed\
│       ├── tradehalts.csv
│       ├── halt_episodes.csv
│       ├── ticker_halt_daily.csv
│       ├── ticker_halt_metrics.csv
│       └── ticker_halt_reason_metrics.csv
│
├── docs\
│   ├── ARCHITECTURE.md
│   ├── METRICS_SPECIFICATION.md
│   ├── CHANGELOG.md
│   ├── DATA_MODEL.md
│   └── VALIDATION.md
│
└── src\
    ├── collect_historical.py
    ├── calculate_halt_metrics.py
    └── [collect_latest.py / autres collecteurs futurs]
```

L'arborescence ci-dessus représente la cible documentaire. Certains
fichiers pourront être créés progressivement au fil des versions.

------------------------------------------------------------------------

## 3. Architecture logique

``` text
                  NASDAQ TRADER
                       │
                       │ XML
                       ▼
              ┌───────────────────┐
              │     COLLECTE      │
              │ collect_historical│
              └─────────┬─────────┘
                        │
                        ▼
              data/raw/nasdaq/
                 historical/
                        │
                        │ Source de vérité
                        ▼
              ┌───────────────────┐
              │ TRANSFORMATION &  │
              │      CALCUL       │
              │ calculate_halt_   │
              │ metrics.py        │
              └─────────┬─────────┘
                        │
                        ▼
                 data/processed/
                        │
          ┌─────────────┼─────────────┐
          ▼             ▼             ▼
     événements      quotidien     métriques
       HALT            ticker        ticker
```

------------------------------------------------------------------------

## 4. Couche de collecte

### `collect_historical.py`

Responsabilités :

-   interroger la source historique Nasdaq;
-   télécharger les données journée par journée;
-   sauvegarder un fichier XML par date;
-   éviter de télécharger inutilement un fichier déjà présent;
-   gérer les erreurs de collecte;
-   permettre une reprise après interruption;
-   utiliser un délai configurable entre les requêtes.

Format cible :

``` text
tradehalts_YYYY-MM-DD.xml
```

Exemple :

``` text
tradehalts_2026-08-10.xml
```

### Collecte courante

Les fichiers courants, par exemple :

``` text
latest_tradehalts.xml
tradehalts_20260816_175801.xml
```

restent séparés de l'historique journalier.

------------------------------------------------------------------------

## 5. Couche RAW --- source de vérité

Répertoire principal :

``` text
data/raw/nasdaq/historical/
```

Les XML téléchargés depuis Nasdaq constituent la **source de vérité du
système**.

Règles :

1.  ne pas modifier manuellement les XML;
2.  ne pas remplacer un fichier valide sans raison documentée;
3.  conserver les données historiques après traitement;
4.  considérer les CSV comme reconstruisibles à partir des XML.

Cette approche permet de modifier ultérieurement les métriques sans
devoir recollecter cinq années de données.

------------------------------------------------------------------------

## 6. Couche de transformation

### `calculate_halt_metrics.py`

Version de référence actuelle :

``` text
V0.6
```

Responsabilités :

1.  lire tous les XML historiques;
2.  normaliser les champs Nasdaq;
3.  dédupliquer les événements;
4.  construire les HALT Episodes;
5.  calculer les durées;
6.  traiter les épisodes multi-day;
7.  déterminer les HALT actifs à la clôture;
8.  produire les données quotidiennes;
9.  calculer les métriques par ticker;
10. calculer les métriques par raison;
11. exécuter les tests de non-régression.

Le moteur de calcul ne doit pas dépendre d'une connexion Internet.

------------------------------------------------------------------------

## 7. Couche PROCESSED

Répertoire :

``` text
data/processed/
```

### `tradehalts.csv`

Événements Nasdaq nettoyés et dédupliqués.

### `halt_episodes.csv`

Épisodes HALT logiques avec :

-   début;
-   fin;
-   durée;
-   raison;
-   statut de clôture.

### `ticker_halt_daily.csv`

Une ligne par ticker et par journée de marché où au moins un HALT est
présent.

### `ticker_halt_metrics.csv`

Métriques consolidées par ticker.

Exemples :

-   nombre total d'épisodes;
-   nombre de jours HALT;
-   HALT par jour avec HALT;
-   HALT par jour de marché;
-   jours HALT à la clôture;
-   durée moyenne;
-   durée médiane.

### `ticker_halt_reason_metrics.csv`

Métriques regroupées par :

``` text
symbol + reason_code
```

Les définitions officielles des métriques appartiennent à :

``` text
docs/METRICS_SPECIFICATION.md
```

------------------------------------------------------------------------

## 8. Configuration

La configuration doit être séparée du code autant que possible.

### `config.json`

Destiné aux paramètres tels que :

-   URLs Nasdaq;
-   chemins;
-   délai entre requêtes;
-   paramètres de collecte;
-   options d'exécution.

### `checkpoint.json`

Destiné à conserver l'état de progression d'une collecte historique.

Exemple :

``` json
{
    "last_completed_date": "2026-08-10",
    "successful_days": 3,
    "failed_days": 0
}
```

Le checkpoint permet de reprendre une collecte interrompue sans
recommencer depuis le début.

------------------------------------------------------------------------

## 9. Principes d'architecture

### 9.1 Source de vérité

``` text
XML RAW = source de vérité
CSV = données dérivées
```

### 9.2 Reproductibilité

Une même collection de XML, avec la même version du calculateur, doit
produire les mêmes résultats.

### 9.3 Idempotence

Relancer le calculateur ne doit pas créer de doublons ni modifier
arbitrairement les résultats.

### 9.4 Séparation des responsabilités

  Couche             Responsabilité
  ------------------ --------------------
  `src`              Code et logique
  `data/raw`         Données originales
  `data/processed`   Données dérivées
  `config`           Paramètres et état
  `docs`             Documentation

### 9.5 Traçabilité

Les modifications de logique ou de métriques doivent être versionnées et
documentées.

------------------------------------------------------------------------

## 10. Validation V0.6

Jeu de validation actuel :

-   15 fichiers XML;
-   744 événements bruts;
-   744 événements uniques;
-   744 HALT Episodes;
-   235 tickers;
-   322 lignes quotidiennes;
-   10 jours de marché;
-   742 durées calculables.

Tests de non-régression :

### QVCG

``` text
2 épisodes
2 jours HALT
2 jours HALT à la clôture
TEST PASS
```

### BCARU

``` text
12 épisodes
5 jours HALT
1 jour HALT à la clôture
TEST PASS
```

Ces cas servent de référence avant toute modification future du moteur
de calcul.

------------------------------------------------------------------------

## 11. Documentation du projet

La documentation de référence est organisée comme suit :

### `ARCHITECTURE.md`

Décrit comment le système est construit.

### `METRICS_SPECIFICATION.md`

Décrit précisément ce que les métriques signifient et comment elles sont
calculées.

### `DATA_MODEL.md`

Décrira les fichiers, colonnes, types et relations entre les jeux de
données.

### `VALIDATION.md`

Conservera les cas de validation et résultats attendus.

### `CHANGELOG.md`

Conservera l'historique des versions et changements.

### `README.md`

Servira de point d'entrée pour installer et utiliser le projet.

------------------------------------------------------------------------

## 12. Gouvernance documentaire

Lorsqu'une modification est apportée au projet :

  -----------------------------------------------------------------------
  Modification                        Documentation
  ----------------------------------- -----------------------------------
  Nouvelle métrique ou changement de  `METRICS_SPECIFICATION.md`
  calcul                              

  Nouveau script ou changement de     `ARCHITECTURE.md`
  flux                                

  Nouvelle table, fichier ou colonne  `DATA_MODEL.md`

  Nouveau test de référence           `VALIDATION.md`

  Nouvelle version ou correction      `CHANGELOG.md`

  Changement                          `README.md`
  d'installation/utilisation          
  -----------------------------------------------------------------------

La documentation doit évoluer en même temps que le code.

------------------------------------------------------------------------

## 13. État actuel

``` text
V0.6 — VALIDÉE
```

Le moteur de métriques V0.6 constitue la baseline fonctionnelle
actuelle.

La logique validée ne doit pas être modifiée pendant la construction du
collecteur historique V1.0, sauf anomalie confirmée et documentée.

------------------------------------------------------------------------

## 14. Prochaine étape --- V1.0 Historical Builder

Objectif :

> Construire automatiquement et de façon robuste l'historique Nasdaq
> HALT sur cinq ans.

Fonctions prévues :

-   collecte jour par jour;
-   période configurable;
-   délai configurable;
-   reprise automatique;
-   détection des fichiers existants;
-   gestion des échecs;
-   journalisation;
-   contrôle de complétude;
-   recalcul des fichiers processed avec le moteur V0.6.

Le collecteur V1.0 alimentera la couche RAW sans modifier la définition
des métriques V0.6.

------------------------------------------------------------------------

## 15. Architecture collaborative future

L'architecture locale actuelle constitue la première étape.

La cible QuantLab prévoit éventuellement :

``` text
Utilisateur A ─┐
               ├── Git / dépôt de code partagé
Utilisateur B ─┘
                       │
                       ▼
              environnement d'exécution
                       │
                       ▼
                base de données
                    partagée
```

Les données CSV actuelles pourront alors être migrées vers une base de
données centrale sans modifier les principes fondamentaux :

-   source brute conservée;
-   calcul reproductible;
-   code versionné;
-   données analytiques centralisées;
-   accès contrôlé pour les collaborateurs.

Cette évolution fera l'objet d'une version d'architecture distincte.

## 16. Migration vers le monorepo QuantLab

Le collecteur Nasdaq Halts a été migré vers le monorepo QuantLab sous :

`collectors/nasdaq_halts/`

La logique fonctionnelle V0.6 a été conservée.

Le seul changement requis pour la migration a été le remplacement du chemin absolu :

`C:\QuantLab\nasdaq_halts`

par une résolution dynamique basée sur `__file__`.

Validation effectuée après migration :

- Événements bruts : 744
- Événements uniques : 744
- HALT Episodes : 744
- Tickers différents : 235
- Lignes quotidiennes : 322
- Jours de marché : 10
- Durées calculables : 742
- QVCG TEST : PASS
- BCARU TEST : PASS

La migration est considérée comme fonctionnellement équivalente à la baseline V0.6.
