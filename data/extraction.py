"""Extraction des DPE ADEME (logements existants et neufs).

API docs :
- https://data.ademe.fr/datasets/dpe03existant/api-doc
- https://data.ademe.fr/datasets/dpe02neuf/api-doc
(anciens slugs : dpe-v2-logements-existants / dpe-v2-logements-neufs)
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import requests
from sklearn.impute import KNNImputer

URL_EXISTANTS = "https://data.ademe.fr/data-fair/api/v1/datasets/dpe03existant/lines"
URL_NEUFS = "https://data.ademe.fr/data-fair/api/v1/datasets/dpe02neuf/lines"

PAGE_SIZE = 1000
DATA_DIR = Path(__file__).resolve().parent / "raw"

# Colonnes encore trop vides après intersection des schémas
COL_MISSING_THRESH = 0.70
# Lignes trop lacunaires → drop (KNN peu fiable au-delà)
ROW_MISSING_THRESH = 0.30
KNN_NEIGHBORS = 5


def fetch_dpe(url: str, n: int, type_logement: str) -> pd.DataFrame:
    """Récupère `n` DPE page par page depuis l'API ADEME."""
    records = []
    page = 1

    while len(records) < n:
        size = min(PAGE_SIZE, n - len(records))
        response = requests.get(url, params={"size": size, "page": page}, timeout=60)
        response.raise_for_status()

        results = response.json().get("results", [])
        if not results:
            break

        records.extend(results)
        page += 1

    df = pd.DataFrame(records[:n])
    df["type_logement"] = type_logement
    return df


def _drop_duplicates(df: pd.DataFrame) -> pd.DataFrame:
    """Supprime les doublons (numero_dpe prioritaire, puis lignes identiques)."""
    before = len(df)
    if "numero_dpe" in df.columns:
        df = df.drop_duplicates(subset=["numero_dpe"], keep="first")
    df = df.drop_duplicates(keep="first")
    removed = before - len(df)
    if removed:
        print(f"Doublons supprimés : {removed}")
    return df.reset_index(drop=True)


def _keep_common_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Ne garde que les colonnes présentes dans les deux jeux (existant ∩ neuf).

    Les NaN « structurels » (colonne absente d'un schéma) ne sont pas de la
    donnée manquante : on les évite en retirant les colonnes propres à un type.
    """
    if "type_logement" not in df.columns:
        return df

    types = df["type_logement"].dropna().unique()
    if len(types) < 2:
        return df

    col_sets = [set(df.loc[df["type_logement"] == t].dropna(axis=1, how="all").columns) for t in types]
    shared = set.intersection(*col_sets)
    shared.add("type_logement")

    dropped = sorted(set(df.columns) - shared)
    if dropped:
        print(f"Colonnes propres à un seul jeu supprimées : {len(dropped)}")
    return df[sorted(shared)].copy()


def _drop_sparse_columns(df: pd.DataFrame, thresh: float = COL_MISSING_THRESH) -> pd.DataFrame:
    """Supprime les colonnes encore trop souvent vides."""
    protect = {c for c in ("type_logement", "numero_dpe", "_id") if c in df.columns}
    miss_rate = df.isna().mean()
    keep = [c for c in df.columns if c in protect or miss_rate[c] <= thresh]
    dropped = len(df.columns) - len(keep)
    if dropped:
        print(f"Colonnes trop vides (> {thresh:.0%}) : {dropped}")
    return df[keep]


def _drop_sparse_rows(df: pd.DataFrame, thresh: float = ROW_MISSING_THRESH) -> pd.DataFrame:
    """Supprime les lignes trop lacunaires pour une imputation KNN fiable."""
    # Ne pas compter les identifiants / labels dans le taux de lacunes
    feature_cols = [c for c in df.columns if c not in {"_id", "_score", "numero_dpe", "type_logement"}]
    if not feature_cols:
        return df.reset_index(drop=True)

    row_miss = df[feature_cols].isna().mean(axis=1)
    mask = row_miss <= thresh
    removed = int((~mask).sum())
    if removed:
        print(f"Lignes trop lacunaires (> {thresh:.0%}) : {removed}")
    return df.loc[mask].reset_index(drop=True)


def _impute_missing(df: pd.DataFrame, n_neighbors: int = KNN_NEIGHBORS) -> pd.DataFrame:
    """KNN sur les numériques ; mode sur les catégorielles restantes."""
    df = df.copy()
    skip = {c for c in ("_id", "_score", "numero_dpe", "type_logement") if c in df.columns}

    num_cols = [
        c
        for c in df.select_dtypes(include="number").columns
        if c not in skip and df[c].isna().any()
    ]
    cat_cols = [
        c
        for c in df.select_dtypes(exclude="number").columns
        if c not in skip and df[c].isna().any()
    ]

    if num_cols:
        k = min(n_neighbors, max(1, len(df) - 1))
        imputer = KNNImputer(n_neighbors=k)
        df[num_cols] = imputer.fit_transform(df[num_cols])
        print(f"  KNN : {len(num_cols)} colonnes numériques (k={k})")

    for col in cat_cols:
        mode = df[col].mode(dropna=True)
        fill_value = mode.iloc[0] if len(mode) else "Inconnu"
        df[col] = df[col].fillna(fill_value)
    if cat_cols:
        print(f"  Mode : {len(cat_cols)} colonnes catégorielles")

    return df


def clean_dpe(
    df: pd.DataFrame,
    col_missing_thresh: float = COL_MISSING_THRESH,
    row_missing_thresh: float = ROW_MISSING_THRESH,
    n_neighbors: int = KNN_NEIGHBORS,
) -> pd.DataFrame:
    """Dédoublonnage + colonnes communes + drop lacunes + imputation.

    Stratégie :
    1. Supprimer les doublons (`numero_dpe`, puis lignes complètes).
    2. Ne garder que les colonnes communes aux deux APIs (existant ∩ neuf).
    3. Drop colonnes encore trop vides, puis lignes trop lacunaires.
    4. Imputer le reste : KNN (numériques) + mode (catégorielles),
       **par type_logement** pour que les voisins restent cohérents.
    """
    print(f"Avant nettoyage : {df.shape}")
    df = _drop_duplicates(df)
    df = _keep_common_columns(df)
    df = _drop_sparse_columns(df, thresh=col_missing_thresh)
    df = _drop_sparse_rows(df, thresh=row_missing_thresh)

    if df.empty:
        print("Après nettoyage : (0 lignes)")
        return df

    # Imputation par type : un neuf ne doit pas servir de voisin à un existant
    parts: list[pd.DataFrame] = []
    for type_logement, group in df.groupby("type_logement", sort=False):
        print(f"Imputation « {type_logement} » ({len(group)} lignes)…")
        parts.append(_impute_missing(group.copy(), n_neighbors=n_neighbors))

    result = pd.concat(parts, ignore_index=True, sort=False)
    print(f"Après nettoyage : {result.shape} | NaN restants : {int(result.isna().sum().sum())}")
    return result


def save_dpe(
    df: pd.DataFrame,
    n_existants: int,
    n_neufs: int,
    out_dir: Path | str = DATA_DIR,
) -> Path:
    """Sauvegarde le DataFrame en CSV ; le nom inclut la taille d'échantillon."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    n_total = n_existants + n_neufs
    path = out_dir / f"dpe_n{n_total}_e{n_existants}_n{n_neufs}.csv"
    df.to_csv(path, index=False)
    print(f"CSV sauvegardé : {path} ({len(df)} lignes)")
    return path


def extract_dpe(
    n_existants: int = 8000,
    n_neufs: int = 2000,
    clean: bool = True,
    save: bool = True,
    out_dir: Path | str = DATA_DIR,
) -> pd.DataFrame:
    """Extrait les DPE existants et neufs, fusionne, nettoie, puis sauvegarde (optionnel)."""
    df_existants = fetch_dpe(URL_EXISTANTS, n_existants, "existant")
    df_neufs = fetch_dpe(URL_NEUFS, n_neufs, "neuf")
    merged = pd.concat([df_existants, df_neufs], ignore_index=True, sort=False)
    if clean:
        merged = clean_dpe(merged)
    if save:
        save_dpe(merged, n_existants=n_existants, n_neufs=n_neufs, out_dir=out_dir)
    return merged


if __name__ == "__main__":
    merged = extract_dpe(n_existants=500, n_neufs=200)
    print(merged["type_logement"].value_counts())
    print(merged.head())
