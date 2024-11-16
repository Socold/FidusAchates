# ADR-0003 - evdev et extension GNOME Shell sous Wayland

- **Statut** : accepté
- **Date** : 2024-11

## Contexte

Poste de test : Fedora, GNOME, session **Wayland**. Wayland isole délibérément les applications les unes des autres : aucune ne peut observer les entrées destinées aux autres, ni connaître la fenêtre active, ni s'afficher au-dessus de tout.

Trois besoins se heurtent à cette isolation : la capture globale des entrées (FR-1), le contexte applicatif (FR-5) et la superposition à l'écran (FR-60).

## Constats vérifiés sur la machine

- L'utilisateur appartient au groupe `input`, donc `/dev/input/event*` est lisible **sans privilège root**.
- Aucune interface D-Bus standard n'expose la fenêtre active sous GNOME Wayland.
- `gtk-layer-shell` n'est pas supporté par Mutter : une fenêtre ordinaire ne peut pas être maintenue au-dessus de tout.

## Décision

1. **Capture** : lecture directe de `/dev/input/event*` via `evdev`, sans root, en s'appuyant sur l'appartenance au groupe `input`.
2. **Contexte et superposition** : une **extension GNOME Shell** minimale, qui publie sur D-Bus la seule catégorie de l'application focalisée et affiche l'overlay. Elle est **requise**, pas optionnelle.

## Conséquences

- L'appartenance au groupe `input` devient un prérequis d'installation, vérifié par `fidus-cli doctor`.
- **Lire `/dev/input` confère les capacités d'un enregistreur de frappe.** Cela impose : publication des sources, construction reproductible, isolement réseau structurel du processus de capture (`PrivateNetwork=yes`), et documentation frontale de ce pouvoir dans le README.
- L'extension GNOME Shell est le composant le plus privilégié côté interface. Elle doit rester assez courte pour être auditée d'une traite, et ne jamais exposer de titre de fenêtre ni de nom d'exécutable.
- `evdev` ne donne pas la notion de champ de saisie : **la détection des champs de mot de passe est impossible**. Compensée imparfaitement par la liste noire applicative (FR-6) et la suspension manuelle (FR-7). Limite documentée, non dissimulée.
- Le portage X11, Windows et macOS ne touche que l'étage `Source` de l'agent.
