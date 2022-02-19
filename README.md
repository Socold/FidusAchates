# FidusAchates

**Authentification continue implicite par biométrie comportementale, locale et
explicable.**

*Fidus Achates* : le compagnon fidèle d'Énée. Celui qui marche à côté, qui
reconnaît, et qui prévient.

L'authentification est un événement, pas un état. On prouve son identité une
fois, à l'ouverture de session, et plus jamais ensuite. FidusAchates apprend la
manière dont j'utilise la machine, puis vérifie en permanence deux choses
distinctes :

1. est-ce toujours la même personne ?
2. est-ce encore un humain ?

Le tout sans jamais enregistrer ce qui est tapé, sans aucun accès réseau, et en
expliquant chaque conclusion.

## Ce que l'outil ne fait pas

Aucun contenu saisi, aucun titre de fenêtre, aucune URL, aucun presse-papiers.
Aucune connexion sortante. Aucune mesure de productivité ou de présence. Aucune
action sur la machine : il observe et signale, il ne verrouille rien.

Un gabarit comportemental est une donnée biométrique au sens du RGPD. Ces
données ne sont donc pas anonymes, elles sont minimisées et confinées à la
machine. Ne jamais observer quelqu'un d'autre sans son accord explicite.

## Notes de travail

- [Idée et périmètre](docs/notes/idee.md)
- [Dynamique de frappe](docs/notes/frappe.md)
- [Dynamique du pointeur](docs/notes/souris.md)
- [Modèle de menace](docs/notes/menaces.md)
- [Catalogue de signaux](docs/notes/signaux.md)
- [Combien de personnes utilisent la machine](docs/notes/profils.md)
- [Fusion des signaux](docs/notes/decision.md)
- [Décision séquentielle](docs/notes/decision-sequentielle.md)
- [Vie privée et cadre juridique](docs/notes/privacy.md)
- [Contraintes Wayland](docs/notes/wayland.md)
- [Architecture](docs/notes/architecture.md)
- [Détecter ce qui n'est pas humain](docs/notes/automation.md)
