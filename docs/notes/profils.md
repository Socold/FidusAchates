# Combien de personnes utilisent la machine ?

Question distincte de la vérification d'identité, et beaucoup moins traitée
dans la littérature : les travaux sur l'authentification supposent l'identité
connue et se contentent de la vérifier.

Ici, ni étiquettes, ni nombre de classes connu. C'est du partitionnement pur.

## Approche envisagée

Chaque fenêtre d'activité donne un vecteur de signaux. On regroupe ces vecteurs
sans fixer le nombre de groupes à l'avance : mélange à processus de Dirichlet,
ou mélange gaussien bayésien avec troncature large, recalculé périodiquement.

## Ce qui compte plus que l'algorithme : la révision

Le système doit pouvoir se corriger. Typiquement : croire à trois personnes au
bout de trois jours, puis comprendre au bout de dix qu'il n'y en avait que
deux. À intervalle régulier, tester chaque paire de groupes et fusionner quand
ils deviennent indistinguables.

Chaque révision doit être conservée avec sa justification chiffrée. Un système
qui change d'avis sans dire pourquoi est inexploitable.

## Le piège

Une même personne produit plusieurs régimes de comportement : clavier du
portable contre clavier externe, souris contre pavé tactile, matin contre fin
de soirée, reposée contre fatiguée. Si on ne distingue pas le **régime** de la
**personne**, on comptera systématiquement trop d'utilisateurs.

Il faut donc un modèle à deux étages : identité, puis modes de cette identité.

## Le critère qui devrait trancher

Deux régimes qui **alternent au sein d'une même session** sont deux modes d'une
même personne : on ne se relaie pas toutes les trois minutes.

Deux régimes qui occupent des plages **disjointes** et ne coexistent jamais
sont candidats à être deux personnes.

L'entrelacement temporel est donc le discriminant principal, plus fiable que la
distance entre gabarits.

## Restitution

Le nombre de personnes ne doit jamais être affiché comme un entier certain. Un
mélange bayésien donne naturellement une distribution a posteriori : autant
afficher « 2 profils, intervalle crédible 2 à 3 ».

## Modèle hiérarchique

Après deux ans à tourner autour, je formalise. Deux étages :

    Identité (la personne)
      └── Mode (régime contextuel : clavier externe, pavé tactile, session tardive)
            └── Gabarit du mode

Un régime nouveau mais **entrelacé** avec un régime connu, c'est-à-dire
alternant avec lui au sein d'une même session, est un mode de la même
identité. Un régime qui occupe des plages disjointes et ne coexiste jamais
avec l'autre est candidat à être une identité distincte.

L'entrelacement temporel est donc le discriminant principal, et il est plus
fiable que la seule distance entre gabarits : deux modes d'une même personne
peuvent être très éloignés l'un de l'autre.

## Révision, en pratique

À intervalle régulier, tester chaque paire de profils.

Fusionner si la distance entre gabarits passe sous un seuil, **et** que le
rapport de vraisemblance favorise le modèle à une seule composante, **et** que
les occurrences sont entrelacées. Les trois conditions, pas une seule.

Scinder si un profil devient nettement bimodal sur plusieurs signaux
indépendants **et** que les deux sous-ensembles sont temporellement disjoints.

Chaque révision laisse une trace permanente avec sa raison chiffrée. Un
système qui change d'avis sans dire pourquoi est inexploitable.
