# 05 - Vie privée, éthique et conformité

> Répond aux exigences PR-1 à PR-10. Ce document fait foi : toute collecte non décrite ici est un défaut.

---

## 1. Position de principe

FidusAchates est un outil capable de lire tout ce qui est tapé sur un clavier. C'est un pouvoir dangereux, assumé plutôt que minimisé. Le projet se donne donc une règle qui prime sur toutes les autres :

> **On ne collecte pas ce qu'on peut déduire, et on ne déduit pas ce dont on n'a pas besoin.**

L'objectif du projet est de répondre à « est-ce la même personne ? ». Il n'est pas de savoir ce que cette personne écrit, lit, cherche ou produit. Toute fonctionnalité qui s'écarte de cette frontière est un défaut à corriger, pas une évolution à discuter (PR-9).

## 2. Ce que l'outil ne fait jamais

Liste opposable, à vérifier en revue de code et par test automatisé :

- Aucun contenu saisi, sous aucune forme, y compris partielle ou dérivée reconstructible.
- Aucun titre de fenêtre, nom d'exécutable, chemin de fichier, URL, terme de recherche.
- Aucun contenu de presse-papiers.
- Aucune capture d'écran, aucun accès à la caméra ou au microphone.
- Aucune géolocalisation, aucun identifiant réseau (adresse MAC, IP, SSID).
- Aucun identifiant civil : nom, compte, adresse électronique, numéro de série, identifiant matériel.
- Aucune connexion réseau sortante, aucune télémétrie, aucun rapport d'incident distant, aucune police ni script distant.
- Aucune mesure de productivité, d'assiduité, de présence ou de performance.
- Aucune action coercitive sur le poste : pas de verrouillage, pas de déconnexion, pas de blocage.

Le point le plus important de cette liste est le suivant : l'absence de réseau n'est pas une promesse, c'est une propriété structurelle. Le processus de capture s'exécute sous `PrivateNetwork=yes`, **il n'a pas d'accès réseau à donner**, même s'il était compromis (SR-3, NFR-9).

## 3. Registre de traitement

| Catégorie | Données | Finalité | Base | Rétention | Emplacement |
|---|---|---|---|---|---|
| Timings d'entrée | Horodatages monotones, classes de touches, boutons | Signaux A, B, E | Fonctionnement | Tampon mémoire 10 s, non persisté | RAM |
| Digraphes hachés | `HMAC(sel volatil, paire de codes)` tronqué à 32 bits | Signal A05 | Fonctionnement | Agrégés seulement | SQLite chiffré |
| Vecteurs de fenêtre | Valeurs des signaux par fenêtre d'activité | Décision, regroupement | Fonctionnement | 7 jours | SQLite chiffré |
| Agrégats | n, moyenne, M2, quantiles par signal, profil, mode | Gabarits | Fonctionnement | 90 jours | SQLite chiffré |
| Gabarits | Paramètres statistiques par profil | Décision | Fonctionnement | Vie du profil | SQLite chiffré |
| Décisions | Horodatage, niveau, contributions | Explicabilité, audit | Fonctionnement | 90 jours | SQLite chiffré |
| Révisions de profils | Fusions, scissions, justifications | Traçabilité | Fonctionnement | Permanent | SQLite chiffré |
| Contexte applicatif | Catégorie (7 valeurs) et identifiant opaque | Signaux C | Fonctionnement | 7 jours | SQLite chiffré |
| Santé | CPU, mémoire, débit | Respect des NFR | Fonctionnement | 7 jours | SQLite chiffré |

Aucune autre donnée n'est écrite sur disque. Toute ligne ajoutée à ce tableau doit l'être dans le même commit que le code qui la produit.

## 4. Qualification juridique

### 4.1 Nature des données

Un gabarit comportemental permettant de distinguer un individu relève de la définition de la **donnée biométrique** (RGPD art. 4-14), et donc du régime de l'**article 9** (catégories particulières). La CNIL range explicitement la dynamique de frappe dans la biométrie comportementale et maintient ce régime pour l'authentification, y compris continue.

**Conséquence : le projet ne prétend pas produire des données anonymes.** Il produit des données pseudonymisées, minimisées et confinées localement. L'affirmation « parfaitement anonyme » serait fausse, et l'écrire exposerait le projet à un reproche fondé.

### 4.2 Situation actuelle : usage personnel

Dans la configuration présente, ma machine personnelle et aucun tiers observé, le traitement relève de l'**exemption pour activité personnelle ou domestique** (art. 2-2-c). Aucune formalité n'est requise.

Cette exemption disparaît dès que l'une des conditions suivantes est remplie :

- une autre personne utilise le poste et est observée ;
- l'outil est installé sur un poste professionnel ;
- des résultats sont publiés à partir de données concernant un tiers ;
- l'outil est déployé sur plusieurs postes.

### 4.3 Conditions à réunir avant tout usage impliquant un tiers (PR-8)

| # | Condition |
|---|---|
| 1 | **Base légale art. 9-2-a** : consentement explicite, libre, spécifique, éclairé, révocable, recueilli et journalisé avant toute collecte |
| 2 | **Analyse d'impact (AIPD)** : obligatoire (biométrie, surveillance systématique). Modèle fourni dans `docs/aipd-modele.md` |
| 3 | **Information préalable** complète : finalités, données, durées, droits, destinataires, absence de décision automatisée |
| 4 | **Droit d'opposition effectif** : arrêt et purge immédiats, sans conséquence pour la personne |
| 5 | **En contexte professionnel** : consultation des représentants du personnel, et vérification que la surveillance est proportionnée. Un tel déploiement est hors périmètre du projet |
| 6 | **Comité d'éthique** si le projet donne lieu à publication académique avec sujets humains |
| 7 | **Aucune décision produisant des effets juridiques** ne peut être fondée sur la sortie de l'outil (art. 22) |

Ces conditions sont reprises dans le README pour être vues avant installation.

## 5. Protection technique

| Mesure | Mise en œuvre | Exigence |
|---|---|---|
| Chiffrement au repos | Base chiffrée, clé dans le trousseau du système, jamais sur disque en clair | PR-4 |
| Sel volatil | Régénéré à chaque démarrage, en mémoire uniquement, jamais persisté | FR-3 |
| Absence d'événements bruts | Propriété du schéma, pas politique de purge | FR-8 |
| Rétention bornée | Purge automatique quotidienne selon le registre ci-dessus | PR-5 |
| Purge totale | `fidus-cli purge` efface base, gabarits et journaux | FR-7, PR-5 |
| Suspension immédiate | Raccourci global et commande CLI, effet en moins d'une seconde | FR-7 |
| Liste noire applicative | Capture suspendue pour les applications listées, par défaut : gestionnaires de mots de passe | FR-6 |
| Isolement réseau | `PrivateNetwork=yes` sur le processus de capture | NFR-9, SR-3 |
| Console locale | Liaison `127.0.0.1` uniquement, jeton à chaque démarrage | FR-50, SR-2 |
| Irréversibilité | Aucun gabarit ne permet de reconstruire une séquence d'entrée | PR-10 |

### Limite assumée, à ne pas dissimuler

**Sous Wayland, il n'existe aucun moyen fiable de détecter qu'un champ de saisie est un champ de mot de passe.** La protection contre la capture des mots de passe repose donc sur trois mesures imparfaites : la liste noire applicative (FR-6), la suspension manuelle (FR-7), et le fait qu'en niveau P0 et P1 aucun keycode en clair ne soit conservé.

Cette limite figure dans le README, au-dessus des instructions d'installation, et non en note de bas de page.

## 6. Niveaux de granularité

| Niveau | Ce qui est conservé | Usage prévu |
|---|---|---|
| **P0** | Classes de touches uniquement | Utilisateur prudent, démonstration publique |
| **P1** (défaut) | Digraphes hachés et salés | Usage normal du projet |
| **P2** | Keycodes en clair | **Corpus de test dédiés uniquement.** Refuser en usage réel. Le mode affiche un avertissement permanent dans la console et dans l'overlay |

Le niveau actif est affiché en permanence dans la console (FR-57).

## 7. Éthique de la recherche

1. **Consentement avant tout sujet.** Aucune donnée d'un tiers n'est collectée sans son accord explicite préalable.
2. **Réciprocité.** Toute personne observée a accès à la console et peut consulter, exporter et effacer ses propres données.
3. **Pas de surprise.** L'outil est visible : service déclaré, indicateur d'état, aucune exécution discrète. Un outil de ce type qui se cache est un logiciel malveillant.
4. **Publication des échecs.** Les signaux mesurés comme non discriminants sont publiés au même titre que les autres. Un catalogue de signaux qui ne contiendrait que des succès serait un catalogue biaisé.
5. **Pas d'usage à charge.** Les sorties ne servent jamais à sanctionner, noter ou évaluer une personne.
6. **Réversibilité.** À tout moment : arrêt, purge, désinstallation complète en une commande.

## 8. Risque de détournement

Le projet produit, de fait, une brique techniquement proche d'un enregistreur de frappe et d'un outil de surveillance. Le nier serait malhonnête. Les contre-mesures retenues :

- **Licence non commerciale** : limite la reprise industrielle sans discussion préalable.
- **Absence de fonction de remontée** : il n'existe aucun code d'exfiltration à réutiliser. Un détournement demande de l'écrire, ce qui en fait un autre logiciel.
- **Absence de fonction d'invisibilité** : l'outil ne sait pas se cacher, et aucune contribution en ce sens ne sera acceptée.
- **Absence d'action coercitive** : pas de verrouillage ni de blocage à détourner.
- **Documentation frontale** : ce document est lié depuis le README, avant les instructions d'installation.

## 9. Ce que ce document engage

Toute contribution doit répondre par l'affirmative aux quatre questions suivantes, sans quoi elle est refusée :

1. La donnée collectée figure-t-elle dans le registre de la section 3 ?
2. Le signal ajouté est-il calculable sans connaître le contenu ?
3. La finalité reste-t-elle « est-ce la même personne, est-ce un humain » ?
4. Un utilisateur qui lirait le code se sentirait-il trahi ?
