# ADR-0004 - Fusion par log-vraisemblance et décision séquentielle de Wald

- **Statut** : accepté
- **Date** : 2024-11

## Contexte

Trois exigences doivent être satisfaites simultanément : décider vite (FR-32), recouper des signaux hétérogènes (FR-31), et expliquer la décision (FR-53, FR-56). L'état de l'art donne un EER de 3 % à 10 % pour une décision isolée : une décision ponctuelle ne suffit donc pas.

## Options

1. **Score composite pondéré** (somme de distances normalisées, seuil fixe) : simple, mais l'échelle n'a pas de sens probabiliste, la pondération est arbitraire, et l'explication est une approximation.
2. **Classifieur monolithique** (forêt aléatoire, réseau de neurones sur vecteur concaténé) : meilleure performance brute possible, mais explicabilité seulement approchée (SHAP, LIME), coût en ligne supérieur, et ajout d'un signal impliquant un réentraînement complet.
3. **Fusion de log-vraisemblances plus SPRT de Wald.**

## Décision

Option 3.

Chaque expert produit un score calibré, converti en rapport de log-vraisemblance exprimé en décibans. La fusion est une somme pondérée. La décision suit un SPRT à deux seuils dérivés des taux d'erreur cibles, avec décroissance exponentielle de l'évidence ancienne.

## Justification

Les trois exigences sont satisfaites par une seule et même propriété :

- **Rapidité** : le SPRT minimise, sous ses hypothèses, le nombre d'observations nécessaires pour atteindre des taux d'erreur fixés. C'est la réponse formelle à « détecter le plus vite possible ».
- **Recoupement** : le LLR met tous les signaux sur une échelle commune ayant un sens probabiliste, ce qu'une somme de distances normalisées ne fait pas.
- **Explicabilité** : la somme étant additive, la contribution de chaque signal est **exacte**, pas estimée. L'explication n'est pas un modèle de substitution, c'est la formule elle-même lue terme à terme.

Cette dernière propriété est décisive : elle fait de l'explicabilité une conséquence du choix de moteur, et non une couche rapportée qui risquerait de mentir.

## Conséquences

- **La calibration devient obligatoire** (FR-30). Sans elle, l'addition est fausse et l'explication trompeuse. C'est le principal coût de cette décision.
- **L'hypothèse d'indépendance conditionnelle est violée** en pratique. Deux correctifs : regrouper les signaux corrélés dans un expert multivarié unique, et appliquer un facteur d'amortissement mesuré empiriquement (lot 2).
- La performance brute sera probablement inférieure à celle d'un modèle profond bien entraîné. C'est un arbitrage assumé au profit de l'explicabilité et du coût en ligne. Un modèle profond reste possible ultérieurement **à l'intérieur d'un expert**, à condition qu'il produise un score calibré.
- Ajouter un signal ne demande aucun réentraînement global : c'est un terme de plus dans la somme.
