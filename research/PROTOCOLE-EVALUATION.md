# Protocole d'évaluation

> Référence unique pour toute mesure publiée. Un chiffre annoncé sans référence à ce protocole n'est pas recevable.

---

## 1. Métriques

### 1.1 Métriques classiques (ISO/IEC 19795)

| Métrique | Définition |
|---|---|
| **FAR** | Taux d'acceptation à tort : proportion de fenêtres d'imposteur classées légitimes |
| **FRR** | Taux de rejet à tort : proportion de fenêtres légitimes classées imposteur |
| **EER** | Point où FAR égale FRR. Sert à comparer, jamais à régler le système en exploitation |
| **Courbe DET** | FRR en fonction de FAR, échelle de déviation normale |

**Toujours préciser l'unité de décision** : une fenêtre de 60 s d'activité, ou une décision cumulée. Un EER par fenêtre et un EER après accumulation ne sont pas comparables, et confondre les deux est la principale source de chiffres flatteurs et faux dans la littérature.

### 1.2 Métriques propres à l'authentification continue

| Métrique | Définition | Pourquoi |
|---|---|---|
| **ANIA** | Nombre moyen d'actions d'un imposteur avant détection | Mesure le coût réel d'une intrusion |
| **ANGA** | Nombre moyen d'actions légitimes avant fausse alarme | Mesure la gêne réelle pour l'utilisateur |
| **TTD** | Temps jusqu'à détection : médiane, 95e centile | Répond à « très rapidement » |
| **Taux de fausse alarme quotidien** | Nombre d'alertes L3 ou plus par 8 h d'usage légitime | Métrique d'acceptabilité |

ANIA et ANGA sont les métriques **primaires** du projet. FAR, FRR et EER sont des métriques secondaires, conservées pour permettre la comparaison avec l'état de l'art.

### 1.3 Métriques de calibration

| Métrique | Seuil |
|---|---|
| Erreur de calibration attendue (ECE) | < 0,05 |
| Diagramme de fiabilité | Publié pour chaque expert |

Un système non calibré peut avoir un excellent EER et des probabilités affichées dénuées de sens. Comme la console **affiche** une probabilité à l'utilisateur, la calibration est une exigence de premier rang, pas un raffinement.

### 1.4 Métriques de regroupement

| Métrique | Définition |
|---|---|
| Exactitude du nombre de profils | Écart entre le nombre estimé et la vérité terrain, en fonction du temps |
| Indice de Rand ajusté | Qualité de l'affectation des fenêtres aux profils |
| Délai de convergence | Temps avant stabilisation du nombre de profils |
| Nombre de révisions | Fusions et scissions avant stabilisation |

### 1.5 Métriques de ressources

CPU moyen et 95e centile, mémoire résidente, croissance du stockage par jour, latence de décision au 95e centile. Mesurées en continu, publiées avec tout résultat de performance : **un gain de performance obtenu en dépassant les budgets NFR n'est pas un gain.**

## 2. Jeux de données

### 2.1 Corpus publics (comparaison avec l'état de l'art)

| Corpus | Modalité | Usage |
|---|---|---|
| CMU Keystroke Dynamics (Killourhy et Maxion) | Frappe, texte imposé | Étalon de référence, repère EER ≈ 0,096 pour la distance de Manhattan mise à l'échelle |
| Clarkson II, Buffalo | Frappe, texte libre | Plus proche du cas réel |
| Balabit Mouse Dynamics Challenge | Pointeur | Repère, état de l'art 2025-2026 à EER ≈ 2,87 % |
| SapiMouse | Pointeur | Second repère, EER ≈ 3,14 % |
| HMOG, Touchalytics | Tactile et inertiel | Lot 9 |

Les corpus ne sont pas redistribués dans le dépôt : `fidus-lab` fournit des scripts d'ingestion et les conditions d'accès.

### 2.2 Collecte propre

| Trace | Contenu | Usage |
|---|---|---|
| `legit-long` | 30 jours d'usage légitime normal, un seul utilisateur | Étalonnage, taux de fausse alarme |
| `multi-user` | Sessions contrôlées et annotées, 2 à 3 personnes consentantes | Validation du comptage de profils |
| `impostor-naive` | Tiers consentant utilisant le poste sans instruction | Menace M6 |
| `impostor-trained` | Tiers consentant ayant observé l'utilisateur et tentant de l'imiter | Menace M7 |
| `modes` | Même personne, périphériques et contextes différents | Validation de la distinction mode / identité |
| `attack-bench` | Sept scénarios d'attaque scriptés (voir lot 5) | Canal Humanité |

Toute trace impliquant un tiers exige son consentement écrit préalable, conformément à [docs/05-PRIVACY.md](../docs/05-PRIVACY.md) section 4.3.

## 3. Règles méthodologiques

1. **Validation croisée temporelle exclusivement.** L'entraînement se fait sur les `k` premières sessions, le test sur la suivante. Une validation croisée aléatoire mélangerait passé et futur et produirait des chiffres optimistes et faux.
2. **Aucune fuite de la population imposteur.** Les profils servant de référence imposteur pendant l'entraînement ne sont jamais ceux du test.
3. **Intervalles de confiance obligatoires.** Bootstrap à 95 %, sur les sujets et non sur les fenêtres (les fenêtres d'un même sujet ne sont pas indépendantes). **Un EER annoncé sans intervalle de confiance est rejeté.**
4. **Reproductibilité.** Toute mesure est produite par rejeu d'une trace figée, avec une graine fixée, et deux exécutions doivent donner un résultat identique bit à bit.
5. **Configuration versionnée.** Le fichier de paramètres utilisé accompagne tout résultat publié.
6. **Publication des échecs.** Les signaux mesurés comme non discriminants, les scénarios d'attaque non détectés et les régressions sont publiés au même titre que les succès. Un catalogue qui ne contiendrait que des réussites serait un catalogue biaisé.
7. **Pas de réglage sur le jeu de test.** Les paramètres sont réglés sur un jeu de développement distinct.

## 4. Format des résultats

Chaque campagne produit dans `research/results/AAAA-MM-JJ-<nom>/` :

```
config.toml          paramètres exacts utilisés
trace.meta.json      identifiant de la trace, volume, période, annotation
metrics.json         toutes les métriques, avec intervalles de confiance
det.svg  roc.svg     courbes
per-signal.csv       pouvoir discriminant mesuré de chaque signal
resources.json       consommation observée pendant la campagne
README.md            conditions, écarts au protocole, limites, conclusions
```

Le `README.md` de campagne doit comporter une section **Limites** non vide. Une campagne sans limites identifiées signale une analyse incomplète, pas un résultat parfait.

## 5. Cibles v1

Rappel des critères d'acceptation globaux du [cahier des charges](../docs/01-CAHIER-DES-CHARGES.md) section 9 :

| ID | Cible |
|---|---|
| AC-1 | EER sous 5 % sur fenêtre de 60 s, imposteur humain non informé |
| AC-2 | TTD médian sous 90 s pour un imposteur humain |
| AC-3 | TTD sous 10 s pour une entrée automatisée, sans enrôlement |
| AC-4 | Moins d'une fausse alarme par 8 h d'usage légitime |
| AC-5 | Comptage exact des utilisateurs après 5 jours, sur trace contrôlée |
| AC-6 | Budgets de ressources respectés 100 % du temps sur 7 jours |

Ces cibles sont des **hypothèses de travail** issues de l'état de l'art. Elles seront révisées après le lot 3 avec les mesures réelles, et toute révision sera justifiée, datée et conservée.
