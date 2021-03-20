# Contraintes Wayland

Ma machine est passée sous Wayland. Une bonne partie de ce que je prévoyais ne
fonctionne plus : Wayland isole délibérément les applications, aucune ne peut
observer les entrées destinées aux autres, ni savoir quelle fenêtre a le focus,
ni s'afficher au-dessus de tout.

Trois besoins se heurtent à cette isolation.

## Capture globale

Impossible par les interfaces de bureau. Reste la lecture directe de
`/dev/input/event*`, sous la couche graphique.

Bonne nouvelle : mon compte appartient déjà au groupe `input`, donc ces
descripteurs sont lisibles **sans privilège root**. C'est la voie à prendre.

Mauvaise nouvelle : lire `/dev/input`, c'est exactement la capacité d'un
enregistreur de frappe. Je l'assume, mais cela impose des contreparties :
sources lisibles, construction reproductible, et surtout un isolement réseau
qui soit structurel et non promis. Si le processus de capture tourne dans un
espace de noms réseau vide, il n'a rien à exfiltrer, même compromis.

## Fenêtre active

Aucune interface standard ne l'expose sous GNOME Wayland. Il faut une extension
GNOME Shell qui publie l'information sur D-Bus.

Je m'en tiens à la **catégorie** de l'application (navigateur, terminal,
bureautique, développement, communication, média, autre) plus un identifiant
opaque. Jamais le titre, jamais le nom de l'exécutable.

## Affichage au-dessus de tout

`gtk-layer-shell` n'est pas supporté par Mutter. Une fenêtre ordinaire ne peut
pas rester au premier plan. Il faut donc, là aussi, passer par l'extension.

L'extension GNOME Shell n'est donc pas un confort, c'est un composant requis,
pour deux fonctions distinctes. À garder assez courte pour être relue d'une
traite : c'est le composant le plus privilégié côté interface.

## Ce que je perds définitivement

`evdev` ne connaît pas la notion de champ de saisie. **Il n'y a aucun moyen
fiable de savoir qu'un champ est un champ de mot de passe.**

Je ne peux compenser qu'imparfaitement : liste noire d'applications, suspension
manuelle immédiate, et surtout ne jamais conserver de code de touche en clair.
Cette limite doit être écrite en tête du fichier d'accueil, pas en note de bas
de page.
