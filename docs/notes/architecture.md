# Architecture

## Découpage

- **agent** : capture, extraction des signaux, experts, fusion, décision.
  Processus unique, sans root, lancé par `systemd --user`.
- **extension GNOME Shell** : contexte applicatif sur D-Bus, et affichage de
  l'alerte. Deux fonctions, rien d'autre.
- **console** : serveur local lié à la boucle locale, protégé par un jeton
  régénéré à chaque démarrage. Diffusion temps réel par SSE plutôt que
  WebSocket : le flux est unidirectionnel, SSE se reconnecte seul et coûte
  moins cher.
- **CLI** : état, pause, reprise, purge, export, diagnostic.
- **laboratoire** : rejeu et évaluation, hors ligne, jamais résident.

## Langage

Rust pour l'agent. Ce qui décide, c'est qu'il tourne en permanence : pas de
ramasse-miettes, empreinte mémoire prévisible, accès `evdev` direct, binaire
unique sans dépendance d'exécution.

Python pour le laboratoire, qui ne tourne qu'à la demande sur des traces
figées. J'y gagne une boucle d'expérimentation rapide sans alourdir l'agent
d'un environnement d'apprentissage.

Le prix : un modèle validé dans le laboratoire doit être porté dans l'agent.
Je le rends vérifiable en exigeant un rejeu déterministe : même trace, même
sortie des deux côtés, sinon c'est un défaut.

## Étages de l'agent

| Étage | Rôle |
|---|---|
| 1 | Capture `evdev`, normalisation, marquage de provenance |
| 2 | Tampon circulaire en mémoire, 10 s au plus, jamais persisté |
| 3 | Extraction des signaux en flux, agrégats de Welford |
| 4 | Experts : un score calibré par modalité |
| 5 | Fusion : somme pondérée de preuves |
| 6 | Décision séquentielle, niveaux |
| 7 | Profils : regroupement, révisions |

Un nouvel expert doit pouvoir s'ajouter sans toucher au cœur. C'est une
conséquence directe du choix de fusion additive : un expert de plus, c'est un
terme de plus dans la somme.

## Stockage

SQLite en mode WAL, un seul fichier, chiffré au repos.

Strates de rétention décroissante : vecteurs de fenêtre 7 jours, agrégats 90
jours, gabarits tant que le profil existe, décisions 90 jours, révisions de
profils en permanence (le volume est négligeable), santé 7 jours.

**Aucune table d'événements bruts.** C'est une propriété du schéma, pas une
politique de purge.

Quantiles maintenus par estimateur incrémental, pour rester en mémoire bornée.

## Portabilité

Seul l'étage 1 est spécifique au système. Sous Windows, la provenance
synthétique est même plus facile à établir qu'ici, l'API signale explicitement
les événements injectés.
