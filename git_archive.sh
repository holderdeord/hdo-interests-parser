#!/usr/bin/env bash
set -e

if ! [ -z "$(git status --porcelain)" ]; then
    git config --global user.email "$GH_EMAIL" > /dev/null 2>&1
    git config --global user.name "$GH_NAME" > /dev/null 2>&1
    git add data pdfs
    git commit -m '🗃 Archive new PDF and parsed data [skip ci]'
    git push --quiet origin master
fi