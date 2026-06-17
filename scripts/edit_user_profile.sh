#!/usr/bin/env bash

set -euo pipefail

repo_root="$(cd "$(dirname "$0")/.." && pwd)"

usage() {
  cat <<'EOF'
Usage: edit_user_profile.sh USERNAME [-s KEY VALUE | -d KEY]

Read or edit a Mission Control user profile in the MissionControl.user
collection of the bundled mongodb container.  With no flags, prints the
user's document.  With -s, sets a field.  With -d, unsets a field.  The
user must already exist; this tool never creates one.

Arguments:
  USERNAME       The username to look up.

Options:
  -s KEY VALUE   Set KEY to VALUE on the user document (adds the field
                 if absent; the user must exist).
  -d KEY         Unset KEY from the user document.
  -h             Show this help.

Authentication and TLS settings are read from .env at the repo root
(MC_MONGO_PASSWORD, MC_MONGO_TLS_ENABLED, and
MC_MONGO_TLS_CLIENT_PEM for mTLS).  The script talks to mongosh inside
the mongodb container, so the backend service does not need to be
running.

Replaces the Python script of the same name that previously lived in
the backend repo and was copied into the backend container at build
time.

Examples:
  scripts/edit_user_profile.sh alice
  scripts/edit_user_profile.sh alice -s role admin
  scripts/edit_user_profile.sh alice -d temporary_token
EOF
}

die() {
  echo "error: $*" >&2
  exit 1
}

username=""
op="get"
set_key=""
set_value=""
del_key=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    -s)
      [[ $# -ge 3 ]] || die "-s requires KEY VALUE"
      op="set"
      set_key="$2"
      set_value="$3"
      shift 3
      ;;
    -d)
      [[ $# -ge 2 ]] || die "-d requires KEY"
      op="del"
      del_key="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    -*)
      die "invalid option: $1 (see -h)"
      ;;
    *)
      [[ -z "$username" ]] || die "unexpected argument: $1"
      username="$1"
      shift
      ;;
  esac
done

[[ -n "$username" ]] || { usage >&2; exit 2; }

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

# The eval script reads its inputs from process.env so we never
# interpolate user-supplied values into JS source — avoids quoting
# bugs and any (small) injection risk for usernames or keys with
# special characters.
read -r -d '' eval_js <<'JS' || true
const op = process.env.OP;
const username = process.env.USERNAME;
const u = db.user.findOne({ username });
// Fail if the user doesn't exist — never create one.
if (!u) { print('No such user: ' + username); quit(1); }
if (op === 'get') {
  for (const k of Object.keys(u)) {
    print(k.padEnd(21) + ': ' + EJSON.stringify(u[k]));
  }
} else if (op === 'set') {
  const key = process.env.SET_KEY;
  const value = process.env.SET_VALUE;
  db.user.updateOne({ username }, { $set: { [key]: value } });
  print(`Set ${key} = ${value} for ${username}`);
} else if (op === 'del') {
  const key = process.env.DEL_KEY;
  db.user.updateOne({ username }, { $unset: { [key]: '' } });
  print(`Unset ${key} for ${username}`);
}
JS

mongosh_args=(--quiet MissionControl)
if [[ -n "${MC_MONGO_PASSWORD:-}" ]]; then
  mongosh_args+=(
    -u rocketgraph
    -p "$MC_MONGO_PASSWORD"
    --authenticationDatabase admin
  )
fi
if [[ "${MC_MONGO_TLS_ENABLED:-}" == "true" ]]; then
  mongosh_args+=(
    --tls
    --tlsCAFile /etc/ssl/mongodb/ca.pem
  )
  # Present a client cert when mTLS is in use (mongod requires one).
  if [[ -n "${MC_MONGO_TLS_CLIENT_PEM:-}" ]]; then
    mongosh_args+=(--tlsCertificateKeyFile /etc/ssl/mongodb/client.pem)
  fi
fi
mongosh_args+=(--eval "$eval_js")

docker exec -i \
  -e OP="$op" \
  -e USERNAME="$username" \
  -e SET_KEY="$set_key" \
  -e SET_VALUE="$set_value" \
  -e DEL_KEY="$del_key" \
  "$mongodb_container" mongosh "${mongosh_args[@]}"
