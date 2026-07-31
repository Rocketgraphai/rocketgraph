# Rocketgraph Deployment Reference

This document describes each container in the Rocketgraph stack — images, ports, volumes, and environment variables — for use with any container orchestration platform.

> **Scope.**  This reference is for writing custom manifests, adapting the stack to another orchestrator, or debugging a running container against its expected configuration.  If you are deploying with Docker Compose or Podman, start with the [main README](../README.md); on Kubernetes or OpenShift, start with the [Helm chart documentation](../charts/rocketgraph/README.md).

---

## Containers

### mission-control-frontend

| | |
|---|---|
| **Image** | `docker.io/rocketgraph/mission-control-frontend:<version>` |
| **Ports** | `80` (HTTP), `443` (HTTPS) |

These are the ports the frontend listens on inside the container.  Publishing them on the privileged host ports 80 and 443 requires a container engine running with privilege — a rootless engine cannot.  See [Running Under Podman](../README.md#running-under-podman) for the unprivileged host-port setup and the ways to map 80 and 443 onto it.

**Volume mounts**

| Mount path | Purpose |
|---|---|
| `/etc/ssl/certs/td.pem` | TLS public certificate |
| `/etc/ssl/private/td.pem` | TLS private key |
| `/etc/ssl/certs/ca-chain.pem` | CA chain for mTLS client cert verification (optional) |

---

### mission-control-backend

| | |
|---|---|
| **Image** | `docker.io/rocketgraph/mission-control-backend:<version>` |
| **Port** | `5000` (HTTP, internal only) |
| **Health check** | `GET http://localhost:5000/api/health` |
| **Depends on** | `mongodb`, `xgt` |

**Environment variables**

| Variable | Required | Description |
|---|---|---|
| `MC_MONGO_URI` | Yes | MongoDB connection URI, e.g. `mongodb://user:pass@host:27017` |
| `MC_DEFAULT_XGT_HOST` | Yes | Hostname of the xGT server |
| `MC_DEFAULT_XGT_PORT` | Yes | Port of the xGT server (default `4367`) |
| `MC_PORT` | No | Frontend HTTP port, used to construct OIDC redirect URIs (default `80`) |
| `MC_SSL_PORT` | No | Frontend HTTPS port, used to construct OIDC redirect URIs (default `443`) |
| `MC_SESSION_TTL` | No | Session time-to-live in seconds (idle users are warned, then logged out) |
| `MC_EXTERNAL_TLS` | No | Set to `true` when users reach Mission Control over HTTPS terminated upstream of the frontend (load balancer, ingress, edge route); marks session cookies `Secure`. Unnecessary when the bundled frontend serves HTTPS itself — the backend detects that per request via the `X-Forwarded-Proto` header the frontend sends |
| `MC_SSL_PUBLIC_CERT` | No | Legacy HTTPS signal superseded by `MC_EXTERNAL_TLS`: when both this and `MC_SSL_PRIVATE_KEY` are non-empty (the values are never read), session cookies are marked `Secure` on every response |
| `MC_SSL_PRIVATE_KEY` | No | See `MC_SSL_PUBLIC_CERT` |
| `MC_SSL_PROXY_PUBLIC_CERT` | No | Path to proxy client cert for mTLS to xGT |
| `MC_SSL_PROXY_PRIVATE_KEY` | No | Path to proxy client key for mTLS to xGT |
| `MC_OIDC_ISSUER` | No | OIDC issuer URL |
| `MC_OIDC_CLIENT_ID` | No | OIDC client ID |
| `MC_OIDC_CLIENT_SECRET` | No | OIDC client secret |
| `MC_OIDC_SCOPES` | No | OIDC scopes (space-separated) |
| `MC_OIDC_FRONTEND_URL` | No | Override frontend base URL for post-login redirects |
| `MC_OIDC_REDIRECT_URI` | No | Override OIDC redirect URI |
| `MC_OIDC_ALLOWED_ORIGINS` | No | Comma-separated list of permitted frontend origins |
| `MC_OIDC_TLS_VERIFY` | No | `true`, `false`, or path to CA bundle for OIDC HTTP calls |
| `MC_OIDC_CA_CERT` | No | Path to CA cert for OIDC provider TLS verification |
| `MC_XGT_ALLOWED_HOSTS` | No | Comma-separated allowlist of permitted xGT `host:port` values |
| `LD_LIBRARY_PATH` | No | ODBC library path, e.g. `/odbc` |

**Volume mounts**

| Mount path | Purpose |
|---|---|
| `/etc/ssl/certs/xgt-server.pem` | xGT server CA cert for verifying TLS to xGT (fixed path — the backend uses it whenever the file is present) |
| `/etc/ssl/certs/proxy-client-cert.pem` | mTLS proxy client cert |
| `/etc/ssl/private/proxy-client-key.pem` | mTLS proxy client key |
| `/etc/ssl/certs/oidc-ca.pem` | OIDC provider CA cert (set `MC_OIDC_CA_CERT` to this path) |
| `/etc/ssl/certs/mongodb-ca.pem` | MongoDB CA cert, to verify the server when MongoDB TLS is on |
| `/etc/ssl/certs/mongodb-client.pem` | MongoDB client cert+key, presented under mTLS |
| `/odbc` | ODBC drivers directory |
| `/opt/ibm/iaccess` | IBM i Access Client Solutions install, for IBM i / Db2 ODBC (optional) |
| `/app/site_config/site_config.yml` | Custom site config YAML (optional) |
| `/app/site_config/site_config.py` | Custom site config Python (optional) |

---

### xgt

| | |
|---|---|
| **Image** | `docker.io/rocketgraph/xgt:<version>` |
| **Ports** | `4367` (gRPC), `4366` (gRPC health probe, plain) |

**Volume mounts**

| Mount path | Purpose |
|---|---|
| `/conf/xgtd.conf` | xGT configuration file |
| `/conf/audit.xml` | Audit logging configuration |
| `/conf/grouplabel.csv` | Group-to-label mappings |
| `/conf/label.csv` | Security label definitions |
| `/conf/proxy_list` | Proxy CN allowlist for PKIAuth (optional) |
| `/conf/ssl/` | TLS certificates directory (optional) |
| `/conf/licenses/` | License files when using a local license server |
| `/license/xgtd.lic` | Direct license file mount (alternative to license server) |
| `/data` | xGT persistent data |
| `/log` | xGT log files |
| `/etc/ssl/certs/oidc-ca.pem` | OIDC provider CA cert (optional) |

**Key xgtd.conf settings**

| Key | Description |
|---|---|
| `license.location` | License path or server, e.g. `/license/xgtd.lic` or `6200@<license-manager-host>` |
| `system.usessl` | `true` to enable TLS |
| `system.usemtls` | `true` to require client certs |
| `system.ssl_root_dir` | Directory containing TLS certs (default `/conf/ssl`) |
| `security.oidc` | OIDC configuration block (see OIDC guide) |

---

### xgt-license-manager

| | |
|---|---|
| **Image** | `docker.io/rocketgraph/xgt-license-manager:<version>` |
| **Ports** | `6200` (license serving), `6199` (management UI, HTTPS) |
| **User** | `1000:1000` |

**Volume mounts**

| Mount path | Purpose |
|---|---|
| `/conf` | Configuration directory (must be writable by uid 1000) |
| `/conf/licenses/` | License files — place `.lic` files here |
| `/log` | Log files |

xGT connects to the license manager by setting `license.location = 6200@<hostname>` in `xgtd.conf`.

---

### mongodb

| | |
|---|---|
| **Image** | `docker.io/library/mongo:<version>` (Community), or `docker.io/percona/percona-server-mongodb:<version>` for FIPS / encryption at rest |
| **Port** | `27017` |

**Environment variables**

| Variable | Required | Description |
|---|---|---|
| `MONGO_INITDB_ROOT_USERNAME` | No | Root username; when set with the password, mongod runs with `--auth` and the user is created on first run |
| `MONGO_INITDB_ROOT_PASSWORD` | No | Root password |

**Volume mounts**

| Mount path | Purpose |
|---|---|
| `/data/db` | MongoDB data directory |
| `/etc/ssl/mongodb/server.pem` | Server cert+key (concatenated), for TLS |
| `/etc/ssl/mongodb/ca.pem` | CA cert, for TLS and client-cert verification |
| `/etc/ssl/mongodb/client.pem` | Client cert+key, for mTLS (lets the healthcheck connect) |
| `/etc/mongodb-encryption/key` | Encryption-at-rest key (Percona; mode 0600, owned by mongod's uid) |

**mongod command flags** (set when the corresponding feature is enabled)

| Flag | Purpose |
|---|---|
| `--tlsMode requireTLS\|preferTLS\|allowTLS` | Enable TLS in the chosen mode |
| `--tlsCertificateKeyFile` / `--tlsCAFile` | Server cert+key / CA file |
| `--tlsAllowConnectionsWithoutCertificates` | Present unless mTLS is required (omit to require client certs) |
| `--tlsFIPSMode` | FIPS-only cipher enforcement (Percona on a FIPS host) |
| `--enableEncryption --encryptionKeyFile` | Encryption at rest (Percona) |

---

## Startup order

```
mongodb → backend → frontend
xgt-license-manager → xgt → backend
```
