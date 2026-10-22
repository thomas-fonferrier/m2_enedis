"""Fonctions partagées par les pages de l'application Streamlit."""

from __future__ import annotations

import io
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "app"
ASSETS = APP_DIR / "assets"
DATA_DIR = ROOT / "data" / "raw"
MODELS_DIR = ROOT / "models"

# Le modèle de classification a été sérialisé avec `classification_dpe` comme
# module de premier niveau, celui de régression avec `models.regression_conso`.
for chemin in (ROOT, MODELS_DIR):
    if str(chemin) not in sys.path:
        sys.path.insert(0, str(chemin))

ETIQUETTES = list("ABCDEFG")
# Couleurs officielles de l'échelle DPE (ADEME) — toujours accompagnées de la lettre.
COULEURS_DPE = {
    "A": "#009C6D",
    "B": "#52B153",
    "C": "#78BD76",
    "D": "#F4E70F",
    "E": "#F0B40F",
    "F": "#EB8235",
    "G": "#D7221F",
}
# Seuils DPE 2021 (énergie primaire, kWh/m²/an)
SEUILS_DPE = {"A": "≤ 70", "B": "71–110", "C": "111–180", "D": "181–250",
              "E": "251–330", "F": "331–420", "G": "> 420"}

# Palette catégorielle validée (ordre fixe, jamais recyclé)
SERIE = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"]
COULEURS_SOURCE = {"existant": SERIE[0], "neuf": SERIE[1]}
SEQUENTIEL = ["#cde2fb", "#86b6ef", "#3987e5", "#256abf", "#184f95", "#0d366b"]

LIBELLES = {
    "conso_5_usages_par_m2_ef": "Consommation (kWh/m²/an)",
    "surface_habitable_logement": "Surface habitable (m²)",
    "annee_construction": "Année de construction",
    "dju": "Degrés-jours unifiés",
    "t_moy_hiver": "T° moyenne hiver (°C)",
    "t_moy_ete": "T° moyenne été (°C)",
    "cout_total_5_usages": "Coût annuel (€)",
    "emission_ges_5_usages_par_m2": "Émissions GES (kgCO₂/m²/an)",
    "etiquette_dpe": "Étiquette DPE",
    "etiquette_ges": "Étiquette GES",
    "source_dpe": "Logement",
    "type_batiment": "Type de bâtiment",
    "type_energie_principale_chauffage": "Énergie de chauffage",
    "zone_climatique": "Zone climatique",
    "nom_commune_ban": "Commune",
}


# --------------------------------------------------------------------------- #
# Données
# --------------------------------------------------------------------------- #
def fichiers_donnees() -> list[Path]:
    """Extractions DPE disponibles, la plus volumineuse en premier."""
    fichiers = sorted(DATA_DIR.glob("dpe_*.csv"), key=lambda p: p.stat().st_size, reverse=True)
    return fichiers


@st.cache_data(show_spinner="Chargement des données…")
def charger_donnees(chemin: str) -> pd.DataFrame:
    df = pd.read_csv(chemin, low_memory=False)
    if "_geopoint" in df:
        coords = df["_geopoint"].astype(str).str.split(",", expand=True)
        df["lat"] = pd.to_numeric(coords[0], errors="coerce")
        df["lon"] = pd.to_numeric(coords[1], errors="coerce")
    if "source_dpe" not in df and "modele_dpe" in df:
        df["source_dpe"] = np.where(
            df["modele_dpe"].astype(str).str.contains("neuf", case=False), "neuf", "existant"
        )
    if "code_departement_ban" in df:
        df["code_departement_ban"] = df["code_departement_ban"].astype("string").str.zfill(2)
    for c in ("annee_construction", "surface_habitable_logement", "conso_5_usages_par_m2_ef"):
        if c in df:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    return df


@st.cache_data
def donnees_reference() -> pd.DataFrame:
    """Jeu le plus complet, utilisé pour les listes de modalités et les comparaisons."""
    return charger_donnees(str(fichiers_donnees()[0]))


def modalites(colonne: str) -> list[str]:
    df = donnees_reference()
    if colonne not in df:
        return []
    return df[colonne].dropna().astype(str).value_counts().index.tolist()


# --------------------------------------------------------------------------- #
# Modèles
# --------------------------------------------------------------------------- #
@st.cache_resource(show_spinner="Chargement du modèle de classification…")
def modele_dpe():
    import joblib
    import classification_dpe  # noqa: F401  (nécessaire au dé-pickling)

    return joblib.load(MODELS_DIR / "modele_dpe_combinaison.joblib")


@st.cache_resource(show_spinner="Chargement du modèle de consommation…")
def modele_conso():
    from models.regression_conso import charger_modele

    return charger_modele()


# --------------------------------------------------------------------------- #
# Graphiques & exports
# --------------------------------------------------------------------------- #
def mise_en_forme(fig: go.Figure, hauteur: int = 380) -> go.Figure:
    fig.update_layout(
        height=hauteur,
        margin=dict(l=8, r=8, t=16, b=8),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0, title=None),
        hoverlabel=dict(font_size=13),
        bargap=0.15,
    )
    fig.update_xaxes(showgrid=False)
    fig.update_yaxes(gridwidth=1)
    return fig


def _png(fig: go.Figure) -> bytes:
    export = go.Figure(fig)
    export.update_layout(template="plotly_white", paper_bgcolor="white", plot_bgcolor="white",
                         font=dict(family="Inter, Arial, sans-serif", color="#222"))
    return export.to_image(format="png", width=1200, height=650, scale=2)


def carte_graphique(titre: str, fig, donnees: pd.DataFrame | None, cle: str,
                    description: str | None = None, hauteur: int = 380, controle=None) -> None:
    """Affiche un graphique dans une carte avec ses boutons d'export PNG / CSV.

    Avec `controle` (fonction affichant un widget et renvoyant sa valeur), `fig`
    est une fonction `valeur -> (figure, données)` construite après le widget.
    """
    with st.container(border=True):
        entete, boutons = st.columns([3, 2], vertical_alignment="center")
        entete.markdown(f"**{titre}**")
        if description:
            entete.caption(description)
        if controle is not None:
            fig, donnees = fig(controle())
        with boutons:
            b1, b2 = st.columns(2)
            b1.download_button("PNG", data=lambda f=fig: _png(f), file_name=f"{cle}.png",
                               mime="image/png", icon=":material/image:", key=f"png_{cle}",
                               on_click="ignore", width="stretch")
            b2.download_button("CSV", data=csv_bytes(donnees), file_name=f"{cle}.csv",
                               mime="text/csv", icon=":material/table:", key=f"csv_{cle}",
                               on_click="ignore", width="stretch")
        st.plotly_chart(mise_en_forme(fig, hauteur), key=f"fig_{cle}",
                        config={"displaylogo": False,
                                "toImageButtonOptions": {"filename": cle, "scale": 2}})


def csv_bytes(df: pd.DataFrame) -> bytes:
    buffer = io.StringIO()
    df.to_csv(buffer, index=False)
    return buffer.getvalue().encode("utf-8-sig")  # BOM : ouverture correcte dans Excel


# --------------------------------------------------------------------------- #
# Composants visuels
# --------------------------------------------------------------------------- #
def css() -> None:
    st.markdown(
        """
        <style>
        .block-container {padding-top: 2.2rem; max-width: 1280px;}
        .hero {
            border-radius: 18px; padding: 2.2rem 2.4rem; color: #fff;
            background: linear-gradient(120deg, #0b5c4b 0%, #0e9f6e 55%, #2a78d6 120%);
        }
        .hero h1 {color: #fff; font-size: 2.3rem; line-height: 1.15; margin: 0 0 .6rem 0; padding: 0;}
        .hero p {color: rgba(255,255,255,.9); font-size: 1.05rem; margin: 0;}
        .hero .tag {display: inline-block; background: rgba(255,255,255,.18); border-radius: 99px;
                    padding: .2rem .8rem; font-size: .8rem; font-weight: 600; letter-spacing: .04em;
                    margin-bottom: .9rem; text-transform: uppercase;}
        .dpe-row {display: flex; align-items: center; gap: .5rem; margin: 4px 0;}
        .dpe-bar {height: 30px; border-radius: 0 16px 16px 0; color: #fff; font-weight: 700;
                  display: flex; align-items: center; padding-left: 12px; font-size: 1rem;
                  text-shadow: 0 1px 2px rgba(0,0,0,.35); transition: transform .2s;}
        .dpe-bar.actif {transform: scale(1.04); box-shadow: 0 0 0 3px rgba(128,128,128,.45);}
        .dpe-bar.inactif {opacity: .35;}
        .dpe-seuil {font-size: .82rem; opacity: .75; white-space: nowrap;}
        .badge-dpe {width: 110px; height: 110px; border-radius: 22px; display: flex;
                    align-items: center; justify-content: center; font-size: 4rem; font-weight: 800;
                    color: #fff; text-shadow: 0 2px 4px rgba(0,0,0,.3); margin: auto;}
        .resultat-chiffre {font-size: 2.8rem; font-weight: 800; line-height: 1;}
        .resultat-unite {font-size: 1rem; opacity: .7; font-weight: 500;}
        </style>
        """,
        unsafe_allow_html=True,
    )


def echelle_dpe(active: str | None = None, avec_seuils: bool = True) -> str:
    lignes = []
    for i, e in enumerate(ETIQUETTES):
        classe = "" if active is None else ("actif" if e == active else "inactif")
        largeur = 38 + i * 9
        texte_fonce = "color:#3a3a00;text-shadow:none;" if e in ("D", "E") else ""
        seuil = f'<span class="dpe-seuil">{SEUILS_DPE[e]} kWh/m²/an</span>' if avec_seuils else ""
        lignes.append(
            f'<div class="dpe-row"><div class="dpe-bar {classe}" '
            f'style="width:{largeur}%;background:{COULEURS_DPE[e]};{texte_fonce}">{e}</div>{seuil}</div>'
        )
    return "".join(lignes)


def badge_dpe(etiquette: str) -> str:
    texte_fonce = "color:#3a3a00;text-shadow:none;" if etiquette in ("D", "E") else ""
    return f'<div class="badge-dpe" style="background:{COULEURS_DPE[etiquette]};{texte_fonce}">{etiquette}</div>'
