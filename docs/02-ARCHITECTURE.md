# 02 - Architecture technique

> Découle de [00-ANALYSE.md](00-ANALYSE.md) et de [01-CAHIER-DES-CHARGES.md](01-CAHIER-DES-CHARGES.md).

---

## 1. Vue d'ensemble

```
┌──────────────────────────────────────────────────────────────────────┐
│  POSTE UTILISATEUR (aucune sortie réseau)                            │
│                                                                      │
│  /dev/input/event*                                                   │
│         │ evdev (groupe input, sans root)                            │
│         ▼                                                            │
│  ┌──────────────────┐   D-Bus    ┌─────────────────────────────┐     │
│  │  fidus-agent     │◄──────────►│  fidus-shell-ext            │     │
│  │  (Rust)          │            │  (GNOME Shell, JS)          │     │
│  │                  │            │                             │     │
│  │ 1. Capture       │  contexte  │  • catégorie d'app focus    │     │
│  │ 2. Tampon chaud  │◄───────────│  • overlay carré rouge      │     │
│  │ 3. Extraction    │  overlay   │  • état verrouillé / idle   │     │
│  │ 4. Experts       │───────────►│                             │     │
│  │ 5. Fusion LLR    │            └─────────────────────────────┘     │
│  │ 6. SPRT          │                                                │
│  │ 7. Profils       │                                                │
│  └────────┬─────────┘                                                │
│           │ socket UNIX (0600)                                       │
│     ┌─────┴──────┬───────────────┐                                   │
│     ▼            ▼               ▼                                   │
│ ┌────────┐  ┌──────────┐  ┌────────────┐                             │
│ │ SQLite │  │ fidus-   │  │ fidus-cli  │                             │
│ │ (WAL,  │  │ console  │  │            │                             │
│ │ chiffré│  │ 127.0.0.1│  │ pause      │                             │
│ │ )      │  │ + jeton  │  │ purge      │                             │
│ └───┬────┘  │ SSE      │  │ export     │                             │
│     │       └──────────┘  └────────────┘                             │
│     │ export de traces (signaux, jamais de contenu)                  │
│     ▼                                                                │
│ ┌──────────────────────────────────────────┐                         │
│ │ fidus-lab (hors ligne, Python)           │                         │
│ │ rejeu déterministe, banc d'évaluation,   │                         │
│ │ corpus publics, courbes DET/ROC          │                         │
│ └──────────────────────────────────────────┘                         │
└──────────────────────────────────────────────────────────────────────┘
```

## 2. Composants

### 2.1 `fidus-agent` (Rust)

Cœur du système. Processus unique, sans privilège root, démarré par une unité `systemd --user`.

**Pourquoi Rust** : l'exigence dominante est NFR-1 à NFR-4 (moins de 1 % de CPU, moins de 40 Mo, latence sous 250 ms) sur un processus qui tourne en permanence. Absence de ramasse-miettes, empreinte mémoire prévisible, accès `evdev` direct, et compilation en binaire unique sans dépendance d'exécution. Voir [ADR-0001](adr/0001-langage-agent-rust.md).

Organisation interne en étages, chacun isolé derrière un trait :

| Étage | Rôle | Trait |
|---|---|---|
| 1. Capture | Lecture `evdev`, normalisation, marquage de provenance | `Source` |
| 2. Tampon chaud | Anneau en mémoire, 10 s maximum, jamais persisté | |
| 3. Extraction | Calcul des signaux en flux, agrégats de Welford | `Extractor` |
| 4. Experts | Un score calibré par modalité | `Expert` |
| 5. Fusion | Somme pondérée de LLR | |
| 6. Décision | SPRT, hystérésis, niveaux | |
| 7. Profils | Regroupement en ligne, révisions | |

Un nouvel expert s'ajoute en implémentant `Expert` et en s'enregistrant : le cœur n'est pas modifié (FR-12).

### 2.2 `fidus-shell-ext` (extension GNOME Shell, JavaScript)

Composant **requis**, pas optionnel, pour deux raisons établies en analyse (T4) : sous GNOME Wayland, ni le contexte de fenêtre active ni une superposition permanente ne sont accessibles depuis un processus ordinaire.

Deux fonctions, et rien d'autre :

1. **Contexte** : publie sur D-Bus la **catégorie** de l'application au premier plan et un identifiant opaque stable, jamais le titre ni le nom binaire (FR-5).
2. **Overlay** : affiche le carré rouge en haut à droite, sans focus ni interception d'événement (FR-60 à FR-62).

L'extension est volontairement minuscule et lisible d'une traite : c'est le composant le plus privilégié de la chaîne côté interface, il doit être auditable en quelques minutes.

### 2.3 `fidus-console` (serveur local + interface web)

Serveur HTTP embarqué dans l'agent ou processus distinct léger, lié à `127.0.0.1`, protégé par un jeton régénéré à chaque démarrage (SR-2).

Diffusion temps réel par **Server-Sent Events** plutôt que WebSocket : le flux est unidirectionnel, SSE se reconnecte tout seul, et coûte moins cher (NFR-5).

Interface sans cadriciel lourd, sans CDN, sans police distante. Cible : moins de 300 Ko transférés (NFR-7). Tracés en SVG calculés côté client à partir du flux, pas de bibliothèque graphique volumineuse.

### 2.4 `fidus-cli`

Commandes : `status`, `pause`, `resume`, `purge`, `export`, `profiles`, `doctor` (diagnostic des prérequis : groupe `input`, extension installée, session Wayland).

### 2.5 `fidus-lab` (Python, hors ligne uniquement)

Séparé de l'agent, jamais exécuté en continu. Rejeu déterministe des traces (FR-71), banc d'évaluation (FR-72), ingestion des corpus publics (FR-73), production des courbes.

Ce découplage est un choix structurant : **l'expérimentation sur les modèles se fait hors ligne, en Python, sur des traces figées**, puis le modèle retenu est porté dans l'agent. On évite ainsi d'alourdir l'agent d'un environnement d'apprentissage, tout en gardant une boucle de recherche rapide.

## 3. Stockage

**SQLite en mode WAL**, un seul fichier, chiffré au repos (PR-4).

Schéma en trois strates de rétention décroissante :

| Table | Contenu | Rétention |
|---|---|---|
| `window_vectors` | Vecteurs de signaux par fenêtre d'activité | 7 jours |
| `aggregates` | Agrégats incrémentaux par profil, mode et signal (n, moyenne, M2, quantiles approchés) | 90 jours |
| `templates` | Gabarits : ancre gelée et version courante | Durée de vie du profil |
| `decisions` | Événements de décision avec vecteur de contributions | 90 jours |
| `profile_revisions` | Historique des fusions et scissions avec justification statistique | Permanent (volume négligeable) |
| `health` | Métriques de ressources | 7 jours |

**Aucune table d'événements bruts.** C'est une propriété du schéma, pas une politique de purge : ce qui n'existe pas ne peut pas fuir.

Les quantiles sont maintenus par t-digest ou par un estimateur P² afin de rester en mémoire bornée (NFR-2, NFR-3).

## 4. Flux de données

```
evdev ──► normalisation ──► tampon chaud (10 s)
                                 │
                 ┌───────────────┼───────────────┬──────────────┐
                 ▼               ▼               ▼              ▼
          expert Frappe   expert Souris   expert Contexte  expert Automation
                 │               │               │              │
              score           score           score          score
              calibré         calibré         calibré        calibré
                 │               │               │              │
                 └──► LLR ◄──────┴───────────────┴──────────────┘
                        │  pondération par qualité et fiabilité
                        ▼
                   Σ LLR pondérés  ──► SPRT (2 seuils, décroissance)
                        │                       │
                        ▼                       ▼
                 contributions (dB)       niveau L0..L4
                        │                       │
                        └────► console ◄────────┘
                                  └──► overlay si P(imposteur) > 0,50
```

## 5. Portabilité

L'étage 1 (`Source`) est le seul à être spécifique au système. Le reste est portable tel quel.

| Cible | Capture | Contexte applicatif | Overlay | Lot |
|---|---|---|---|---|
| Linux Wayland (GNOME) | `evdev` | extension GNOME Shell | extension GNOME Shell | 1 à 6 |
| Linux X11 | `evdev` ou XInput2 | XLib | fenêtre `override-redirect` | 8 |
| Windows | `SetWindowsHookEx` bas niveau ou Raw Input | Win32 | fenêtre par couches | 8 |
| macOS | `CGEventTap` (autorisation accessibilité requise) | Accessibility API | `NSWindow` de niveau écran | 8 |
| Android et iOS | SDK in-app uniquement (cf. T6) | dans l'application | dans l'application | 9 |

Sur Windows, la détection de provenance synthétique est facilitée par l'indicateur `LLKHF_INJECTED` ; sur Linux, par l'identification du périphérique `uinput`. Les deux alimentent le même signal.

## 6. Déploiement sur le poste de test

- Unité `systemd --user`, durcie : `NoNewPrivileges`, `PrivateNetwork=yes` pour le processus de capture, `ProtectSystem=strict`, `ProtectHome=read-only` hors répertoire de données, `SystemCallFilter=@system-service`, `MemoryMax` aligné sur NFR-2 (SR-3).
- `PrivateNetwork=yes` sur le processus de capture rend NFR-9 structurel : **il ne peut pas exfiltrer, même compromis**.
- Données dans `~/.local/share/fidusachates/`, configuration dans `~/.config/fidusachates/`.
- Installation de l'extension GNOME Shell par script, activation explicite par l'utilisateur.


## 7. Modèle d'exécution et empreinte

L'outil est destiné à tourner en permanence en arrière-plan. Son coût réel ne se mesure donc pas en charge, mais **au repos**, état dans lequel il passe la quasi-totalité de son temps.

| Composant | Au repos | En activité |
|---|---|---|
| `fidus-agent` | Bloqué sur `epoll`, 0 % de processeur, aucun réveil | Moins de 1 % en moyenne (NFR-1) |
| `fidus-shell-ext` | Réagit à un signal de changement de focus déjà émis par le Shell | Négligeable |
| `fidus-console` | **N'existe pas** : démarrée par activation de socket à la première consultation | Moins de 2 % (NFR-5) |
| `fidus-lab` | N'existe pas : exécuté à la demande, hors ligne | |

Conséquences de conception, à ne pas perdre de vue au fil des lots :

- **Aucune boucle de sondage, nulle part.** Un minuteur, même à faible fréquence, empêche le processeur de descendre dans ses états de veille profonds et se paie en autonomie sur un portable (INS-1, INS-4).
- **La maintenance est déclenchée par seuil d'événements**, jamais par horloge, avec un plafond d'une exécution toutes les 5 minutes (INS-3).
- **L'agent lit en parallèle du serveur d'affichage, il ne s'interpose pas.** Il ne peut donc ni bloquer ni ralentir la saisie, même en cas de plantage. Cette propriété est structurelle et doit être préservée par toute évolution.
- **L'extension GNOME Shell est facultative au démarrage** : sans elle, l'agent tourne en mode dégradé (perte de la famille de signaux C et de l'overlay, remplacé par une notification de bureau). L'installation ne doit jamais échouer faute d'extension (INS-25).

Autorisations, en totalité :

| Autorisation | Quand | Révocation |
|---|---|---|
| Appartenance au groupe `input` | Une fois, à l'installation | `sudo gpasswd -d $USER input` |

Aucune autre, à aucun moment : pas de root à l'exécution, pas de setuid, pas de capability, pas de module noyau, pas de service système, pas d'accès réseau, pas d'autorisation d'accessibilité. Voir [ADR-0006](adr/0006-moindre-privilege-installation.md).

## 8. Décisions d'architecture

| ADR | Sujet |
|---|---|
| [0001](adr/0001-langage-agent-rust.md) | Rust pour l'agent, Python pour le laboratoire hors ligne |
| [0002](adr/0002-licence-non-commerciale.md) | PolyForm Noncommercial plutôt qu'une licence OSI |
| [0003](adr/0003-evdev-et-extension-gnome.md) | evdev plus extension GNOME Shell sous Wayland |
| [0004](adr/0004-fusion-llr-sprt.md) | Fusion par LLR et décision séquentielle de Wald |
| [0005](adr/0005-digraphes-haches.md) | Digraphes hachés et salés comme compromis par défaut |
| [0006](adr/0006-moindre-privilege-installation.md) | Moindre privilège, installation sans root, exécution événementielle |
