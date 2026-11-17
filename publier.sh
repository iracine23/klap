#!/bin/bash
# Met à jour les séances puis publie le site sur la branche gh-pages (une seule version gardée).
# Usage : ./publier.sh --jours 7   (toute la France, 7 jours : la grosse mise à jour de la nuit)
#         ./publier.sh --jours 2   (aujourd'hui et demain : la mise à jour rapide)
#         ./publier.sh --sans-maj  (publie sans récupérer les séances)
set -euo pipefail
cd "$(dirname "$0")"
LOCK=/tmp/klap-publier.lock
if [ -e "$LOCK" ] && kill -0 "$(cat "$LOCK")" 2>/dev/null; then echo "Une mise à jour tourne déjà : rien à faire"; exit 0; fi
echo $$ > "$LOCK"; trap 'rm -f "$LOCK"' EXIT
git pull -q --rebase || true
if [ "${1:-}" != "--sans-maj" ]; then
  python3 fetch_seances.py "$@"
fi
n=$(ls data/*.json 2>/dev/null | wc -l | tr -d ' ')
[ "$n" -gt 0 ] || { echo "Pas de données : rien publié"; exit 1; }
OUT=$(mktemp -d)
cp index.html manifest.webmanifest icon.svg icon-180.png icon-512.png favicon-32.png cinemas.json "$OUT"/
cp -R data "$OUT"/data
touch "$OUT/.nojekyll"
EMAIL=$(git config user.email); NAME=$(git config user.name)
(
  cd "$OUT"
  git init -q -b gh-pages
  git -c user.name="$NAME" -c user.email="$EMAIL" add -A
  git -c user.name="$NAME" -c user.email="$EMAIL" commit -qm "Séances du $(date '+%d/%m/%Y %Hh%M')"
  git push -q -f https://github.com/iracine23/klap.git gh-pages
)
rm -rf "$OUT"
echo "publié"
