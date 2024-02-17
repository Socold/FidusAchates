# 02 - Architecture technique

> Découle de [00-ANALYSE.md](00-ANALYSE.md) et de le cahier des charges (a ecrire).

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
