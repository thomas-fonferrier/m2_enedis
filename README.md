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
├── models/
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

## Dépendances

- `pandas`
- `requests`
- `scikit-learn` (KNNImputer)
