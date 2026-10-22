"""Régression conso — modèle propriétaire (Elastic Net) pour la production.

Prédit `conso_5_usages_par_m2_ef` (kWh/m²) à partir de variables
généralement connues d'un propriétaire de logement.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.linear_model import ElasticNet
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

TARGET = "conso_5_usages_par_m2_ef"

# Hyperparamètres retenus en CV (notebook exploration_regression.ipynb)
ALPHA = 0.02310129700083159
L1_RATIO = 0.2
RANDOM_STATE = 42
TEST_SIZE = 0.30

ORDINAL_MAPS = {
    "etiquette_dpe": {"A": 0, "B": 1, "C": 2, "D": 3, "E": 4, "F": 5, "G": 6},
    "etiquette_ges": {"A": 0, "B": 1, "C": 2, "D": 3, "E": 4, "F": 5, "G": 6},
    "qualite_isolation_murs": {
        "insuffisante": 0,
        "moyenne": 1,
        "bonne": 2,
        "très bonne": 3,
    },
}

OWNER_NUM_ORDINAL = [
    "etiquette_dpe",
    "etiquette_ges",
    "qualite_isolation_murs",
    "logement_traversant",
    "nombre_niveau_immeuble",
]
OWNER_CAT = [
    "type_installation_chauffage",
    "type_installation_ecs",
    "type_energie_principale_chauffage",
    "type_energie_principale_ecs",
    "zone_climatique",
]
ENTREES = OWNER_NUM_ORDINAL + OWNER_CAT

MODELE_PATH = Path(__file__).parent / "modele_conso_proprietaire.joblib"
INFO_PATH = Path(__file__).parent / "informations_modele_conso.json"
SCHEMA_PATH = Path(__file__).parent / "schema_entrees_conso.json"
EXEMPLE_ENTREES_PATH = Path(__file__).parent / "exemple_entrees_conso.csv"
EXEMPLE_PRED_PATH = Path(__file__).parent / "exemple_predictions_conso.csv"
DEFAULT_DATA = (
    Path(__file__).resolve().parents[1] / "data" / "raw" / "dpe_n700_e500_n200.csv"
)


def preparer_entrees(donnees, colonnes_modele: list[str] | None = None) -> pd.DataFrame:
    """Normalise un dict / DataFrame vers la matrice de features du modèle."""
    if isinstance(donnees, dict):
        table = pd.DataFrame([donnees])
    elif isinstance(donnees, pd.DataFrame):
        table = donnees.copy()
    else:
        table = pd.DataFrame(donnees)

    table.columns = [str(c).strip() for c in table.columns]
    manquants = [c for c in ENTREES if c not in table.columns]
    if manquants:
        # colonnes absentes → NaN (imputation médiane du pipeline)
        for c in manquants:
            table[c] = np.nan

    x = table.reindex(columns=ENTREES).copy()

    for col, mapping in ORDINAL_MAPS.items():
        x[col] = x[col].map(mapping)

    for col in ("logement_traversant", "nombre_niveau_immeuble"):
        x[col] = pd.to_numeric(x[col], errors="coerce")

    x = pd.get_dummies(x, columns=OWNER_CAT, drop_first=True, dtype=float)

    if colonnes_modele is not None:
        for c in colonnes_modele:
            if c not in x.columns:
                x[c] = 0.0
        x = x.reindex(columns=colonnes_modele, fill_value=0.0)

    return x


class RegressionConsoProprietaire:
    """Wrapper production : prétraitement + Elastic Net."""

    def __init__(self, pipeline: Pipeline, colonnes: list[str], informations: dict):
        self.pipeline_ = pipeline
        self.colonnes_ = list(colonnes)
        self.informations_ = informations
        self.cible_ = TARGET
        self.unite_ = "kWh/m²"

    def predict(self, donnees) -> np.ndarray:
        x = preparer_entrees(donnees, colonnes_modele=self.colonnes_)
        return np.asarray(self.pipeline_.predict(x), dtype=float).reshape(-1)

    def coefficients(self) -> pd.DataFrame:
        enet = self.pipeline_.named_steps["enet"]
        return (
            pd.DataFrame(
                {"variable": self.colonnes_, "coefficient": enet.coef_}
            )
            .assign(abs_coef=lambda d: d["coefficient"].abs())
            .sort_values("abs_coef", ascending=False)
            .drop(columns="abs_coef")
            .reset_index(drop=True)
        )


def charger_modele(chemin=None) -> RegressionConsoProprietaire:
    if chemin is None:
        chemin = MODELE_PATH
    return joblib.load(chemin)


def _construire_pipeline() -> Pipeline:
    return Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="median")),
            ("scaler", StandardScaler()),
            (
                "enet",
                ElasticNet(
                    alpha=ALPHA,
                    l1_ratio=L1_RATIO,
                    max_iter=20000,
                    random_state=RANDOM_STATE,
                ),
            ),
        ]
    )


def entrainer_et_exporter(
    chemin_donnees: Path | str | None = None,
    dossier_sortie: Path | str | None = None,
) -> RegressionConsoProprietaire:
    """Entraîne l'Elastic Net propriétaire et exporte joblib + métadonnées."""
    chemin_donnees = Path(chemin_donnees) if chemin_donnees else DEFAULT_DATA
    dossier = Path(dossier_sortie) if dossier_sortie else Path(__file__).parent

    df = pd.read_csv(chemin_donnees, low_memory=False)
    mask = df[TARGET].notna()
    data = df.loc[mask].copy()
    y = data[TARGET].astype(float)

    X_raw = data[ENTREES].copy()
    X = preparer_entrees(X_raw)

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=TEST_SIZE, random_state=RANDOM_STATE
    )

    # Alignement strict des colonnes train/test (modalités absentes du test)
    colonnes = list(X_train.columns)
    X_train = X_train.reindex(columns=colonnes, fill_value=0.0)
    X_test = X_test.reindex(columns=colonnes, fill_value=0.0)

    pipe = _construire_pipeline()
    pipe.fit(X_train, y_train)
    y_pred = pipe.predict(X_test)

    mae = float(mean_absolute_error(y_test, y_pred))
    rmse = float(np.sqrt(mean_squared_error(y_test, y_pred)))
    r2 = float(r2_score(y_test, y_pred))

    # Modèle final production : réentraînement sur l'ensemble des lignes valides
    X_all = X.reindex(columns=colonnes, fill_value=0.0)
    pipe_final = _construire_pipeline()
    pipe_final.fit(X_all, y)

    informations = {
        "date_export_utc": datetime.now(timezone.utc).isoformat(),
        "strategie": "Elastic Net (L1+L2) — variables propriétaire",
        "cible": TARGET,
        "unite": "kWh/m²",
        "alpha": ALPHA,
        "l1_ratio": L1_RATIO,
        "n_apprentissage_eval": int(len(X_train)),
        "n_test_eval": int(len(X_test)),
        "n_reentrainement_production": int(len(X_all)),
        "reentrainement_sur_tous_les_logements": True,
        "nombre_champs_bruts": len(ENTREES),
        "nombre_variables_preparees": len(colonnes),
        "champs_bruts": ENTREES,
        "variables_preparees": colonnes,
        "ordinales": list(ORDINAL_MAPS.keys()),
        "categoriques": OWNER_CAT,
        "metriques_test_split": {
            "mae": mae,
            "rmse": rmse,
            "r2": r2,
            "test_size": TEST_SIZE,
            "random_state": RANDOM_STATE,
            "note": (
                "Métriques sur split 70/30 avant réentraînement final "
                "sur l'ensemble des logements."
            ),
        },
        "source_notebook": "notebooks/exploration_regression.ipynb",
        "source_donnees": str(chemin_donnees),
        "versions": {
            "numpy": np.__version__,
            "pandas": pd.__version__,
            "scikit-learn": __import__("sklearn").__version__,
            "joblib": joblib.__version__,
        },
    }

    modele = RegressionConsoProprietaire(pipe_final, colonnes, informations)

    joblib.dump(modele, dossier / MODELE_PATH.name)
    (dossier / INFO_PATH.name).write_text(
        json.dumps(informations, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    schema = {
        "cible": TARGET,
        "unite": "kWh/m²",
        "obligatoires": [],
        "numeriques": ["logement_traversant", "nombre_niveau_immeuble"],
        "ordinales": {
            "etiquette_dpe": list(ORDINAL_MAPS["etiquette_dpe"].keys()),
            "etiquette_ges": list(ORDINAL_MAPS["etiquette_ges"].keys()),
            "qualite_isolation_murs": list(
                ORDINAL_MAPS["qualite_isolation_murs"].keys()
            ),
        },
        "categoriels": {
            "type_installation_chauffage": [
                "collectif",
                "individuel",
                "mixte (collectif-individuel)",
            ],
            "type_installation_ecs": [
                "collectif",
                "individuel",
                "mixte (collectif-individuel)",
            ],
            "type_energie_principale_chauffage": [
                "Bois – Bûches",
                "Bois – Granulés (pellets) ou briquettes",
                "Fioul domestique",
                "GPL",
                "Gaz naturel",
                "Propane",
                "Réseau de Chauffage urbain",
                "Électricité",
            ],
            "type_energie_principale_ecs": [
                "Fioul domestique",
                "GPL",
                "Gaz naturel",
                "Non affecté",
                "Propane",
                "Réseau de Chauffage urbain",
                "Électricité",
            ],
            "zone_climatique": [
                "H1a",
                "H1b",
                "H1c",
                "H2a",
                "H2b",
                "H2c",
                "H2d",
                "H3",
            ],
        },
        "autres_champs_absents": (
            "Acceptés ; imputation médiane / modalités one-hot absentes à 0"
        ),
        "consommations_emissions": "Ne sont pas des entrées du modèle",
    }
    (dossier / SCHEMA_PATH.name).write_text(
        json.dumps(schema, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # Exemples : quelques lignes du jeu + prédictions
    exemples = data[ENTREES].head(4).copy()
    preds = modele.predict(exemples)
    exemples.to_csv(dossier / EXEMPLE_ENTREES_PATH.name, index=False)
    pd.DataFrame(
        {
            TARGET + "_observe": y.iloc[:4].to_numpy(),
            TARGET + "_predit": preds,
        }
    ).to_csv(dossier / EXEMPLE_PRED_PATH.name, index=False)

    print(f"Modèle exporté → {dossier / MODELE_PATH.name}")
    print(f"MAE test={mae:.2f} | RMSE test={rmse:.2f} | R² test={r2:.3f}")
    print(f"Réentraîné sur n={len(X_all)} | features={len(colonnes)}")
    return modele


if __name__ == "__main__":
    import sys

    # Garantit un pickle sous models.regression_conso (et non __main__)
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root))
    import models.regression_conso as _mod

    _mod.entrainer_et_exporter()
