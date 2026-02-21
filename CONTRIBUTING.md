# Contribuer à FidusAchates

Projet de recherche, **source-available, usage commercial interdit** (voir [LICENSE](LICENSE) et [ADR-0002](docs/adr/0002-licence-non-commerciale.md)).

## Avant de proposer quoi que ce soit

Lire [docs/05-PRIVACY.md](docs/05-PRIVACY.md). Toute contribution doit répondre oui aux quatre questions de sa section 9 :

1. La donnée collectée figure-t-elle dans le registre de traitement ?
2. Le signal ajouté est-il calculable sans connaître le contenu ?
3. La finalité reste-t-elle « est-ce la même personne, est-ce un humain » ?
4. Un utilisateur qui lirait le code se sentirait-il trahi ?

## Refusé par principe

Ces contributions sont refusées quelle que soit leur qualité technique :

- Capture de contenu, de titres de fenêtre, d'URL, de noms de fichiers, du presse-papiers.
- Toute sortie réseau depuis l'agent, sous quelque forme que ce soit.
- Fonction permettant de dissimuler l'exécution de l'agent.
- Action coercitive sur le poste (verrouillage, blocage, déconnexion).
- Métrique de productivité, de présence ou d'assiduité.
- Passage du niveau de granularité P2 en configuration par défaut.

## Ajouter un signal

1. L'inscrire dans [docs/04-CATALOGUE-SIGNAUX.md](docs/04-CATALOGUE-SIGNAUX.md) avec son coût, son pouvoir discriminant attendu et sa difficulté de falsification.
2. Vérifier qu'il n'exige aucune donnée absente du registre de [docs/05-PRIVACY.md](docs/05-PRIVACY.md) section 3. Si une donnée manque, elle doit être ajoutée au registre **dans le même commit**.
3. Implémenter le trait `Expert` ou `Extractor` : le moteur de fusion n'est pas modifié.
4. Fournir une mesure de qualité (FR-11).
5. Fournir un test unitaire avec vecteur de référence.
6. Mesurer son pouvoir discriminant réel selon [research/PROTOCOLE-EVALUATION.md](research/PROTOCOLE-EVALUATION.md). **Un signal dont le pouvoir discriminant mesuré est nul est retiré, pas conservé par confort.**

## Commits

- Messages en français, impératif, préfixés par le lot : `lot1: ajoute la lecture evdev sans privilège`.
- Aucun secret, clé ou jeton dans le dépôt.
- Les tests de vie privée sont bloquants : ne jamais les contourner ni les marquer comme ignorés.

## Licence des contributions

Le projet réservant les droits commerciaux à son auteur, toute contribution extérieure nécessitera une licence entrante explicite. Ouvrir une discussion **avant** de soumettre un travail conséquent.
