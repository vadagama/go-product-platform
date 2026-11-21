#!/bin/sh
set -eu
cd "$(dirname "$0")"
printf '\nGo Product Platform v15 — запуск мастера настройки\n\n'
if command -v osascript >/dev/null 2>&1; then
  PROJECT=$(osascript -e 'POSIX path of (choose folder with prompt "Выберите Git-проект для Go Product Platform")')
else
  printf 'Путь к корню Git-проекта: '
  IFS= read -r PROJECT
fi
if [ -z "$PROJECT" ]; then
  echo 'Не указан путь. Операция отменена.'
  printf 'Нажмите Enter...'
  read -r _
  exit 1
fi
python3 installer/gpp.py install-cli
"${HOME}/.local/bin/gpp" wizard --project "$PROJECT"
printf '\nГотово. Нажмите Enter для закрытия окна...'
read -r _
