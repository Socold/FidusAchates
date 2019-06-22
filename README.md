# FidusAchates

Notes de travail sur une question simple : **l'appareil peut-il savoir que la
personne qui l'utilise n'est plus celle qui s'est connectée ?**

L'authentification actuelle est ponctuelle. On prouve son identité une fois, à
l'ouverture de session, puis plus jamais. Tout ce qui se passe ensuite est
attribué à cette identité, qu'elle soit encore présente ou non.

L'idée est d'apprendre la manière dont une personne se sert de la machine
(rythme de frappe, gestuelle du pointeur, habitudes), puis de vérifier en
permanence que c'est toujours elle.

Contraintes que je me donne dès le départ :

- ne jamais enregistrer ce qui est tapé ;
- tout traiter localement, aucune donnée ne sort de la machine ;
- rester assez léger pour tourner en permanence sans qu'on le remarque ;
- pouvoir expliquer pourquoi le système conclut ce qu'il conclut.

Projet personnel, à but d'étude. Rien de publiable pour l'instant.

## Notes

- [Idée et périmètre](docs/notes/idee.md)
- [Dynamique de frappe](docs/notes/frappe.md)
- [Dynamique du pointeur](docs/notes/souris.md)
- [Modèle de menace](docs/notes/menaces.md)
- [Catalogue de signaux](docs/notes/signaux.md)
- [Combien de personnes utilisent la machine](docs/notes/profils.md)
