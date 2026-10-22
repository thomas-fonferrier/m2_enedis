import json

import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st

from utils import (COULEURS_DPE, ETIQUETTES, MODELS_DIR, SERIE, badge_dpe, csv_bytes,
                   donnees_reference, echelle_dpe, mise_en_forme, modalites, modele_conso,
                   modele_dpe)

INCONNU = "Je ne sais pas"
QUALITES = [INCONNU, "insuffisante", "moyenne", "bonne", "très bonne"]
ZONES = ["H1a", "H1b", "H1c", "H2a", "H2b", "H2c", "H2d", "H3"]
AIDE_ZONE = ("H1 : nord, est et montagne · H2 : ouest et sud-ouest · H3 : pourtour méditerranéen. "
             "La zone figure sur tout DPE existant.")


def ou_nan(valeur):
    return np.nan if valeur in (INCONNU, None, "") else valeur


def oui_non(valeur):
    return {"Oui": 1.0, "Non": 0.0}.get(valeur, np.nan)


def periode(annee: int) -> str:
    bornes = [(1947, "avant 1948"), (1974, "1948-1974"), (1977, "1975-1977"), (1982, "1978-1982"),
              (1988, "1983-1988"), (2000, "1989-2000"), (2005, "2001-2005"), (2012, "2006-2012"),
              (2021, "2013-2021")]
    for fin, libelle in bornes:
        if annee <= fin:
            return libelle
    return "après 2021"


@st.cache_data
def options_encodeur(colonne: str) -> list[str]:
    """Modalités apprises par le modèle de classification (hors valeur manquante)."""
    prep = modele_dpe().modeles_["existant"].named_steps["preparation"]
    for _, transformeur, colonnes in prep.transformers_:
        if colonne in colonnes and hasattr(transformeur, "named_steps"):
            encodeur = transformeur.named_steps.get("encodage")
            if encodeur is not None:
                cats = encodeur.categories_[list(colonnes).index(colonne)]
                return [c for c in cats if c != "__manquant__"]
    return []


@st.cache_data
def infos(nom: str) -> dict:
    return json.loads((MODELS_DIR / nom).read_text(encoding="utf-8"))


def choix(colonne: str, avec_inconnu: bool = True) -> list[str]:
    opts = modalites(colonne)
    return ([INCONNU] if avec_inconnu else []) + opts


st.title(":material/online_prediction: Prédiction")
st.caption("Décrivez un logement : le simulateur estime son étiquette DPE puis sa consommation d'énergie.")

onglet_dpe, onglet_conso, onglet_lot = st.tabs([
    ":material/energy_savings_leaf: Étiquette DPE",
    ":material/bolt: Consommation",
    ":material/upload_file: Prédiction par lot",
])

# --------------------------------------------------------------------------- #
# 1. Classification — étiquette DPE
# --------------------------------------------------------------------------- #
with onglet_dpe:
    formulaire, resultat = st.columns([3, 2], gap="large")

    with formulaire.form("form_dpe", border=False):
        with st.container(border=True):
            st.markdown("##### :material/home: Le logement")
            c = st.columns(2)
            source = c[0].segmented_control("État", ["existant", "neuf"], default="existant", key="d_source")
            batiment = c[1].segmented_control("Type", ["appartement", "maison"], default="appartement", key="d_bat")
            c = st.columns(3)
            surface = c[0].number_input("Surface habitable (m²)", 9.0, 1000.0, 70.0, step=1.0, key="d_surface")
            annee = c[1].number_input("Année de construction", 1700, 2026, 1985, step=1, key="d_annee")
            hauteur = c[2].number_input("Hauteur sous plafond (m)", 2.0, 5.0, 2.5, step=0.1, key="d_hauteur")
            c = st.columns(3)
            zone = c[0].selectbox("Zone climatique", ZONES, index=ZONES.index("H1b"), help=AIDE_ZONE, key="d_zone")
            altitude = c[1].selectbox("Altitude", choix("classe_altitude"), key="d_alt")
            etage = c[2].number_input("Étage (appartement)", -1, 30, 1, help="0 = rez-de-chaussée", key="d_etage")

        with st.container(border=True):
            st.markdown("##### :material/local_fire_department: Chauffage & eau chaude")
            c = st.columns(2)
            energie = c[0].selectbox("Énergie de chauffage", choix("type_energie_principale_chauffage"), index=1,
                                     key="d_energie")
            installation = c[1].selectbox("Installation de chauffage", choix("type_installation_chauffage"),
                                          index=1, key="d_install")
            c = st.columns(2)
            energie_ecs = c[0].selectbox("Énergie eau chaude", choix("type_energie_principale_ecs"), index=1,
                                         key="d_energie_ecs")
            installation_ecs = c[1].selectbox("Installation eau chaude", choix("type_installation_ecs"), index=1,
                                              key="d_install_ecs")

        with st.container(border=True):
            st.markdown("##### :material/roofing: Isolation")
            c = st.columns(2)
            iso_env = c[0].select_slider("Enveloppe (globale)", QUALITES, value="moyenne", key="d_iso_env")
            iso_murs = c[1].select_slider("Murs", QUALITES, value="moyenne", key="d_iso_murs")
            c = st.columns(2)
            iso_menu = c[0].select_slider("Fenêtres / menuiseries", QUALITES, value="moyenne", key="d_iso_menu")
            iso_bas = c[1].select_slider("Plancher bas", QUALITES, value=INCONNU, key="d_iso_bas")

        with st.expander(":material/tune: Paramètres avancés (facultatifs)"):
            c = st.columns(2)
            ubat = c[0].number_input("Ubat (W/m².K)", 0.0, 5.0, value=None, step=0.05,
                                     help="Coefficient de déperdition de l'enveloppe, indiqué sur le DPE.")
            niveaux = c[1].number_input("Niveaux du logement", 1, 10, 1)
            generateur = st.selectbox("Générateur de chauffage", [INCONNU] + options_encodeur(
                "type_generateur_chauffage_principal"), format_func=str.capitalize)
            ventilation = st.selectbox("Ventilation", [INCONNU] + options_encodeur("type_ventilation"),
                                       format_func=str.capitalize)
            c = st.columns(3)
            inertie = c[0].selectbox("Inertie du bâtiment", choix("classe_inertie_batiment"))
            traversant = c[1].selectbox("Logement traversant", [INCONNU, "Oui", "Non"], key="d_traversant")
            toiture = c[2].selectbox("Toiture isolée", [INCONNU, "Oui", "Non"])
            c = st.columns(3)
            pv = c[0].selectbox("Panneaux photovoltaïques", [INCONNU, "Oui", "Non"])
            clim = c[1].number_input("Surface climatisée (m²)", 0.0, 1000.0, value=None)
            combles = c[2].select_slider("Combles perdus", QUALITES, value=INCONNU)

        envoye = st.form_submit_button("Estimer l'étiquette DPE", type="primary", icon=":material/bolt:",
                                       width="stretch")

    if envoye:
        logement = {
            "source_dpe": source or "existant",
            "type_batiment": batiment or "appartement",
            "surface_habitable_logement": surface,
            "hauteur_sous_plafond": hauteur,
            "annee_construction": float(annee),
            "periode_construction": periode(int(annee)),
            "nombre_niveau_logement": float(niveaux),
            "ubat_w_par_m2_k": ubat if ubat is not None else np.nan,
            "surface_climatisee": clim if clim is not None else np.nan,
            "zone_climatique": zone,
            "classe_altitude": ou_nan(altitude),
            "classe_inertie_batiment": ou_nan(inertie),
            "numero_etage_appartement": float(etage) if batiment == "appartement" else np.nan,
            "type_installation_chauffage": ou_nan(installation),
            "type_installation_ecs": ou_nan(installation_ecs),
            "type_energie_n1": ou_nan(energie),
            "type_energie_principale_chauffage": ou_nan(energie),
            "type_energie_principale_ecs": ou_nan(energie_ecs),
            "type_generateur_chauffage_principal": ou_nan(generateur),
            "type_ventilation": ou_nan(ventilation),
            "presence_production_pv": oui_non(pv),
            "isolation_toiture": oui_non(toiture),
            "logement_traversant": oui_non(traversant),
            "qualite_isolation_enveloppe": ou_nan(iso_env),
            "qualite_isolation_murs": ou_nan(iso_murs),
            "qualite_isolation_menuiseries": ou_nan(iso_menu),
            "qualite_isolation_plancher_bas": ou_nan(iso_bas),
            "qualite_isolation_plancher_haut_comble_amenage": np.nan,
            "qualite_isolation_plancher_haut_comble_perdu": ou_nan(combles),
            "qualite_isolation_plancher_haut_toit_terrasse": np.nan,
        }
        modele = modele_dpe()
        proba = modele.predict_proba(logement)[0]
        st.session_state["res_dpe"] = {
            "etiquette": str(modele.predict(logement)[0]),
            "proba": proba.tolist(),
            "logement": logement,
        }

    with resultat:
        res = st.session_state.get("res_dpe")
        if res is None:
            with st.container(border=True):
                st.markdown("##### Votre résultat apparaîtra ici")
                st.caption("Renseignez les caractéristiques connues puis lancez l'estimation. "
                           "Les champs « Je ne sais pas » sont complétés automatiquement par le modèle.")
                st.markdown(echelle_dpe(avec_seuils=False), unsafe_allow_html=True)
        else:
            e = res["etiquette"]
            proba = np.array(res["proba"])
            i = ETIQUETTES.index(e)
            voisins = proba[max(0, i - 1): i + 2].sum()
            with st.container(border=True):
                b, t = st.columns([1, 2], vertical_alignment="center")
                b.markdown(badge_dpe(e), unsafe_allow_html=True)
                t.markdown(f"<div style='opacity:.7'>Étiquette estimée</div>"
                           f"<div class='resultat-chiffre'>Classe {e}</div>"
                           f"<div style='margin-top:.4rem'>Confiance : <b>{proba[i]:.0%}</b><br>"
                           f"Classe {e} ± 1 : <b>{voisins:.0%}</b></div>", unsafe_allow_html=True)
                if e in ("F", "G"):
                    st.warning("Ce logement serait une **passoire thermique** : sa location sera interdite "
                               f"à partir de {'2025' if e == 'G' else '2028'}.", icon=":material/warning:")
                elif e in ("A", "B"):
                    st.success("Logement très performant.", icon=":material/eco:")
                st.markdown(echelle_dpe(active=e, avec_seuils=False), unsafe_allow_html=True)

            with st.container(border=True):
                st.markdown("**Probabilité de chaque classe**")
                tab = pd.DataFrame({"etiquette": ETIQUETTES, "probabilite": proba * 100})
                fig = px.bar(tab, x="etiquette", y="probabilite", color="etiquette",
                             color_discrete_map=COULEURS_DPE,
                             labels={"etiquette": "Étiquette", "probabilite": "Probabilité (%)"})
                fig.update_traces(hovertemplate="Classe %{x} : %{y:.1f} %<extra></extra>",
                                  texttemplate=[f"{p:.0f} %" if p >= 5 else "" for p in tab["probabilite"]],
                                  textposition="outside")
                fig.update_layout(showlegend=False, yaxis_range=[0, max(100, tab["probabilite"].max() + 10)])
                st.plotly_chart(mise_en_forme(fig, 260), config={"displaylogo": False})
            st.info("Rendez-vous dans l'onglet **Consommation** : il est pré-rempli avec ce logement.",
                    icon=":material/arrow_forward:")

# --------------------------------------------------------------------------- #
# 2. Régression — consommation
# --------------------------------------------------------------------------- #
with onglet_conso:
    precedent = (st.session_state.get("res_dpe") or {}).get("logement", {})
    dpe_estime = (st.session_state.get("res_dpe") or {}).get("etiquette")

    def defaut(liste, valeur, repli=0):
        return liste.index(valeur) if valeur in liste else repli

    formulaire, resultat = st.columns([3, 2], gap="large")
    with formulaire.form("form_conso", border=False):
        if dpe_estime:
            st.caption(f":material/auto_awesome: Pré-rempli avec votre simulation (étiquette estimée : **{dpe_estime}**).")
        with st.container(border=True):
            st.markdown("##### :material/energy_savings_leaf: Étiquettes & bâtiment")
            c = st.columns(3)
            et_dpe = c[0].selectbox("Étiquette DPE", [INCONNU] + ETIQUETTES,
                                    index=defaut([INCONNU] + ETIQUETTES, dpe_estime, 4))
            et_ges = c[1].selectbox("Étiquette GES", [INCONNU] + ETIQUETTES, index=0,
                                    help="Émissions de gaz à effet de serre, indiquées sur le DPE.")
            surface_c = c[2].number_input("Surface habitable (m²)", 9.0, 1000.0,
                                          float(precedent.get("surface_habitable_logement", 70.0)),
                                          help="Sert uniquement à calculer la consommation annuelle totale.")
            c = st.columns(3)
            iso = c[0].selectbox("Isolation des murs", QUALITES,
                                 index=defaut(QUALITES, precedent.get("qualite_isolation_murs"), 2))
            trav = c[1].selectbox("Logement traversant", [INCONNU, "Oui", "Non"],
                                  index={1.0: 1, 0.0: 2}.get(precedent.get("logement_traversant"), 0))
            niv = c[2].number_input("Niveaux de l'immeuble", 1, 30, 1, help="1 pour une maison de plain-pied.")
            zones_c = [INCONNU] + ZONES
            zone_c = st.selectbox("Zone climatique", zones_c, index=defaut(zones_c, precedent.get("zone_climatique"), 0),
                                  help=AIDE_ZONE)

        with st.container(border=True):
            st.markdown("##### :material/local_fire_department: Chauffage & eau chaude")
            c = st.columns(2)
            o = choix("type_energie_principale_chauffage")
            en_ch = c[0].selectbox("Énergie de chauffage", o, index=defaut(o, precedent.get("type_energie_principale_chauffage"), 1))
            o = choix("type_installation_chauffage")
            in_ch = c[1].selectbox("Installation de chauffage", o, index=defaut(o, precedent.get("type_installation_chauffage"), 1))
            c = st.columns(2)
            o = choix("type_energie_principale_ecs")
            en_ecs = c[0].selectbox("Énergie eau chaude", o, index=defaut(o, precedent.get("type_energie_principale_ecs"), 1))
            o = choix("type_installation_ecs")
            in_ecs = c[1].selectbox("Installation eau chaude", o, index=defaut(o, precedent.get("type_installation_ecs"), 1))

        envoye_c = st.form_submit_button("Estimer la consommation", type="primary", icon=":material/bolt:",
                                         width="stretch")

    if envoye_c:
        entree = {
            "etiquette_dpe": ou_nan(et_dpe),
            "etiquette_ges": ou_nan(et_ges),
            "qualite_isolation_murs": ou_nan(iso),
            "logement_traversant": oui_non(trav),
            "nombre_niveau_immeuble": float(niv),
            "type_installation_chauffage": ou_nan(in_ch),
            "type_installation_ecs": ou_nan(in_ecs),
            "type_energie_principale_chauffage": ou_nan(en_ch),
            "type_energie_principale_ecs": ou_nan(en_ecs),
            "zone_climatique": ou_nan(zone_c),
        }
        st.session_state["res_conso"] = {"conso": max(0.0, float(modele_conso().predict(entree)[0])),
                                         "surface": surface_c}

    with resultat:
        res = st.session_state.get("res_conso")
        if res is None:
            with st.container(border=True):
                st.markdown("##### Votre résultat apparaîtra ici")
                st.caption("Le modèle estime la consommation d'énergie finale (chauffage, eau chaude, "
                           "refroidissement, éclairage et auxiliaires) par m² et par an.")
        else:
            mae = infos("informations_modele_conso.json")["metriques_test_split"]["mae"]
            ref = donnees_reference()["conso_5_usages_par_m2_ef"].dropna()
            conso = res["conso"]
            rang = (ref > conso).mean()
            with st.container(border=True):
                st.markdown(f"<div style='opacity:.7'>Consommation estimée</div>"
                            f"<div class='resultat-chiffre'>{conso:.0f} <span class='resultat-unite'>kWh/m²/an</span></div>"
                            f"<div style='opacity:.7;margin-top:.3rem'>Fourchette indicative : "
                            f"{max(0, conso - mae):.0f} – {conso + mae:.0f} kWh/m²/an</div>",
                            unsafe_allow_html=True)
                st.write("")
                m1, m2 = st.columns(2)
                m1.metric("Total annuel (kWh)", f"{conso * res['surface']:,.0f}".replace(",", " "),
                          help="Consommation au m² × surface habitable.", border=True)
                m2.metric("Plus sobre que", f"{rang:.0%}", help="Part des logements de l'échantillon "
                          "qui consomment davantage au m².", border=True)
            with st.container(border=True):
                st.markdown("**Position par rapport à l'échantillon**")
                fig = px.histogram(ref[ref < ref.quantile(.98)], nbins=40, color_discrete_sequence=[SERIE[0]],
                                   labels={"value": "Consommation (kWh/m²/an)"})
                fig.add_vline(x=conso, line_width=3, line_color="#d03b3b",
                              annotation_text="votre logement", annotation_position="top")
                fig.update_layout(showlegend=False, yaxis_title="Logements")
                fig.update_traces(hovertemplate="%{x} kWh/m² : %{y} logements<extra></extra>")
                st.plotly_chart(mise_en_forme(fig, 260), config={"displaylogo": False})

# --------------------------------------------------------------------------- #
# 3. Prédiction par lot
# --------------------------------------------------------------------------- #
with onglet_lot:
    st.markdown("Importez un fichier CSV (une ligne par logement) pour obtenir les prédictions de tous "
                "les logements d'un coup, puis téléchargez le résultat.")
    cible = st.segmented_control("Modèle", ["Étiquette DPE", "Consommation"], default="Étiquette DPE")
    modele_choisi = cible or "Étiquette DPE"
    exemple = MODELS_DIR / ("exemple_entrees.csv" if modele_choisi == "Étiquette DPE" else "exemple_entrees_conso.csv")
    st.download_button("Télécharger un modèle de fichier", exemple.read_bytes(), file_name=exemple.name,
                       mime="text/csv", icon=":material/description:", on_click="ignore", type="tertiary")
    fichier = st.file_uploader("Fichier CSV", type="csv")
    if fichier is not None:
        try:
            lot = pd.read_csv(fichier, low_memory=False)
            if modele_choisi == "Étiquette DPE":
                m = modele_dpe()
                sortie = lot.copy()
                sortie["etiquette_dpe_predite"] = m.predict(lot)
                sortie["confiance"] = m.predict_proba(lot).max(axis=1).round(3)
                resume = sortie["etiquette_dpe_predite"].value_counts().reindex(ETIQUETTES, fill_value=0)
            else:
                sortie = lot.copy()
                sortie["conso_5_usages_par_m2_ef_predite"] = modele_conso().predict(lot).clip(min=0).round(1)
                resume = None
        except Exception as erreur:  # noqa: BLE001 — message affiché à l'utilisateur
            st.error(f"Le fichier n'a pas pu être traité : {erreur}", icon=":material/error:")
        else:
            st.success(f"{len(sortie)} logements prédits.", icon=":material/check_circle:")
            if resume is not None:
                cols = st.columns(7)
                for col, (e, n) in zip(cols, resume.items()):
                    col.markdown(badge_dpe(e).replace("110px", "56px").replace("4rem", "1.8rem"),
                                 unsafe_allow_html=True)
                    col.markdown(f"<div style='text-align:center;font-weight:700'>{n}</div>", unsafe_allow_html=True)
            st.dataframe(sortie, hide_index=True, height=320)
            st.download_button("Télécharger les prédictions (CSV)", csv_bytes(sortie),
                               file_name="predictions.csv", mime="text/csv", icon=":material/download:",
                               type="primary", on_click="ignore")
