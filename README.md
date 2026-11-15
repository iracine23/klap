# Klap

Le cinéma le plus proche de toi, ses séances qui suivent l'heure, les notes presse et spectateurs d'AlloCiné et un conseil pour chaque film.

- **Position** : le site demande ta localisation ; tu peux aussi choisir une ville ou un cinéma (bouton en haut).
- **Mise à jour** : une GitHub Action relance `fetch_seances.py` trois fois par jour et met à jour `seances.json`.
- **Ajouter un cinéma** : ajoute son identifiant AlloCiné (le `P0091` de `salle_gen_csalle=P0091.html`) dans `CINEMAS`, en haut de `fetch_seances.py`, puis la ville dans `CITIES`, dans `index.html`.

Données : AlloCiné. Projet personnel, sans lien avec AlloCiné.
