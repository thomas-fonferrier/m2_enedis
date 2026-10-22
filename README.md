# Projet Enedis - GreenTech Solutions

Pipeline d’extraction et d’enrichissement des **DPE ADEME** (logements existants et neufs) à l’échelle nationale, avec climat départemental (Open-Meteo).

## Structure

```
m2_enedis/
├── data/
│   ├── extraction.py      # Fetch ADEME + nettoyage + jointure météo + CSV
│   ├── meteo.py           # Fetch Open-Meteo Historical par département
│   └── raw/
│       ├── meteo_departements.csv   # DJU / T° hiver / T° été (101 dép.)
│       └── dpe_n*_e*_n*.csv         # extractions DPE enrichies
├── notebooks/
│   └── exploration_regression.ipynb  # régression conso + régularisation + ACM
├── models/
│   ├── regression_conso.py                 # API prod conso (Elastic Net propriétaire)
│   ├── modele_conso_proprietaire.joblib    # artefact entraîné
│   ├── schema_entrees_conso.json
│   ├── informations_modele_conso.json
│   ├── classification_dpe.py               # API prod étiquette DPE
│   └── modele_dpe_combinaison.joblib
├── requirements.txt
└── README.md
```

## Installation

```bash
cd m2_enedis
pip install -r requirements.txt
```

## 1. Climat départemental (`data/meteo.py`)

Récupère une fois pour tous les départements français (métropole + Corse + DOM) via [Open-Meteo Historical Weather API](https://open-meteo.com/en/docs/historical-weather-api) (ERA5, période 2019–2023).

Variables calculées par département (chef-lieu) :

| Colonne | Description |
|---|---|
| `dju` | Degrés-jours unifiés annuels moyens (base 18 °C, méthode chauffagiste) |
| `t_moy_hiver` | Température moyenne déc–fév (°C) |
| `t_moy_ete` | Température moyenne juin–août (°C) |

```bash
python data/meteo.py
```

- Sortie : `data/raw/meteo_departements.csv`
- Reprise automatique si le CSV est partiel (rate-limit Open-Meteo)
- Les 3 features limitent la multicolinéarité (pas de profil mensuel 12/24 colonnes)

## 2. Extraction DPE (`data/extraction.py`)

Sources ADEME :

- Existants : [dpe03existant](https://data.ademe.fr/datasets/dpe03existant)
- Neufs : [dpe02neuf](https://data.ademe.fr/datasets/dpe02neuf)

### Pipeline `extract_dpe`

1. Fetch national (existants + neufs)
2. **Nettoyage** (`clean_dpe`) :
   - suppression des doublons (`numero_dpe`)
   - conservation des colonnes communes aux deux jeux
   - drop colonnes trop vides (> 70 %) et lignes trop lacunaires (> 30 %)
   - imputation : KNN (numériques) + mode (catégorielles), **par `type_logement`**
3. **Enrichissement météo** : jointure sur `code_departement_ban` → `dju`, `t_moy_hiver`, `t_moy_ete`
4. Sauvegarde CSV : `data/raw/dpe_n{total}_e{existants}_n{neufs}.csv`

La colonne `zone_climatique` DPE (H1a/b/c, H2…, H3) est déjà présente dans les données ADEME ; le climat Open-Meteo la complète par des grandeurs continues.

### Usage

```python
from data.extraction import extract_dpe

df = extract_dpe(n_existants=8000, n_neufs=2000)
# options : clean=True, enrich_meteo=True, save=True
```

```bash
python data/extraction.py
# défaut du __main__ : 500 existants + 200 neufs
```

Si `meteo_departements.csv` est absent, le fetch Open-Meteo est lancé automatiquement au moment de la jointure.

Les logements sans géocodage BAN (`code_departement_ban` manquant) restent sans valeurs météo (NaN).

## 3. Régression — prédire `conso_5_usages_par_m2_ef`

Notebook : `notebooks/exploration_regression.ipynb`  
Jeu : `data/raw/dpe_n700_e500_n200.csv` (~700 DPE demandés ; ~680 lignes après nettoyage).

### Objectif

Prédire la consommation énergétique finale au m² (`conso_5_usages_par_m2_ef`, kWh/m²) à partir des variables DPE + climat (`dju`, `t_moy_hiver`, `t_moy_ete`).

### Préparation des features

| Type | Traitement |
|---|---|
| Numériques | Conservées (hors ids) |
| Ordinales (étiquette DPE/GES, qualités d’isolation, altitude, inertie, période de construction, confort d’été) | Encodage ordinal |
| Autres qualitatives | `get_dummies` (one-hot, `drop_first=True`) |
| Manquants | Médiane estimée sur le **train** uniquement (`SimpleImputer`) |
| Scaling (modèles pénalisés) | `StandardScaler` fit sur le train |

Split : **70 % train / 30 % test** (`random_state=42`) → environ 478 / 205 lignes, ~1770 features après encodage.

### Tests menés

1. **OLS** (`LinearRegression`) — baseline sans pénalité (~1770 features)  
2. **Ridge (L2)** — `GridSearchCV` sur `alpha`, scoring RMSE, CV 5 folds  
3. **Lasso (L1)** — idem  
4. **Elastic Net (L1+L2)** — grille sur `(alpha, l1_ratio)`  
5. **OLS restreinte « propriétaire »** — sous-ensemble de features significatives OLS **et** connues d’un propriétaire  
6. **Régularisation CV sur le modèle propriétaire** — Ridge / Lasso / Elastic Net (même protocole)  
7. **ACM** (`prince.MCA`) sur les qualitatives non ordinales — exploration des associations de modalités

### Résultats — toutes features (échantillon n≈700)

| Modèle | Meilleurs hyperparamètres (CV) | RMSE CV | MAE test | RMSE test | R² test |
|---|---|---|---|---|---|
| OLS | — | — | 4.69 | 9.26 | 0.986 |
| Ridge (L2) | `alpha ≈ 0.53` | 35.9 | 23.8 | 42.1 | 0.709 |
| **Lasso (L1)** | **`alpha ≈ 0.53`** | **11.4** | **4.4** | **8.2** | **0.989** |
| Elastic Net | `alpha ≈ 0.023`, `l1_ratio = 0.8` | 21.9 | 11.9 | 20.8 | 0.929 |

L’ACM n’a pas fait ressortir d’axe ou de groupe d’axes suffisamment interprétable / utile pour la suite modélisation.

### Modèle « propriétaire » (features restreintes)

Objectif : un modèle utilisable en input par un propriétaire, sans variables trop techniques ni leakage (`emission_ges_*`, `conso_*_ep`, `methode_application_dpe`, `inertie_lourde`, `categorie_enr`, `type_energie_n1`).

**Features retenues** (~29 après one-hot) :

| Type | Variables |
|---|---|
| Ordinales / numériques | `etiquette_dpe`, `etiquette_ges`, `qualite_isolation_murs`, `logement_traversant`, `nombre_niveau_immeuble` |
| Qualitatives (dummies) | `type_installation_chauffage`, `type_installation_ecs`, `type_energie_principale_chauffage`, `type_energie_principale_ecs`, `zone_climatique` |

Même split 70/30 (`random_state=42`), imputation médiane + `StandardScaler` pour les modèles pénalisés.

| Modèle | Meilleurs hyperparamètres (CV) | RMSE CV | MAE test | RMSE test | R² test |
|---|---|---|---|---|---|
| OLS restreinte | — | — | 22.0 | 28.5 | 0.867 |
| Ridge (L2) | `alpha ≈ 4.33` | 35.6 | 22.2 | 28.1 | 0.870 |
| Lasso (L1) | `alpha ≈ 0.53` | 35.6 | 22.0 | 27.4 | 0.876 |
| **Elastic Net (L1+L2)** | **`alpha ≈ 0.023`, `l1_ratio = 0.2`** | **35.6** | **22.2** | **28.1** | **0.870** |

Sur ce sous-ensemble, les trois pénalisations sont quasi équivalentes en RMSE CV ; **Elastic Net** est retenu de justesse. Les coefficients les plus forts portent surtout sur `etiquette_ges`, `etiquette_dpe`, les énergies principales (ECS / chauffage) et `qualite_isolation_murs`.

### Choix finaux

- **Toutes features** : régression **Lasso (L1)** (`alpha ≈ 0.53`) — meilleur RMSE CV / test ; sélection automatique adaptée au grand nombre de dummies DPE  
- **Modèle propriétaire** : **Elastic Net** (`alpha ≈ 0.023`, `l1_ratio = 0.2`) — performances proches de Ridge/Lasso, features interprétables et saisissables sans expertise DPE  
- **ACM** : non poursuivie pour l’instant (peu d’intérêt structurel observé)  
- **OLS pleine** : R² élevé mais non régularisé et exposé au leakage (`conso_*_ep`, `emission_ges_*`) ; Lasso reste préférable quand `p ≫ n`

### Pistes d’optimisation ultérieures

- Affiner `alpha` / `l1_ratio` (grilles plus denses autour des optima)  
- Pipeline unique imputer → scaler → modèle en CV (zéro fuite de prétraitement)  
- Retirer d’éventuelles variables de **leakage** restantes sur le modèle toutes features  
- Augmenter la taille d’extraction ADEME pour stabiliser la sélection  
- Enrichir le modèle propriétaire avec d’autres variables « grand public » (surface, année de construction, type de logement)

```bash
# ouvrir / exécuter le notebook
jupyter notebook notebooks/exploration_regression.ipynb
```

## 4. Production — modèle conso « propriétaire »

Modèle retenu pour la prédiction opérationnelle de `conso_5_usages_par_m2_ef` :

- **Elastic Net** (`alpha ≈ 0.023`, `l1_ratio = 0.2`)
- Entrées limitées aux variables qu’une personne lambda peut connaître (étiquette DPE/GES, isolation murs, traversant, étages, type d’installation, énergie principale, zone climatique)
- Module : `models/regression_conso.py`
- Artefact : `models/modele_conso_proprietaire.joblib`

### (Ré)entraîner / exporter

```bash
cd m2_enedis
python -c "from models.regression_conso import entrainer_et_exporter; entrainer_et_exporter()"
# ou : python models/regression_conso.py
```

Sorties : joblib, `informations_modele_conso.json`, `schema_entrees_conso.json`, CSV d’exemples.

Le script évalue sur un split 70/30 (`random_state=42`), puis **réentraîne sur l’ensemble** des logements valides pour l’artefact de production.

### Prédire

```python
from models.regression_conso import charger_modele

modele = charger_modele()
pred = modele.predict({
    "etiquette_dpe": "D",
    "etiquette_ges": "C",
    "qualite_isolation_murs": "moyenne",
    "logement_traversant": 1.0,
    "nombre_niveau_immeuble": 4,
    "type_installation_chauffage": "individuel",
    "type_installation_ecs": "individuel",
    "type_energie_principale_chauffage": "Gaz naturel",
    "type_energie_principale_ecs": "Gaz naturel",
    "zone_climatique": "H1a",
})
# → array de conso_5_usages_par_m2_ef en kWh/m²

modele.coefficients()  # coefficients Elastic Net triés par |coef|
```

Champs absents → NaN puis imputation médiane ; modalités catégorielles inconnues → colonnes one-hot à 0.

## Dépendances

- `pandas`
- `numpy`
- `requests`
- `scikit-learn` (KNNImputer, régression, GridSearchCV)
- `joblib` (sérialisation des modèles)
- `prince` (ACM)
- `matplotlib`
