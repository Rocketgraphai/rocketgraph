#!/usr/bin/env bash

set -euo pipefail

# The dump contains the entire database — create the archive owner-only
# from the start, not just after the trailing chmod, so it's never
# briefly world-readable while the dump streams.
umask 077

# Always operate from the repo root so .env and docker compose resolve.
repo_root="$(cd "$(dirname "$0")/.." && pwd)"

usage() {
  cat <<'EOF'
Usage: db_dump.sh [-o FILE]

Stream a gzip-compressed mongodump archive from the running mongodb
container to a file on the host.  Works for both MongoDB Community and
Percona Server for MongoDB — the archive format is wire-compatible.

Options:
  -o FILE  Write archive to FILE.  Defaults to
           mongo-dump-<UTC timestamp>.archive.gz in the current
           directory.
  -h       Show this help.

Authentication and TLS settings are read from .env at the repo root
(MC_MONGO_PASSWORD, MC_MONGO_TLS_ENABLED, and
MC_MONGO_TLS_CLIENT_PEM for mTLS).  The running mongodb container is
found by its compose service label and entered with `docker exec` — no
host port mapping required, and it works regardless of which compose
file or project name started the stack.

Example — round-trip for a Community → Percona engine switch:

  scripts/db_dump.sh -o /tmp/snapshot.archive.gz
  docker compose down
  docker volume rm rocketgraph_mongodb-data
  # edit MC_MONGODB_IMAGE in .env, then:
  docker compose up -d
  scripts/db_restore.sh -i /tmp/snapshot.archive.gz
EOF
}

die() {
  echo "error: $*" >&2
  exit 1
}

output_file=""
while getopts ":o:h" opt; do
  case "$opt" in
    o) output_file="$OPTARG" ;;
    h) usage; exit 0 ;;
    \?) die "invalid option: -$OPTARG (see -h)" ;;
    :) die "option -$OPTARG requires an argument" ;;
  esac
done

if [[ -z "$output_file" ]]; then
  output_file="mongo-dump-$(date -u +%Y%m%dT%H%M%SZ).archive.gz"
fi

# Resolve to absolute path before cd'ing.
if [[ "$output_file" != /* ]]; then
  output_file="$PWD/$output_file"
fi
if [[ -e "$output_file" ]]; then
  die "$output_file already exists; refusing to overwrite"
fi

cd "$repo_root"

# Source .env for MC_MONGO_* settings.  Quote values in .env if they
# contain '#' or '$' so bash source doesn't misinterpret them.
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
# of which compose file or project name brought the stack up — operator
# doesn't need to remember to set -f or COMPOSE_FILE.
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

mongodump_args=(--archive --gzip)
if [[ -n "${MC_MONGO_PASSWORD:-}" ]]; then
  mongodump_args+=(
    -u rocketgraph
    -p "$MC_MONGO_PASSWORD"
    --authenticationDatabase admin
  )
fi
if [[ "${MC_MONGO_TLS_ENABLED:-}" == "true" ]]; then
  # --ssl* (not --tls*) — Percona's bundled mongo-tools (and older
  # Community mongo-tools) only know the older flag names.  Newer
  # mongo-tools (100.x+) still accept --ssl* as deprecated aliases.
  mongodump_args+=(
    --ssl
    --sslCAFile /etc/ssl/mongodb/ca.pem
  )
  # Present a client cert when mTLS is in use (mongod requires one).
  if [[ -n "${MC_MONGO_TLS_CLIENT_PEM:-}" ]]; then
    mongodump_args+=(--sslPEMKeyFile /etc/ssl/mongodb/client.pem)
  fi
fi

# -T disables TTY allocation so the archive stream is clean binary.
# mongodump's progress lines go to stderr and stay visible to the user.
docker exec -i "$mongodb_container" mongodump "${mongodump_args[@]}" > "$output_file"

chmod 600 "$output_file"

bytes=$(stat -c%s "$output_file" 2>/dev/null || stat -f%z "$output_file")
echo "Wrote $output_file ($bytes bytes)"
