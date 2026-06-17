# Operational Scripts

Helper scripts for operating the bundled MongoDB.  The first three connect to the running `mongodb` container; `generate_mongo_certs.sh` is a standalone cert generator.  Each supports `-h` for full usage.

| Script                   | Purpose                                                                |
|--------------------------|------------------------------------------------------------------------|
| `db_dump.sh`             | Stream a gzip-compressed `mongodump` archive to the host.              |
| `db_restore.sh`          | Pipe an archive back into the running stack via `mongorestore`.        |
| `edit_user_profile.sh`   | Read or edit fields in the `MissionControl.user` collection via `mongosh`. |
| `generate_mongo_certs.sh`| Generate a CA chain + SAN server cert + client cert for MongoDB TLS/mTLS. |

## Why These Exist

The bundled MongoDB is reachable only from inside the Compose project (`database-network` is marked `internal: true` and port 27017 is not host-mapped in production).  Anything that needs to read or modify it has to run inside a container on that network.  `db_dump.sh`, `db_restore.sh`, and `edit_user_profile.sh` locate the running MongoDB container by its Compose service label (`com.docker.compose.service=mongodb`) and `docker exec` into it — so they work regardless of which compose file or project name brought the stack up, and you don't have to pass `-f` or remember the container name.

`edit_user_profile.sh` replaces the Python script of the same name that used to live in the backend repo and was copied into the backend image at build time.  Pushing the tool out to this (deployment) repo decouples it from the backend release cycle and lets it run even when the backend is unhealthy.

`generate_mongo_certs.sh` is different — it doesn't touch any container.  It produces the cert files that the MongoDB TLS / mTLS options consume.

## Setup

Invoke from anywhere; the container scripts `cd` to the repo root automatically.  Only the `mongodb` container needs to be running and healthy — the backend, frontend, and xgt services are not used.  If the rest of the stack is down (or you don't want to start it), bring up just mongodb:

```bash
docker compose up -d mongodb
```

## `.env` Handling

The container scripts read connection settings from `.env` at the repo root — the same source the compose file reads — and translate them into the right `mongosh` / `mongodump` / `mongorestore` flags automatically.  They honour:

- `MC_MONGO_PASSWORD` — authenticate as `rocketgraph` with `--authenticationDatabase admin` when set.
- `MC_MONGO_TLS_ENABLED` — add `--tls`/`--ssl` and the CA file when `true`.
- `MC_MONGO_TLS_CLIENT_PEM` — present a client certificate when set, so the scripts keep working under mTLS (mongod requiring client certs).

So whether the stack is plain, auth-only, TLS, or mTLS, the scripts adapt without extra flags.

The scripts `source ./.env` (the leading `./` is deliberate — it stops bash from PATH-searching for a stray `.env` elsewhere).  Values with shell-special characters (`$`, `#`, backticks, etc.) need quoting:

```dotenv
MC_MONGO_PASSWORD='s3cret#stuff'
```

Plain alphanumeric passwords need no quoting.

## Generating Certificates

`generate_mongo_certs.sh` produces everything the TLS and mTLS options need, in one run:

```bash
scripts/generate_mongo_certs.sh ~/.rocketgraph/mongo-tls
```

Output:

- `server.pem` — server cert + key concatenated → `MC_MONGO_TLS_SERVER_PEM`.
- `ca-chain.cert.pem` — intermediate + root CA → `MC_MONGO_TLS_CA_PEM`.
- `client.pem` — client cert + key, for mTLS → `MC_MONGO_TLS_CLIENT_PEM`.

The server cert carries a `subjectAltName` (default `DNS:mongodb, DNS:localhost, IP:127.0.0.1`) so strict TLS hostname verification passes.  Override the SAN with `MONGO_TLS_SAN`.  See [`../doc/mongodb_security.md`](../doc/mongodb_security.md) for the full TLS / mTLS walkthrough.

## Switching MongoDB Engines (Community ↔ Percona)

The archive format is wire-compatible across engines, so a dump from Community restores cleanly into Percona (and vice versa).  The standard workflow:

```bash
scripts/db_dump.sh -o /tmp/snapshot.archive.gz

docker compose down
docker volume rm rocketgraph_mongodb-data

# edit MC_MONGODB_IMAGE in .env, e.g.:
#   MC_MONGODB_IMAGE=docker.io/percona/percona-server-mongodb:latest

docker compose up -d
scripts/db_restore.sh -i /tmp/snapshot.archive.gz
```

The destination volume must be empty when restoring (auth is initialised on first run of the mongo entrypoint — that's how the admin user gets created on the new engine).

## Limitations

The container scripts assume the local bundled `mongodb` container — they don't work against an external MongoDB you've pointed `MC_MONGO_URI` at.  For external MongoDB, run `mongodump` / `mongorestore` / `mongosh` directly against the external endpoint.
