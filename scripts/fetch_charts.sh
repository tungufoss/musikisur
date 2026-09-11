#!/usr/bin/env bash
# Fetch only the two Billboard chart files from the pinned utdata/rwd-billboard-data submodule
# (sparse, blob-less, one commit) instead of the whole ~540 MB repository.
#
#   bash scripts/fetch_charts.sh
#
# Used by the GitHub workflows; locally it also works after a plain clone of this repo.
set -euo pipefail

path=vendor/rwd-billboard-data
url=$(git config -f .gitmodules "submodule.$path.url")
sha=$(git ls-tree HEAD "$path" | awk '{print $3}')

mkdir -p "$path"
cd "$path"
if [ ! -d .git ]; then
  git init -q
  git remote add origin "$url"
fi
git sparse-checkout set --no-cone data-out/hot-100-current.csv data-out/billboard-200-current.csv
git fetch -q --depth 1 --filter=blob:none origin "$sha"
git checkout -q FETCH_HEAD
ls -l data-out
