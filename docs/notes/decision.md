# Combiner les signaux : première approche

Chaque signal pris isolément est faible. L'état de l'art donne des taux
d'erreur de l'ordre de 10 % pour une décision ponctuelle. Il faut donc croiser,
et accumuler.

## Approche naïve

Normaliser chaque signal en écarts à la référence, sommer avec des poids,
comparer à un seuil :

    score = somme( poids_i * |x_i - mediane_i| / MAD_i )

Utiliser la médiane et l'écart absolu médian plutôt que moyenne et écart-type :
les valeurs aberrantes sont la règle, pas l'exception.

## Ce qui ne va pas

Trois problèmes, et je ne vois pas comment les résoudre dans ce cadre.

1. **L'échelle n'a pas de sens.** Un score de 4,7 ne veut rien dire. Impossible
   d'en tirer une probabilité, donc impossible d'annoncer un niveau de
   confiance honnête à l'utilisateur.
2. **Les poids sont arbitraires.** Rien ne dit comment les fixer, sinon à la
   main et au jugé.
3. **Le seuil est fixe.** Donc soit on décide vite et on se trompe, soit on
   attend et on ne détecte rien. Aucun moyen de régler explicitement le
   compromis entre fausse alarme et non-détection.

## Piste

Passer à des rapports de vraisemblance. Pour chaque signal, comparer la
probabilité de l'observation sous l'hypothèse « c'est bien lui » à celle sous
l'hypothèse « c'est quelqu'un d'autre ». Le logarithme de ce rapport s'additionne
naturellement, et il a une interprétation.

À creuser sérieusement, y compris la question de l'accumulation dans le temps.
