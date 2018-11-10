# Modèle de menace

Ce que l'outil devrait détecter, par difficulté croissante.

| # | Scénario | Ce qui devrait trahir | Difficulté |
|---|---|---|---|
| M1 | Poste laissé déverrouillé, un tiers s'en sert | Tout diverge en même temps | Faible |
| M2 | Injection matérielle (BadUSB, clé de type Rubber Ducky) | Régularité anormale, débit soutenu | Faible |
| M3 | Automatisation locale (script, robot de test) | Provenance virtuelle du périphérique, trajectoires idéales | Faible |
| M4 | Prise de contrôle à distance (RDP, VNC, cheval de Troie) | Rafales alignées sur la latence réseau, événements groupés | Moyenne |
| M5 | Imposteur humain non informé | Divergence progressive sur plusieurs modalités | Moyenne |
| M6 | Imposteur humain ayant observé la victime | Ne reste que l'involontaire : micro-corrections, Fitts, digraphes rares | Élevée |
| M7 | Contrefaçon entraînée sur les statistiques du gabarit | Cohérence entre modalités, signaux de second ordre | Très élevée |

Remarque importante : M2, M3 et M4 ne demandent **aucune** connaissance de
l'utilisateur. On peut les détecter sur une machine vierge, dès la première
seconde, sans avoir appris quoi que ce soit. C'est probablement ce qu'il faut
construire en premier.

## Menaces contre l'outil lui-même

Un outil qui lit les entrées est une cible.

- M8 : vol du gabarit. Il faut chiffrer au repos.
- M9 : empoisonnement. Si le gabarit s'adapte en continu, un imposteur patient
  peut le faire dériver vers lui. Il faudra brider l'adaptation et garder une
  référence gelée.
- M10 : arrêt silencieux de l'agent par l'attaquant. Détecter les trous.
- M11 : accès à l'interface d'administration par l'imposteur lui-même.

## Remarque sur le retour visuel

Afficher une alerte à l'écran prévient l'imposteur qu'il est repéré et lui
permet d'itérer jusqu'à passer dessous. Utile pour un banc d'essai, à éviter
en usage réel. Prévoir deux modes.
