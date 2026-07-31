# MongoDB Security

This guide shows how to harden the bundled MongoDB for Rocketgraph Mission Control: authentication, TLS, mutual TLS, and encryption at rest.  Each is opt-in.

> **Applies to all deployments.**  The examples below use Docker Compose and Podman — each feature is opt-in via environment variables in your `.env` file, which the base `docker-compose.yml` reads to wire the credentials, certificate mounts, and connection string automatically.  On Kubernetes and OpenShift the same four features are configured through chart values and Secrets instead; see [With MongoDB Authentication](../charts/rocketgraph/README.md#with-mongodb-authentication), [MongoDB TLS](../charts/rocketgraph/README.md#mongodb-tls), and [MongoDB Encryption at Rest](../charts/rocketgraph/README.md#mongodb-encryption-at-rest) in the Helm chart documentation.  The enforcement rules, certificate requirements, upgrade path, and troubleshooting in this guide apply to every platform.

## Environment Variables

The `MC_MONGO_*` variables are listed in the [environment-variable table in the main README](../README.md#environment-variables), which is the authoritative reference.  This guide explains how to use them; each section below introduces the variables it needs.

The base compose file builds `MC_MONGO_URI` automatically from the auth and TLS variables; you only need to set `MC_MONGO_URI` directly if you are connecting to an external MongoDB you manage yourself.

## Enable Authentication

1. Add a password to your `.env` (the root user is always `rocketgraph`):

   ```dotenv
   MC_MONGO_PASSWORD=<choose a strong password>
   ```

1. Start the stack:

   ```bash
   docker compose up -d
   ```

   When a password is set, compose passes `MONGO_INITDB_ROOT_USERNAME=rocketgraph` / `MONGO_INITDB_ROOT_PASSWORD` to the container.  On first start the `mongo` image's entrypoint sees them and:
   1. starts mongod with `--auth`,
   1. creates the root user in the `admin` database.

   The backend's `MC_MONGO_URI` is built as `mongodb://rocketgraph:<pw>@mongodb:27017/?authSource=admin` and the healthcheck authenticates with the same credentials.

1. Verify:

   ```bash
   docker compose exec mongodb mongosh \
     -u rocketgraph -p "$MC_MONGO_PASSWORD" \
     --authenticationDatabase admin \
     --eval "db.adminCommand('listDatabases')"
   ```

### How Auth Enforcement Is Decided

Authentication is opt-in and re-evaluated **on every start** — it is not a property stored in the database.  When `MC_MONGO_PASSWORD` is set, the stack starts mongod with `--auth` (and, on a fresh volume, creates the `rocketgraph` root user).  When it is unset, mongod starts with no `--auth` and enforces nothing.

The important consequence: clearing `MC_MONGO_PASSWORD` (or never setting it) on a data volume that *was* initialised with authentication leaves the `rocketgraph` user in the volume but **disables enforcement entirely** — any client that can reach the database connects with full access, no password required.  Re-setting `MC_MONGO_PASSWORD` and restarting turns enforcement back on.  The user records in the volume never change; only the startup flag does.  So removing the password does not "lock" the database — it opens it.

### Upgrading an Existing Deployment

`MONGO_INITDB_ROOT_USERNAME` / `MONGO_INITDB_ROOT_PASSWORD` are honoured **only on first run** — when `/data/db` is empty.  If you already have a MongoDB data volume, setting these variables will not create the user, and mongod started with `--auth` will refuse all logins.

To migrate an existing unauthenticated deployment:

1. With the stack running unauthenticated, create the root user manually:

   ```bash
   docker compose exec mongodb mongosh --eval '
     db.getSiblingDB("admin").createUser({
       user: "rocketgraph",
       pwd: "<choose a strong password>",
       roles: [{ role: "root", db: "admin" }]
     })'
   ```

1. Add `MC_MONGO_PASSWORD` to `.env` (matching the password you just set for `rocketgraph`).

1. Restart the stack:

   ```bash
   docker compose down
   docker compose up -d
   ```

   mongod will now start with `--auth` and the existing admin user will be honoured.

## Enable TLS

TLS is optional for single-host Compose installs — traffic stays on the internal `database-network` and never leaves the host.  Enable it when the deployment spans hosts (e.g. Docker Swarm overlay) or when a compliance policy requires application-level encryption in transit regardless of network topology.

1. Generate (or obtain) a server cert+key and a CA cert.  The bundled stack verifies the hostname strictly, so the server cert must carry a `subjectAltName` matching the service name `mongodb`.  The helper script does this for you:

   ```bash
   scripts/generate_mongo_certs.sh ~/.rocketgraph/mongo-tls
   ```

   This writes `server.pem` (cert+key concatenated, the form mongod wants) and `ca-chain.cert.pem`, with a SAN covering `mongodb`, `localhost`, and `127.0.0.1`.  To add more hostnames/IPs (e.g. an external DNS name), set `MONGO_TLS_SAN`:

   ```bash
   MONGO_TLS_SAN="DNS:mongodb, DNS:db.example.com, IP:127.0.0.1" \
     scripts/generate_mongo_certs.sh ~/.rocketgraph/mongo-tls
   ```

   For production you can instead obtain certs from an internal CA or a public issuer — just ensure the server cert's SAN includes the name the backend uses to reach mongod (`mongodb` on the bundled Docker network).

1. Add the TLS settings to `.env`:

   ```dotenv
   MC_MONGO_TLS_ENABLED=true
   MC_MONGO_TLS_SERVER_PEM=/home/you/.rocketgraph/mongo-tls/server.pem
   MC_MONGO_TLS_CA_PEM=/home/you/.rocketgraph/mongo-tls/ca-chain.cert.pem
   ```

1. Start the stack:

   ```bash
   docker compose up -d
   ```

   mongod is launched with `--tlsMode requireTLS --tlsCertificateKeyFile … --tlsCAFile … --tlsAllowConnectionsWithoutCertificates`.  The backend's `MC_MONGO_URI` gets `tls=true&tlsCAFile=/etc/ssl/certs/mongodb-ca.pem` appended.

1. Verify:

   ```bash
   docker compose exec mongodb mongosh \
     --tls --tlsCAFile /etc/ssl/mongodb/ca.pem \
     --eval "db.adminCommand('ping')"
   ```

### Server TLS Mode

`MC_MONGO_TLS_MODE` controls what kinds of connections mongod accepts:

- **`requireTLS`** (default) — every connection must use TLS.  Non-TLS clients are rejected outright.  Use this in production.
- **`preferTLS`** — mongod accepts both TLS and non-TLS connections; uses TLS when the client offers it.  Useful during a migration where some clients are still on plaintext.
- **`allowTLS`** — mongod accepts both, prefers non-TLS.  The looser end of the spectrum; reach for it only if a specific tool or test needs plaintext while you flip the switch.

The mode is a *server-side* policy.  The backend's URI always carries `tls=true` once `MC_MONGO_TLS_ENABLED=true`, so the backend speaks TLS regardless of which mode the server allows.  Once all clients are on TLS, set `MC_MONGO_TLS_MODE=requireTLS` (or unset it) to lock the door.

## Enable Both Together

The two concepts compose cleanly — set all four variables in `.env`:

```dotenv
MC_MONGO_PASSWORD=<choose a strong password>
MC_MONGO_TLS_ENABLED=true
MC_MONGO_TLS_SERVER_PEM=/home/you/.rocketgraph/mongo-tls/server.pem
MC_MONGO_TLS_CA_PEM=/home/you/.rocketgraph/mongo-tls/ca-chain.cert.pem
```

`MC_MONGO_URI` is built as:

```
mongodb://rocketgraph:<pw>@mongodb:27017/?authSource=admin&tls=true&tlsCAFile=/etc/ssl/certs/mongodb-ca.pem
```

Verifying from inside the mongodb container:

```bash
docker compose exec mongodb mongosh \
  --tls --tlsCAFile /etc/ssl/mongodb/ca.pem \
  -u rocketgraph -p "$MC_MONGO_PASSWORD" \
  --authenticationDatabase admin \
  --eval "db.adminCommand('listDatabases')"
```

## Enable Mutual TLS (mTLS)

By default mongod runs with `--tlsAllowConnectionsWithoutCertificates`, so TLS clients may connect without presenting a certificate.  mTLS removes that allowance: mongod requires every client to present a certificate signed by the trusted CA, and the backend presents one.  This is opt-in on top of TLS.

mTLS is gated by two settings, both of which must be set together:

1. `MC_MONGO_MTLS_ENABLED` is off by default (server-only TLS).  Set it to `true` to make mongod require client certs.  It keys on the literal value `true` — any other value (including empty or unset) leaves mTLS off, matching the Helm chart's `mongodb.tls.mtls`.
1. `MC_MONGO_TLS_CLIENT_PEM` points at the client cert+key PEM the backend presents.  `scripts/generate_mongo_certs.sh` already emits this as `client.pem` alongside `server.pem` and `ca-chain.cert.pem`.

Steps (on top of an already-working TLS setup):

1. Generate certs if you haven't — `client.pem` comes for free:

   ```bash
   scripts/generate_mongo_certs.sh ~/.rocketgraph/mongo-tls
   ```

1. In `.env`, set `MC_MONGO_MTLS_ENABLED=true` and point `MC_MONGO_TLS_CLIENT_PEM` at the client PEM:

   ```dotenv
   MC_MONGO_TLS_ENABLED=true
   MC_MONGO_TLS_SERVER_PEM=/home/you/.rocketgraph/mongo-tls/server.pem
   MC_MONGO_TLS_CA_PEM=/home/you/.rocketgraph/mongo-tls/ca-chain.cert.pem
   MC_MONGO_MTLS_ENABLED=true
   MC_MONGO_TLS_CLIENT_PEM=/home/you/.rocketgraph/mongo-tls/client.pem
   ```

1. Restart:

   ```bash
   docker compose up -d
   ```

   mongod now starts without `--tlsAllowConnectionsWithoutCertificates`.  The backend's `MC_MONGO_URI` gains `&tlsCertificateKeyFile=/etc/ssl/certs/mongodb-client.pem`, the client PEM is mounted into the backend and mongodb containers, and the healthcheck presents it.

1. Verify a certless connection is now rejected and a cert-bearing one succeeds:

   ```bash
   # Rejected (no client cert):
   docker compose exec mongodb mongosh --tls \
     --tlsCAFile /etc/ssl/mongodb/ca.pem \
     --eval "db.adminCommand('ping')"

   # Succeeds (presents the client cert):
   docker compose exec mongodb mongosh --tls \
     --tlsCAFile /etc/ssl/mongodb/ca.pem \
     --tlsCertificateKeyFile /etc/ssl/mongodb/client.pem \
     -u rocketgraph -p "$MC_MONGO_PASSWORD" --authenticationDatabase admin \
     --eval "db.adminCommand('ping')"
   ```

### Caveats

- **Both settings must agree.**  Setting `MC_MONGO_MTLS_ENABLED=true` without setting `MC_MONGO_TLS_CLIENT_PEM` makes mongod require a cert the backend can't present — the backend (and healthcheck) fail to connect.  That failure is loud.  The reverse — setting the client PEM but forgetting `MC_MONGO_MTLS_ENABLED=true` — leaves mTLS silently *not* enforced (TLS and auth still apply).
- **No backend code change.**  pymongo reads `tlsCertificateKeyFile` straight from the URI, so mTLS is entirely a compose + cert concern.
- **The `scripts/` tooling handles mTLS automatically.**  `db_dump.sh`, `db_restore.sh`, and `edit_user_profile.sh` present the client cert whenever `MC_MONGO_TLS_CLIENT_PEM` is set, so they keep working under mTLS.

## Enable Encryption at Rest (FIPS Only)

Application-level encryption at rest is available only when using the FIPS compose overlay (`docker-compose.fips.yml`), because the default Community `mongo` image refuses to start with `--enableEncryption`.  The FIPS overlay swaps in Percona Server for MongoDB, which supports it.

1. Generate a 32-byte base64-encoded key file on the host:

   ```bash
   sudo mkdir -p /opt/rocketgraph
   sudo openssl rand -base64 32 -out /opt/rocketgraph/mongo-encryption.key
   ```

1. Set ownership and permissions.  Percona's mongod runs as uid `1001` inside the container; mongod refuses to start unless the key file is mode `0600` (or `0400`) and readable by that uid:

   ```bash
   sudo chown 1001:1001 /opt/rocketgraph/mongo-encryption.key
   sudo chmod 600 /opt/rocketgraph/mongo-encryption.key
   ```

1. Add the settings to `.env` (alongside any auth / TLS settings you already use):

   ```dotenv
   MC_MONGO_ENCRYPTION_ENABLED=true
   MC_MONGO_ENCRYPTION_KEY_FILE=/opt/rocketgraph/mongo-encryption.key
   ```

1. Start the stack with the FIPS overlay:

   ```bash
   docker compose -f docker-compose.yml -f docker-compose.fips.yml up -d
   ```

   mongod is launched with `--enableEncryption --encryptionKeyFile /etc/mongodb-encryption/key`.  Encryption is transparent to clients — the backend, `mongosh`, and the `scripts/` tooling all continue to work unchanged.

1. Verify mongod started with encryption enabled:

   ```bash
   docker compose logs mongodb | grep -i encryption
   ```

### Caveats

- **Key loss is data loss.**  Back the key file up out-of-band (e.g. to an HSM, an offline secret store, or a sealed envelope in a safe).  Anyone who can read the key file can decrypt the database.
- **Can't retroactively encrypt an existing volume.**  Percona refuses to start with `--enableEncryption` against an existing unencrypted data volume.  To migrate, use `scripts/db_dump.sh`, remove the data volume (`docker volume rm rocketgraph_mongodb-data`), bring the stack up with encryption enabled (which initialises a fresh encrypted volume), and restore with `scripts/db_restore.sh`.  See the Community ↔ Percona switch workflow in `scripts/README.md` — the encryption-on migration follows the same pattern.
- **Dumps are NOT encrypted.**  `db_dump.sh` reads via the mongo wire protocol, which the server decrypts before sending.  The archive on disk is plaintext.  If the dump file needs encryption, encrypt it separately (`gpg`, `age`, an encrypted backup target, etc.) before storing or transmitting.
- **KMIP is not yet wired.**  Percona supports `--kmipServerName` and friends as an alternative to a local key file.  Not currently exposed — would be a future addition for customers running a KMS.

## Connecting from Outside the Host

`docker-compose.dev.yml` exposes port `27017` on the host for development.  To connect from your laptop with both auth and TLS on:

```bash
mongosh --host localhost:27017 \
  --tls --tlsCAFile ~/.rocketgraph/mongo-tls/ca-chain.cert.pem \
  -u rocketgraph -p "$MC_MONGO_PASSWORD" \
  --authenticationDatabase admin
```

This works because the generated cert's SAN includes `DNS:localhost` and `IP:127.0.0.1`.  If you connect by some other name, add it via `MONGO_TLS_SAN` when generating the cert.

Production deployments (`docker-compose.yml`) do not expose 27017 — the database is reachable only from the `backend` container over the internal `database-network`.

## Troubleshooting

**Backend healthcheck fails after enabling auth on an existing deployment.**  The data volume was initialised without auth, so the admin user does not exist.  See [Upgrading an Existing Deployment](#upgrading-an-existing-deployment).

**A database that previously required a password now accepts unauthenticated connections.**  `MC_MONGO_PASSWORD` is unset or empty, so mongod started without `--auth`.  Enforcement is decided by the password at each start, not by the data volume — the `rocketgraph` user still exists but is not enforced.  Set `MC_MONGO_PASSWORD` and restart to re-enable auth.  See [How Auth Enforcement Is Decided](#how-auth-enforcement-is-decided).

**mongod fails to start with "Error opening file: /etc/ssl/mongodb/server.pem".**  `MC_MONGO_TLS_SERVER_PEM` is unset (or points at a missing file) while `MC_MONGO_TLS_ENABLED=true`.  Provide a real cert path.

**TLS handshake fails with "certificate verify failed".**  The CA used to sign the server cert is not the one the client is trusting.  Check that `MC_MONGO_TLS_CA_PEM` is the CA that signed `MC_MONGO_TLS_SERVER_PEM`.

**Hostname verification fails** (e.g. `certificate is not valid for 'mongodb'`).  The server cert's `subjectAltName` does not include the name the client used to connect.  The bundled stack connects to the service name `mongodb`, and the in-container tooling connects to `localhost`/`127.0.0.1` — regenerate the cert with `scripts/generate_mongo_certs.sh` (its default SAN covers all three), or add the missing name via `MONGO_TLS_SAN`.  A cert with only a Common Name and no SAN will always fail: modern TLS clients (including the backend's pymongo) ignore CN.

**mongod fails to start with `Unknown --setParameter 'opensslFIPSMode'`.**  This comes from the older `--setParameter opensslFIPSMode=true` syntax, which current Percona/MongoDB releases no longer accept.  FIPS-mode TLS uses the `--tlsFIPSMode` flag instead — the FIPS overlay (`docker-compose.fips.yml`) sets it for you, so don't add the old `setParameter` form.

**Want to rotate the password.**  Update `MC_MONGO_PASSWORD` in `.env`, change the user's password inside mongod, then `docker compose up -d`:

```bash
docker compose exec mongodb mongosh \
  -u rocketgraph -p "$OLD_PASSWORD" \
  --authenticationDatabase admin \
  --eval 'db.getSiblingDB("admin").changeUserPassword("rocketgraph", "<new password>")'
```
