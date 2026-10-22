import base64

import streamlit as st

from utils import ASSETS, donnees_reference, echelle_dpe

illustration = base64.b64encode((ASSETS / "maison.svg").read_bytes()).decode()

st.markdown(
    f"""
    <div class="hero">
      <div style="display:flex;flex-wrap:wrap;align-items:center;gap:2rem;">
        <div style="flex:1 1 380px;">
          <span class="tag">Enedis · GreenTech Solutions</span>
          <h1>Comprendre et prédire la performance énergétique des logements</h1>
          <p>Explorez les diagnostics de performance énergétique (DPE) de l'ADEME,
          estimez l'étiquette d'un logement et sa consommation annuelle en
          quelques clics.</p>
        </div>
        <div style="flex:0 1 340px;">
          <img src="data:image/svg+xml;base64,{illustration}" style="width:100%;" alt="Maison et étiquette DPE">
        </div>
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)
st.write("")

df = donnees_reference()
k1, k2, k3, k4 = st.columns(4)
k1.metric("Logements analysés", f"{len(df):,}".replace(",", " "), border=True)
k2.metric("Départements couverts", df["code_departement_ban"].nunique(), border=True)
k3.metric("Consommation médiane", f"{df['conso_5_usages_par_m2_ef'].median():.0f} kWh/m²", border=True)
passoires = df["etiquette_dpe"].isin(["F", "G"]).mean()
k4.metric("Passoires thermiques (F-G)", f"{passoires:.0%}", border=True)

st.write("")
gauche, droite = st.columns([3, 2], gap="large")
with gauche:
    st.subheader(":material/lightbulb: Le projet")
    st.markdown(
        """
Avec l'accélération du changement climatique et la hausse des prix de l'énergie,
la **sobriété énergétique** est devenue une priorité. Enedis souhaite évaluer
l'impact de la classe de DPE sur la consommation électrique des logements.

Cette application, développée par **GreenTech Solutions**, rassemble :

- les **données DPE** de l'ADEME (logements existants et neufs), géolocalisées
  grâce à la Base Adresse Nationale ;
- un **enrichissement climatique** par département (Open-Meteo : degrés-jours,
  températures moyennes d'hiver et d'été) ;
- deux **modèles de machine learning** : l'un prédit l'étiquette DPE, l'autre
  la consommation d'énergie au m².
        """
    )
    st.subheader(":material/gavel: Pourquoi c'est important")
    st.markdown(
        """
La loi *Climat et Résilience* interdit progressivement la mise en location
des logements les plus énergivores :
        """
    )
    c1, c2, c3 = st.columns(3)
    for col, annee, etiquette in ((c1, "2025", "G"), (c2, "2028", "F"), (c3, "2034", "E")):
        with col.container(border=True):
            st.markdown(f"<div style='font-size:1.6rem;font-weight:800'>{annee}</div>"
                        f"Logements classés <b>{etiquette}</b> interdits à la location",
                        unsafe_allow_html=True)

with droite:
    st.subheader(":material/energy_savings_leaf: L'étiquette DPE")
    st.caption("Consommation d'énergie primaire par m² et par an (méthode 2021).")
    st.markdown(echelle_dpe(), unsafe_allow_html=True)
    st.caption("Le classement final retient aussi les émissions de gaz à effet de serre : "
               "c'est la plus mauvaise des deux notes qui s'applique.")

st.divider()
st.subheader(":material/explore: Que pouvez-vous faire ?")
cartes = [
    (":material/monitoring:", "Explorer", "Carte interactive, filtres et graphiques sur les DPE.",
     "vues/exploration.py"),
    (":material/online_prediction:", "Prédire", "Estimez l'étiquette DPE et la consommation d'un logement.",
     "vues/prediction.py"),
    (":material/model_training:", "Comprendre les modèles", "Performances, variables clés et réentraînement.",
     "vues/modeles.py"),
]
for col, (icone, titre, texte, page) in zip(st.columns(3), cartes):
    with col.container(border=True, height="stretch"):
        st.markdown(f"#### {icone} {titre}")
        st.write(texte)
        st.page_link(page, label=f"Ouvrir « {titre} »", icon=":material/arrow_forward:")

with st.expander(":material/database: Sources des données"):
    st.markdown(
        """
- [DPE logements existants — ADEME](https://data.ademe.fr/datasets/dpe03existant)
- [DPE logements neufs — ADEME](https://data.ademe.fr/datasets/dpe02neuf)
- [Base Adresse Nationale](https://adresse.data.gouv.fr/)
- [Open-Meteo Historical Weather API](https://open-meteo.com/en/docs/historical-weather-api) (ERA5, 2019–2023)
        """
    )
