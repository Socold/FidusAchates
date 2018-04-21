# Dynamique de frappe : état de l'art

Modalité la plus ancienne et la mieux documentée.

## Mesures de base

Pour chaque touche et chaque paire de touches :

- **temps de maintien** : durée entre l'appui et le relâchement ;
- **temps de vol** : entre le relâchement d'une touche et l'appui de la suivante ;
- **latences DD, UU, DU, UD** : les quatre combinaisons appui / relâchement
  entre deux touches consécutives.

Les latences par **digraphe** (paire de touches) sont les plus discriminantes.
Les trigraphes apportent encore un peu.

## Texte imposé

Le banc d'essai de référence est le jeu de données de Killourhy et Maxion
(Carnegie Mellon, 2009) : 51 sujets, 8 sessions espacées d'au moins un jour,
même mot de passe tapé 400 fois.

Résultat marquant : le meilleur détecteur simple y est la **distance de
Manhattan mise à l'échelle**, avec un taux d'erreur égal d'environ 0,096.
Des méthodes bien plus sophistiquées ne font pas mieux.

Un EER de 10 % pour une décision isolée, c'est mauvais pris tel quel. Mais on
n'a pas besoin de trancher sur une seule observation : on peut accumuler.
C'est le point central à retenir.

## Texte libre

Plus proche de mon cas. Gunetti et Picardi (2005) proposent deux mesures, R et
A, sur les n-graphes partagés entre deux échantillons. Elles supportent bien le
fait que deux textes libres ne contiennent pas les mêmes suites de touches.

## Problème immédiat

Les digraphes supposent de savoir **quelles** touches ont été pressées. C'est
exactement ce que je me suis interdit. Trois pistes :

1. ne garder que des classes de touches (lettre, chiffre, espace, correction) :
   on perd le meilleur signal ;
2. garder les codes en clair : inacceptable ;
3. hacher la paire de touches avec un sel : on conserve la capacité de
   regrouper les observations d'un même digraphe sans pouvoir reconstituer le
   texte. À creuser, c'est probablement la bonne réponse.

## Signaux annexes à ne pas oublier

- taux de correction (retours arrière), très personnel ;
- chevauchement de touches : la suivante pressée avant relâchement de la
  précédente. Trahit le doigté, et un automate n'en produit jamais ;
- préférence Maj gauche ou Maj droite pour une même lettre ;
- usage du pavé numérique contre la rangée de chiffres.

## Sur la falsification

Stefan et al. (2010) montrent qu'un générateur entraîné sur des statistiques
agrégées peut produire une frappe qui passe. À garder comme modèle de menace,
pas à ignorer.
