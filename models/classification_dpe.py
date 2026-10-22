import re
import unicodedata
from pathlib import Path
import joblib
import numpy as np
import pandas as pd

NUMERIQUES_BASE = ['surface_habitable_logement', 'hauteur_sous_plafond', 'annee_construction', 'nombre_niveau_logement', 'ubat_w_par_m2_k', 'surface_climatisee']
NUMERIQUES = ['surface_habitable_logement', 'hauteur_sous_plafond', 'annee_construction', 'nombre_niveau_logement', 'ubat_w_par_m2_k', 'surface_climatisee', 'volume_habitable_estime_m3']
CATEGORIELLES = ['source_dpe', 'type_batiment', 'periode_construction', 'zone_climatique', 'classe_altitude', 'classe_inertie_batiment', 'numero_etage_appartement', 'type_installation_chauffage', 'type_installation_ecs', 'type_energie_n1', 'type_energie_principale_chauffage', 'type_energie_principale_ecs', 'type_generateur_chauffage_principal', 'type_ventilation', 'presence_production_pv', 'isolation_toiture', 'logement_traversant', 'qualite_isolation_enveloppe', 'qualite_isolation_murs', 'qualite_isolation_menuiseries', 'qualite_isolation_plancher_bas', 'qualite_isolation_plancher_haut_comble_amenage', 'qualite_isolation_plancher_haut_comble_perdu', 'qualite_isolation_plancher_haut_toit_terrasse']
ENTREES = NUMERIQUES_BASE + CATEGORIELLES

def normaliser_modalite(v):
    if pd.isna(v):
        return np.nan
    texte = unicodedata.normalize('NFKD', str(v))
    texte = ''.join(c for c in texte if not unicodedata.combining(c))
    texte = texte.casefold().replace('–', '-').replace('—', '-')
    texte = re.sub(r'\s+', ' ', texte).strip()
    return texte if texte else np.nan

def preparer_entrees(donnees):
    if isinstance(donnees, dict):
        table = pd.DataFrame([donnees])
    elif isinstance(donnees, pd.DataFrame):
        table = donnees.copy()
    else:
        table = pd.DataFrame(donnees)

    table.columns = [re.sub(r'\s+', '_', str(c).strip().lower())
                     for c in table.columns]
    if table.columns.duplicated().any():
        raise ValueError('Noms de colonnes en double après normalisation.')
    manquants = [c for c in ['source_dpe', 'type_batiment'] if c not in table]
    if manquants:
        raise ValueError('Champs obligatoires absents : ' + ', '.join(manquants))
    table = table.reindex(columns=ENTREES)
    x = pd.DataFrame(index=table.index)
    for c in NUMERIQUES_BASE:
        x[c] = pd.to_numeric(table[c], errors='coerce').astype('float64')
        x[c] = x[c].replace([np.inf, -np.inf], np.nan)
    for c in CATEGORIELLES:
        x[c] = table[c].map(normaliser_modalite)
    x['volume_habitable_estime_m3'] = (
        x['surface_habitable_logement'] * x['hauteur_sous_plafond']
    )
    for c, choix in [('source_dpe', ['existant', 'neuf']),
                     ('type_batiment', ['maison', 'appartement'])]:
        if not x[c].isin(choix).all():
            raise ValueError(c + ' doit appartenir à : ' + ', '.join(choix))
    return x[NUMERIQUES + CATEGORIELLES]

class ClassificationDPE:
    def __init__(self, modele_existant, modele_neuf, informations):
        self.modeles_ = {'existant': modele_existant, 'neuf': modele_neuf}
        self.informations_ = informations
        self.classes_ = np.array(list('ABCDEFG'))

    def predict(self, donnees):
        x = preparer_entrees(donnees)
        predictions = np.empty(len(x), dtype=object)
        for source, modele in self.modeles_.items():
            masque = x['source_dpe'].eq(source).to_numpy()
            if masque.any():
                predictions[masque] = np.asarray(
                    modele.predict(x.loc[masque])
                ).reshape(-1)
        return predictions

    def predict_proba(self, donnees):
        x = preparer_entrees(donnees)
        probabilites = np.zeros((len(x), len(self.classes_)))
        for source, modele in self.modeles_.items():
            masque = x['source_dpe'].eq(source).to_numpy()
            if masque.any():
                p = modele.predict_proba(x.loc[masque])
                colonnes = [list(self.classes_).index(c) for c in modele.classes_]
                probabilites[np.ix_(np.flatnonzero(masque), colonnes)] = p
        return probabilites

def charger_modele(chemin=None):
    if chemin is None:
        chemin = Path(__file__).parent / 'modele_dpe_combinaison.joblib'
    return joblib.load(chemin)
