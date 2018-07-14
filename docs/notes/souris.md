# Dynamique du pointeur : état de l'art

Moins étudiée que la frappe, mais au moins aussi prometteuse, et surtout
disponible dans les moments où l'on ne tape pas. Pour une surveillance
continue, c'est décisif.

## Travaux

Ahmed et Traore (2007) : courbes de vitesse par direction de déplacement, une
des premières approches systématiques.

Le **Balabit Mouse Dynamics Challenge** (2016) est le premier corpus public :
10 utilisateurs en tâches d'administration. Défauts connus (peu de sujets,
tâches non contrôlées) mais c'est la seule base commune disponible. Les
résultats publiés tournent autour de 7 à 13 % d'EER.

## Mesures

- vitesse, accélération, et la dérivée troisième (l'à-coup), très liée à la
  motricité fine ;
- courbure de la trajectoire, et rectitude (distance parcourue rapportée à la
  distance directe) ;
- dépassement de la cible, puis micro-corrections dans les derniers pixels ;
- pause avant le clic, durée du clic, intervalle de double-clic ;
- molette : amplitude par cran, cadence, inversions de sens.

## Loi de Fitts

L'idée la plus intéressante que j'aie trouvée. Le temps de pointage suit

    T = a + b log2(D/W + 1)

avec D la distance à la cible et W sa largeur. Le couple (a, b) s'estime par
régression sur les pointages ordinaires, sans rien demander à l'utilisateur.

C'est une caractéristique motrice individuelle, stable, et très peu coûteuse à
calculer. Personne ne semble l'utiliser comme signature biométrique. À tester
en priorité.

## Micro-corrections

Un humain qui pointe une petite cible dépasse, corrige, hésite. Ces ajustements
sont involontaires, donc très difficiles à imiter, et un automate n'en produit
aucun. Double intérêt : reconnaître la personne, et reconnaître qu'il s'agit
d'une personne.

## Autres modalités, pour mémoire

Tactile et inertiel sur mobile : Touchalytics (Frank et al., 2013) pour les
gestes de glissement, HMOG pour la prise en main et l'orientation. Hors
périmètre pour l'instant : sur téléphone, rien ne permet d'observer en dehors
de sa propre application.
