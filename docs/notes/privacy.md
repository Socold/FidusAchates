# Vie privée et cadre juridique

## Position

Cet outil peut lire tout ce qui est tapé. Autant le dire franchement plutôt que
de le minimiser. Règle que je me donne, au-dessus de toutes les autres :

> On ne collecte pas ce qu'on peut déduire, et on ne déduit pas ce dont on n'a
> pas besoin.

## Jamais

- Aucun contenu saisi, sous aucune forme, même partielle ou reconstructible.
- Aucun titre de fenêtre, nom d'exécutable, chemin, URL, terme de recherche.
- Aucun presse-papiers, aucune capture d'écran, ni caméra ni microphone.
- Aucune géolocalisation, aucun identifiant réseau.
- Aucun identifiant civil. Les profils sont des étiquettes opaques.
- Aucune connexion sortante, aucune télémétrie.
- Aucune mesure de productivité, de présence ou d'assiduité.
- Aucune action coercitive : ni verrouillage, ni blocage, ni déconnexion.

L'absence de réseau ne doit pas être une promesse mais une propriété : faire
tourner le processus de capture dans un espace de noms réseau vide. Il n'aura
pas d'accès à donner, même compromis.

## Le mot « anonyme » est faux

Le RGPD définit la donnée biométrique comme résultant d'un traitement technique
portant sur des caractéristiques physiques, physiologiques **ou
comportementales**, et permettant l'identification unique d'une personne
(art. 4-14). Un gabarit comportemental dont la fonction est précisément de
distinguer un utilisateur d'un autre entre dans cette définition, donc dans le
régime de l'article 9.

La CNIL range explicitement la dynamique de frappe dans la biométrie
comportementale.

Donc : ces données ne sont pas anonymes, elles sont pseudonymisées, minimisées
et confinées. Écrire « parfaitement anonyme » serait faux et se retournerait
contre le projet. Trois engagements vérifiables à la place :

- **sans contenu** : rien de ce qui est saisi ou affiché n'est capturé ;
- **sans identité** : aucun identifiant civil ;
- **strictement local** : rien ne sort de la machine.

## Situation actuelle

Poste personnel, propriétaire seul utilisateur, aucun tiers observé : exemption
pour activité personnelle et domestique (art. 2-2-c). Aucune formalité.

Cette exemption disparaît dès qu'une autre personne est observée, dès qu'il
s'agit d'un poste professionnel, ou dès qu'on publie des résultats portant sur
un tiers. Il faudrait alors un consentement explicite au titre de l'article
9-2-a, une analyse d'impact, et une information préalable complète.

## Mesures techniques

- Chiffrement de la base au repos, clé dans le trousseau du système.
- Aucun événement brut persisté : propriété du schéma, pas politique de purge.
  Ce qui n'existe pas ne peut pas fuir.
- Rétention bornée par défaut, purge automatique.
- Purge totale et suspension immédiate accessibles en une commande.
- Liste noire d'applications pour lesquelles la capture est suspendue.

## Risque de détournement

Le projet produit une brique techniquement proche d'un enregistreur de frappe.
Le nier serait malhonnête. Contre-mesures : aucune fonction de remontée à
détourner, aucune fonction permettant de se dissimuler, aucune action
coercitive, et documentation frontale plutôt qu'en note de bas de page.
