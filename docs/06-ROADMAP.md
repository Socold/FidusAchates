# 06 - Feuille de route et critères d'acceptation

> Chaque lot se termine par un critère **vérifiable**, pas par une impression. Un lot n'est pas clos tant que son critère n'est pas mesuré et consigné dans `research/`.

---

## Vue d'ensemble

| Lot | Titre | Objet | Dépend de |
|---|---|---|---|
| **0** | Socle | Dépôt, licence, spécifications, protocole d'évaluation | |
| **1** | Capture et frappe | Agent evdev, signaux clavier, stockage, console minimale, détection d'automate de base | 0 |
| **2** | Pointeur et fusion | Signaux souris, LLR, SPRT, explicabilité | 1 |
| **3** | Étalonnage | Critères de convergence, courbe de performance, calibration des paramètres | 2 |
| **4** | Profils multiples | Regroupement, révision, modes | 3 |
| **5** | Canal Humanité | Détection complète d'entrée non humaine | 2 |
| **6** | Retour visuel | Extension GNOME Shell, overlay | 2 |
| **7** | Banc de recherche | Rejeu, corpus publics, résultats publiables | 3 |
| **8** | Portage | Windows, macOS, Linux X11 | 5 |
| **9** | Mobile | SDK in-app | 7 |

Chemin critique : 0 → 1 → 2 → 3 → 4. Les lots 5 et 6 sont parallélisables après le lot 2.

---

## Lot 0 - Socle

**Contenu** : dépôt, licence PolyForm Noncommercial 1.0.0, documents 00 à 06, décisions d'architecture, protocole d'évaluation, intégration continue de base, gabarits de contribution et de revue.

**Critère d'acceptation** : les documents 00 à 06 existent, sont cohérents entre eux, et chaque exigence du cahier des charges porte un moyen de vérification explicite.

**État** : en cours.

---

## Lot 1 - Capture et dynamique de frappe

**Contenu**
- `fidus-agent` : lecture `evdev` sans root, normalisation, marquage de provenance (E01).
- Tampon chaud borné à 10 s, jamais persisté.
- Signaux A01 à A05, A07, A08, A10, A23.
- Signaux E01, E03, E05 (canal Humanité, sans enrôlement).
- Schéma SQLite chiffré, agrégats de Welford, quantiles approchés.
- Hachage salé des digraphes, niveaux P0 et P1.
- `fidus-cli` : `status`, `pause`, `resume`, `purge`, `doctor`.
- Console : vue Temps réel minimale (jauge, flux d'événements, santé).
- Unité `systemd --user` durcie.

**Critères d'acceptation**

| # | Critère | Mesure |
|---|---|---|
| 1.1 | L'agent tourne 24 h sans fuite mémoire ni perte d'événement | RSS stable sous 40 Mo, zéro événement perdu |
| 1.2 | NFR-1 à NFR-4 respectés sur 24 h d'usage réel | Journal de santé |
| 1.3 | Test « content-free » bloquant en CI | 200 mots témoins saisis, zéro occurrence en base |
| 1.4 | Une injection `ydotool` est marquée comme virtuelle | Test automatisé |
| 1.5 | Une rafale `ydotool` déclenche L3 sur le canal Humanité en moins de 10 s, sans aucun enrôlement | Test de bout en bout |
| 1.6 | `purge` ne laisse aucun résidu | Vérification du système de fichiers |

---

## Lot 2 - Pointeur, fusion et explicabilité

**Contenu**
- Signaux B01 à B11, B13, B21, et E08.
- Calibration des experts (Platt), diagrammes de fiabilité.
- Fusion LLR pondérée, mesure du facteur d'amortissement.
- SPRT à deux seuils, décroissance exponentielle, hystérésis, niveaux L0 à L4.
- Deux canaux séparés (Identité, Humanité).
- Console : vue Explication (cascade en décibans, cinq preuves dominantes, trajectoire).

**Critères d'acceptation**

| # | Critère | Mesure |
|---|---|---|
| 2.1 | La somme des contributions affichées égale l'évidence totale | Écart inférieur à 0,01 dB |
| 2.2 | Les experts sont calibrés | Erreur de calibration attendue sous 0,05 |
| 2.3 | Les taux d'erreur simulés correspondent aux cibles | Écart inférieur à 20 % relatif sur `α` et `β` |
| 2.4 | Le couple `(a,b)` de la loi de Fitts (B06) est estimé de façon stable | Coefficient de variation inter-session sous 15 % |
| 2.5 | Chaque alerte produit une explication en langue naturelle lisible | Revue sur 20 alertes réelles |

---

## Lot 3 - Étalonnage et calibration

**Contenu**
- Quatre phases du cycle de vie, transitions automatiques.
- Critères C1 à C4, affichage de l'avancement.
- Courbe performance / volume, estimation du `X` propre au poste.
- Validation croisée temporelle, bootstrap, intervalles de confiance.
- Calibration des paramètres de [03-MODELE-DECISION.md](03-MODELE-DECISION.md) section 8, par mesure.
- Mesure du pouvoir discriminant réel de chaque signal, et retrait des signaux nuls.
- Protection anti-empoisonnement (filtre d'admission, taux borné, ancre gelée, signal F06).

**Critères d'acceptation**

| # | Critère | Mesure |
|---|---|---|
| 3.1 | La courbe performance / volume est produite et reproductible par rejeu | Deux exécutions identiques |
| 3.2 | Le `X` empirique du poste est publié avec son intervalle de confiance | Consigné dans `research/` |
| 3.3 | AC-1 atteint : EER sous 5 % sur fenêtre de 60 s contre imposteur humain | Protocole d'évaluation |
| 3.4 | AC-4 atteint : moins d'une fausse alarme par 8 h d'usage légitime | Mesure sur 7 jours |
| 3.5 | Le tableau de pouvoir discriminant réel remplace les hypothèses du catalogue | [04-CATALOGUE-SIGNAUX.md](04-CATALOGUE-SIGNAUX.md) mis à jour |
| 3.6 | Scénario M10 : un imposteur actif 2 h par jour pendant 7 jours ne fait pas dériver le gabarit au-delà du seuil | Test d'attaque |

---

## Lot 4 - Profils multiples

**Contenu**
- Vecteur de session, regroupement à nombre de composantes non borné.
- Hiérarchie identité / mode, critère d'entrelacement temporel (F04).
- Révision par fusion et scission, avec justification statistique.
- Historique permanent des révisions.
- Nombre de profils avec incertitude.
- Signaux C01 à C08, D01 à D05, F01 à F03.
- Console : vue Profils.

**Critères d'acceptation**

| # | Critère | Mesure |
|---|---|---|
| 4.1 | AC-5 atteint : sur trace contrôlée à 2 ou 3 personnes, le compte est exact après 5 jours | Protocole d'évaluation |
| 4.2 | Une même personne sur deux périphériques distincts reste un seul profil, avec deux modes | Scénario dédié |
| 4.3 | Au moins une fusion rétrospective est observée et justifiée lisiblement | Chronologie dans la console |
| 4.4 | Le nombre de profils est toujours présenté avec son intervalle crédible | Revue de l'interface |

---

## Lot 5 - Canal Humanité complet

**Contenu** : signaux E02, E04, E06, E07, E09 à E18, et F05. Banc d'attaque dédié.

**Banc d'attaque** (reproductible, scripté) :
1. `ydotool` et automatisation locale.
2. Injection HID matérielle (clé de type Rubber Ducky).
3. Rejeu de presse-papiers via KVM sur IP.
4. Session distante RDP puis VNC.
5. **Agent IA pilotant le poste** (boucle percevoir / agir sur clavier et souris).
6. Contrefaçon statistique : générateur entraîné sur les agrégats du gabarit (menace M8).
7. Adversaire adaptatif : automate qui ralentit et randomise ses délais pour contourner E03 et E05.

**Critères d'acceptation**

| # | Critère | Mesure |
|---|---|---|
| 5.1 | AC-3 atteint : détection des scénarios 1 à 3 en moins de 10 s sans enrôlement | Banc d'attaque |
| 5.2 | Scénarios 4 et 5 détectés en moins de 60 s | Banc d'attaque |
| 5.3 | Le scénario 7 (adversaire adaptatif) est détecté par des signaux non temporels (E01, E07, E10, E13) | Banc d'attaque |
| 5.4 | Zéro fausse alarme du canal Humanité sur 7 jours d'usage humain normal | Mesure |
| 5.5 | Le scénario 6 est documenté avec son taux de réussite, y compris s'il met le système en échec | Publication honnête dans `research/` |

---

## Lot 6 - Extension GNOME Shell et retour visuel

**Contenu**
- Extension GNOME Shell : contexte applicatif par catégorie sur D-Bus, et overlay.
- Carré rouge en haut à droite, seuil `P > 0,50`, pourcentage affiché, hystérésis.
- Modes `research` et `silent`.
- Vue Santé et vie privée dans la console.

**Critères d'acceptation**

| # | Critère | Mesure |
|---|---|---|
| 6.1 | Le carré apparaît en moins de 500 ms après franchissement du seuil | Mesure |
| 6.2 | L'overlay ne vole jamais le focus et n'intercepte aucun clic | Test manuel documenté |
| 6.3 | Pas plus d'une transition d'affichage par période de garde | Mesure sur 24 h |
| 6.4 | L'extension n'expose jamais de titre de fenêtre ni de nom d'exécutable sur D-Bus | Inspection D-Bus |
| 6.5 | Le mode `silent` n'affiche rien | Vérification |

---

## Lot 7 - Banc de recherche

**Contenu**
- `fidus-lab` : rejeu déterministe, banc d'évaluation (FAR, FRR, EER, ANIA, ANGA, TTD), courbes DET et ROC.
- Format de trace documenté et versionné.
- Ingestion des corpus CMU, Balabit, SapiMouse.
- Premier rapport de résultats comparé à l'état de l'art.

**Critères d'acceptation**

| # | Critère | Mesure |
|---|---|---|
| 7.1 | Deux rejeux de la même trace donnent un résultat identique bit à bit | Test automatisé |
| 7.2 | Au moins un résultat comparable à l'état de l'art est publié sur un corpus public | Rapport dans `research/` |
| 7.3 | AC-6 vérifié sur 7 jours consécutifs | Journal de santé |
| 7.4 | Le rapport publie aussi les signaux non discriminants et les échecs | Revue |

---

## Lot 8 - Portage

Windows (Raw Input, indicateur `LLKHF_INJECTED`), macOS (`CGEventTap`), Linux X11. Seul l'étage `Source` est réécrit.

**Critère d'acceptation** : sur chaque plateforme, les critères 1.1 à 1.5 du lot 1 sont atteints, et une trace capturée sur une plateforme est rejouable par `fidus-lab` sans adaptation.

---

## Lot 9 - Mobile

SDK intégrable dans une application, modalités G01 à G10. Périmètre limité à l'intérieur de l'application hôte (cf. 00-ANALYSE T6).

**Critère d'acceptation** : EER sous 10 % sur une session de 60 s d'interaction tactile, avec le même moteur de fusion et le même format de trace que le bureau.

---

## Ce qui n'est pas planifié

Conformément à la section 9 du [cahier des charges](01-CAHIER-DES-CHARGES.md) : console centralisée, déploiement en parc, action coercitive sur le poste, reconnaissance faciale, capture audio ou vidéo, clavier IME de substitution, service d'accessibilité Android.

Ces éléments ne sont pas « plus tard » : ils sont hors projet. Les inscrire dans une feuille de route même lointaine serait une invitation à les développer.
