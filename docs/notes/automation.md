# Détecter ce qui n'est pas humain

C'est la partie la plus rentable du projet, et je ne l'avais pas assez creusée.
Aucun de ces signaux ne demande d'enrôlement : ils fonctionnent sur une machine
vierge, dès la première seconde, et ils ne stockent aucun gabarit personnel.

| ID | Signal | Disc. | Falsif. |
|---|---|---|---|
| E01 | Provenance du périphérique : virtuel contre matériel réel | Très élevé | 4 |
| E02 | Horodatages quantifiés sur une grille (1 ms, 10 ms, une trame) | Très élevé | 3 |
| E03 | Sous-dispersion : régularité de métronome, qu'aucun humain n'a | Élevé | 2 |
| E04 | Entropie des intervalles, comparée à la référence humaine | Élevé | 2 |
| E05 | Débit soutenu au-delà du plausible | Élevé | 1 |
| E06 | Production longue sans aucune correction | Élevé | 2 |
| E07 | Chevauchement de touches strictement nul à vitesse élevée | Très élevé | 4 |
| E08 | Curseur qui se téléporte, sans positions intermédiaires | Très élevé | 4 |
| E09 | Trajectoire idéale : droite parfaite ou courbe trop lisse | Très élevé | 3 |
| E10 | Aucune micro-correction alors que les cibles sont petites | Très élevé | 4 |
| E11 | Rafales alignées sur une latence réseau (RDP, VNC) | Élevé | 3 |
| E12 | Rejeu de presse-papiers émis en frappes par un KVM sur IP | Très élevé | 3 |
| E13 | Ordre d'événements physiquement impossible | Très élevé | 4 |
| E14 | Incohérence entre modalités : frappe humaine, souris synthétique | Très élevé | 4 |
| E15 | Enchaînement d'applications plus rapide que le temps de réaction | Élevé | 3 |
| E16 | Action sur un contenu nouveau sans délai de lecture plausible | Élevé | 4 |
| E17 | Défilement par incréments rigoureusement constants | Élevé | 3 |

## Le piège à éviter

Les heuristiques fondées sur la seule vitesse ou la seule régularité se
contournent trivialement : il suffit de ralentir et de randomiser les délais.
E03 et E05 ne valent donc que contre un adversaire naïf.

Les signaux qui tiennent contre un adversaire qui sait ce qu'il fait sont ceux
qu'il faudrait reproduire physiquement : la provenance du périphérique, le
chevauchement de touches, les micro-corrections de pointage, la cohérence entre
modalités, et les impossibilités physiques.

Un automate qui voudrait passer devrait simuler un humain plausible sur toutes
les modalités à la fois, en restant cohérent. C'est beaucoup plus dur que de
ralentir sa frappe.

## Banc d'attaque à construire

1. automatisation locale par outil d'injection ;
2. injection matérielle ;
3. rejeu de presse-papiers par KVM sur IP ;
4. session distante RDP puis VNC ;
5. contrefaçon statistique entraînée sur les agrégats du gabarit ;
6. adversaire adaptatif qui ralentit et randomise pour contourner E03 et E05.

Le scénario 6 est celui qui compte : c'est lui qui dira si les signaux non
temporels tiennent.
