import json
import tempfile
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

from utils import MODELS_DIR, SERIE, carte_graphique, fichiers_donnees, modele_conso


def lire(nom: str) -> dict:
    return json.loads((MODELS_DIR / nom).read_text(encoding="utf-8"))


st.title(":material/model_training: Les modèles")
st.caption("Performances mesurées, variables les plus influentes et réentraînement sur de nouvelles données.")

onglet_cls, onglet_reg, onglet_train = st.tabs([
    ":material/category: Classification DPE",
    ":material/show_chart: Régression consommation",
    ":material/sync: Réentraînement",
])

# --------------------------------------------------------------------------- #
with onglet_cls:
    info = lire("informations_modele.json")
    retenu = next(m for m in info["comparaison_test"] if "+" in m["methode"])
    st.markdown(f"**Stratégie retenue :** {info['strategie']} — un modèle par type de DPE "
                f"(entraîné sur {info['n_apprentissage']:,} logements, testé sur {info['n_test']:,}).".replace(",", " "))
    k = st.columns(4)
    k[0].metric("Exactitude", f"{retenu['accuracy']:.0%}", help="Part des logements dont la classe exacte est trouvée.", border=True)
    k[1].metric("À ± 1 classe", f"{retenu['exact_ou_une_classe_ecart']:.0%}", help="Erreur d'au plus une lettre.", border=True)
    k[2].metric("F1 macro", f"{retenu['f1_macro']:.2f}", help="Moyenne des F1 de chaque classe (classes rares comprises).", border=True)
    k[3].metric("Kappa quadratique", f"{retenu['kappa_quadratique']:.2f}", help="Accord ordinal : pénalise davantage les grosses erreurs.", border=True)

    noms = {"accuracy": "Exactitude", "f1_macro": "F1 macro", "balanced_accuracy": "Exactitude équilibrée",
            "exact_ou_une_classe_ecart": "À ± 1 classe", "kappa_quadratique": "Kappa quadratique"}
    comp = (pd.DataFrame(info["comparaison_validation"])
            .melt(id_vars="methode", value_vars=list(noms), var_name="metrique", value_name="score"))
    comp["metrique"] = comp["metrique"].map(noms)
    methodes = [m["methode"] for m in info["comparaison_validation"]]
    fig = px.bar(comp, x="metrique", y="score", color="methode", barmode="group",
                 color_discrete_sequence=SERIE, category_orders={"methode": methodes},
                 labels={"metrique": "", "score": "Score", "methode": "Méthode"})
    fig.update_traces(marker_line_width=2, marker_line_color="rgba(255,255,255,.9)",
                      hovertemplate="%{fullData.name}<br>%{x} : %{y:.3f}<extra></extra>")
    fig.update_layout(yaxis_range=[0, 1])
    carte_graphique("Comparaison des méthodes (validation croisée)", fig,
                    pd.DataFrame(info["comparaison_validation"]), "comparaison_classification",
                    "La combinaison Gradient Boosting (existant) + Random Forest (neuf) obtient le meilleur compromis.")
    st.caption(":material/info: " + info["limite_evaluation"])

# --------------------------------------------------------------------------- #
with onglet_reg:
    info_r = lire("informations_modele_conso.json")
    met = info_r["metriques_test_split"]
    st.markdown(f"**Modèle :** {info_r['strategie']} — α = {info_r['alpha']:.3f}, ratio L1 = {info_r['l1_ratio']}. "
                f"Uniquement des variables connues d'un propriétaire, réentraîné sur "
                f"{info_r['n_reentrainement_production']} logements.")
    k = st.columns(4)
    k[0].metric("R²", f"{met['r2']:.2f}", help="Part de la variance de la consommation expliquée.", border=True)
    k[1].metric("Erreur moyenne (MAE)", f"{met['mae']:.0f} kWh/m²", border=True)
    k[2].metric("RMSE", f"{met['rmse']:.0f} kWh/m²", border=True)
    k[3].metric("Variables", info_r["nombre_variables_preparees"], f"{info_r['nombre_champs_bruts']} champs saisis",
                delta_color="off", delta_arrow="off", border=True)

    coefs = modele_conso().coefficients()
    coefs = coefs[coefs["coefficient"].abs() > 1e-9].head(15).copy()
    coefs["variable"] = (coefs["variable"].str.replace("type_energie_principale_", "énergie ", regex=False)
                         .str.replace("type_installation_", "installation ", regex=False)
                         .str.replace("_", " ", regex=False))
    coefs["effet"] = coefs["coefficient"].map(lambda v: "Augmente la conso." if v > 0 else "Diminue la conso.")
    fig = px.bar(coefs, x="coefficient", y="variable", color="effet", orientation="h",
                 color_discrete_map={"Augmente la conso.": "#e34948", "Diminue la conso.": "#2a78d6"},
                 labels={"coefficient": "Effet standardisé (kWh/m²)", "variable": "", "effet": ""})
    fig.update_layout(yaxis=dict(autorange="reversed"))
    fig.update_traces(hovertemplate="%{y}<br>%{x:+.1f} kWh/m²<extra></extra>")
    carte_graphique("Variables les plus influentes", fig, coefs, "coefficients_regression",
                    "Coefficients Elastic Net sur variables standardisées : effet d'un écart-type sur la consommation.",
                    hauteur=460)

# --------------------------------------------------------------------------- #
with onglet_train:
    st.markdown(
        "Réentraînez le **modèle de consommation** sur une nouvelle extraction ADEME. "
        "Le modèle est évalué sur un découpage 70/30, puis réentraîné sur tous les logements et "
        "**remplace le modèle en production**."
    )
    from models.regression_conso import ENTREES, TARGET, entrainer_et_exporter

    origine = st.segmented_control("Source des données", ["Extraction existante", "Importer un CSV"],
                                   default="Extraction existante")
    chemin = None
    if origine == "Importer un CSV":
        fichier = st.file_uploader("Fichier CSV d'extraction DPE", type="csv")
        if fichier is not None:
            tmp = Path(tempfile.gettempdir()) / "reentrainement_dpe.csv"
            tmp.write_bytes(fichier.getvalue())
            chemin = tmp
    else:
        chemin = st.selectbox("Extraction", fichiers_donnees(), format_func=lambda p: p.name)

    with st.expander("Colonnes requises"):
        st.code(", ".join(ENTREES + [TARGET]))

    if chemin is not None:
        colonnes = pd.read_csv(chemin, nrows=0).columns
        manquantes = [c for c in ENTREES + [TARGET] if c not in colonnes]
        if manquantes:
            st.error("Colonnes manquantes : " + ", ".join(manquantes), icon=":material/error:")
        else:
            confirme = st.checkbox("Je comprends que le modèle actuel sera remplacé.")
            if st.button("Lancer le réentraînement", type="primary", icon=":material/sync:", disabled=not confirme):
                avant = lire("informations_modele_conso.json")["metriques_test_split"]
                with st.spinner("Entraînement en cours…"):
                    entrainer_et_exporter(chemin_donnees=chemin)
                modele_conso.clear()
                apres = lire("informations_modele_conso.json")
                m = apres["metriques_test_split"]
                st.success(f"Modèle réentraîné sur {apres['n_reentrainement_production']} logements.",
                           icon=":material/check_circle:")
                c = st.columns(3)
                c[0].metric("R²", f"{m['r2']:.3f}", f"{m['r2'] - avant['r2']:+.3f}", border=True)
                c[1].metric("MAE", f"{m['mae']:.1f}", f"{m['mae'] - avant['mae']:+.1f}", delta_color="inverse", border=True)
                c[2].metric("RMSE", f"{m['rmse']:.1f}", f"{m['rmse'] - avant['rmse']:+.1f}", delta_color="inverse", border=True)

    st.divider()
    st.caption(":material/info: Le modèle de classification DPE (≈ 19 500 logements) se réentraîne depuis "
               "le notebook `notebooks/classification_dpe.ipynb`.")
