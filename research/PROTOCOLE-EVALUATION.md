# Protocole d'évaluation

Référence unique pour toute mesure que je publierai. Un chiffre annoncé sans
référence à ce protocole ne vaut rien.

## Métriques

Classiques : FAR, FRR, EER, courbe DET. Elles servent à comparer avec la
littérature, pas à régler le système.

**Toujours préciser l'unité de décision.** Un EER par fenêtre de 60 secondes et
un EER après accumulation ne sont pas comparables. Confondre les deux est la
principale source de chiffres flatteurs et faux dans ce domaine.

Propres à l'authentification continue, et ce sont celles qui comptent vraiment :

- **ANIA** : nombre moyen d'actions d'un imposteur avant détection. Mesure le
  coût réel d'une intrusion.
- **ANGA** : nombre moyen d'actions légitimes avant fausse alarme. Mesure la
  gêne réelle.
- **TTD** : temps jusqu'à détection, médiane et 95e centile.
- Taux de fausse alarme par tranche de 8 heures d'usage normal.

Calibration : erreur de calibration attendue sous 0,05, diagramme de fiabilité
publié pour chaque expert. Comme la console **affiche** une probabilité, une
calibration approximative rendrait l'affichage mensonger.

Ressources : processeur, mémoire, stockage, latence. À publier avec tout
résultat de performance. Un gain obtenu en dépassant les budgets n'est pas un
gain.

## Jeux de données

Corpus publics, pour la comparaison : CMU pour la frappe en texte imposé,
Clarkson II et Buffalo pour le texte libre, Balabit pour le pointeur. Je ne les
redistribue pas, je fournis des scripts d'ingestion.

Collecte propre :

- usage légitime long, un seul utilisateur, pour le taux de fausse alarme ;
- sessions annotées à deux ou trois personnes, pour le comptage de profils ;
- imposteur non informé, puis imposteur ayant observé ;
- même personne sur des périphériques et contextes différents, pour valider la
  distinction entre mode et identité ;
- banc d'attaque scripté pour le canal Humanité.

Toute trace impliquant quelqu'un d'autre que moi exige son accord écrit
préalable.

## Règles

1. **Validation croisée temporelle uniquement.** Entraînement sur les k
   premières sessions, test sur la suivante. Une validation croisée aléatoire
   mélangerait passé et futur et donnerait des chiffres faux et flatteurs.
2. Aucune fuite de la population imposteur entre entraînement et test.
3. **Intervalles de confiance obligatoires**, par bootstrap sur les sujets et
   non sur les fenêtres : les fenêtres d'un même sujet ne sont pas
   indépendantes. Un EER sans intervalle de confiance est à rejeter.
4. Toute mesure doit être reproductible par rejeu d'une trace figée, à graine
   fixée, au bit près.
5. La configuration exacte accompagne tout résultat.
6. **Publier les échecs** : signaux non discriminants, attaques non détectées,
   régressions. Un catalogue qui ne contiendrait que des réussites serait un
   catalogue biaisé.
7. Pas de réglage sur le jeu de test.

## Format

Une campagne produit un répertoire daté contenant la configuration, les
métadonnées de la trace, les métriques avec intervalles, les courbes, le
pouvoir discriminant mesuré par signal, la consommation observée, et un compte
rendu.

Ce compte rendu doit comporter une section **Limites** non vide. Une campagne
sans limites identifiées signale une analyse incomplète, pas un résultat
parfait.
