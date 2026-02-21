# 01 - Cahier des charges

**Projet** : FidusAchates
**Version** : 0.1
**Nature** : projet de recherche, source-available, usage commercial réservé

> Lire d'abord [00-ANALYSE.md](00-ANALYSE.md), qui justifie les arbitrages ci-dessous.

---

## 1. Objet

FidusAchates est un agent local d'**authentification continue implicite** par biométrie comportementale. Il apprend la manière dont une personne utilise un appareil, puis évalue en permanence la probabilité que la personne aux commandes soit toujours la même, et signale les prises de contrôle par un tiers humain ou par un automate.

**Finalité** : recherche en sécurité défensive, détection d'usurpation de session et de pilotage non humain.

**Non-finalité, opposable** : l'outil n'a pas vocation à surveiller la productivité, le contenu du travail, les communications ou la localisation d'une personne. Toute fonctionnalité allant dans ce sens est hors périmètre et doit être refusée en revue de code.

## 2. Glossaire

| Terme | Définition |
|---|---|
| **Gabarit** | Modèle statistique du comportement d'un profil. Jamais une donnée brute. |
| **Profil** | Étiquette opaque désignant un ensemble de comportements attribués à une même personne présumée. |
| **Mode** | Sous-régime d'un profil (clavier externe, trackpad, session nocturne). Un profil possède plusieurs modes. |
| **Expert** | Module produisant un score pour une modalité (frappe, souris, contexte, automation). |
| **LLR** | Rapport de log-vraisemblance. Unité de preuve du moteur de décision. |
| **Déciban (dB)** | Unité de preuve, `10·log10` du rapport de vraisemblance. |
| **EER** | Taux d'erreur égal (FAR = FRR). Métrique de comparaison standard. |
| **ANIA** | Nombre moyen d'actions d'un imposteur avant détection. |
| **ANGA** | Nombre moyen d'actions légitimes avant fausse alarme. |
| **TTD** | Temps jusqu'à détection. |
| **Fenêtre** | Bloc d'activité sur lequel un expert produit un score (durée ou nombre d'événements). |

## 3. Cas d'usage

| ID | Cas d'usage | Priorité |
|---|---|---|
| UC-1 | Le poste est laissé déverrouillé et un tiers s'en sert. L'outil le détecte et l'affiche. | Doit |
| UC-2 | Un automate ou agent IA pilote le clavier et la souris. L'outil le détecte sans enrôlement préalable. | Doit |
| UC-3 | Consulter une console locale pour comprendre en temps réel ce qui fait bouger la confiance. | Doit |
| UC-4 | Savoir combien de personnes distinctes ont utilisé la machine. | Doit |
| UC-5 | Rejouer une trace passée pour comparer deux versions du modèle. | Doit |
| UC-6 | Mesurer le volume d'usage nécessaire pour que le modèle soit fiable sur cette machine. | Doit |
| UC-7 | Suspendre la collecte et purger les données. | Doit |
| UC-8 | Une session distante (RDP, VNC, RAT) prend la main sur le poste. | Devrait |
| UC-9 | L'outil s'exécute sur Windows ou macOS. | Pourrait (lot 8) |
| UC-10 | Une application mobile intègre le SDK et évalue son propre utilisateur. | Pourrait (lot 9) |

---

## 4. Exigences fonctionnelles (FR)

### 4.1 Collecte

| ID | Exigence | Vérification |
|---|---|---|
| **FR-1** | L'agent capture les événements clavier et pointeur au niveau `evdev` sans privilège root, via l'appartenance au groupe `input`. | L'agent démarre et produit des événements sous un compte non root. |
| **FR-2** | L'agent enregistre pour chaque événement : horodatage monotone en microsecondes, type, **classe** de touche ou de bouton, identifiant du périphérique source, et indicateur de provenance virtuelle (`uinput`) ou matérielle. | Test unitaire sur trace synthétique ; un événement injecté par `ydotool` est marqué virtuel. |
| **FR-3** | Selon le niveau de granularité configuré (P0, P1, P2, cf. 00-ANALYSE T2), l'agent conserve ou non l'empreinte **hachée et salée** du digraphe. Le sel est volatil et régénéré à chaque démarrage. | Inspection de la base : aucun keycode en clair en P0 et P1 ; le sel est absent du disque. |
| **FR-4** | Aucun contenu saisi, titre de fenêtre, URL, nom de fichier ou contenu de presse-papiers n'est capturé. | Test automatisé : grep de la base sur un corpus de mots témoins saisis pendant la collecte ; zéro occurrence. Ce test est bloquant en CI. |
| **FR-5** | Le contexte applicatif est réduit à une **catégorie** (navigateur, terminal, bureautique, développement, communication, média, autre) et à un identifiant opaque stable, obtenus via l'extension GNOME Shell. | Le journal ne contient jamais de nom d'exécutable ni de titre de fenêtre. |
| **FR-6** | L'agent applique une liste noire d'applications pour lesquelles toute capture est suspendue. | Capture nulle pendant l'usage d'une application listée. |
| **FR-7** | Un raccourci global et une commande CLI suspendent immédiatement la collecte, et une commande purge les données. | La suspension prend effet en moins d'une seconde et est visible dans la console. |
| **FR-8** | Les événements bruts ne sont jamais persistés : seuls des agrégats incrémentaux et des vecteurs de fenêtre le sont. Le tampon circulaire en mémoire ne dépasse pas 10 secondes d'activité. | Revue de code plus test d'intégration sur la taille du tampon. |

### 4.2 Extraction de signaux

| ID | Exigence | Vérification |
|---|---|---|
| **FR-10** | L'agent calcule les signaux du catalogue [04-CATALOGUE-SIGNAUX.md](04-CATALOGUE-SIGNAUX.md), par famille, en flux et sans seconde passe. | Chaque signal a un test unitaire avec un vecteur de référence. |
| **FR-11** | Chaque signal expose une **mesure de qualité** (nombre d'observations, variance de l'estimateur) permettant de le pondérer ou de l'ignorer quand l'évidence est trop mince. | Un signal calculé sur moins de N observations a un poids nul dans la fusion. |
| **FR-12** | L'ajout d'un nouveau signal ou d'un nouvel expert ne demande pas de modifier le moteur de fusion. | Un expert d'exemple est ajouté dans un test sans toucher au cœur. |

### 4.3 Apprentissage et étalonnage

| ID | Exigence | Vérification |
|---|---|---|
| **FR-20** | Le cycle de vie comporte quatre phases explicites : **Amorçage**, **Enrôlement**, **Opérationnel**, **Adaptation**. La phase courante est affichée dans la console. | Transition observable sur une collecte de plusieurs jours. |
| **FR-21** | La sortie de l'enrôlement n'est pas déclenchée par une durée arbitraire mais par **quatre critères de convergence** cumulatifs C1 à C4 (volume, stabilité du gabarit, performance auto-estimée, couverture contextuelle), définis en [03-MODELE-DECISION.md](03-MODELE-DECISION.md) section 5. | La console affiche l'avancement de chaque critère en pourcentage ; la transition n'a lieu qu'à 100 % des quatre. |
| **FR-22** | Le système produit une **courbe « performance estimée en fonction du volume d'enrôlement »** propre au poste, et en déduit le volume `X` réellement nécessaire, avec intervalle de confiance. | La courbe est exportable et reproductible par rejeu. |
| **FR-23** | En phase d'adaptation, seules les fenêtres classées à haute confiance alimentent la mise à jour du gabarit, et le taux d'adaptation est borné par période. | Test d'attaque M10 : un imposteur actif n'entraîne pas la dérive du gabarit au-delà d'un seuil mesuré. |
| **FR-24** | Le gabarit d'enrôlement initial est conservé gelé et sert d'ancre de référence. | Comparaison ancre / gabarit courant disponible dans la console. |

### 4.4 Décision et confiance

| ID | Exigence | Vérification |
|---|---|---|
| **FR-30** | Chaque expert produit un score **calibré** en probabilité, converti en LLR. | Diagramme de fiabilité : écart de calibration inférieur au seuil fixé. |
| **FR-31** | La fusion est une **somme pondérée de LLR**, donc exactement décomposable en contributions par signal. | La somme des contributions affichées égale le LLR total, à l'erreur numérique près. |
| **FR-32** | La décision suit un **SPRT de Wald** à deux seuils dérivés des taux d'erreur cibles, avec décroissance exponentielle de l'évidence ancienne. | Simulation : les taux d'erreur observés correspondent aux taux cibles. |
| **FR-33** | Le système expose à tout instant `P(imposteur)` dans `[0,1]` et un **niveau** L0 à L4. | Valeur lisible par API locale et par la console. |
| **FR-34** | La détection d'entrée non humaine (Q3) fonctionne **sans enrôlement** et constitue un expert indépendant. | Sur une machine vierge, une injection `ydotool` est détectée dès la première rafale. |
| **FR-35** | Le système distingue dans ses alertes « comportement différent » (autre humain) et « comportement non humain » (automate), et ne les mélange pas dans un score unique. | Deux sorties distinctes, deux seuils distincts. |
| **FR-36** | Tout changement de niveau produit un **événement de décision** horodaté, conservant le vecteur de contributions ayant conduit à la décision. | Le journal permet de reconstituer la décision par rejeu. |

### 4.5 Estimation du nombre d'utilisateurs

| ID | Exigence | Vérification |
|---|---|---|
| **FR-40** | Le système regroupe les fenêtres d'activité en profils sans connaître à l'avance leur nombre. | Sur une trace à deux personnes, deux profils émergent. |
| **FR-41** | Le système **révise** ses partitions : deux profils jugés indistinguables sont fusionnés, un profil hétérogène est scindé. | Scénario de test : trois profils initiaux convergent vers deux ; la fusion est journalisée. |
| **FR-42** | Le système distingue **mode** et **identité** : les régimes d'une même personne sont rattachés à un profil unique. | Scénario : la même personne sur clavier interne puis externe reste un seul profil. |
| **FR-43** | L'historique complet des révisions est conservé et consultable, avec la raison statistique de chaque fusion ou scission. | La console affiche la chronologie « J+3 : 3 profils ; J+9 : fusion #2 et #3, distance de Hellinger 0,08 sous le seuil 0,15 ». |
| **FR-44** | Le nombre de profils est présenté avec une **incertitude** et non comme un entier certain. | Affichage du type « 2 profils (intervalle crédible 2 à 3) ». |

### 4.6 Console d'administration

| ID | Exigence | Vérification |
|---|---|---|
| **FR-50** | Console web servie localement, liée à `127.0.0.1` uniquement, protégée par jeton. | `ss -lntp` ne montre aucune écoute sur une interface externe. |
| **FR-51** | Mise à jour temps réel par flux poussé (SSE), sans rechargement ni sondage. | Latence perçue inférieure à 500 ms entre l'action et son effet à l'écran. |
| **FR-52** | Vue **Temps réel** : jauge de confiance, courbe de LLR cumulé, flux des événements de décision, indicateurs d'automation. | Revue visuelle plus test de bout en bout. |
| **FR-53** | Vue **Explication** : histogramme en cascade des contributions en décibans sur la fenêtre courante, et phrase en langue naturelle des cinq preuves dominantes. | Chaque alerte est accompagnée d'un « pourquoi » lisible. |
| **FR-54** | Vue **Profils** : profils détectés, modes, chronologie des révisions, matrice de séparabilité inter-profils. | Couvre FR-43 et FR-44. |
| **FR-55** | Vue **Modèle** : avancement de l'enrôlement (C1 à C4), EER estimé avec intervalle de confiance, courbes DET et ROC, courbe performance / volume. | Couvre FR-21 et FR-22. |
| **FR-56** | Vue **Pédagogie** : explication du fonctionnement de chaque expert, distributions apprises, et simulateur interactif permettant de faire varier un signal et d'observer l'effet sur le LLR. | Permet de comprendre la logique d'identification. |
| **FR-57** | Vue **Santé et vie privée** : consommation CPU et mémoire, débit d'événements, volume stocké, niveau de granularité actif, état de la collecte, bouton de purge. | Couvre NFR et PR. |
| **FR-58** | Toutes les données affichées sont exportables en JSON et CSV. | Export vérifié sur chaque vue. |

### 4.7 Retour visuel sur le poste

| ID | Exigence | Vérification |
|---|---|---|
| **FR-60** | En mode `research`, un indicateur carré rouge apparaît **en haut à droite de l'écran** dès que `P(imposteur) > 0,50`, affichant le pourcentage de confiance. | Test manuel avec injection d'un comportement étranger. |
| **FR-61** | L'indicateur est rendu par l'extension GNOME Shell, au-dessus de toutes les fenêtres, sans voler le focus ni intercepter les clics. | L'usage normal n'est pas perturbé. |
| **FR-62** | L'intensité ou l'opacité suit le score, et l'indicateur disparaît sous le seuil avec une hystérésis évitant le clignotement. | Pas plus d'une transition par période de garde. |
| **FR-63** | Le mode `silent` désactive tout retour visuel et se contente de journaliser. | Aucun élément à l'écran en mode `silent`. |

### 4.8 Rejeu et recherche

| ID | Exigence | Vérification |
|---|---|---|
| **FR-70** | Les traces de signaux (jamais de contenu) sont exportables dans un format documenté et versionné. | Schéma publié dans `research/`. |
| **FR-71** | Le moteur complet peut être **rejoué hors ligne** sur une trace, de façon déterministe. | Deux exécutions sur la même trace produisent des sorties identiques bit à bit. |
| **FR-72** | Un banc d'évaluation calcule FAR, FRR, EER, ANIA, ANGA et TTD sur une trace annotée. | Résultats reproductibles, publiés dans `research/`. |
| **FR-73** | Le banc peut ingérer les corpus publics (CMU, Balabit, SapiMouse) pour comparaison avec l'état de l'art. | Au moins un résultat comparable publié. |

---

## 5. Exigences non fonctionnelles (NFR)

| ID | Exigence | Seuil | Vérification |
|---|---|---|---|
| **NFR-1** | Consommation CPU de l'agent, moyenne sur une heure d'usage intensif | < 1 % d'un cœur | Mesure en continu, affichée et journalisée |
| **NFR-2** | Mémoire résidente de l'agent | < 40 Mo | Idem |
| **NFR-3** | Croissance du stockage | < 2 Mo par jour d'usage intensif | Idem |
| **NFR-4** | Latence entre un événement et la mise à jour du score | < 250 ms au 95e centile | Instrumentation interne |
| **NFR-5** | Consommation de la console, onglet ouvert en continu | < 2 % de CPU, < 150 Mo | Mesure navigateur |
| **NFR-6** | Démarrage de l'agent | < 500 ms jusqu'au premier événement traité | Mesure au démarrage |
| **NFR-7** | Poids des ressources front | < 300 Ko transférés, sans dépendance CDN | Contrôle en CI |
| **NFR-8** | L'agent ne perd aucun événement sous charge : en cas de saturation, il dégrade la fréquence d'échantillonnage plutôt que de bloquer l'entrée utilisateur | Aucune latence perceptible à la frappe | Test de charge |
| **NFR-9** | Aucune dépendance réseau dans l'agent | Zéro socket sortant | Test d'intégration bloquant en CI, et audit des dépendances |
| **NFR-10** | Le projet se construit et s'exécute hors ligne | Construction réussie sans accès réseau après récupération des dépendances | Test en conteneur isolé |

## 6. Exigences de vie privée et de conformité (PR)

| ID | Exigence | Vérification |
|---|---|---|
| **PR-1** | Content-free : aucun contenu saisi, affiché ou copié n'est capturé. | Test bloquant FR-4. |
| **PR-2** | Identity-free : aucun identifiant civil, compte, adresse, numéro de série. Les profils sont des étiquettes opaques. | Audit du schéma de base. |
| **PR-3** | Local-first : aucune sortie réseau, aucune télémétrie, aucun service tiers. | NFR-9. |
| **PR-4** | Le gabarit et la base sont chiffrés au repos, la clé étant conservée dans le trousseau du système. | Base illisible hors session utilisateur. |
| **PR-5** | Purge complète en une commande, et rétention par défaut bornée (90 jours d'agrégats, 7 jours de vecteurs détaillés). | Vérification après expiration. |
| **PR-6** | Toute donnée collectée est documentée dans un registre public dans le dépôt : quoi, pourquoi, combien de temps, où. | [05-PRIVACY.md](05-PRIVACY.md) tenu à jour, contrôlé en revue. |
| **PR-7** | Le consentement est explicite au premier démarrage, avec une explication en langue claire de ce qui est capturé et de ce qui ne l'est pas. | Premier lancement bloquant tant que le consentement n'est pas donné. |
| **PR-8** | Le projet fournit un modèle d'AIPD et la liste des conditions à réunir avant tout usage impliquant un tiers. | Document présent dans `docs/`. |
| **PR-9** | L'outil refuse par conception de produire des métriques de productivité, de présence ou de contenu. | Revue de code : toute demande en ce sens est refusée et tracée. |
| **PR-10** | Irréversibilité et non-chaînabilité des gabarits, conformément à l'esprit d'ISO/IEC 24745. | Documentation du schéma de protection, et test d'inversion. |

## 7. Exigences de sécurité du produit (SR)

Un outil qui lit `/dev/input` est une cible de grande valeur. Ces exigences le protègent.

| ID | Exigence | Vérification |
|---|---|---|
| **SR-1** | Surface d'attaque minimale : aucun port réseau, IPC par socket UNIX avec permissions restreintes au compte utilisateur. | Audit. |
| **SR-2** | La console exige un jeton, régénéré à chaque démarrage, non persisté en clair. | Accès refusé sans jeton. |
| **SR-3** | Séparation des privilèges : le processus de capture ne fait que capturer et ne possède ni accès réseau ni accès en écriture au reste du système de fichiers. Durcissement `systemd` documenté. | Unité `systemd` avec `ProtectSystem`, `PrivateNetwork`, `NoNewPrivileges`, `SystemCallFilter`. |
| **SR-4** | Les dépendances sont minimales, épinglées, et auditées automatiquement. | Audit en CI, bloquant sur vulnérabilité connue de gravité élevée. |
| **SR-5** | La construction est reproductible et la publication signée. | Somme de contrôle vérifiable. |
| **SR-6** | Détection et journalisation des interruptions de service de l'agent (menace M11). | Un arrêt du service laisse une trace horodatée. |
| **SR-7** | Résistance à l'empoisonnement du gabarit (menace M10) : voir FR-23 et FR-24. | Scénario d'attaque dans le banc d'évaluation. |
| **SR-8** | Aucun secret, aucune clé, aucun jeton dans le dépôt. Analyse automatique à chaque commit. | Contrôle en CI. |

---

## 8. Critères d'acceptation globaux

Le projet est considéré comme atteignant son objectif de recherche quand les six conditions suivantes sont simultanément vérifiées et publiées dans `research/` :

| ID | Critère | Cible v1 |
|---|---|---|
| **AC-1** | EER de la décision fusionnée sur une fenêtre de 60 secondes d'activité, imposteur humain non informé | < 5 % |
| **AC-2** | Temps jusqu'à détection médian pour un imposteur humain (UC-1) | < 90 secondes d'activité |
| **AC-3** | Temps jusqu'à détection pour une entrée automatisée (UC-2, sans enrôlement) | < 10 secondes d'activité |
| **AC-4** | Fausses alarmes en usage légitime normal | < 1 par période de 8 heures d'usage |
| **AC-5** | Estimation du nombre d'utilisateurs, sur une trace contrôlée à 2 ou 3 personnes | Exact après 5 jours, et révisions journalisées |
| **AC-6** | Budgets NFR-1 à NFR-4 respectés en continu | 100 % du temps sur 7 jours |

Ces cibles sont des hypothèses de travail issues de l'état de l'art (EER de 6 % à 10 % selon la modalité pour une décision isolée, amélioré par l'accumulation séquentielle). Elles seront révisées après le lot 3 avec les mesures réelles du poste, et toute révision sera justifiée et datée.

## 9. Hors périmètre

Explicitement exclu, et à refuser en revue :

- Enregistrement du contenu saisi, des titres de fenêtres, des URL, du presse-papiers, des captures d'écran.
- Toute forme de télémétrie, de remontée vers un serveur, de synchronisation entre postes.
- Mesure de productivité, de temps de présence, d'assiduité.
- Blocage automatique de session, verrouillage, déconnexion ou toute action coercitive. L'outil observe et signale ; il n'agit pas sur le poste. Une éventuelle action de réponse relèverait d'une décision séparée, à spécifier pour elle-même.
- Reconnaissance faciale, capture audio, captures vidéo, géolocalisation.
- Clavier IME de substitution et service d'accessibilité Android (cf. 00-ANALYSE T6).
- Contournement du bac à sable d'iOS ou d'Android.
- Déploiement sur un parc, gestion multi-postes, console centralisée.

## 10. Livrables

| Lot | Livrable | Référence |
|---|---|---|
| 0 | Dépôt, licence, analyse, cahier des charges, protocole d'évaluation | ce document |
| 1 à 9 | Feuille de route par lot, à écrire | |

## 11. Licence et statut juridique

Le projet est publié en **source-available** sous **PolyForm Noncommercial 1.0.0** : lecture, modification, redistribution et usage à des fins de recherche et d'enseignement autorisés ; **usage commercial interdit**. Les droits commerciaux sont intégralement réservés à l'auteur, qui pourra ultérieurement publier une version sous une autre licence.

Le terme « open source » au sens de l'Open Source Initiative ne s'applique pas, puisqu'une restriction de champ d'usage est incompatible avec le critère 6 de la définition OSI. Le dépôt emploie donc « source-available » ou « recherche ouverte ». Voir [ADR-0002](adr/0002-licence-non-commerciale.md).
