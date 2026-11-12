# Documentation technique – Application GreenTech DPE

## 1. Présentation

GreenTech DPE est une application web développée en Python 3.13 avec Streamlit. Elle sert à explorer les DPE publiés par l'ADEME et à prédire l'étiquette DPE et la consommation d'énergie d'un logement. Elle est fournie sous forme d'image Docker, qui regroupe le code, les modèles, les données et toutes les dépendances : il suffit d'avoir Docker sur son poste pour la faire fonctionner.

## 2. Architecture

```mermaid
flowchart LR
    subgraph EXT["Sources externes"]
        ADEME["API ADEME<br/>DPE existants et neufs"]
        METEO["API Open-Meteo<br/>climat 2019-2023"]
    end

    subgraph DEV["Préparation (hors Docker)"]
        MET["data/meteo.py<br/>climat par département"]
        EXTR["data/extraction.py<br/>collecte et nettoyage"]
        NB["notebooks/<br/>entraînement des modèles"]
    end

    subgraph IMG["Image Docker (python:3.13-slim + Chromium)"]
        RAW[("data/raw/<br/>CSV des DPE et du climat")]
        MOD[("models/<br/>modèles .joblib et .json")]
        UT["app/utils.py<br/>chargement et cache"]
        PAGES["app/app.py + app/vues/<br/>4 pages Streamlit"]
    end

    USER(["Navigateur<br/>port 8501"])

    METEO --> MET --> EXTR
    ADEME --> EXTR
    EXTR --> RAW
    RAW -- lecture --> NB
    NB --> MOD
    RAW --> UT
    MOD --> UT
    UT --> PAGES
    PAGES <--> USER
    PAGES -. réentraînement .-> MOD
```

*Figure 1 – Architecture de l'application, de la collecte des données au navigateur*

Le projet fonctionne en deux temps. Les scripts du dossier `data/` récupèrent d'abord les DPE et le climat, puis les notebooks entraînent les modèles. Les fichiers obtenus sont ensuite copiés dans l'image Docker, où l'application les charge au démarrage.

```text
m2_enedis/
├── app/              # application : app.py, utils.py, vues/ (4 pages), assets/
├── data/             # extraction.py, meteo.py et raw/ (fichiers CSV)
├── models/           # modèles entraînés (.joblib) et leurs métadonnées (.json)
├── notebooks/        # exploration et entraînement des modèles
├── .streamlit/       # thème de l'interface
└── Dockerfile        # instructions de construction de l'image
```

## 3. Installation avec Docker

Avant de commencer, Docker Desktop (Windows ou macOS) ou Docker Engine (Linux) doit être installé et lancé.

**Étape 1 – Construire l'image.** Ouvrez un terminal dans le dossier du projet, là où se trouve le `Dockerfile`, puis lancez :

```bash
docker build -t greentech-dpe .
```

La première construction prend quelques minutes. Si vous avez reçu l'archive `greentech-dpe.tar`, la commande `docker load -i greentech-dpe.tar` remplace cette étape.

**Étape 2 – Démarrer le conteneur.**

```bash
docker run -d --name greentech-dpe -p 8501:8501 greentech-dpe
```

**Étape 3 – Ouvrir l'application.** Une dizaine de secondes plus tard, elle est accessible à l'adresse **http://localhost:8501**. Dans `docker ps`, le statut passe de `health: starting` à `healthy` en une trentaine de secondes.

### Commandes utiles

| Action | Commande |
|---|---|
| Afficher les journaux | `docker logs -f greentech-dpe` |
| Arrêter, puis relancer l'application | `docker stop greentech-dpe`, puis `docker start greentech-dpe` |
| Garder les modèles réentraînés | ajouter `-v greentech-models:/app/models` à la commande `docker run` |
| Exporter l'image pour la partager | `docker save -o greentech-dpe.tar greentech-dpe` |

### Problèmes fréquents

| Problème | Solution |
|---|---|
| Le port 8501 est déjà utilisé | Supprimer le conteneur, le relancer avec `-p 8080:8501` (port du poste, puis port du conteneur) et ouvrir http://localhost:8080 |
| Le nom `greentech-dpe` est déjà pris | Supprimer l'ancien conteneur avec `docker rm -f greentech-dpe`, puis refaire l'étape 2 |
| Une modification du code n'apparaît pas | Reconstruire l'image, supprimer le conteneur et refaire l'étape 2 |

## 4. Packages nécessaires

Les packages de l'application sont installés automatiquement lors de la construction de l'image, avec les versions figées dans `app/requirements.txt` et `models/requirements.txt`.

| Package | Version | Rôle |
|---|---|---|
| Python | 3.13 | Langage de l'application (image `python:3.13-slim`) |
| streamlit | 1.66.1 | Interface web et navigation entre les pages |
| plotly | 7.1.0 | Graphiques et carte interactifs |
| kaleido | 1.5.0 | Export des graphiques en PNG, avec Chromium (inclus dans l'image) |
| pandas | 2.2.3 | Lecture et manipulation des données |
| numpy | 2.1.3 | Calcul numérique |
| scikit-learn | 1.6.1 | Modèles de prédiction (version obligatoire pour les recharger) |
| joblib | 1.6.0 | Chargement des modèles enregistrés |

Les notebooks d'entraînement utilisent en plus requests, prince, matplotlib, catboost et lightgbm.
