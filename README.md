# Market Emotion Radar v0.5 — CAC 40 + Nasdaq 100

Application Streamlit de suivi expérimental des changements de domination acheteurs/vendeurs à partir de bougies de 5 minutes.

## Marchés

- **CAC 40** : indice **^FCHI** coté à Paris, en EUR, session régulière 09:00–17:30 Europe/Paris. Le volume de l’indice peut être absent : l’application utilise la somme des volumes des actions disponibles, avec un seuil minimum de couverture. Ce proxy n’est pas le volume de l’indice. Sans couverture suffisante, les prix restent affichés mais aucun MER ni signal exploitable n’est produit.
- **Nasdaq 100** : proxy **QQQ**, en USD, session régulière 09:30–16:00 America/New_York.

Sélectionne le marché dans la barre latérale. Le mode « Yahoo + échantillon » essaie de charger un ensemble de titres, puis se replie sur le proxy de prix si les données sont insuffisantes. Les listes sont indicatives, non exhaustives, et ne garantissent pas la composition historique exacte des indices.

## Installation et lancement

```bash
pip install -r requirements.txt
streamlit run app.py
```

Pour Streamlit Community Cloud : copier `app.py`, `markets.py`, `engine.py`, `dominance.py`, `live_data.py`, `requirements.txt` à la racine du dépôt. Le déploiement se mettra à jour au prochain commit.

## Tester

```bash
python -m pytest -q tests/test_markets.py
```

## Comment interpréter les signaux

Le MER combine breadth (35 %), momentum (30 %), pression-volume (20 %) et VWAP (15 %). Un signal LONG/SHORT exige un franchissement de seuil MER, une variation rapide sur 10 minutes, une participation dans le même sens, une cassure de prix et un volume relatif suffisant. Le détecteur impose 15 minutes de délai entre signaux.

Un signal est connu **à la clôture** d'une bougie de 5 minutes. L'étude événementielle simule une entrée à l'ouverture de la bougie suivante, puis une sortie après 5, 10, 15 ou 30 minutes. Aucun résultat historique ne prouve une performance future.

## Méthode de validation

1. Collecter plusieurs mois de données 5 minutes fiables, sans bougies incomplètes, avec calendrier de marché et constituants point-in-time.
2. Vérifier la causalité : aucune valeur de la bougie suivante n'entre dans le signal courant.
3. Fixer les seuils sur un échantillon d'entraînement et mesurer sur une période ultérieure non utilisée pour les réglages.
4. Mesurer, séparément pour CAC et Nasdaq : nombre de signaux, rendement net moyen/médian, taux de réussite, excursion favorable/défavorable, résultats par heure et par volatilité.
5. Intégrer frais, spread, glissement et liquidité réels de l'instrument négocié (ETF, CFD, future, etc.). Ne pas confondre les performances de l'ETF proxy et celles du produit effectivement tradé.
6. Comparer à une stratégie de cassure simple et à une stratégie aléatoire de même fréquence.

## Limites importantes

- Yahoo Finance peut être retardé, indisponible, ou fournir un volume peu représentatif.
- Le CAC 40 `^FCHI` n'offre pas forcément un volume intraday exploitable : nous utilisons donc un ETF proxy. Il faut valider le ticker et la qualité de ses données avant tout usage opérationnel.
- Le filtre de volume relatif compare les 6 bougies précédentes ; il ne corrige pas la saisonnalité intrajournalière.
- Le breadth de l'échantillon est non pondéré et ne représente pas tous les titres.
- Les marchés ont des horaires et jours fériés distincts ; les clôtures exceptionnelles ne sont pas intégrées.
- Ceci est un outil d'observation expérimental, pas un ordre ni un conseil financier.


## v0.5 — données CAC
Le cours est obtenu via `^FCHI` (bougies 5 minutes). Le volume est une somme des volumes d’actions de l’échantillon, susceptible de varier avec la couverture; les signaux sont expérimentaux et ne sont pas validés. Yahoo peut fournir des données retardées.
