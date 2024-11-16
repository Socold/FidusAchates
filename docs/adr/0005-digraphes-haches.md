# ADR-0005 - Digraphes hachés et salés comme compromis par défaut

- **Statut** : accepté
- **Date** : 2024-11

## Contexte

Les latences par digraphe sont parmi les signaux les plus discriminants de la dynamique de frappe. Elles supposent de savoir quelles touches ont été pressées. Or conserver l'identité des touches, c'est construire un enregistreur de frappe, ce que PR-1 interdit.

## Options

1. **Classes de touches seulement** : aucun risque, mais perte du signal A05, l'un des plus forts.
2. **Keycodes en clair** : performance maximale, reconstruction du texte possible. Inacceptable en usage réel.
3. **Digraphes hachés avec un sel volatil** : `HMAC(sel, code1 ‖ code2)` tronqué à 32 bits, agrégé en ligne.

## Décision

Option 3 par défaut (niveau P1), avec l'option 1 disponible (P0) et l'option 2 réservée aux corpus de test dédiés (P2, avertissement permanent affiché).

Le sel est régénéré à chaque démarrage de l'agent, conservé **en mémoire uniquement**, jamais écrit sur disque.

## Justification

Le modèle a besoin de statistiques *par digraphe*, pas de savoir *quel* digraphe. Le hachage conserve exactement la capacité de regrouper les observations de la même paire de touches, tout en rendant le dictionnaire inversé inexploitable : avec un sel inconnu et non persisté, une attaque par dictionnaire sur un espace pourtant petit (quelques milliers de paires plausibles) ne peut pas être montée hors ligne à partir de la base seule.

## Conséquences

- **La rotation du sel casse la continuité des statistiques par digraphe d'une session à l'autre.** L'agent maintient donc en mémoire une table de correspondance pour la session courante, et ne persiste que les agrégats déjà rapprochés. C'est une complexité réelle à implémenter au lot 1.
- Un attaquant ayant accès à la mémoire du processus en cours d'exécution peut récupérer le sel. Cette protection vise la fuite de la base au repos, pas un adversaire ayant déjà le contrôle du processus.
- La troncature à 32 bits provoque des collisions. Sur quelques milliers de digraphes effectivement observés, leur effet sur les statistiques est négligeable, mais il doit être **mesuré** au lot 3 et non supposé.
- Le niveau P2 ne doit jamais devenir le défaut, par inadvertance ou par confort de développement. Un test de configuration le vérifie.
