# Décider vite : test séquentiel

Reste la question du moment. Avec des preuves qui s'additionnent, quand
conclut-on ?

## Wald

Le test séquentiel du rapport de probabilité répond exactement à ça. On fixe
les taux d'erreur visés, alpha pour la fausse alarme et beta pour la
non-détection, et on en déduit deux seuils :

    seuil haut  A = 10 log10( (1-beta) / alpha )      conclure « imposteur »
    seuil bas   B = 10 log10( beta / (1-alpha) )      conclure « légitime »
    entre les deux : continuer à observer

Avec alpha = 0,01 et beta = 0,05 : A vaut environ 19,8 dB, B environ -19,9 dB.

La propriété qui m'intéresse : sous ses hypothèses, ce test minimise le nombre
d'observations nécessaires pour atteindre les taux d'erreur fixés. C'est la
réponse formelle à « détecter le plus tôt possible ».

Et cela résout le paradoxe apparent de la dynamique de frappe : un EER de 10 %
par décision isolée n'interdit pas une détection fiable, il impose seulement
d'accumuler assez de preuve avant de conclure.

## Oubli

Une preuve vieille de trois heures ne vaut pas une preuve d'il y a dix
secondes. L'évidence cumulée doit décroître :

    E(t) = E(t-1) * 2^(-dt / T)  +  e(t)

La demi-vie T est le paramètre sensible. Trop courte, le système oublie et ne
conclut jamais. Trop longue, il reste bloqué sur une conclusion périmée.
Première valeur d'essai : 15 minutes d'**activité effective**, pas de temps
mural, pour qu'une pause déjeuner n'efface pas l'historique.

## Niveaux

| Niveau | Évidence | P(imposteur) | Effet |
|---|---|---|---|
| L0 | E < B | < 0,01 | rien |
| L1 | B à 5 dB | 0,01 à 0,24 | rien |
| L2 | 5 à 10 dB | 0,24 à 0,50 | journalisé |
| L3 | 10 dB à A | 0,50 à 0,99 | alerte visible |
| L4 | E >= A | > 0,99 | conclusion imposteur |

Prévoir une hystérésis à la descente, sinon l'indicateur clignotera au moindre
bruit : redescendre de 3 dB sous le seuil de montée, et rester au moins 20
secondes au niveau courant.

## Deux canaux, jamais additionnés

« Ce n'est pas la même personne » et « ce n'est pas un humain » sont deux
affirmations différentes, avec des conséquences différentes. Il faut deux
évidences cumulées séparées :

- **Identité** : exige un enrôlement préalable.
- **Humanité** : n'en exige aucun, et doit être plus strict sur les fausses
  alarmes, puisqu'il conclut à une compromission.

Ne jamais les mélanger dans un score unique. L'alerte doit toujours dire lequel
des deux est en cause.
