# ADR-0001 — Reconstruction depuis zéro, dans un paquet indépendant

**Statut** : accepté — phase 0
**Date** : 2026-08-22

## Contexte

Le dépôt contient l'ancien système PDZ (~25 000 lignes sous `pdz/`), avec son
point d'entrée `pdz`, ses workflows GitHub Actions et ses tests. Le cahier des
charges PDZ 2 demande une reconstruction *from zero* : l'ancien code n'est ni
une base à migrer, ni une architecture à reproduire.

## Décision

PDZ 2 est écrit dans un **nouveau paquet `pdz2/`**, indépendant.

* Aucun module de `pdz2/` n'importe quoi que ce soit de `pdz/`.
* L'ancien système n'est pas supprimé : il continue de tourner, ses workflows
  restent intacts, et son historique reste consultable. Le supprimer serait une
  destruction que le cahier des charges ne demande pas — il demande de ne pas
  s'en servir comme base, ce qui est une autre chose.
* Le nom `pdz2` est un nom de transition. Quand l'ancien système sera retiré,
  `pdz2` pourra être renommé `pdz` : c'est un renommage de paquet et un
  changement de `[project.scripts]`, sans fusion de code.

## Conséquences

* La commande cible du cahier des charges s'écrit aujourd'hui
  `pdz2 create --topic "..." --duration 45 --format 9:16`. Elle refuse
  explicitement de produire tant que les phases 1 à 12 ne sont pas faites.
* Deux paquets Python cohabitent dans le même dépôt et la même distribution.
  Coût accepté : la seule alternative était de casser l'ancien système avant
  que le nouveau ne sache produire quoi que ce soit.
* Les enseignements de l'ancien système (fenêtre de mouvement réellement
  conservée au montage, dégradation silencieuse d'un fournisseur, timing
  théorique vs timing mesuré) sont réinterprétés dans les contrats de PDZ 2,
  jamais recopiés depuis son code.
