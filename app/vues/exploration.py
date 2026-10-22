import pandas as pd
import plotly.express as px
import streamlit as st

from utils import (COULEURS_DPE, COULEURS_SOURCE, ETIQUETTES, LIBELLES, SEQUENTIEL, SERIE,
                   carte_graphique, charger_donnees, csv_bytes, fichiers_donnees)

titre, choix_fichier = st.columns([3, 1], vertical_alignment="bottom")
titre.title(":material/monitoring: Exploration des DPE")
titre.caption("Filtrez l'échantillon : la carte, les indicateurs et tous les graphiques se mettent à jour.")
fichier = choix_fichier.selectbox("Jeu de données", fichiers_donnees(), format_func=lambda p: p.name)
df = charger_donnees(str(fichier))

# --------------------------------------------------------------------------- #
# Filtres — une seule zone au-dessus des graphiques
# --------------------------------------------------------------------------- #
with st.container(border=True):
    l1 = st.columns([1.4, 2.6, 3], vertical_alignment="bottom")
    sources = l1[0].pills("Logement", ["existant", "neuf"], selection_mode="multi",
                          default=["existant", "neuf"])
    batiments = l1[1].pills("Bâtiment", sorted(df["type_batiment"].dropna().unique()),
                            selection_mode="multi", default=sorted(df["type_batiment"].dropna().unique()))
    etiquettes = l1[2].pills("Étiquette DPE", ETIQUETTES, selection_mode="multi", default=ETIQUETTES)

    l2 = st.columns(4, vertical_alignment="bottom")
    zones = l2[0].multiselect("Zone climatique", sorted(df["zone_climatique"].dropna().unique()),
                              placeholder="Toutes les zones")
    energies = l2[1].multiselect("Énergie de chauffage",
                                 df["type_energie_principale_chauffage"].value_counts().index.tolist(),
                                 placeholder="Toutes")
    s_max = int(df["surface_habitable_logement"].quantile(0.99)) + 1
    surface = l2[2].slider("Surface (m²)", 0, s_max, (0, s_max), step=5)
    a_min = int(df["annee_construction"].min())
    a_max = int(df["annee_construction"].max())
    annees = l2[3].slider("Année de construction", a_min, a_max, (a_min, a_max))


def dans_intervalle(serie: pd.Series, bornes: tuple, borne_min, borne_max) -> pd.Series:
    """Un curseur laissé en butée n'exclut ni les valeurs au-delà ni les manquants."""
    ok = pd.Series(True, index=serie.index)
    if bornes[0] > borne_min:
        ok &= serie >= bornes[0]
    if bornes[1] < borne_max:
        ok &= serie <= bornes[1]
    return ok


masque = (
    df["source_dpe"].isin(sources or [])
    & df["type_batiment"].isin(batiments or [])
    & df["etiquette_dpe"].isin(etiquettes or [])
    & dans_intervalle(df["surface_habitable_logement"], surface, 0, s_max)
    & dans_intervalle(df["annee_construction"], annees, a_min, a_max)
)
if zones:
    masque &= df["zone_climatique"].isin(zones)
if energies:
    masque &= df["type_energie_principale_chauffage"].isin(energies)
vue = df[masque].copy()

if vue.empty:
    st.warning("Aucun logement ne correspond à ces filtres. Élargissez la sélection.", icon=":material/filter_alt_off:")
    st.stop()

# --------------------------------------------------------------------------- #
# Indicateurs
# --------------------------------------------------------------------------- #
k = st.columns(5)
k[0].metric("Logements", f"{len(vue):,}".replace(",", " "), f"{len(vue) / len(df):.0%} de l'échantillon",
            delta_color="off", delta_arrow="off", border=True)
k[1].metric("Conso. médiane", f"{vue['conso_5_usages_par_m2_ef'].median():.0f}", "kWh/m²/an",
            delta_color="off", delta_arrow="off", border=True)
k[2].metric("Surface médiane", f"{vue['surface_habitable_logement'].median():.0f} m²", border=True)
k[3].metric("Passoires (F-G)", f"{vue['etiquette_dpe'].isin(['F', 'G']).mean():.0%}", border=True)
k[4].metric("Coût annuel médian", f"{vue['cout_total_5_usages'].median():,.0f} €".replace(",", " "), border=True)

colonnes_export = [c for c in [
    "numero_dpe", "source_dpe", "type_batiment", "etiquette_dpe", "etiquette_ges",
    "conso_5_usages_par_m2_ef", "surface_habitable_logement", "annee_construction",
    "type_energie_principale_chauffage", "zone_climatique", "nom_commune_ban",
    "code_departement_ban", "lat", "lon", "dju", "t_moy_hiver", "t_moy_ete", "cout_total_5_usages",
] if c in vue]
st.download_button("Exporter les logements filtrés (CSV)", csv_bytes(vue[colonnes_export]),
                   file_name="dpe_filtres.csv", mime="text/csv", icon=":material/download:",
                   on_click="ignore", type="tertiary")

survol = {"nom_commune_ban": True, "conso_5_usages_par_m2_ef": ":.0f",
          "surface_habitable_logement": ":.0f", "annee_construction": ":.0f",
          "etiquette_dpe": True, "lat": False, "lon": False}
ordre = {"etiquette_dpe": ETIQUETTES, "source_dpe": ["existant", "neuf"]}

# --------------------------------------------------------------------------- #
# Carte
# --------------------------------------------------------------------------- #
geo = vue.dropna(subset=["lat", "lon"])


def carte(couleur):
    commun = dict(lat="lat", lon="lon", hover_data=survol, labels=LIBELLES, zoom=4.9,
                  center=dict(lat=46.5, lon=2.5), map_style="carto-positron")
    if couleur == "Consommation":
        fig = px.scatter_map(geo, color="conso_5_usages_par_m2_ef", color_continuous_scale=SEQUENTIEL,
                             range_color=(0, geo["conso_5_usages_par_m2_ef"].quantile(.95)), **commun)
    else:
        fig = px.scatter_map(geo, color="etiquette_dpe", color_discrete_map=COULEURS_DPE,
                             category_orders=ordre, **commun)
    fig.update_traces(marker=dict(size=9, opacity=.85))
    return fig, geo[colonnes_export]


carte_graphique("Carte des logements", carte, None, "carte_dpe",
                f"{len(geo)} logements géolocalisés (Base Adresse Nationale). Survolez un point pour le détail.",
                hauteur=540,
                controle=lambda: st.segmented_control("Colorer par", ["Étiquette DPE", "Consommation"],
                                                      default="Étiquette DPE", key="couleur_carte"))

# --------------------------------------------------------------------------- #
# Graphiques
# --------------------------------------------------------------------------- #
g1, g2 = st.columns(2)

with g1:
    repartition = (vue.groupby(["etiquette_dpe", "source_dpe"]).size().rename("logements").reset_index())
    fig = px.bar(repartition, x="etiquette_dpe", y="logements", color="source_dpe",
                 color_discrete_map=COULEURS_SOURCE, category_orders=ordre, labels=LIBELLES)
    fig.update_layout(barmode="stack", yaxis_title="Nombre de logements")
    fig.update_traces(marker_line_width=2, marker_line_color="rgba(255,255,255,.9)")
    carte_graphique("Répartition des étiquettes DPE", fig, repartition, "repartition_etiquettes",
                    "Nombre de logements par classe, existants et neufs empilés.")

with g2:
    fig = px.histogram(vue, x="conso_5_usages_par_m2_ef", color="source_dpe", nbins=40,
                       color_discrete_map=COULEURS_SOURCE, category_orders=ordre, labels=LIBELLES,
                       barmode="overlay", opacity=.75)
    fig.update_layout(yaxis_title="Nombre de logements")
    fig.add_vline(x=vue["conso_5_usages_par_m2_ef"].median(), line_width=2, line_color="#52514e",
                  annotation_text="médiane", annotation_position="top right")
    carte_graphique("Distribution de la consommation", fig,
                    vue[["source_dpe", "conso_5_usages_par_m2_ef"]], "histogramme_conso",
                    "Consommation d'énergie finale, 5 usages, par m² et par an.")

g3, g4 = st.columns(2)

with g3:
    fig = px.box(vue, x="etiquette_dpe", y="conso_5_usages_par_m2_ef", color="etiquette_dpe",
                 color_discrete_map=COULEURS_DPE, category_orders=ordre, labels=LIBELLES, points=False)
    fig.update_layout(showlegend=False)
    stats = (vue.groupby("etiquette_dpe")["conso_5_usages_par_m2_ef"]
             .describe()[["count", "min", "25%", "50%", "75%", "max"]].round(1).reset_index())
    carte_graphique("Consommation par étiquette", fig, stats, "boxplot_conso_etiquette",
                    "Médiane, quartiles et dispersion de la consommation pour chaque classe.")

with g4:
    options_x = {k: v for k, v in LIBELLES.items()
                 if k in ("surface_habitable_logement", "annee_construction", "dju", "t_moy_hiver")}
    def nuage(axe_x):
        donnees = vue.dropna(subset=[axe_x])
        donnees = donnees[donnees[axe_x] <= donnees[axe_x].quantile(.99)]  # écarte les valeurs extrêmes
        fig = px.scatter(donnees, x=axe_x, y="conso_5_usages_par_m2_ef", color="source_dpe",
                         color_discrete_map=COULEURS_SOURCE, category_orders=ordre, labels=LIBELLES,
                         hover_data={"etiquette_dpe": True, "nom_commune_ban": True})
        fig.update_traces(marker=dict(size=8, opacity=.75, line=dict(width=1, color="white")))
        return fig, donnees[[axe_x, "conso_5_usages_par_m2_ef", "source_dpe", "etiquette_dpe"]]

    carte_graphique("Consommation selon une variable", nuage, None, "nuage_conso",
                    "Chaque point est un logement.", hauteur=316,
                    controle=lambda: st.selectbox("Variable en abscisse", list(options_x), format_func=options_x.get,
                                                  key="axe_x_nuage", label_visibility="collapsed"))

# Énergie × étiquette (part en %)
croise = pd.crosstab(vue["type_energie_principale_chauffage"], vue["etiquette_dpe"], normalize="index") * 100
effectifs = vue["type_energie_principale_chauffage"].value_counts()
croise = croise.loc[effectifs.index].reindex(columns=[e for e in ETIQUETTES if e in croise.columns])
long = croise.reset_index().melt(id_vars="type_energie_principale_chauffage",
                                 var_name="etiquette_dpe", value_name="part")
long["libelle"] = long["type_energie_principale_chauffage"] + " (n=" + \
    long["type_energie_principale_chauffage"].map(effectifs).astype(str) + ")"
fig = px.bar(long, y="libelle", x="part", color="etiquette_dpe", orientation="h",
             color_discrete_map=COULEURS_DPE, category_orders=ordre,
             labels={**LIBELLES, "part": "Part des logements (%)", "libelle": ""})
fig.update_traces(marker_line_width=2, marker_line_color="rgba(255,255,255,.9)",
                  hovertemplate="%{y}<br>Étiquette %{fullData.name} : %{x:.1f} %<extra></extra>")
fig.update_layout(barmode="stack", yaxis=dict(autorange="reversed"))
carte_graphique("Étiquettes selon l'énergie de chauffage", fig, croise.round(1).reset_index(),
                "energie_x_etiquette", "Part de chaque classe DPE pour chaque énergie de chauffage principale.",
                hauteur=max(280, 46 * len(croise)))

with st.expander(":material/table: Voir les données filtrées"):
    st.dataframe(vue[colonnes_export], hide_index=True, height=360,
                 column_config={"conso_5_usages_par_m2_ef": st.column_config.NumberColumn(format="%.0f kWh/m²")})
