# Catalogue de signaux

Premier inventaire. Colonnes : coût de calcul, pouvoir discriminant attendu
(hypothèse, à mesurer), difficulté de falsification de 1 (facile) à 4.

## Clavier

| ID | Signal | Coût | Disc. | Falsif. |
|---|---|---|---|---|
| A01 | Temps de maintien par classe de touche | F | Élevé | 2 |
| A02 | Temps de vol | F | Élevé | 2 |
| A03 | Latence appui / appui | F | Élevé | 2 |
| A04 | Latence relâchement / relâchement | F | Moyen | 2 |
| A05 | Statistiques par digraphe | M | Très élevé | 3 |
| A06 | Statistiques par trigraphe | M | Très élevé | 3 |
| A07 | Chevauchement de touches (vol négatif) | F | Très élevé | 4 |
| A08 | Vitesse de frappe | F | Moyen | 1 |
| A09 | Structure des rafales et des pauses | M | Élevé | 3 |
| A10 | Taux de correction | F | Élevé | 3 |
| A11 | Profondeur de correction | F | Élevé | 3 |
| A12 | Latence avant correction | M | Élevé | 4 |
| A13 | Préférence Maj gauche ou droite | F | Très élevé | 4 |
| A15 | Usage des modificateurs | F | Moyen | 2 |
| A16 | Répertoire de raccourcis employés | F | Élevé | 3 |
| A17 | Part des actions faites au clavier plutôt qu'à la souris | F | Élevé | 3 |
| A19 | Pavé numérique contre rangée de chiffres | F | Élevé | 3 |
| A23 | Asymétrie entre les deux moitiés du clavier | F | Élevé | 4 |

## Pointeur

| ID | Signal | Coût | Disc. | Falsif. |
|---|---|---|---|---|
| B01 | Vitesse par direction | F | Élevé | 2 |
| B02 | Profil d'accélération | M | Élevé | 3 |
| B03 | À-coup | M | Élevé | 4 |
| B04 | Courbure de trajectoire | M | Élevé | 3 |
| B05 | Rectitude | F | Élevé | 3 |
| B06 | Loi de Fitts : couple (a, b) | M | Très élevé | 4 |
| B07 | Dépassement de cible | M | Très élevé | 4 |
| B08 | Micro-corrections finales | M | Très élevé | 4 |
| B09 | Pause avant clic | F | Élevé | 3 |
| B10 | Durée du clic | F | Élevé | 3 |
| B11 | Intervalle de double-clic | F | Très élevé | 4 |
| B13 | Molette : amplitude, cadence, inversions | F | Élevé | 3 |
| B16 | Dérive du curseur au repos (tremblement) | M | Très élevé | 4 |

## Règles

1. Aucun signal ne doit dépendre du contenu.
2. Chaque signal doit porter une mesure de qualité : avec trop peu
   d'observations, il ne doit pas voter du tout, et surtout pas voter neutre.
3. Les colonnes « Disc. » sont des hypothèses. Il faudra les mesurer et retirer
   ce qui ne discrimine pas, plutôt que de le garder par confort.
