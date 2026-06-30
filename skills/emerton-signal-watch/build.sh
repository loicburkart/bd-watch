#!/usr/bin/env bash
#
# Refresh the bundled engine from the live repo, then (re)zip the .skill file.
#
# The skill bundles a MINIMAL copy of the bd_watch package (steps 01-02 only) plus
# the targeting matrix and scraper config, so it runs self-contained inside Cowork.
# Re-run this after the package, matrix or config change on main.
#
# Output: skills/emerton-signal-watch.skill  (zip, folder at its root)

set -euo pipefail

SK="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"          # skills/emerton-signal-watch
REPO="$(cd "${SK}/../.." && pwd)"                           # repo root
SRC="${REPO}/src/bd_watch"

echo "→ Refreshing minimal bd_watch package (steps 01-02) from src/"
rm -rf "${SK}/scripts/bd_watch"
mkdir -p "${SK}/scripts/bd_watch/steps" "${SK}/scripts/bd_watch/scrapers"

cp "${SRC}/__init__.py"            "${SK}/scripts/bd_watch/__init__.py"
cp "${SRC}/config.py"              "${SK}/scripts/bd_watch/config.py"
cp "${SRC}/schemas.py"             "${SK}/scripts/bd_watch/schemas.py"
cp "${SRC}/steps/__init__.py"      "${SK}/scripts/bd_watch/steps/__init__.py"
cp "${SRC}/steps/step01_watch.py"  "${SK}/scripts/bd_watch/steps/step01_watch.py"
cp "${SRC}/steps/step02_qualify.py" "${SK}/scripts/bd_watch/steps/step02_qualify.py"
cp "${SRC}/scrapers/__init__.py"   "${SK}/scripts/bd_watch/scrapers/__init__.py"
cp "${SRC}/scrapers/rss.py"        "${SK}/scripts/bd_watch/scrapers/rss.py"
cp "${SRC}/scrapers/press.py"      "${SK}/scripts/bd_watch/scrapers/press.py"

echo "→ Refreshing config at skill root (resolved via package parents[3])"
cp "${REPO}/targeting_matrix.json"                     "${SK}/targeting_matrix.json"
cp "${REPO}/triggers_module/targeting_config.yaml"     "${SK}/triggers_module/targeting_config.yaml"

echo "→ Zipping emerton-signal-watch.skill"
( cd "${REPO}/skills" \
  && rm -f emerton-signal-watch.skill \
  && zip -q -r emerton-signal-watch.skill emerton-signal-watch \
       -x '*/__pycache__/*' '*.pyc' )

echo ""
echo "✓ Built ${REPO}/skills/emerton-signal-watch.skill"
echo "  Import via Cowork: Customize → Skills → \"+\" → upload the .skill file."
