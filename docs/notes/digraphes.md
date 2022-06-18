# Digraphes hachés

Je reviens sur le compromis laissé en suspens depuis 2018 : les latences par
digraphe sont parmi mes meilleurs signaux, et elles supposent de savoir quelles
touches ont été pressées.

## Ce que je retiens

Trois niveaux de granularité, le deuxième par défaut.

| Niveau | Conservé | Reconstruction du texte |
|---|---|---|
| P0 | classes de touches seulement | impossible |
| P1 | digraphe haché : HMAC(sel, code1, code2) tronqué à 32 bits | impossible sans le sel |
| P2 | codes en clair | possible, donc corpus de test dédiés uniquement |

Le sel est régénéré à chaque démarrage, gardé en mémoire, jamais écrit.

## Pourquoi ça marche

Le modèle a besoin de statistiques **par** digraphe, pas de savoir **quel**
digraphe. Le hachage conserve exactement la capacité de regrouper les
observations d'une même paire de touches, et rien d'autre. Avec un sel inconnu
et non persisté, le dictionnaire inversé n'est pas exploitable à partir de la
base seule, malgré le petit nombre de paires plausibles.

## Ce que ça coûte

- La rotation du sel casse la continuité des statistiques d'une session à
  l'autre. Il faut donc une table de correspondance en mémoire pour la session
  courante, et ne persister que les agrégats déjà rapprochés. C'est une vraie
  complication d'implémentation.
- Quelqu'un qui accède à la mémoire du processus récupère le sel. Cette
  protection vise la fuite de la base au repos, pas un adversaire qui a déjà
  pris le contrôle du processus.
- La troncature à 32 bits provoque des collisions. Sur quelques milliers de
  digraphes réellement observés, l'effet devrait être négligeable, mais c'est à
  mesurer, pas à supposer.
- P2 ne doit jamais redevenir le défaut par inadvertance ou par confort de
  développement. À verrouiller par un test.
