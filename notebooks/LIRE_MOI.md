# Classification des étiquettes DPE

## Objectif

Cette partie du projet porte sur la prédiction de l’étiquette DPE, de A à G,
à partir des caractéristiques des maisons et des appartements. Le notebook
`classification_dpe.ipynb` présente la préparation des données, les expériences
de classification, l’analyse des erreurs et l’export du modèle retenu.

## Données

L’étude utilise deux extractions ADEME de 10 000 diagnostics chacune : logements
existants et logements neufs. Après harmonisation et exclusion de 494 diagnostics
d’immeubles entiers, le périmètre comprend **19 506 logements**.

| Ensemble | Existant | Neuf | Total |
|---|---:|---:|---:|
| Apprentissage | 7 746 | 7 869 | 15 615 |
| Évaluation | 1 935 | 1 956 | 3 891 |

Les diagnostics sont regroupés à partir des liens disponibles entre identifiants
DPE, identifiants RNB et informations d’adresse BAN. Aucun groupe détecté n’est
partagé entre apprentissage et évaluation.

## Préparation et protocole

- Contrôle des identifiants, des étiquettes et des valeurs manquantes.
- Analyse des caractéristiques physiques et comparaison de variantes brute et contrôlée.
- Construction de **31 caractéristiques**, dont un volume estimé à partir de la surface et de la hauteur.
- Exclusion des consommations, émissions, coûts et étiquettes des entrées du modèle.
- Imputation numérique par médiane avec indicateurs de valeurs manquantes, puis standardisation.
- Traitement des catégories manquantes et encodage disjonctif avec regroupement des modalités rares.
- Validation croisée sur quatre plis par groupes ; les transformations sont apprises dans chaque partie d’apprentissage.

Le **F1 macro** est le critère principal de comparaison. L’accuracy, la balanced
accuracy et des métriques tenant compte de la distance entre les classes
complètent l’évaluation. CatBoost et LightGBM sont étudiés avec leur propre
traitement des catégories et des valeurs manquantes.

## Modèles et sélection

Les expériences comparent une référence majoritaire, la régression logistique,
Random Forest, Extra Trees, le gradient boosting par histogrammes (HistGB),
CatBoost et LightGBM. Des essais ciblés portent sur la pondération des classes
et la complexité des arbres.

| Configuration | F1 macro hors pli |
|---|---:|
| HistGB, 31 feuilles | 0,5483 |
| Random Forest initial | 0,5405 |
| LightGBM | 0,5401 |
| CatBoost | 0,5328 |
| **Combinaison selon la source** | **0,5549** |

La combinaison retenue utilise le **HistGB à 31 feuilles pour l’existant** et le
**Random Forest pour le neuf**. Chaque modèle est entraîné sur l’ensemble
d’apprentissage ; la source détermine le modèle utilisé pour la prédiction.

## Résultats de la combinaison

| Métrique sur les 3 891 logements d’évaluation | Valeur |
|---|---:|
| Accuracy | 65,77 % |
| F1 macro | 0,5532 |
| Balanced accuracy | 0,5705 |
| Prédiction exacte ou à une classe près | 95,84 % |
| Écart moyen en classes | 0,3876 |
| Kappa quadratique | 0,8866 |

Le gain de F1 macro par rapport au HistGB seul est d’environ **0,6 point** sur cet
ensemble d’évaluation. L’importance par permutation, calculée pour le HistGB,
met principalement en évidence l’Ubat, la source du diagnostic et le type
d’énergie principal.

## Environnement et sorties

Les dépendances sont décrites dans `requirements-classification.txt`. Les deux
CSV bruts attendus par défaut sont `dpe03existant (3).csv` et `dpe02neuf (3).csv`.
Les chemins des données et des résultats sont définis dans la première cellule.

Le notebook produit les graphiques, les tableaux de scores, la partition par
groupes et un export autonome de la combinaison. Cet export comprend les
modèles entraînés, la préparation des entrées, le schéma des champs et des
exemples de prédiction. Le contrôle du rechargement confirme **3 891 prédictions
identiques** aux prédictions évaluées.

## Limites

Les classes sont déséquilibrées et plusieurs caractéristiques sont incomplètes.
Le F1 macro du neuf porte sur cinq classes présentes en validation et trois
dans l’ensemble d’évaluation : ces deux scores par source ne sont pas directement
comparables. La diversité géographique ne garantit pas une représentativité nationale.

L’ensemble d’évaluation a été consulté pendant le développement, avant certains
essais complémentaires. Les résultats décrivent donc les performances observées
sur cette partition et nécessitent une confirmation sur de nouvelles données
indépendantes. Les probabilités du modèle n’ont pas fait l’objet d’une étude de calibration.
