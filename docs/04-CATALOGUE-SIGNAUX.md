# 04 - Catalogue des signaux

> Répond à FR-10 et FR-11. Chaque signal est destiné à devenir une ligne testable.

**Colonnes** :
- **Coût** : charge de calcul (F faible, M moyen, E élevé).
- **Disc.** : pouvoir discriminant attendu, d'après l'état de l'art ou par raisonnement (à confirmer par mesure au lot 3 ; les valeurs sont des hypothèses).
- **Falsif.** : difficulté pour un adversaire de falsifier ce signal, de 1 (facile) à 4 (très difficile).
- **Lot** : lot d'implémentation prévu.

---

## Famille A - Dynamique de frappe

| ID | Signal | Définition | Coût | Disc. | Falsif. | Lot |
|---|---|---|---|---|---|---|
| A01 | Temps de maintien | Durée appui / relâchement, par classe de touche | F | Élevé | 2 | 1 |
| A02 | Temps de vol | Intervalle relâchement / appui suivant | F | Élevé | 2 | 1 |
| A03 | Latence DD | Appui / appui suivant | F | Élevé | 2 | 1 |
| A04 | Latence UU | Relâchement / relâchement suivant | F | Moyen | 2 | 1 |
| A05 | Digraphes | Statistiques par paire de touches (hachée en P1) | M | Très élevé | 3 | 1 |
| A06 | Trigraphes | Statistiques par triplet, sur les plus fréquents seulement | M | Très élevé | 3 | 3 |
| A07 | Chevauchement | Vol négatif : touche suivante pressée avant relâchement de la précédente. Trahit la dextérité et le doigté | F | Très élevé | 4 | 1 |
| A08 | Vitesse de frappe | Caractères par minute, en glissant | F | Moyen | 1 | 1 |
| A09 | Rythme | Structure des rafales et des pauses : longueur des rafales, durée des pauses | M | Élevé | 3 | 2 |
| A10 | Taux de correction | Proportion de retours arrière et de suppressions | F | Élevé | 3 | 1 |
| A11 | Profondeur de correction | Nombre de caractères effacés par épisode de correction | F | Élevé | 3 | 2 |
| A12 | Latence de correction | Délai entre l'erreur et le début de la correction. Très personnel : trahit la vitesse de relecture | M | Élevé | 4 | 3 |
| A13 | Préférence de Maj | Maj gauche contre Maj droite pour une même lettre | F | Très élevé | 4 | 2 |
| A14 | Verr. Maj contre Maj | Stratégie pour les majuscules consécutives | F | Moyen | 3 | 3 |
| A15 | Usage des modificateurs | Fréquence et combinaisons Ctrl, Alt, Super, AltGr | F | Moyen | 2 | 2 |
| A16 | Répertoire de raccourcis | Ensemble des raccourcis employés et leur fréquence relative | F | Élevé | 3 | 3 |
| A17 | Clavier contre souris | Part des actions faites au clavier plutôt qu'à la souris pour une même fonction | F | Élevé | 3 | 3 |
| A18 | Doubles lettres | Cadence des lettres répétées consécutives | F | Moyen | 3 | 3 |
| A19 | Pavé numérique | Usage du pavé numérique contre rangée de chiffres | F | Élevé | 3 | 3 |
| A20 | Ponctuation et espaces | Délais autour des espaces et de la ponctuation, double espace après point | M | Moyen | 3 | 3 |
| A21 | Répétition automatique | Usage du maintien de touche pour répéter, plutôt que d'appuis successifs | F | Moyen | 3 | 4 |
| A22 | Stabilité inter-session | Variance de A01 à A05 d'une session à l'autre. Un utilisateur régulier a une variance faible : c'est un méta-signal | M | Moyen | 4 | 3 |
| A23 | Asymétrie main gauche / main droite | Rapport des temps de maintien entre les deux moitiés du clavier | F | Élevé | 4 | 2 |
| A24 | Effet de fatigue | Dérive de la vitesse et du taux d'erreur au cours d'une session longue | E | Faible | 4 | 7 |
| A25 | Entrée composée | Usage des touches mortes et des caractères accentués, temps de composition | F | Moyen | 3 | 4 |

## Famille B - Dynamique du pointeur

| ID | Signal | Définition | Coût | Disc. | Falsif. | Lot |
|---|---|---|---|---|---|---|
| B01 | Vitesse | Distribution des vitesses, par octant de direction | F | Élevé | 2 | 2 |
| B02 | Accélération | Profil d'accélération et de décélération par geste | M | Élevé | 3 | 2 |
| B03 | À-coup (jerk) | Dérivée troisième de la position. Très lié à la motricité fine | M | Élevé | 4 | 2 |
| B04 | Courbure | Courbure moyenne et maximale de la trajectoire | M | Élevé | 3 | 2 |
| B05 | Rectitude | Rapport distance parcourue sur distance directe | F | Élevé | 3 | 2 |
| B06 | **Loi de Fitts** | Régression `T = a + b·log2(D/W+1)` sur les pointages. Le couple `(a,b)` est un invariant individuel stable et peu coûteux | M | **Très élevé** | 4 | 2 |
| B07 | Dépassement | Amplitude et fréquence du dépassement de la cible | M | Très élevé | 4 | 2 |
| B08 | Micro-corrections | Nombre et amplitude des ajustements dans les 100 derniers pixels | M | **Très élevé** | 4 | 2 |
| B09 | Pause avant clic | Délai entre l'arrêt du curseur et le clic | F | Élevé | 3 | 2 |
| B10 | Durée du clic | Temps appui / relâchement du bouton | F | Élevé | 3 | 2 |
| B11 | Intervalle de double-clic | Délai entre les deux clics, et dérive du curseur entre les deux | F | Très élevé | 4 | 2 |
| B12 | Glisser-déposer | Vitesse, hésitations, précision du dépôt | M | Élevé | 3 | 4 |
| B13 | Molette | Amplitude par cran, cadence, pauses, inversions de sens | F | Élevé | 3 | 2 |
| B14 | Style de défilement | Molette contre barre de défilement contre clavier contre glissement à deux doigts | F | Élevé | 3 | 3 |
| B15 | Angle d'approche | Direction privilégiée d'arrivée sur les cibles. Trahit la latéralité et la position de la main | M | Élevé | 4 | 3 |
| B16 | Dérive au repos | Micro-mouvements du curseur pendant les pauses. Trahit le tremblement physiologique | M | Très élevé | 4 | 4 |
| B17 | Zone de stationnement | Position où le curseur est laissé au repos | F | Moyen | 3 | 3 |
| B18 | Couverture de l'écran | Carte de chaleur des positions, normalisée | M | Moyen | 2 | 3 |
| B19 | Vitesse de transition | Temps de traversée entre deux zones éloignées de l'écran | F | Moyen | 3 | 3 |
| B20 | Rapport pointeur / défilement | Part du temps passé à pointer contre à défiler | F | Moyen | 2 | 3 |
| B21 | Signature du périphérique | Résolution effective, cadence d'échantillonnage, présence d'accélération. Distingue souris, trackpad, trackball | F | Élevé (mode) | 2 | 2 |
| B22 | Gestes du trackpad | Nombre de doigts, vitesse de balayage, pincement | M | Élevé | 3 | 4 |
| B23 | Rapport clic droit / clic gauche | Et usage du menu contextuel | F | Moyen | 3 | 3 |
| B24 | Précision de sélection | Longueur et stabilité des sélections par glissement | M | Moyen | 3 | 4 |

## Famille C - Contexte applicatif

Rappel : catégories et identifiants opaques uniquement, jamais de titre ni de nom d'exécutable (FR-5).

| ID | Signal | Définition | Coût | Disc. | Falsif. | Lot |
|---|---|---|---|---|---|---|
| C01 | Répertoire d'applications | Ensemble des catégories utilisées et leur fréquence | F | Élevé | 2 | 3 |
| C02 | Chaîne de Markov des applications | Probabilités de transition d'une catégorie à la suivante. Capture l'ordre d'utilisation habituel | M | **Très élevé** | 3 | 3 |
| C03 | Séquence d'ouverture | Ordre des applications lancées en début de session | F | Très élevé | 3 | 3 |
| C04 | Durée de séjour | Temps passé par catégorie et par visite | F | Élevé | 2 | 3 |
| C05 | Cadence de bascule | Fréquence des changements de fenêtre | F | Élevé | 3 | 3 |
| C06 | Nombre de fenêtres | Distribution du nombre de fenêtres ouvertes simultanément | F | Moyen | 2 | 3 |
| C07 | Usage des bureaux virtuels | Nombre d'espaces de travail, fréquence des changements | F | Élevé | 3 | 4 |
| C08 | Rapport terminal / graphique | Préférence pour la ligne de commande | F | Élevé | 3 | 3 |
| C09 | Catégories de commandes | Classes de commandes shell (fichiers, réseau, versionnement, conteneurs), **jamais les arguments** | M | Élevé | 3 | 4 |
| C10 | Cadence d'élévation | Fréquence des demandes de privilèges | F | Moyen | 3 | 4 |
| C11 | Style de navigation de fichiers | Profondeur d'arborescence, usage de la recherche contre la navigation | M | Moyen | 3 | 5 |
| C12 | Densité du multitâche | Entropie de la répartition du temps entre applications | M | Moyen | 3 | 4 |

## Famille D - Rythme temporel

| ID | Signal | Définition | Coût | Disc. | Falsif. | Lot |
|---|---|---|---|---|---|---|
| D01 | Profil horaire | Distribution de l'activité sur 24 heures | F | Élevé | 2 | 3 |
| D02 | Profil hebdomadaire | Distribution sur les 7 jours | F | Moyen | 2 | 3 |
| D03 | Durée des sessions | Distribution des durées d'activité continue | F | Moyen | 2 | 3 |
| D04 | Structure des pauses | Distribution des durées d'inactivité intra-session | M | Élevé | 3 | 3 |
| D05 | Latence de démarrage | Délai entre le déverrouillage et la première action utile | F | Élevé | 3 | 3 |
| D06 | Rythme d'échauffement | Évolution de la vitesse de frappe dans les 5 premières minutes | M | Élevé | 4 | 4 |
| D07 | Régularité circadienne | Stabilité du profil horaire d'un jour à l'autre | M | Moyen | 3 | 4 |
| D08 | Cadence de verrouillage | Fréquence et contexte des verrouillages manuels | F | Moyen | 3 | 4 |

## Famille E - Détection d'entrée non humaine (canal Humanité)

**Ces signaux ne nécessitent aucun enrôlement** (FR-34). Ils constituent le canal le plus rentable et le plus rapide.

| ID | Signal | Définition | Coût | Disc. | Falsif. | Lot |
|---|---|---|---|---|---|---|
| E01 | **Provenance du périphérique** | Événement issu d'un périphérique `uinput` virtuel plutôt que d'un matériel réel. Sous Windows, indicateur `LLKHF_INJECTED` | F | **Très élevé** | 4 | 1 |
| E02 | Quantification des horodatages | Les délais sont-ils des multiples d'une grille (1 ms, 10 ms, une trame vidéo) ? Signature d'une temporisation programmée | F | Très élevé | 3 | 5 |
| E03 | Sous-dispersion | Coefficient de variation des intervalles anormalement bas. Un humain ne tape jamais avec une régularité de métronome | F | Élevé | 2 | 1 |
| E04 | Entropie des intervalles | Entropie de la distribution des délais, contre la référence humaine | M | Élevé | 2 | 5 |
| E05 | Débit soutenu | Rafales dépassant durablement le maximum humain plausible | F | Élevé | 1 | 1 |
| E06 | Absence de correction | Longue production sans aucun retour arrière | F | Élevé | 2 | 5 |
| E07 | Absence de chevauchement | A07 strictement nul sur une frappe rapide : physiquement improbable chez un humain rapide | F | Très élevé | 4 | 5 |
| E08 | Téléportation du curseur | Saut de position sans événements intermédiaires | F | **Très élevé** | 4 | 2 |
| E09 | Trajectoire idéale | Ligne droite parfaite, ou courbe de Bézier trop lisse, avec à-coup quasi nul | M | Très élevé | 3 | 5 |
| E10 | Absence de micro-corrections | B08 nul alors que les cibles sont petites : le pointage parfait est non humain | M | **Très élevé** | 4 | 5 |
| E11 | Signature de session distante | Rafales alignées sur la latence réseau, gigue bimodale, événements groupés par paquets (RDP, VNC, RAT) | M | Élevé | 3 | 5 |
| E12 | Rejeu de presse-papiers | Séquence longue et parfaitement cadencée, typique d'un collage émis en frappes par un KVM sur IP | F | Très élevé | 3 | 5 |
| E13 | Ordre impossible | Relâchement sans appui, modificateur incohérent, ordre d'événements physiquement irréalisable | F | Très élevé | 4 | 5 |
| E14 | Incohérence inter-modale | Frappe humaine plausible mais souris synthétique, ou inversement | M | Très élevé | 4 | 5 |
| E15 | Cadence d'enchaînement applicatif | Bascules entre applications plus rapides que le temps de réaction humain | F | Élevé | 3 | 5 |
| E16 | Absence de temps de lecture | Action sur un contenu nouvellement affiché sans délai de lecture plausible | M | Élevé | 4 | 5 |
| E17 | Régularité du pas de défilement | Défilement par incréments rigoureusement constants | F | Élevé | 3 | 5 |
| E18 | Signature de cadence d'émission | Cadence, gigue, resserrement, percentiles robustes, largeur de queue sur les intervalles entre appuis, d'après la littérature sur la détection d'injection HID | M | Très élevé | 3 | 5 |

## Famille F - Méta-signaux

| ID | Signal | Définition | Coût | Disc. | Falsif. | Lot |
|---|---|---|---|---|---|---|
| F01 | Détection de rupture | Changement brusque de régime sur plusieurs signaux simultanément (CUSUM ou Page-Hinkley). Un relais d'utilisateur produit une rupture nette, pas une dérive | M | **Très élevé** | 4 | 4 |
| F02 | Cohérence inter-modale | Corrélation habituelle entre modalités (celui qui tape vite pointe-t-il vite ?). Rompue lors d'une usurpation partielle | M | Élevé | 4 | 4 |
| F03 | Dérive contre saut | Un gabarit qui évolue lentement est le même utilisateur ; un saut est un autre utilisateur | M | Élevé | 4 | 4 |
| F04 | Entrelacement temporel | Deux régimes alternent-ils dans une même session ? Discriminant central entre « mode » et « personne » (cf. 03, section 6.1) | F | Très élevé | 4 | 4 |
| F05 | Trou de service | Interruption de l'agent puis reprise avec un comportement différent (menace M11) | F | Élevé | 4 | 5 |
| F06 | Dérive contre ancre | Écart cumulé entre le gabarit courant et le gabarit d'enrôlement gelé (menace M10) | F | Moyen | 4 | 3 |
| F07 | Qualité globale de l'évidence | Quantité d'évidence disponible sur la fenêtre. Sert à distinguer « conforme » de « pas assez d'information », qui ne doivent jamais être confondus | F | n/a | n/a | 2 |

## Famille G - Modalités mobiles (lot 9, SDK in-app)

| ID | Signal | Définition |
|---|---|---|
| G01 | Pression de contact | Force rapportée par l'écran, par type de geste |
| G02 | Surface de contact | Taille de l'empreinte, corrélée à la morphologie du doigt |
| G03 | Durée de tap | Temps de contact |
| G04 | Vitesse et courbure de balayage | Équivalents tactiles de B01 et B04 |
| G05 | Angle de balayage | Direction privilégiée, trahit la main dominante |
| G06 | Position de frappe dans la touche | Décalage systématique par rapport au centre des touches du clavier virtuel |
| G07 | Multi-touch | Fréquence et type des gestes à plusieurs doigts |
| G08 | Orientation de l'appareil | Distribution des angles de tenue (accéléromètre, gyroscope) |
| G09 | Micro-tremblement | Signature inertielle pendant l'interaction |
| G10 | Réaction au geste | Stabilisation de l'appareil après un tap |

---

## Règles transversales

1. **Aucun signal ne dépend du contenu.** Un signal qui exigerait de connaître le texte, une URL ou un nom de fichier est rejeté par conception (PR-1).
2. **Chaque signal expose sa qualité** (FR-11). Un signal sans observation suffisante a un poids nul, il ne « vote » pas neutre : il ne vote pas.
3. **Chaque signal est mesuré avant d'être cru.** Les colonnes « Disc. » sont des hypothèses. Le lot 3 produit les valeurs réelles, et un signal dont le pouvoir discriminant mesuré est nul est retiré plutôt que conservé par confort.
4. **Chaque signal a un coût en vie privée**, évalué et consigné dans [05-PRIVACY.md](05-PRIVACY.md). Un signal légèrement discriminant mais coûteux en vie privée est refusé.
5. **Priorité au canal Humanité** : la famille E n'exige aucun enrôlement, ne stocke aucun gabarit personnel, et détecte les menaces M2 à M5. C'est le meilleur rapport valeur sur risque du projet, et c'est pourquoi E01, E03 et E05 sont au lot 1.
