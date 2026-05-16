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
| [01 - Cahier des charges](docs/01-CAHIER-DES-CHARGES.md) | Exigences numérotées et vérifiables, critères d'acceptation |
| [02 - Architecture](docs/02-ARCHITECTURE.md) | Composants, flux, stockage, portabilité |
| [03 - Moteur de décision](docs/03-MODELE-DECISION.md) | Fusion, décision séquentielle, étalonnage, comptage |
| [04 - Catalogue des signaux](docs/04-CATALOGUE-SIGNAUX.md) | Signaux par famille |
| [05 - Vie privée](docs/05-PRIVACY.md) | Registre de traitement, cadre juridique, éthique |
| [Protocole d'évaluation](research/PROTOCOLE-EVALUATION.md) | Métriques et règles de mesure |
| [06 - Feuille de route](docs/06-ROADMAP.md) | Lots et critères d'acceptation |
| [ADR](docs/adr/) | Décisions d'architecture et alternatives écartées |

## Empreinte, installation et autorisations

L'outil est fait pour être installé une fois et oublié. Son coût se mesure **au repos**, état dans lequel il passe la quasi-totalité de son temps.

**Exécution.** L'agent est piloté par les événements : il reste bloqué sur `epoll` en attente des descripteurs d'entrée. Sans frappe ni mouvement, il ne s'exécute pas du tout, et ne réveille pas le processeur. Aucune boucle de sondage, nulle part. La console n'existe pas tant qu'on ne l'ouvre pas : elle est démarrée par activation de socket.

| | Au repos | En activité |
|---|---|---|
| Processeur | 0 % | moins de 1 % en moyenne |
| Mémoire résidente | moins de 40 Mo | moins de 40 Mo |
| Stockage | moins de 2 Mo par jour d'usage intensif | |
| Binaire | moins de 8 Mo, empreinte installée moins de 15 Mo | |

**Autorisations demandées, en totalité :**

| Autorisation | Quand | Révocation |
|---|---|---|
| Appartenance au groupe `input` | Une seule fois, à l'installation | `sudo gpasswd -d $USER input` |

Rien d'autre, à aucun moment : **pas de root à l'exécution**, pas de setuid, pas de capability, pas de module noyau, pas de service système (uniquement `systemd --user`), pas d'accès réseau, pas d'autorisation d'accessibilité, pas d'extension de navigateur, aucun fichier de configuration du système modifié.

Cette unique autorisation est néanmoins un privilège fort : elle donne accès à toutes les entrées de la session. Elle est incompressible pour une capture globale sous Wayland. Le projet ne la présente pas comme anodine, il la réduit au strict nécessaire et la compense par l'auditabilité des sources et un isolement réseau structurel (`PrivateNetwork=yes` : le processus de capture n'a pas d'accès réseau à donner, même compromis). Voir [ADR-0006](docs/adr/0006-moindre-privilege-installation.md).

**Installation.** Une commande, binaire précompilé, aucune chaîne de compilation requise, moins de 60 secondes jusqu'au premier événement traité. Désinstallation complète en une commande, purge des données comprise.

L'extension GNOME Shell est **facultative** : sans elle, l'agent fonctionne en mode dégradé (perte du contexte applicatif et de l'overlay, remplacé par une notification de bureau). L'installation n'échoue jamais faute d'extension.

**Prérequis (à partir du lot 1)**

- Linux, session Wayland ou X11 (développé sur Fedora / GNOME / Wayland)
- Appartenance au groupe `input`
- Facultatif : GNOME Shell, pour le contexte applicatif et l'overlay
- Pour contribuer au code : Rust stable ; pour `fidus-lab`, Python 3.12 ou supérieur, hors ligne uniquement

## Licence

**PolyForm Noncommercial 1.0.0.** Lecture, modification, redistribution et usage
autorisés à des fins de **recherche, d'étude et d'enseignement**. **Usage
commercial interdit.** Je réserve tous les droits commerciaux et la possibilité
de relicencier plus tard.

Le terme « open source » au sens de l'Open Source Initiative ne s'applique pas :
une restriction de champ d'usage est incompatible avec le critère 6 de la
définition. Le projet se décrit donc comme **source-available**, et comme projet
de recherche ouvert. Voir [ADR-0002](docs/adr/0002-licence-non-commerciale.md).

Contributions : voir [CONTRIBUTING.md](CONTRIBUTING.md).
