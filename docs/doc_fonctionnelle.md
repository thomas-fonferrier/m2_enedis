# Documentation fonctionnelle – Application GreenTech DPE

## 1. Présentation générale

L'application GreenTech DPE aide à comprendre et à estimer la performance énergétique des logements à partir des diagnostics de performance énergétique (DPE) publiés par l'ADEME. Elle s'adresse aux chargés d'études d'Enedis, ainsi qu'aux propriétaires et aux bailleurs qui souhaitent évaluer leur logement avant des travaux ou une mise en location. Elle comporte quatre pages, accessibles depuis le menu en haut de l'écran : **Contexte**, **Exploration**, **Prédiction** et **Modèles**.

## 2. Intérêt de chaque page

### 2.1 Contexte

**Intérêt :** comprendre rapidement le sujet et ses enjeux avant d'utiliser l'outil.

**Contenu :**

- Quatre indicateurs clés : nombre de logements analysés, départements couverts, consommation médiane et part de passoires thermiques 
- le calendrier de la loi Climat et Résilience, qui interdit la location des logements G depuis 2025, puis des logements F en 2028 et E en 2034 
- l'échelle officielle du DPE, de A à G, et la liste des sources de données.

### 2.2 Exploration

**Intérêt :** analyser les données des DPE et repérer les grandes tendances avant de passer aux prédictions.

**Contenu :**

- des filtres sur le type de logement (existant ou neuf), le type de bâtiment, l'étiquette, la zone climatique, l'énergie de chauffage, la surface et l'année de construction ;
- cinq indicateurs : nombre de logements, consommation médiane, surface médiane, part de passoires thermiques et coût annuel médian ;
- une carte des logements et des graphiques : répartition des étiquettes, distribution de la consommation, consommation par étiquette et étiquettes selon l'énergie de chauffage.

### 2.3 Prédiction

**Intérêt :** estimer l'étiquette DPE et la consommation d'un logement à partir de ses caractéristiques, même lorsque certaines informations sont inconnues.

**Contenu :** trois onglets.

- **Étiquette DPE :** l'utilisateur décrit son logement (surface, année, chauffage, isolation…) et peut répondre « Je ne sais pas ». L'application affiche l'étiquette estimée et la probabilité de chaque classe.
- **Consommation :** à partir des informations de l'onglet précédent, l'application estime la consommation en kWh/m²/an et par an, et situe le logement par rapport aux autres.
- **Prédiction par lot :** l'utilisateur importe un fichier CSV contenant plusieurs logements et récupère toutes les prédictions.

### 2.4 Modèles

**Intérêt :** comprendre le fonctionnement des modèles, évaluer leur fiabilité et les mettre à jour.

**Contenu :** trois onglets.

- **Classification DPE :** méthode retenue et résultats (66 % d'étiquettes exactes, 96 % à une classe près) ;
- **Régression consommation :** résultats (erreur moyenne de 22 kWh/m²/an) et variables les plus influentes ;
- **Réentraînement :** mise à jour du modèle de consommation à partir de nouvelles données.

## 3. Fonctionnalités majeures

| Fonctionnalité | Description | Page |
|---|---|---|
| Filtrage interactif | Indicateurs, carte et graphiques mis à jour à chaque filtre | Exploration |
| Carte des logements | Logements colorés selon leur étiquette ou leur consommation | Exploration |
| Prédiction de l'étiquette DPE | Classe de A à G, niveau de confiance, alerte pour les passoires | Prédiction |
| Estimation de la consommation | Consommation au m² et annuelle, avec une fourchette indicative | Prédiction |
| Prédiction par lot | Traitement de nombreux logements en une seule fois, à partir d'un fichier CSV | Prédiction |
| Export des résultats | Graphiques en image (PNG), données et prédictions en tableau (CSV) | Exploration, Prédiction, Modèles |
| Réentraînement | Mise à jour du modèle de consommation avec de nouvelles données | Modèles |
