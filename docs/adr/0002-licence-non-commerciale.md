# ADR-0002 - PolyForm Noncommercial plutôt qu'une licence OSI

- **Statut** : accepté
- **Date** : 2024-11

## Contexte

Je veux publier le projet en recherche ouverte, interdire l'exploitation commerciale par des tiers, et me réserver la possibilité d'en faire moi-même un usage commercial plus tard.

## Problème

« Open source » au sens de l'Open Source Initiative interdit toute restriction de champ d'usage (critère 6 de la définition). Une licence interdisant l'usage commercial **n'est pas open source**, quelle que soit la visibilité du code. Employer le terme serait inexact et exposerait le projet à un reproche fondé.

## Options

1. **MIT ou Apache-2.0** : vraiment open source, mais autorise l'exploitation commerciale par des tiers. Écarté, contraire à la demande.
2. **AGPL-3.0** : open source, contraint fortement les services en ligne, mais n'interdit pas le commerce. Écarté.
3. **CC BY-NC** : non conçue pour le logiciel, ambiguë sur les brevets et le code source. Écarté.
4. **BUSL-1.1** : restriction commerciale avec bascule automatique vers une licence libre à une date fixée. Solide, mais impose de choisir dès maintenant une date de bascule. Écarté pour cette raison.
5. **PolyForm Noncommercial 1.0.0** : rédigée par des juristes pour le logiciel, formulation claire, définition explicite des usages non commerciaux (recherche personnelle, enseignement, organismes publics), licence de brevet incluse, identifiant SPDX existant.

## Décision

Option 5 : **PolyForm Noncommercial 1.0.0**, avec un en-tête de droit d'auteur réservant explicitement les droits commerciaux.

Le dépôt emploie systématiquement « source-available » ou « recherche ouverte », **jamais « open source »**.

## Conséquences

- Le projet n'apparaîtra pas dans les annuaires d'outils open source, et certaines organisations l'écarteront de fait.
- Les contributions extérieures nécessiteront une licence entrante explicite pour que je conserve la liberté de relicencier. À traiter dans `CONTRIBUTING.md` au moment de la première contribution extérieure.
- Le passage ultérieur à une licence commerciale ou libre reste entièrement ouvert, puisque je détiens tous les droits.
