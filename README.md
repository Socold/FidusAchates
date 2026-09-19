# FidusAchates

**Authentification continue implicite par biométrie comportementale, locale et explicable.**

> *Fidus Achates* : le compagnon fidèle d'Énée. Celui qui marche à côté, qui reconnaît, et qui prévient.

FidusAchates apprend la manière dont une personne utilise un appareil (rythme de frappe, gestuelle du pointeur, enchaînement des applications, rythme temporel), puis évalue en continu deux questions distinctes :

1. **Est-ce toujours la même personne ?**
2. **Est-ce encore un humain ?** (automate, agent IA, injection HID, prise de contrôle à distance)

Le tout **sans jamais enregistrer ce qui est tapé**, **sans aucun accès réseau**, et en **expliquant chaque décision**.

---

## À lire avant toute installation

**Cet outil lit `/dev/input`. Il a donc techniquement les capacités d'un enregistreur de frappe.** Le projet est conçu pour ne jamais s'en servir ainsi, et cette contrainte est vérifiée par des tests bloquants en intégration continue, mais le pouvoir existe. Ne l'installez que si vous êtes prêt à lire le code, ou à faire confiance à quelqu'un qui l'a lu.

**Limite connue, non contournable sous Wayland :** il n'existe aucun moyen fiable de détecter qu'un champ de saisie est un champ de mot de passe. La protection repose sur une liste noire d'applications, une suspension manuelle immédiate, et le fait qu'en configuration par défaut aucun code de touche n'est conservé en clair. Voir [docs/05-PRIVACY.md](docs/05-PRIVACY.md).

**N'observez jamais une autre personne sans son consentement explicite préalable.** Un gabarit comportemental est une donnée biométrique au sens du RGPD (art. 4-14), relevant de l'article 9. Les conditions à réunir avant tout usage impliquant un tiers sont listées dans [docs/05-PRIVACY.md](docs/05-PRIVACY.md) section 4.3.

---

## État

**Conception.** La documentation de référence est stabilisée. L'implémentation démarre au lot 1.

| Lot | Objet | État |
|---|---|---|
| 0 | Analyse, spécifications, architecture, licence | fait |
| 1 | Agent evdev, dynamique de frappe, console minimale | à faire |
| 2 | Dynamique du pointeur, fusion LLR, explicabilité | à faire |
| 3 | Étalonnage et calibration | à faire |
| 4 | Profils multiples et révision | à faire |
| 5 | Détection d'entrée non humaine (complet) | à faire |
| 6 | Extension GNOME Shell et overlay | à faire |
| 7 | Banc de recherche et corpus publics | à faire |
| 8 | Portage Windows, macOS, X11 | à faire |
| 9 | SDK mobile | à faire |

Feuille de route détaillée avec critères d'acceptation : [docs/06-ROADMAP.md](docs/06-ROADMAP.md).

## Documentation

| Document | Contenu |
|---|---|
| [00 - Analyse](docs/00-ANALYSE.md) | Reformulation du besoin, points de tension, état de l'art sourcé, modèle de menace |
| [01 - Cahier des charges](docs/01-CAHIER-DES-CHARGES.md) | Exigences numérotées et vérifiables (FR, NFR, PR, SR), critères d'acceptation |
| [02 - Architecture](docs/02-ARCHITECTURE.md) | Composants, flux, stockage, portabilité |
| [03 - Moteur de décision](docs/03-MODELE-DECISION.md) | Fusion LLR, SPRT, niveaux, étalonnage, comptage des utilisateurs |
| [04 - Catalogue des signaux](docs/04-CATALOGUE-SIGNAUX.md) | 90 signaux répartis en 7 familles, avec coût, pouvoir discriminant et difficulté de falsification |
| [05 - Vie privée](docs/05-PRIVACY.md) | Registre de traitement, qualification juridique, éthique, risque de détournement |
| [06 - Feuille de route](docs/06-ROADMAP.md) | Lots et critères d'acceptation |
| [ADR](docs/adr/) | Décisions d'architecture et leurs alternatives écartées |

## Principes de conception

**Content-free.** Aucun contenu saisi, titre de fenêtre, URL, nom de fichier ou presse-papiers n'est capturé. Un test bloquant en intégration continue saisit des mots témoins et vérifie qu'aucun ne se retrouve en base.

**Identity-free.** Aucun identifiant civil, compte ou numéro de série. Les profils sont des étiquettes opaques du type `profil-a1b2`.

**Local-first, structurellement.** Le processus de capture s'exécute sous `PrivateNetwork=yes` : il n'a pas d'accès réseau à donner, même compromis. Aucune télémétrie, aucun CDN, aucune police distante.

**Explicable par construction.** Le moteur additionne des rapports de log-vraisemblance exprimés en décibans. La contribution de chaque signal à la décision est donc **exacte**, pas estimée. L'explication affichée est la formule elle-même, lue terme à terme.

**Observe, n'agit pas.** L'outil ne verrouille rien, ne bloque rien, ne déconnecte personne. Il signale.

## Fonctionnement en bref

```
Chaque signal apporte une preuve, mesurée en décibans :

   e = 10 · log10 [ P(observation | légitime) / P(observation | imposteur) ]

Les preuves s'additionnent, pondérées par leur fiabilité et leur qualité,
avec oubli progressif des preuves anciennes.

Le test séquentiel de Wald tranche dès que la preuve cumulée franchit
un seuil dérivé des taux d'erreur visés, donc le plus tôt possible.
```

Deux évidences cumulées sont maintenues séparément, jamais confondues :

| Canal | Question | Enrôlement | Détecte |
|---|---|---|---|
| **Identité** | Même personne ? | Requis | Usurpation humaine |
| **Humanité** | Humain ? | **Aucun** | `ydotool`, BadUSB, KVM sur IP, RDP, agent IA |

Le canal Humanité est le meilleur rapport valeur sur risque du projet : il détecte les menaces les plus concrètes, il fonctionne dès la première seconde, et **il ne stocke aucun gabarit personnel**.

## Étalonnage

À la question « combien de temps faut-il pour que l'outil me reconnaisse ? », le projet ne répond pas par une durée arbitraire. La fin de l'enrôlement est déclenchée par quatre critères de convergence mesurés (volume, stabilité du gabarit, performance auto-estimée par validation croisée temporelle avec intervalle de confiance, couverture contextuelle), et le système produit la courbe de performance en fonction du volume, qui donne la valeur réelle pour ce poste et cet utilisateur. Détail en [docs/03-MODELE-DECISION.md](docs/03-MODELE-DECISION.md) section 5.

## Comptage des utilisateurs

Le regroupement se fait sans connaître à l'avance le nombre de personnes, et il se **révise** : deux profils jugés indistinguables sont fusionnés, avec la justification statistique conservée et affichée.

```
J+3   3 profils
J+9   fusion c3d4 ← e5f6
      distance de Hellinger 0,08 < seuil 0,15
      rapport de vraisemblance 1 composante / 2 composantes = 4,2
      entrelacement temporel 0,71 (les deux régimes alternent dans 14 sessions)
      conclusion : même personne, deux modes (clavier interne / clavier externe)
J+9   2 profils (intervalle crédible 2 à 3)
```

La distinction entre **mode** (un même individu a plusieurs régimes) et **identité** est centrale : sans elle, le système compte systématiquement trop d'utilisateurs.

## Empreinte, installation et autorisations

L'outil est fait pour être installé une fois et oublié. Son coût se mesure **au repos**, état dans lequel il passe la quasi-totalité de son temps.

**Exécution.** L'agent est piloté par les événements : il reste bloqué sur `epoll` en attente des descripteurs d'entrée. Sans frappe ni mouvement, il ne s'exécute pas du tout, et ne réveille pas le processeur. Aucune boucle de sondage, nulle part. La console n'existe pas tant qu'on ne l'ouvre pas : elle est démarrée par activation de socket.

| | Au repos | En activité |
|---|---|---|
| Processeur | 0 % | moins de 1 % en moyenne |
| Mémoire résidente | moins de 40 Mo | moins de 40 Mo |
| Stockage | moins de 2 Mo par jour d'usage intensif | |
| Binaire | moins de 8 Mo, empreinte installée moins de 15 Mo | |

**Autorisations demandées, en totalité :**

| Autorisation | Quand | Révocation |
|---|---|---|
| Appartenance au groupe `input` | Une seule fois, à l'installation | `sudo gpasswd -d $USER input` |

Rien d'autre, à aucun moment : **pas de root à l'exécution**, pas de setuid, pas de capability, pas de module noyau, pas de service système (uniquement `systemd --user`), pas d'accès réseau, pas d'autorisation d'accessibilité, pas d'extension de navigateur, aucun fichier de configuration du système modifié.

Cette unique autorisation est néanmoins un privilège fort : elle donne accès à toutes les entrées de la session. Elle est incompressible pour une capture globale sous Wayland. Le projet ne la présente pas comme anodine, il la réduit au strict nécessaire et la compense par l'auditabilité des sources et un isolement réseau structurel (`PrivateNetwork=yes` : le processus de capture n'a pas d'accès réseau à donner, même compromis). Voir [ADR-0006](docs/adr/0006-moindre-privilege-installation.md).

**Installation.** Une commande, binaire précompilé, aucune chaîne de compilation requise, moins de 60 secondes jusqu'au premier événement traité. Désinstallation complète en une commande, purge des données comprise.

L'extension GNOME Shell est **facultative** : sans elle, l'agent fonctionne en mode dégradé (perte du contexte applicatif et de l'overlay, remplacé par une notification de bureau). L'installation n'échoue jamais faute d'extension.

**Prérequis (à partir du lot 1)**

- Linux, session Wayland ou X11 (développé sur Fedora / GNOME / Wayland)
- Appartenance au groupe `input`
- Facultatif : GNOME Shell, pour le contexte applicatif et l'overlay
- Pour contribuer au code : Rust stable ; pour `fidus-lab`, Python 3.12 ou supérieur, hors ligne uniquement

## Hors périmètre

Explicitement exclu, et refusé en revue : enregistrement de contenu, télémétrie, mesure de productivité ou de présence, action coercitive sur le poste, reconnaissance faciale, capture audio ou vidéo, géolocalisation, clavier IME de substitution, service d'accessibilité Android, console centralisée, déploiement en parc.

Ces éléments ne sont pas « prévus plus tard » : ils sont hors projet.

## Licence

**PolyForm Noncommercial 1.0.0.** Lecture, modification, redistribution et usage autorisés à des fins de **recherche, d'étude et d'enseignement**. **Usage commercial interdit.** Tous les droits commerciaux sont réservés à l'auteur, qui se réserve la possibilité de relicencier ultérieurement.

Le terme « open source » au sens de l'Open Source Initiative ne s'applique pas, une restriction de champ d'usage étant incompatible avec le critère 6 de la définition OSI. Le projet se décrit donc comme **source-available** et comme **projet de recherche ouvert**. Voir [ADR-0002](docs/adr/0002-licence-non-commerciale.md).

## Sources et travaux antérieurs

Le projet s'appuie sur un état de l'art documenté et sourcé en [docs/00-ANALYSE.md](docs/00-ANALYSE.md) section 3 : corpus de référence (CMU, Balabit, SapiMouse, HMOG, Clarkson II), travaux sur la détection d'injection HID, littérature sur la fusion biométrique et la décision séquentielle, panorama des outils UEBA libres et commerciaux, et normes ISO/IEC 19795, 24745, 30107 ainsi que NIST SP 800-63B.
