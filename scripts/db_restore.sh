#!/usr/bin/env bash

set -euo pipefail

repo_root="$(cd "$(dirname "$0")/.." && pwd)"

usage() {
  cat <<'EOF'
Usage: db_restore.sh -i FILE [--merge] [--force]

Pipe a gzip-compressed mongodump archive (from db_dump.sh) into the
running mongodb container via mongorestore.

Options:
  -i FILE    Archive to restore (required).
  --merge    Merge into existing data instead of dropping the target
             collections first.  Default behaviour drops each
             collection before restoring it.
  --force    Skip the confirmation prompt.
  -h         Show this help.

Authentication and TLS settings are read from .env at the repo root
(MC_MONGO_PASSWORD, MC_MONGO_TLS_ENABLED, and
MC_MONGO_TLS_CLIENT_PEM for mTLS).

The destructive default (--drop) is the right one for the "switch
MongoDB engines" workflow described in db_dump.sh -h: after that
workflow's `docker volume rm` step the destination is empty and there
is nothing to merge with.

Example:
  scripts/db_restore.sh -i /tmp/snapshot.archive.gz
EOF
}

die() {
  echo "error: $*" >&2
  exit 1
}

input_file=""
mode="drop"
force=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    -i) input_file="${2:-}"; shift 2 ;;
    --merge) mode="merge"; shift ;;
    --force) force=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) die "invalid option: $1 (see -h)" ;;
  esac
done

[[ -n "$input_file" ]] || die "no input file specified (see -h)"

# Resolve to absolute path before cd'ing.
if [[ "$input_file" != /* ]]; then
  input_file="$PWD/$input_file"
fi
[[ -f "$input_file" ]] || die "input file not found: $input_file"

cd "$repo_root"

if [[ -f .env ]]; then
  set -a
  # ./ prefix is load-bearing: bash's `source` does a PATH search when
  # given a filename without a slash, and could pick up an unrelated
  # .env elsewhere in PATH.
  # shellcheck disable=SC1091
  source ./.env
  set +a
fi

# Find the running mongodb container by compose label.  Works regardless
# of which compose file or project name brought the stack up.
mongodb_containers=$(docker ps \
  --filter "label=com.docker.compose.service=mongodb" \
  --filter "status=running" \
  --format '{{.Names}}')
if [[ -z "$mongodb_containers" ]]; then
  die "no running mongodb container found.  'docker compose up -d mongodb' first."
fi
mongodb_container=$(printf '%s\n' "$mongodb_containers" | head -n 1)
container_count=$(printf '%s\n' "$mongodb_containers" | grep -c .)
if [[ "$container_count" -gt 1 ]]; then
  others=$(printf '%s\n' "$mongodb_containers" | tail -n +2 | tr '\n' ' ')
  echo "warning: multiple mongodb containers running, using $mongodb_container" >&2
  echo "         (others: $others)" >&2
fi

if [[ $force -eq 0 ]]; then
  # Without a TTY the prompt below would read EOF and silently cancel
  # (exit 0) — fail loudly instead so automated runs don't look like a
  # successful no-op.  Pass --force to restore non-interactively.
  if [[ ! -t 0 ]]; then
    die "stdin is not a TTY; re-run with --force to restore non-interactively"
  fi
  echo "About to restore $input_file into the running mongodb container."
  if [[ "$mode" == "drop" ]]; then
    echo "Mode: --drop (target collections will be replaced)."
  else
    echo "Mode: --merge (existing data preserved where possible)."
  fi
  read -r -p "Proceed? [y/N] " ans
  [[ "$ans" =~ ^[Yy]$ ]] || { echo "Cancelled."; exit 0; }
fi

mongorestore_args=(--archive --gzip)
if [[ "$mode" == "drop" ]]; then
  mongorestore_args+=(--drop)
fi
if [[ -n "${MC_MONGO_PASSWORD:-}" ]]; then
  mongorestore_args+=(
    -u rocketgraph
    -p "$MC_MONGO_PASSWORD"
    --authenticationDatabase admin
  )
fi
if [[ "${MC_MONGO_TLS_ENABLED:-}" == "true" ]]; then
  # --ssl* (not --tls*) — Percona's bundled mongo-tools (and older
  # Community mongo-tools) only know the older flag names.  Newer
  # mongo-tools (100.x+) still accept --ssl* as deprecated aliases.
  mongorestore_args+=(
    --ssl
    --sslCAFile /etc/ssl/mongodb/ca.pem
  )
  # Present a client cert when mTLS is in use (mongod requires one).
  if [[ -n "${MC_MONGO_TLS_CLIENT_PEM:-}" ]]; then
    mongorestore_args+=(--sslPEMKeyFile /etc/ssl/mongodb/client.pem)
  fi
fi

docker exec -i "$mongodb_container" mongorestore "${mongorestore_args[@]}" \
  < "$input_file"

echo "Restored from $input_file"
