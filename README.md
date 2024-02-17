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

## À lire avant toute installation

Cet outil lit `/dev/input`. Il a donc techniquement les capacités d'un
enregistreur de frappe. Il est conçu pour ne jamais s'en servir ainsi, mais le
pouvoir existe.

Sous Wayland, il n'existe aucun moyen fiable de détecter qu'un champ de saisie
est un champ de mot de passe. La protection repose sur une liste noire
d'applications, une suspension manuelle immédiate, et le fait qu'aucun code de
touche n'est conservé en clair.

Un gabarit comportemental est une donnée biométrique au sens du RGPD. Ces
données ne sont pas anonymes, elles sont minimisées et confinées à la machine.
Ne jamais observer quelqu'un d'autre sans son accord explicite préalable.

## Documentation

| Document | Contenu |
|---|---|
| [00 - Analyse](docs/00-ANALYSE.md) | Points de tension, état de l'art, modèle de menace |
| [02 - Architecture](docs/02-ARCHITECTURE.md) | Composants, flux, stockage, portabilité |
| [03 - Moteur de décision](docs/03-MODELE-DECISION.md) | Fusion, décision séquentielle, étalonnage, comptage |
| [04 - Catalogue des signaux](docs/04-CATALOGUE-SIGNAUX.md) | Signaux par famille |
| [05 - Vie privée](docs/05-PRIVACY.md) | Registre de traitement, cadre juridique, éthique |
| [Protocole d'évaluation](research/PROTOCOLE-EVALUATION.md) | Métriques et règles de mesure |

Reste à écrire : le cahier des charges et la feuille de route.
