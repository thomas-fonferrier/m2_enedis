"""Point d'entrée de l'application — `streamlit run app/app.py`."""

import streamlit as st

from utils import ASSETS, css

st.set_page_config(
    page_title="GreenTech · DPE & consommation",
    page_icon=str(ASSETS / "icone.svg"),
    layout="wide",
)
st.logo(str(ASSETS / "logo.svg"), icon_image=str(ASSETS / "icone.svg"), size="large")
css()

pages = [
    st.Page("vues/contexte.py", title="Contexte", icon=":material/home:", default=True),
    st.Page("vues/exploration.py", title="Exploration", icon=":material/monitoring:"),
    st.Page("vues/prediction.py", title="Prédiction", icon=":material/online_prediction:"),
    st.Page("vues/modeles.py", title="Modèles", icon=":material/model_training:"),
]
st.navigation(pages, position="top").run()
