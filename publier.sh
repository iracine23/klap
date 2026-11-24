#!/bin/bash
# Met à jour les séances puis publie le site sur la branche gh-pages (une seule version gardée).
# Usage : ./publier.sh --auto      (aujourd'hui+demain puis publication, puis 7 jours puis publication : ce que lance le service)
#         ./publier.sh --jours 7   (7 jours puis publication)
#         ./publier.sh --sans-maj  (publie sans récupérer les séances)
set -euo pipefail
cd "$(dirname "$0")"
LOCK=/tmp/klap-publier.lock
if [ -e "$LOCK" ] && kill -0 "$(cat "$LOCK")" 2>/dev/null; then echo "Une mise à jour tourne déjà : rien à faire"; exit 0; fi
echo $$ > "$LOCK"; trap 'rm -f "$LOCK"' EXIT
git pull -q --rebase || true

publish(){
  n=$(ls data/*.json 2>/dev/null | wc -l | tr -d ' ')
  [ "$n" -gt 0 ] || { echo "Pas de données : rien publié"; return 1; }
  OUT=$(mktemp -d)
  # tout le site public, sans les scripts ni l'historique
  rsync -a --exclude '.git' --exclude '*.py' --exclude '*.sh' --exclude 'README.md' --exclude '__pycache__' --exclude '.gitignore' ./ "$OUT"/
  touch "$OUT/.nojekyll"
  ( cd "$OUT"
    git init -q -b gh-pages
    git -c user.name=Klap -c user.email=klap-bot@users.noreply.github.com add -A
    git -c user.name=Klap -c user.email=klap-bot@users.noreply.github.com commit -qm "Séances du $(date '+%d/%m/%Y %Hh%M')"
    git push -q -f https://github.com/iracine23/klap.git gh-pages )
  rm -rf "$OUT"
  echo "publié $(date '+%d/%m %Hh%M')"
}

case "${1:-}" in
  --sans-maj) publish ;;
  --auto)
    # 1) aujourd'hui et demain, vite, puis publication ; 2) les 7 jours, puis publication
    python3 fetch_seances.py --jours 2 --max-minutes 60 && publish
    python3 fetch_seances.py --jours 7 --max-minutes 200 && publish ;;
  *) python3 fetch_seances.py "$@" && publish ;;
esac
