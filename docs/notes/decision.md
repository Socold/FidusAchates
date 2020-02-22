# Combiner les signaux : rapports de vraisemblance

Le score composite pondéré est abandonné. Trois défauts rédhibitoires :
échelle dénuée de sens, poids arbitraires, seuil fixe sans rapport avec un
taux d'erreur. Remplacé par ce qui suit.

## Principe

Pour chaque signal `i` observé à la valeur `x_i`, on mesure la **preuve**
apportée :

    e_i = 10 * log10 [ P(x_i | legitime) / P(x_i | imposteur) ]

Positif : l'observation soutient l'utilisateur légitime. Négatif : elle le
contredit. Nul : le signal n'apprend rien.

L'unité est le **déciban**. Elle est additive et elle se dit en français :
« cette rafale a apporté 12 dB de preuve contre l'utilisateur légitime ».

## Ce que ça règle

1. **L'échelle a un sens.** On peut afficher une probabilité honnête :

       P(imposteur) = 1 / (1 + 10^(E/10))

2. **Les poids ne sont plus arbitraires.** La fiabilité d'un signal se déduit
   de son taux d'erreur mesuré. Reste une pondération par la qualité de
   l'observation courante : un signal calculé sur trois observations ne doit
   pas peser autant que sur trois cents.

3. **Le recoupement est une addition.** Des signaux de natures très
   différentes deviennent comparables parce qu'ils sont tous exprimés en
   preuve.

## Le bénéfice auquel je ne m'attendais pas

Comme la fusion est une **somme**, la contribution de chaque signal à la
décision est exacte. Pas approchée, pas estimée par un modèle de substitution :
exacte. L'explication qu'on affichera, c'est la formule elle-même lue terme à
terme.

Autrement dit, l'explicabilité n'est pas une couche à rajouter plus tard, elle
est une propriété du choix de moteur. Cela suffit à trancher en sa faveur,
même si un modèle monolithique devait être un peu plus performant.

## Ce que ça coûte

- **Il faut calibrer.** Les scores bruts des experts ne sont pas des
  probabilités. Sans calibration, l'addition est fausse et l'explication ment.
  C'est le prix à payer, et il n'est pas négociable.
- **L'indépendance conditionnelle est fausse.** Vitesse de frappe et latence
  des digraphes sont corrélées. Deux correctifs : regrouper les signaux
  corrélés dans un même expert multivarié, et appliquer un facteur
  d'amortissement sur la somme, mesuré empiriquement et non deviné.

## Densité imposteur

Il faut deux densités par signal. Celle du légitime s'estime à l'enrôlement.
Celle de l'imposteur, par ordre de préférence : les autres profils de la
machine, une population de référence issue des corpus publics, ou à défaut un
modèle large non informatif.
