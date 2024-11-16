# ADR-0001 - Rust pour l'agent, Python pour le laboratoire hors ligne

- **Statut** : accepté
- **Date** : 2024-11

## Contexte

L'exigence dominante est NFR-1 à NFR-4 : moins de 1 % de CPU, moins de 40 Mo de mémoire résidente, latence sous 250 ms, pour un processus qui s'exécute en permanence et traite chaque événement d'entrée. En parallèle, la recherche sur les modèles demande une boucle d'itération rapide, ce que Rust ne donne pas.

## Options

1. **Tout en Python** : itération rapide, écosystème scientifique complet, mais empreinte mémoire d'un interpréteur plus NumPy incompatible avec NFR-2, et latence imprévisible liée au ramasse-miettes.
2. **Tout en Rust** : conforme aux NFR, mais expérimentation sur les modèles lente et pénible.
3. **Tout en Go** : bon compromis, mais ramasse-miettes et empreinte supérieure à Rust, et accès `evdev` moins direct.
4. **Rust pour l'agent, Python pour le laboratoire hors ligne.**

## Décision

Option 4.

L'agent (`fidus-agent`) est écrit en Rust : binaire unique, pas de ramasse-miettes, empreinte prévisible, accès `evdev` direct, durcissement `systemd` simple.

Le laboratoire (`fidus-lab`) est écrit en Python et **ne s'exécute jamais en continu**. Il travaille sur des traces figées exportées par l'agent. La frontière entre les deux est le **format de trace**, documenté et versionné (FR-70).

## Conséquences

- Un modèle validé dans `fidus-lab` doit être **porté** dans l'agent, ce qui est un coût réel et récurrent.
- Ce coût est accepté, et il est atténué par l'exigence de rejeu déterministe (FR-71) : le portage se vérifie en comparant la sortie de l'agent et celle du laboratoire sur la même trace. Toute divergence est un défaut.
- Rust n'est pas installé sur le poste de test. C'est un prérequis du lot 1.
