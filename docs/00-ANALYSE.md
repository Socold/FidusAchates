# 00 - Analyse préalable et état de l'art

> Notes d'analyse. Elles précèdent et justifient le [cahier des charges](01-CAHIER-DES-CHARGES.md).

---

## 1. Reformulation du besoin

Ce que je cherche à construire porte, en langage académique, le nom suivant :

> **Authentification continue implicite multimodale par biométrie comportementale, locale, explicable, avec estimation non supervisée du nombre d'utilisateurs distincts et détection d'entrée non humaine.**

Quatre questions distinctes se cachent derrière, et elles n'ont pas les mêmes réponses techniques :

| # | Question | Nature | Difficulté |
|---|---|---|---|
| Q1 | *Est-ce toujours la même personne qu'à l'ouverture de session ?* | Vérification 1:1 contre un gabarit | Moyenne, bien couverte par la littérature |
| Q2 | *Combien de personnes différentes utilisent cette machine ?* | Clustering non supervisé, nombre de classes inconnu | Élevée, peu couverte |
| Q3 | *L'entrée provient-elle d'un humain ou d'un automate / agent IA / RAT ?* | Détection d'anomalie sans enrôlement | Moyenne, très discriminante |
| Q4 | *Pourquoi le système a-t-il conclu cela ?* | Explicabilité | Structurelle, à traiter dans l'architecture du moteur |

Ces quatre questions structurent tout le projet. Q3 est la plus utile en sécurité opérationnelle et la moins coûteuse en vie privée : elle ne nécessite **aucun** gabarit personnel. Q4 n'est pas une couche cosmétique ajoutée à la fin : elle impose un choix de moteur de décision (fusion additive de log-vraisemblances) qui doit être fait dès le départ.

---

## 2. Points de tension identifiés

Six contradictions ou impossibilités sont présentes dans l'expression du besoin. Les nommer maintenant évite de bâtir sur une hypothèse fausse.

### T1. « Parfaitement anonyme » est intenable au sens strict

Le RGPD (art. 4-14) définit la donnée biométrique comme *« les données à caractère personnel résultant d'un traitement technique spécifique, relatives aux caractéristiques physiques, physiologiques ou **comportementales** d'une personne physique, qui permettent ou confirment son identification unique »*. La CNIL range explicitement la dynamique de frappe au clavier dans la biométrie comportementale, et considère que l'authentification biométrique relève du régime des données sensibles (art. 9), y compris en authentification continue.

Autrement dit : **un outil dont la fonction même est de distinguer un utilisateur d'un autre produit par construction une donnée biométrique.** Un gabarit comportemental n'est pas anonyme, il est au mieux pseudonymisé.

**Décision retenue.** On abandonne le mot « anonyme » et on le remplace par trois engagements vérifiables, plus forts en pratique que l'étiquette :

- **Content-free** : aucun contenu saisi n'est capturé, stocké ni reconstructible (ni texte, ni URL, ni nom de fichier, ni titre de fenêtre en clair).
- **Identity-free** : aucun identifiant civil, compte, e-mail, adresse MAC, numéro de série. Les profils sont des étiquettes opaques (`profil-a1b2`).
- **Local-first** : aucune sortie réseau, aucune télémétrie, aucun appel tiers. Le poste est le seul lieu de traitement.

S'y ajoutent la minimisation (agrégats plutôt qu'événements), le chiffrement du gabarit au repos et une purge par défaut.

Cadre juridique applicable au projet dans sa phase actuelle : usage strictement personnel sur un poste de test, ce qui relève de l'exemption domestique (art. 2-2-c). **Dès qu'un tiers est observé, ou dès qu'un déploiement en organisation est envisagé, il faut une base légale art. 9-2-a (consentement explicite) et une AIPD.** C'est écrit dans [05-PRIVACY.md](05-PRIVACY.md).

### T2. Dynamique de frappe contre zéro enregistrement de touches

Les meilleurs discriminants du clavier sont les latences **par digraphe** (`t-h`, `e-r`) : elles supposent de savoir *quelles* touches ont été pressées. Or capturer l'identité des touches, c'est un enregistreur de frappe.

**Décision retenue : trois niveaux de granularité, P1 par défaut.**

| Niveau | Ce qui est conservé | Discriminance | Reconstruction du texte |
|---|---|---|---|
| **P0** (paranoïaque) | Classe de touche seulement (lettre / chiffre / espace / correction / modificateur / navigation) + timings | Bonne | Impossible |
| **P1** (défaut) | Digraphe **haché** : `HMAC(sel_volatil, keycode_1 ‖ keycode_2)` tronqué à 32 bits, agrégé en ligne | Très bonne | Impossible sans le sel, qui n'est jamais persisté et tourne à chaque session |
| **P2** (recherche) | Keycodes en clair | Référence | Possible : **réservé aux corpus de test dédiés, jamais en usage réel** |

Le hachage salé conserve la capacité à calculer une moyenne et un écart-type par digraphe (ce dont le modèle a besoin) tout en rendant le dictionnaire inversé inexploitable d'une session à l'autre. Un sel qui tourne oblige à ré-ancrer les statistiques : l'agent maintient donc une table de correspondance en mémoire volatile uniquement, et ne persiste que les agrégats.

**Garde-fous complémentaires** : aucune séquence ordonnée de plus de 2 touches n'est persistée, agrégation en ligne (algorithme de Welford) sans conservation des événements bruts au-delà d'un tampon circulaire de quelques secondes, et arrêt de capture sur liste noire d'applications (gestionnaire de mots de passe, navigateur en navigation privée, terminal si souhaité).

**Limite honnête à documenter** : sous Wayland, il n'existe aucun moyen fiable de savoir qu'un champ de saisie est un champ mot de passe. La protection repose donc sur la liste noire applicative, un raccourci de pause immédiate et la purge. Ce point doit figurer dans le README, pas dans une note de bas de page.

### T3. « Le plus léger possible » contre « détection fine »

Sans budget chiffré, cette exigence n'est pas testable. On la transforme en plafonds mesurés en continu et affichés dans la console (voir NFR-1 à NFR-5) : moins de 1 % de CPU moyen, moins de 40 Mo de mémoire résidente pour l'agent, moins de 2 Mo de stockage par jour d'usage intensif, latence de décision inférieure à 250 ms.

La conséquence architecturale est directe : **traitement en flux**, agrégats incrémentaux, aucun stockage d'événements bruts au-delà d'un tampon chaud, pas de réseau de neurones profond en ligne dans les premiers lots.

### T4. Contraintes du poste de test : GNOME sur Wayland

Vérifié sur la machine cible (Fedora, GNOME, session Wayland, utilisateur membre du groupe `input`) :

- **Capture globale clavier/souris** : impossible via les API de bureau (Wayland isole les applications). **Possible via `/dev/input/event*` (evdev)**, et l'appartenance au groupe `input` rend cet accès disponible sans privilège root. C'est la voie retenue.
- **Fenêtre active / application au premier plan** : inaccessible depuis un processus ordinaire sous GNOME Wayland. Il faut une **extension GNOME Shell** exposant la catégorie de l'application focalisée via D-Bus.
- **Superposition à l'écran (le carré rouge)** : `gtk-layer-shell` n'est pas supporté par Mutter. L'overlay doit donc lui aussi passer par l'extension GNOME Shell.

L'extension GNOME Shell n'est donc pas un confort : c'est un composant requis, pour deux fonctions.

**Conséquence de sécurité à assumer** : lire `/dev/input` confère les mêmes capacités qu'un enregistreur de frappe. Cela impose que le code soit auditable (d'où la publication des sources), que le binaire soit reproductible, et que les garanties de non-exfiltration soient vérifiables (absence de toute dépendance réseau dans l'agent, testée en CI).

### T5. Le carré rouge prévient l'attaquant

Afficher un indicateur de suspicion apprend à l'imposteur qu'il est détecté et lui permet d'itérer jusqu'à passer sous le seuil. C'est acceptable et souhaitable pour un banc de recherche (c'est même le retour visuel qui rend le projet démontrable), mais ce serait une faute en déploiement réel.

**Décision retenue** : deux modes explicites, `research` (overlay visible, celui que j'utilise sur ma machine) et `silent` (journalisation seule, aucun retour visuel). Le mode figure dans la configuration et est affiché dans la console.

### T6. Le périmètre mobile n'est pas le périmètre desktop

Sur iOS et sur Android non rooté, la capture globale des interactions est interdite par le bac à sable. Trois voies seulement existent :

1. **SDK intégré à une application** : on n'observe que l'intérieur de cette application (c'est ce que font BioCatch, TypingDNA, BehavioSec). Voie retenue à terme.
2. **Clavier IME personnalisé** : couvre la frappe dans tout le système, mais un IME voit le texte en clair, ce qui contredit frontalement T1.
3. **Service d'accessibilité Android** : très intrusif, et rejeté par les politiques des magasins d'applications hors cas d'usage d'accessibilité réel.

**Décision retenue** : lot 9, SDK in-app (voie 1), avec les modalités tactiles et inertielles. Les voies 2 et 3 sont explicitement hors périmètre.

---

## 3. État de l'art

### 3.1 Dynamique de frappe (keystroke dynamics)

Modalité la plus ancienne et la mieux documentée. La synthèse de référence récente est *Keystroke Dynamics: Concepts, Techniques, and Applications* (ACM Computing Surveys, 2025).

- **Texte imposé** : le banc d'essai de référence est le jeu de données CMU de Killourhy et Maxion (51 sujets, 8 sessions espacées d'au moins un jour, mot de passe `.tie5Roanl`, 400 vecteurs par sujet). Le meilleur détecteur simple y est la **distance de Manhattan mise à l'échelle**, avec un EER d'environ **0,096**. Des métriques plus récentes descendent à 0,087. Cet ordre de grandeur (10 %) est le repère à garder en tête pour une décision *ponctuelle*.
- **Texte libre** (le cas qui nous concerne) : les travaux de Gunetti et Picardi (mesures R et A sur les n-graphes partagés) restent la base conceptuelle. Les jeux de données pertinents sont Clarkson II, Buffalo et le corpus Aalto (136 millions de frappes).
- **Enseignement clé pour ce projet** : un EER de 10 % sur *une* décision isolée devient excellent dès qu'on accumule les décisions dans le temps. C'est tout l'intérêt de la décision séquentielle (voir 3.5).

### 3.2 Dynamique de la souris (mouse dynamics)

- Travaux fondateurs : Ahmed et Traore (2007), sur les courbes de vitesse par direction.
- Jeux de données : **Balabit Mouse Dynamics Challenge** (2016, 10 utilisateurs en tâches d'administration, premier corpus public), **SapiMouse**, **DFL**.
- Résultats récents : EER d'environ **6 %** sur Balabit, contre 13 % à 7,5 % pour les travaux antérieurs. Des approches plus simples (CNN 2D sur trajectoires) obtiennent environ 7,9 % d'EER.
- **Enseignement clé** : la souris est au moins aussi discriminante que le clavier, et elle est disponible dans des contextes où l'on ne tape pas. Elle est indispensable à la couverture continue.
- **Signal sous-exploité et peu coûteux** : la **loi de Fitts**. Le temps de pointage d'un utilisateur suit `T = a + b·log2(D/W + 1)`. Le couple `(a, b)`, estimé par régression sur les mouvements de pointage, est un invariant individuel remarquablement stable et très bon marché à calculer. Il est retenu comme signal de premier plan.

### 3.3 Modalités tactiles et inertielles (mobile)

- **Touchalytics** (Frank et al., 2013) : 30 caractéristiques de glissement, référence historique.
- **HMOG** : combinaison du mouvement de la main, de l'orientation et de la prise en main, avec les capteurs inertiels.
- **BB-MAS** : corpus multi-appareils.
- Pertinent pour le lot 9 seulement.

### 3.4 Détection d'entrée synthétique, d'automate et de prise de contrôle

C'est le volet le plus directement « sécurité », et le plus rentable.

- **Attaques BadUSB / Rubber Ducky** : détectables par analyse des journaux et par la régularité temporelle. La littérature forensique montre qu'une signature purement temporelle suffit souvent, sans enrôlement de l'utilisateur et sans accès au contenu. C'est exactement la propriété recherchée pour Q3.
- **Avertissement de la littérature, à intégrer au conception** : les heuristiques fondées sur la seule vitesse ou la seule régularité **sont contournables** en ralentissant et en randomisant les délais. Il faut donc des signaux structurellement plus difficiles à falsifier : provenance du périphérique (matériel réel contre `uinput`), quantification des horodatages sur une grille, absence de micro-corrections, cohérence entre modalités, et impossibilités physiques (chevauchement de touches incohérent, téléportation du curseur).
- **Robustesse contre contrefaçons synthétiques** : la dynamique de frappe reste attaquable par des générateurs entraînés sur des statistiques agrégées (Stefan et al., 2010 ; Serwadda et Phoha). À traiter comme modèle de menace, pas à ignorer.

### 3.5 Fusion et décision séquentielle

- *A Comprehensive Overview of Biometric Fusion* (arXiv 1902.02919) : panorama des niveaux de fusion. Le niveau **score** est le bon compromis ici.
- Les systèmes d'authentification continue utilisent classiquement un **modèle de confiance dynamique** : un score de confiance qui monte quand le comportement est conforme et descend sinon.
- Des implémentations séquentielles calculent un **rapport de log-vraisemblance (LLR)** par tour d'interaction, le cumulent et le comparent à deux seuils issus du **test séquentiel du rapport de probabilité de Wald (SPRT)**.

**C'est la réponse directe à l'exigence « très rapidement capable de dire que ce n'est pas lui ».** Le SPRT est, sous ses hypothèses, la procédure qui minimise le nombre d'observations nécessaires pour atteindre des taux d'erreur cibles. Le projet le retient comme cœur du moteur de décision. Bénéfice secondaire décisif : le LLR est **additif**, donc la contribution de chaque signal à la décision est exactement décomposable. **L'explicabilité (Q4) devient une propriété du modèle et non une approximation a posteriori.**

### 3.6 Estimation du nombre d'utilisateurs

Question peu traitée dans la littérature d'authentification (qui suppose l'identité connue). Elle relève du clustering à nombre de classes inconnu : modèles de mélange à **processus de Dirichlet**, ou mélange gaussien bayésien à troncature, avec révision rétrospective des partitions.

Le comportement que je veux, croire d'abord à plusieurs utilisateurs puis comprendre en recoupant qu'il n'y en a qu'un ou deux, correspond précisément à une procédure de **fusion de composantes** testée par rapport de vraisemblance. Voir [03-MODELE-DECISION.md](03-MODELE-DECISION.md), section 6.

**Piège principal, à traiter explicitement** : un même individu produit plusieurs **régimes** de comportement (clavier de portable contre clavier externe, main droite contre trackpad, matin contre fin de soirée, sobre contre fatigué). Sans distinction entre *régime* et *identité*, le système comptera systématiquement trop d'utilisateurs. Le modèle doit donc être **hiérarchique** : identité → modes.

### 3.7 Outils et produits existants

| Catégorie | Exemples | Ce qu'on en retient |
|---|---|---|
| Biométrie comportementale commerciale | BioCatch, BehavioSec (LexisNexis), TypingDNA, Plurilock | Cible principalement la fraude bancaire et l'accès à distance ; modèles fermés, non explicables, traitement serveur |
| UEBA d'entreprise | Exabeam, Securonix, Microsoft Defender for Identity | Raisonnent sur des journaux applicatifs et réseau, pas sur l'interaction physique ; granularité trop grossière pour Q1 |
| UEBA libre | OpenUBA, CyberSentinel-UEBA, Wazuh | Bonne inspiration pour la partie corrélation et tableau de bord ; aucun ne traite la biométrie comportementale locale |
| Recherche académique | Corpus CMU, Balabit, SapiMouse, HMOG, Clarkson II | Fournissent la base d'évaluation comparable, indispensable pour publier des résultats crédibles |

**Créneau de FidusAchates** (ce qui n'existe pas déjà en libre accès) :

1. Agent **local-first** et **content-free** assumé, sans serveur, auditable.
2. Décision **explicable par construction** (LLR additif, contributions en décibans).
3. **Estimation non supervisée du nombre d'utilisateurs**, avec révision rétrospective visible.
4. Traitement conjoint des deux menaces : **imposteur humain** et **pilotage automatisé** (agent IA, RAT, injection HID).
5. Banc de **rejeu déterministe** permettant de comparer des modèles sur des traces réelles sans recollecter.

### 3.8 Normes de rattachement

- **ISO/IEC 19795** : méthodologie d'évaluation des performances biométriques (vocabulaire FAR/FRR/EER, protocoles).
- **ISO/IEC 24745** : protection des gabarits biométriques (irréversibilité, non-chaînabilité, révocabilité).
- **ISO/IEC 30107** : détection des attaques de présentation.
- **NIST SP 800-63B** : niveaux d'assurance d'authentification, réauthentification de session.
- **MITRE ATT&CK** : T1078 (comptes valides) et T1219 (outils d'accès à distance) côté menaces détectées ; T1056.001 (capture d'entrée) côté risque que l'outil représente lui-même.

---

## 4. Modèle de menace

Ce que l'outil cherche à détecter, par ordre de difficulté croissante :

| # | Scénario | Signaux attendus | Difficulté |
|---|---|---|---|
| M1 | Poste laissé déverrouillé, quelqu'un s'en sert | Toutes modalités divergent simultanément | Faible |
| M2 | Injection HID (BadUSB, Rubber Ducky, KVM sur IP) | Régularité anormale, débit, provenance du périphérique | Faible |
| M3 | Automatisation locale (`ydotool`, `xdotool`, robot de test) | Provenance `uinput`, quantification des horodatages, trajectoires idéales | Faible |
| M4 | Agent IA pilotant le poste | Comme M3, plus absence de micro-corrections et séquences applicatives atypiques | Faible à moyenne |
| M5 | Prise de contrôle à distance (RDP, VNC, RAT) | Rafales alignées sur la latence réseau, gigue réseau, absence d'événements intermédiaires de la souris | Moyenne |
| M6 | Imposteur humain non informé | Divergence multimodale progressive | Moyenne |
| M7 | Imposteur humain ayant observé la victime | Divergence sur les signaux involontaires (Fitts, micro-corrections, digraphes rares) | Élevée |
| M8 | Contrefaçon synthétique entraînée sur les statistiques du gabarit | Cohérence inter-modale, signaux de second ordre | Très élevée |

Menaces **contre l'outil lui-même**, à traiter dans [01-CAHIER-DES-CHARGES.md](01-CAHIER-DES-CHARGES.md) section SR :

- M9 : vol de la base de gabarits (à chiffrer au repos, clé dans le trousseau système).
- M10 : empoisonnement du gabarit par adaptation lente d'un imposteur (le *drift hijacking*).
- M11 : arrêt silencieux de l'agent par l'attaquant (détecter et journaliser le trou de service).
- M12 : accès à la console d'administration locale par l'imposteur lui-même.

---

## 5. Hypothèses retenues

Elles sont explicites parce qu'elles conditionnent tout le reste. Si l'une est fausse, le cahier des charges doit être révisé.

- **H1** : la machine de test est ma machine personnelle, j'en suis l'utilisateur légitime, aucun tiers n'y est observé à son insu.
- **H2** : la machine cible est sous Fedora / GNOME / Wayland, mon compte appartient au groupe `input`, et cet accès restera disponible.
- **H3** : la phase 1 vise la recherche et la démonstration, pas un déploiement en production ni sur un parc.
- **H4** : un taux de fausse alarme non nul est acceptable en phase de recherche, à condition d'être mesuré et affiché.
- **H5** : j'accepte d'exécuter en continu un processus qui lit `/dev/input`, et je comprends ce que cela implique.
- **H6** : les données collectées restent sur le poste et ne servent à aucune décision automatisée produisant des effets juridiques.

---

## 6. Sources

- [Keystroke Dynamics: Concepts, Techniques, and Applications (ACM Computing Surveys)](https://dl.acm.org/doi/full/10.1145/3733103) et sa [version arXiv](https://arxiv.org/html/2303.04605v2)
- [Robust Keystroke Biometric Anomaly Detection (arXiv)](https://arxiv.org/pdf/1606.09075)
- [Distinguishability of keystroke dynamic template (PLOS One)](https://journals.plos.org/plosone/article?id=10.1371%2Fjournal.pone.0261291)
- [Optimizing Mouse Dynamics for User Authentication by Machine Learning (arXiv 2504.21415)](https://arxiv.org/html/2504.21415v1)
- [From Clicks to Security: Investigating Continuous Authentication via Mouse Dynamics (arXiv 2403.03828)](https://arxiv.org/pdf/2403.03828)
- [Machine and Deep Learning Applications to Mouse Dynamics (arXiv 2205.13646)](https://arxiv.org/pdf/2205.13646)
- [Forensic Log Based Detection For Keystroke Injection BadUSB Attacks (arXiv 2302.04541)](https://arxiv.org/pdf/2302.04541)
- [Keystroke-Dynamics Authentication Against Synthetic Forgeries (UCSD)](https://cseweb.ucsd.edu/~dstefan/pubs/stefan:2010:keystroke.pdf)
- [Robustness of keystroke-dynamics based biometrics against synthetic forgeries (ScienceDirect)](https://www.sciencedirect.com/science/article/abs/pii/S0167404811001179)
- [A Comprehensive Overview of Biometric Fusion (arXiv 1902.02919)](https://arxiv.org/pdf/1902.02919)
- [Continuous User Authentication Using Machine Learning and Multi-Finger Mobile Touch Dynamics (arXiv 2207.13648)](https://arxiv.org/pdf/2207.13648)
- [Continuous Authentication Using Mouse Movements, Machine Learning, and Minecraft (arXiv 2110.11080)](https://arxiv.org/pdf/2110.11080)
- [Design and Implementation of Continuous Authentication Mechanism Based on Multimodal Fusion (Wiley)](https://onlinelibrary.wiley.com/doi/10.1155/2021/6669429)
- [GitHub Topics : user-behavior-analytics](https://github.com/topics/user-behavior-analytics)
- [CyberSentinel-UEBA](https://github.com/AdityaUmathe/CyberSentinel-UEBA)
- [Top Open Source UEBA Tools (AIMultiple)](https://aimultiple.com/open-source-ueba)
- [CNIL : Biométrie](https://www.cnil.fr/fr/biometrie) et [Questions-réponses sur le règlement type biométrie](https://www.cnil.fr/fr/question-reponses-sur-le-reglement-type-biometrie)
- [CNIL : Biométrie à disposition de particuliers](https://www.cnil.fr/fr/biometrie-disposition-de-particuliers-quels-sont-les-principes-respecter)
- [CNIL : Guide pratique RGPD sécurité des données personnelles (PDF)](https://www.cnil.fr/sites/cnil/files/atoms/files/cnil_guide_securite_des_donnees_personnelles-2023.pdf)
