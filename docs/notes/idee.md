# Idée et périmètre

## Le problème

L'authentification est un événement, pas un état. Après l'ouverture de session,
plus rien ne vérifie que la personne aux commandes est bien celle qui s'est
authentifiée. Un poste laissé déverrouillé, un mot de passe partagé, une session
reprise par quelqu'un d'autre : dans tous ces cas, le système continue
d'attribuer les actions au compte, sans jamais se poser la question.

## Ce que je veux tester

Qu'une personne se trahit par sa manière de faire, indépendamment de ce qu'elle
fait. Le rythme de frappe, la façon de déplacer un curseur, l'ordre dans lequel
on ouvre ses outils : ce sont des gestes appris, largement involontaires, donc
difficiles à imiter délibérément.

## Questions à traiter séparément

Je note dès maintenant qu'il y a plusieurs questions distinctes, et je ne dois
pas les confondre :

1. Est-ce toujours la même personne qu'à l'ouverture de session ?
2. Combien de personnes différentes utilisent cette machine ?
3. Ce qui pilote la machine est-il seulement humain ?
4. Comment justifier la réponse ?

La question 2 est un problème de classification sans étiquettes ni nombre de
classes connu. La question 3 est probablement la plus facile et la plus utile :
un automate a une régularité qu'un humain n'a pas.

## Limites que je me fixe

- Aucun contenu saisi n'est conservé. Ni texte, ni titre de fenêtre, ni URL.
- Rien ne sort de la machine.
- L'outil observe et signale. Il ne bloque rien, ne verrouille rien.
- Ce n'est pas un outil de surveillance de l'activité ou de la productivité.

## À creuser

- Quelle quantité de données faut-il avant de reconnaître quelqu'un de façon
  fiable ? Une durée fixe ne veut rien dire, il faut un critère mesurable.
- Comment combiner des signaux de natures différentes sans additionner des
  choux et des carottes ?
- Le RGPD devient applicable en mai. Un gabarit comportemental qui identifie
  une personne est probablement une donnée biométrique. À vérifier.
