# Klap

Site : https://klap.pages.dev — le cinéma le plus proche de toi, partout en France : séances qui suivent l'heure, notes presse et spectateurs d'AlloCiné, un conseil pour chaque film, une liste « À voir » et l'historique des films vus avec ta note.

## Comment ça marche

- `cinemas.json` : toutes les salles AlloCiné de France (≈ 2 400) avec leurs coordonnées. Reconstruit par `build_cinemas.py` (à relancer de temps en temps).
- `fetch_seances.py` : récupère les séances des 3 prochains jours pour toutes les salles et écrit un fichier par département dans `data/`.
- `publier.sh` : lance la récupération puis publie le site sur la branche `gh-pages` (une seule version gardée, pour que le dépôt reste léger).
- L'appli ne charge que les départements autour de ta position.
- « À voir » et « Déjà vus » restent sur ton téléphone (aucun compte, rien n'est envoyé).

Données : AlloCiné. Coordonnées et recherche de ville : Base Adresse Nationale. Projet personnel, sans lien avec AlloCiné.

## Mise à jour en continu

Un service macOS (`~/Library/LaunchAgents/fr.klap.maj.plist`) lance `./publier.sh --jours 7` toutes les 30 minutes ; s'il en tourne déjà une, il ne fait rien. Journal : `~/Library/Logs/klap-maj.log`.
Arrêter : `launchctl bootout gui/$(id -u)/fr.klap.maj` · Relancer : `launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/fr.klap.maj.plist`.
