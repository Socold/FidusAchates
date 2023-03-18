# Étalonnage : quand le modèle est-il prêt ?

La question que je me pose depuis le début : à partir de quelle durée
d'utilisation suis-je sûr d'avoir assez de données ?

La réponse est qu'une durée ne veut rien dire. Deux heures de frappe intensive
valent mieux que trois semaines à consulter des pages. Ce qu'il faut, ce n'est
pas postuler un X, c'est le **mesurer**.

## Quatre critères de convergence

L'enrôlement se termine quand les quatre sont atteints simultanément. Chacun
s'affiche en pourcentage.

| Critère | Ce qu'il vérifie | Valeur d'essai |
|---|---|---|
| C1 volume | assez d'observations par modalité | 10 000 frappes, 5 000 événements de pointage, 300 pointages avec cible, 8 sessions, 5 jours distincts |
| C2 stabilité | le gabarit ne bouge plus : divergence de Jensen-Shannon entre le gabarit à t et à t-delta | sous 0,02 sur 3 fenêtres de 24 h |
| C3 performance | EER auto-estimé par validation croisée temporelle contre population de référence, avec intervalle bootstrap | borne haute de l'intervalle sous 8 % |
| C4 couverture | diversité des contextes | 4 catégories d'applications, 3 plages horaires, tous les périphériques usuels |

C3 est le seul qui mesure directement ce qui m'intéresse. C1 empêche de le
calculer sur trop peu de données, C2 garantit que je n'ai pas figé un régime
transitoire, C4 que je n'ai pas appris un seul contexte.

## La courbe

Le système trace l'EER estimé en fonction du volume d'enrôlement, recalculé à
chaque palier. Elle donne le X empirique pour cette machine et cette personne,
le temps restant au rythme d'usage observé, et un résultat comparable puisque
la même courbe se calcule sur les corpus publics.

## Phases

Amorçage (observe, ne décide rien, seul le canal Humanité fonctionne puisqu'il
ne demande pas d'enrôlement), puis Enrôlement (construit le gabarit, seuils
élargis, affiche que la fiabilité est partielle), puis Opérationnel, puis
Adaptation continue.

## Empoisonnement

L'adaptation continue est une porte d'entrée : un imposteur patient peut faire
glisser le gabarit vers lui. Trois garde-fous :

1. seules les fenêtres franchement classées légitimes alimentent la mise à
   jour ;
2. le gabarit ne peut pas bouger de plus d'une fraction fixée par 24 heures,
   quelle que soit la quantité de données ;
3. le gabarit d'enrôlement est **gelé** et sert d'ancre. Un expert compare en
   permanence le gabarit courant à cette ancre, et une dérive cumulée trop
   forte déclenche une alerte, pas un ajustement silencieux.
