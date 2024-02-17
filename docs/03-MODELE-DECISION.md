# 03 - Moteur de décision, confiance et étalonnage

> Répond aux exigences FR-20 à FR-44 du cahier des charges (a ecrire).

---

## 1. Principe directeur

Une décision isolée est faible. L'état de l'art donne un EER de l'ordre de 8 % à 10 % pour une décision ponctuelle selon la modalité. Le système ne cherche donc **jamais** à trancher sur une observation : il **accumule de la preuve** et tranche dès que l'évidence cumulée franchit un seuil correspondant aux taux d'erreur visés.

Trois propriétés sont recherchées simultanément, et une seule formulation les donne toutes les trois :

1. **Rapidité** : décider avec le minimum d'observations, à taux d'erreur fixé.
2. **Recoupement** : combiner des signaux hétérogènes sur une échelle commune.
3. **Explicabilité** : savoir exactement ce qui a fait bouger la décision.

La formulation qui satisfait les trois est le **rapport de log-vraisemblance cumulé**, évalué par un **test séquentiel du rapport de probabilité** (SPRT de Wald). Le recoupement y est une addition, et l'explication est cette addition lue terme à terme.

## 2. Unité de preuve : le déciban

Pour chaque signal `i` observé avec la valeur `x_i`, on définit la preuve apportée :

```
e_i = 10 · log10 [ P(x_i | légitime) / P(x_i | imposteur) ]      (en décibans)
```

- `e_i > 0` : l'observation soutient l'utilisateur légitime.
- `e_i < 0` : elle le contredit.
- `e_i = 0` : le signal n'apporte rien.

Le déciban est une unité additive et lisible : « cette rafale de frappe a apporté 12 dB de preuve contre l'utilisateur légitime » est une phrase qui a un sens précis, affichable telle quelle dans la console (FR-53).

L'évidence totale sur une fenêtre est :

```
E = Σ_i  w_i · q_i · e_i
```

- `w_i` : **fiabilité** du signal, apprise et bornée. Initialisée à `1 - 2·EER_i` puis réestimée.
- `q_i` : **qualité** de l'observation courante (assez d'observations, variance de l'estimateur acceptable). Nul si l'évidence est trop mince (FR-11).

La probabilité affichée découle directement de l'évidence cumulée :

```
P(imposteur) = 1 / (1 + 10^(E_cumulé / 10))
```

## 3. Densités de référence

Chaque signal a besoin de deux densités : sous hypothèse légitime et sous hypothèse imposteur.

- **Légitime** : estimée pendant l'enrôlement, par statistiques robustes (médiane, écart absolu médian) plutôt que moyenne et écart-type, pour résister aux valeurs aberrantes. Modèle par défaut : gaussienne sur la valeur robustement standardisée, ou mélange à deux composantes quand la distribution est manifestement bimodale (signe d'un second **mode**, cf. section 6).
- **Imposteur** : trois sources, par ordre de préférence :
  1. Les autres profils observés sur la machine, quand il y en a.
  2. Une population de référence issue des corpus publics (CMU, Balabit, SapiMouse), fournie avec le projet.
  3. Un modèle non informatif large, en dernier recours.

**Calibration obligatoire.** Les scores bruts des experts ne sont pas des probabilités. Chaque expert passe par une calibration (régression logistique de Platt, ou isotonique si les données le permettent), validée par diagramme de fiabilité (FR-30). Sans cette étape, l'addition des LLR est fausse et l'explication trompeuse.

**Hypothèse d'indépendance : assumée et corrigée.** L'addition des LLR suppose l'indépendance conditionnelle des signaux, qui n'est pas vérifiée (la vitesse de frappe et la latence des digraphes sont corrélées). Deux correctifs :

- Regroupement des signaux fortement corrélés en un expert unique, qui produit un seul LLR multivarié.
- Application d'un facteur d'amortissement `0 < λ ≤ 1` sur la somme, estimé empiriquement pour que les taux d'erreur observés correspondent aux taux nominaux. C'est exactement la correction employée en fusion naïve bayésienne, et elle doit être mesurée, pas devinée.

## 4. Décision séquentielle

### 4.1 Seuils de Wald

Pour des cibles `α` (fausse alarme) et `β` (non-détection) :

```
seuil haut  A = 10 · log10 ( (1-β) / α )       → conclure « imposteur »
seuil bas   B = 10 · log10 ( β / (1-α) )       → conclure « légitime »
entre les deux                                  → continuer à observer
```

Avec `α = 0,01` et `β = 0,05`, on obtient `A ≈ 19,8 dB` et `B ≈ -19,9 dB`.

### 4.2 Oubli

Une preuve vieille de trois heures ne doit pas peser autant qu'une preuve d'il y a dix secondes. L'évidence cumulée décroît exponentiellement :

```
E_cumulé(t) = E_cumulé(t-1) · 2^(-Δt / T½)  +  E(t)
```

La demi-vie `T½` est un paramètre central : trop courte, le système oublie et ne conclut jamais ; trop longue, il reste bloqué sur une conclusion périmée. Valeur initiale proposée : **15 minutes d'activité effective** (et non de temps mural, afin qu'une pause déjeuner n'efface pas l'historique). À calibrer au lot 3.

### 4.3 Niveaux

| Niveau | Évidence cumulée | P(imposteur) | Signification | Effet |
|---|---|---|---|---|
| **L0** | `E < B` | < 0,01 | Conforme | Aucun |
| **L1** | `B ≤ E < 5 dB` | 0,01 à 0,24 | Nominal | Aucun |
| **L2** | `5 ≤ E < 10 dB` | 0,24 à 0,50 | Signal faible | Journalisé, visible dans la console |
| **L3** | `10 ≤ E < A` | 0,50 à 0,99 | Doute | **Overlay rouge** (FR-60), alerte |
| **L4** | `E ≥ A` | > 0,99 | Conclusion imposteur | Alerte, événement de décision complet |

Le seuil d'affichage du carré rouge, 50 % de confiance, tombe donc à l'entrée du niveau L3.

**Hystérésis** (FR-62) : la descente d'un niveau exige de repasser 3 dB sous le seuil de montée, et une durée minimale de 20 secondes au niveau courant. Sans cela, l'indicateur clignote au moindre bruit.

### 4.4 Deux canaux séparés

Conformément à FR-35, le système maintient **deux évidences cumulées distinctes**, jamais confondues :

| Canal | Question | Enrôlement nécessaire | Seuils |
|---|---|---|---|
| **Identité** | Est-ce la même personne ? | Oui | `α = 0,01`, `β = 0,05` |
| **Humanité** | Est-ce un humain ? | Non | `α = 0,001`, `β = 0,05` |

Le canal Humanité est plus strict sur les fausses alarmes parce qu'il conclut à une compromission, ce qui est une affirmation plus lourde. Il est aussi le plus rapide : une injection HID produit typiquement plusieurs dizaines de décibans en quelques secondes.

L'affichage combine les deux sans les additionner : `P(imposteur)` retenu pour l'overlay est le maximum des deux probabilités, et la console indique toujours lequel des deux canaux est en cause.

## 5. Étalonnage : quand le modèle est-il prêt ?

Ma question de départ : à partir de quelle durée d'utilisation ai-je assez de données pour reconnaître quelqu'un de façon fiable ?

**Réponse : `X` n'est pas une durée, c'est une condition statistique, et sa valeur en heures dépend du poste et de l'utilisateur.** Le système mesure `X` au lieu de le postuler.

### 5.1 Les quatre critères de convergence (FR-21)

La phase d'enrôlement se termine quand les quatre critères sont satisfaits simultanément. Chacun est affiché en pourcentage dans la console.

| Critère | Définition | Valeur initiale proposée |
|---|---|---|
| **C1 - Volume** | Observations minimales par modalité | 10 000 frappes, 5 000 événements de pointage, 300 pointages avec cible (pour Fitts), 8 sessions, 5 jours distincts |
| **C2 - Stabilité** | Le gabarit ne bouge plus : divergence de Jensen-Shannon entre le gabarit à `t` et à `t-Δ` sous seuil, sur 3 fenêtres consécutives | JS < 0,02 sur 3 fenêtres de 24 h |
| **C3 - Performance** | EER auto-estimé par validation croisée temporelle (entraînement sur les `k` premières sessions, test sur la suivante), contre population imposteur de référence, avec intervalle de confiance bootstrap à 95 % | Borne haute de l'IC < 8 % |
| **C4 - Couverture** | Diversité contextuelle : nombre de catégories d'applications, de plages horaires, de périphériques d'entrée | ≥ 4 catégories, ≥ 3 plages horaires, tous les périphériques usuels |

C3 est le critère décisif : c'est le seul qui mesure directement ce qui nous intéresse. C1 empêche de le calculer sur trop peu de données, C2 garantit qu'on n'a pas figé un régime transitoire, C4 qu'on n'a pas appris un seul contexte.

### 5.2 La courbe de convergence (FR-22)

Le système produit et affiche la courbe **EER estimé en fonction du volume d'enrôlement**, recalculée à chaque palier. Elle donne :

- le `X` empirique pour ce poste et cet utilisateur (le volume au-delà duquel la courbe s'aplatit) ;
- une estimation du temps restant avant la fin de l'enrôlement, au rythme d'usage observé ;
- un résultat publiable, puisque la même courbe est calculable sur les corpus publics pour comparaison.

### 5.3 Phases

| Phase | Entrée | Ce que fait le système | Sortie |
|---|---|---|---|
| **Amorçage** | Premier démarrage | Observe, ne décide rien, ne montre aucune alerte. Seul le canal Humanité est actif (il ne demande pas d'enrôlement). | Après C1 à 30 % |
| **Enrôlement** | Fin d'amorçage | Construit le gabarit, affiche l'avancement C1 à C4, décide avec des seuils élargis et signale que la fiabilité est partielle | Les quatre critères à 100 % |
| **Opérationnel** | Fin d'enrôlement | Décision nominale, seuils nominaux, gabarit d'ancre gelé | Permanent |
| **Adaptation** | Continu, à partir d'Opérationnel | Met à jour le gabarit uniquement avec des fenêtres classées à haute confiance, taux borné | Permanent |

### 5.4 Protection contre l'empoisonnement (FR-23, FR-24, menace M10)

L'adaptation continue est une porte d'entrée : un imposteur patient peut faire dériver le gabarit vers son propre comportement.

Trois garde-fous :

1. **Filtre d'admission** : seules les fenêtres avec `E ≤ B` (conclusion « légitime » franche) alimentent la mise à jour.
2. **Taux borné** : le gabarit ne peut pas bouger de plus d'une fraction fixée par période de 24 heures, quelle que soit la quantité de données.
3. **Ancre gelée** : le gabarit d'enrôlement est conservé intact. Un expert dédié compare en permanence le gabarit courant à l'ancre ; une dérive cumulée au-delà d'un seuil déclenche une alerte de dérive, et non un simple ajustement silencieux.

## 6. Comptage et révision des profils

### 6.1 Modèle hiérarchique

Le piège identifié en analyse (section 3.6) est qu'une même personne produit plusieurs régimes. Le modèle est donc à deux étages :

```
Identité (personne présumée)
   └── Mode (régime contextuel : clavier externe, trackpad, session tardive)
          └── Gabarit du mode
```

Un nouveau régime bien séparé mais **temporellement entrelacé** avec un régime connu (alternance rapide entre les deux au cours d'une même session) est un **mode** de la même identité, pas une nouvelle personne. Un régime qui occupe des plages disjointes et ne coexiste jamais avec l'autre est candidat à être une identité distincte. Ce critère d'entrelacement temporel est le principal discriminant entre « mode » et « personne ».

### 6.2 Regroupement

Représentation : chaque fenêtre d'activité produit un vecteur de signaux normalisés. Le regroupement s'opère sur ces vecteurs par **mélange à processus de Dirichlet** (nombre de composantes non borné a priori), ou par une approximation en ligne (agrégation incrémentale type BIRCH, suivie d'un mélange gaussien bayésien recalculé périodiquement).

### 6.3 Révision (FR-41, FR-43)

C'est le comportement que je veux : commencer par croire à plusieurs utilisateurs, puis comprendre en recoupant qu'il y en a moins.

À intervalle régulier, le système teste chaque paire de profils :

- **Fusion** si la distance entre les deux gabarits (Hellinger ou Bhattacharyya) passe sous un seuil **et** que le rapport de vraisemblance favorise le modèle à une seule composante **et** que les occurrences sont temporellement entrelacées.
- **Scission** si un profil devient nettement bimodal sur plusieurs signaux indépendants **et** que les deux sous-ensembles sont temporellement disjoints.

Chaque révision produit une entrée permanente dans `profile_revisions`, avec la raison statistique chiffrée, restituée dans la console sous forme de chronologie :

```
J+3   3 profils   (a1b2, c3d4, e5f6)
J+9   fusion c3d4 ← e5f6
      raison : distance de Hellinger 0,08 < seuil 0,15
               rapport de vraisemblance 1 composante / 2 composantes = 4,2
               entrelacement temporel 0,71 (les deux régimes alternent dans 14 sessions)
      conclusion : même personne, deux modes (clavier interne / clavier externe)
J+9   2 profils   (a1b2, c3d4)
```

### 6.4 Incertitude (FR-44)

Le nombre de profils n'est jamais affiché comme un entier certain. Le mélange à processus de Dirichlet fournit naturellement une distribution a posteriori sur le nombre de composantes, restituée sous la forme : **« 2 profils, intervalle crédible 2 à 3 »**.

## 7. Explicabilité (FR-53, FR-56)

L'explicabilité n'est pas une reconstruction a posteriori : elle est la lecture directe de la formule de fusion.

Pour toute décision, la console restitue :

1. **La cascade** : histogramme des contributions `w_i · q_i · e_i` triées par valeur absolue, dont la somme est exactement l'évidence affichée (FR-31).
2. **Les cinq preuves dominantes**, en langue naturelle, générées à partir d'un gabarit de phrase par signal. Exemple : *« La latence moyenne des digraphes est de 118 ms contre 164 ms habituellement (2,9 écarts robustes sous la référence) : 7,2 dB contre l'utilisateur légitime. »*
3. **Ce qui a joué en sens inverse** : les signaux qui soutenaient l'utilisateur légitime, pour éviter de ne montrer que la charge.
4. **Le canal responsable** : Identité ou Humanité.
5. **La trajectoire** : la courbe d'évidence cumulée sur la dernière heure, avec les points de franchissement de seuil.
6. **Le simulateur** : des curseurs permettant de modifier la valeur d'un signal et d'observer en direct le déplacement de l'évidence et du niveau. C'est ce qui permet de comprendre la logique d'identification plutôt que de la subir.

## 8. Paramètres et valeurs initiales

Toutes les valeurs ci-dessous sont des **hypothèses de départ à calibrer au lot 3**, pas des constantes justifiées. Elles sont regroupées dans un fichier de configuration unique et versionné, afin que toute expérience soit reproductible.

| Paramètre | Valeur initiale | À calibrer |
|---|---|---|
| `alpha_identite` | 0,01 | Lot 3 |
| `beta_identite` | 0,05 | Lot 3 |
| `alpha_humanite` | 0,001 | Lot 5 |
| `demi_vie_evidence` | 15 min d'activité effective | Lot 3 |
| `lambda_amortissement` | 0,6 | Lot 2, par mesure |
| `seuil_overlay` | P = 0,50 | Fixé par le besoin |
| `hysteresis` | 3 dB et 20 s | Lot 6 |
| `fenetre_frappe` | 50 frappes ou 60 s | Lot 1 |
| `fenetre_souris` | 30 gestes ou 60 s | Lot 2 |
| `seuil_fusion_hellinger` | 0,15 | Lot 4 |
| `taux_adaptation_max` | 2 % du gabarit par 24 h | Lot 3 |
