#!/usr/bin/env bash
# Wrapper do `openspec archive` que mantém a convenção do repositório.
#
# O CLI @fission-ai/openspec arquiva em openspec/changes/archive/ (hardcoded,
# sem opção de configuração), caminho que está no .gitignore. A convenção
# versionada deste repositório é openspec/archive/<change-name>/ — ver
# docs/adr/ADR-0005-local-de-archive-openspec.md.
#
# Uso: scripts/openspec-archive.sh <change-name> [opções do openspec archive]
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

if [ $# -lt 1 ]; then
  echo "Uso: $0 <change-name> [opções do openspec archive]" >&2
  echo "Exemplo: $0 meu-change --skip-specs" >&2
  exit 1
fi

change_name="$1"
shift

change_dir="openspec/changes/$change_name"
cli_archive_dir="openspec/changes/archive"
repo_archive_dir="openspec/archive"
dest="$repo_archive_dir/$change_name"

if [ ! -d "$change_dir" ]; then
  echo "ERRO: change '$change_name' não existe em $change_dir" >&2
  echo "Changes disponíveis:" >&2
  find openspec/changes -mindepth 1 -maxdepth 1 -type d ! -name archive \
    -printf '  - %f\n' >&2 || true
  exit 1
fi

if [ -e "$dest" ]; then
  echo "ERRO: destino '$dest' já existe; remova-o ou escolha outro nome." >&2
  exit 1
fi

echo "==> openspec archive $change_name $*"
openspec archive "$change_name" "$@"

# O CLI cria openspec/changes/archive/YYYY-MM-DD-<change-name>/ (prefixo de
# data hardcoded). Localiza o diretório criado para este change.
src="$(find "$cli_archive_dir" -mindepth 1 -maxdepth 1 -type d \
  -name "*-$change_name" 2>/dev/null | sort | tail -1 || true)"

if [ -z "$src" ]; then
  echo "ERRO: archive criado pelo CLI não foi encontrado em $cli_archive_dir." >&2
  echo "Verifique a saída acima e conclua o move manualmente conforme a ADR-0005." >&2
  exit 1
fi

mv "$src" "$dest"
echo "OK: '$change_name' arquivado em $dest (convenção ADR-0005)."
echo "Lembre de commitar: git add openspec/ && git commit"
