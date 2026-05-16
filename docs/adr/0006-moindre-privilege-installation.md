# ADR-0006 - Moindre privilège, installation sans root, exécution événementielle

- **Statut** : accepté
- **Date de la décision** : 2026-05

## Contexte

Trois exigences du besoin se tiennent : l'outil doit être aussi **léger** que possible, tourner **en arrière-plan** en permanence sans qu'on y pense, et **ne pas réclamer de privilèges**. Un outil qui exige root, qui installe un service système ou qui consomme en continu ne sera pas gardé, quelles que soient ses performances de détection.

Or la fonction même du projet demande de lire toutes les entrées de la session, ce qui est un privilège fort. Les deux exigences se heurtent frontalement.

## Options pour la capture

1. **Démon root** : simple, fonctionne partout, mais réclame le privilège le plus élevé en permanence. Écarté.
2. **Binaire setuid ou `CAP_DAC_OVERRIDE`** : privilège permanent attaché à un exécutable, surface d'attaque durable. Écarté.
3. **Règle `udev` dédiée plus groupe applicatif** : évite d'ajouter l'utilisateur au groupe `input` global, mais exige de déposer un fichier dans `/etc/udev/rules.d`, donc de modifier le système (contraire à INS-27), et le gain de confinement est illusoire puisque le groupe créé aurait exactement les mêmes droits.
4. **Appartenance de l'utilisateur au groupe `input`** : une seule opération privilégiée, à l'installation, réversible en une commande, aucun privilège à l'exécution.

## Décision

Option 4, assortie de quatre contreparties non négociables :

1. **Aucun privilège à l'exécution** : pas de root, pas de setuid, pas de capability, pas de module noyau, pas de service système. Uniquement `systemd --user`.
2. **Isolement réseau structurel** : `PrivateNetwork=yes` sur le processus de capture. Il n'a pas d'accès réseau à donner, même compromis.
3. **Confinement en écriture** : `ProtectSystem=strict`, accès en écriture limité au répertoire de données.
4. **Réversibilité en une commande**, proposée à la désinstallation.

Pour l'exécution, la décision est un agent **piloté par les événements** : bloqué sur `epoll`, il ne consomme rien en l'absence d'entrée. Aucune boucle de sondage, aucun minuteur périodique hors maintenance plafonnée. La console est démarrée par activation de socket et n'existe pas tant qu'on ne la consulte pas.

## Justification

Le coût réel d'un outil résident ne se mesure pas à sa consommation en charge, mais à sa consommation **au repos**, car c'est l'état dans lequel il passe la quasi-totalité de son temps. Un agent événementiel y est strictement à zéro. Un agent à sondage, même à faible fréquence, empêche le processeur de descendre dans ses états de veille profonds et se paie en autonomie sur un portable.

## Conséquences

- L'appartenance au groupe `input` devient un prérequis vérifié par `fidus-cli doctor`, et énoncé avant installation.
- **Cette autorisation est un privilège fort, et le projet ne le présente jamais comme anodin.** Elle permet de lire toutes les entrées de la session. C'est la raison pour laquelle les sources sont publiées, la construction reproductible, et l'isolement réseau structurel plutôt que promis.
- L'extension GNOME Shell devient **facultative** : sans elle, l'agent fonctionne, en perdant la famille de signaux C et l'overlay. L'installation ne doit jamais échouer faute d'extension.
- Le portage Windows et macOS devra rouvrir cette décision : macOS impose une autorisation d'accessibilité accordée par l'utilisateur, plus visible mais aussi plus large.
- La maintenance déclenchée par seuil d'événements, et non par horloge, complique légèrement l'implémentation. C'est le prix de INS-1 et INS-2.
