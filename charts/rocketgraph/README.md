# Rocketgraph Helm Chart

Deploys the Rocketgraph Mission Control stack on Kubernetes and OpenShift.

## Components

- **Frontend** — Nginx-based web UI that proxies API requests to the backend
- **Backend** — Flask API server
- **MongoDB** — Document database for application state
- **xGT** — Graph analytics engine

## Quick Start

```bash
helm install rocketgraph ./charts/rocketgraph -f charts/rocketgraph/values-simple.yaml
```

That's it. All components deploy with sensible defaults. The chart ships a few example overlays you can use as starting points:

- [`values-simple.yaml`](values-simple.yaml) — minimal configuration (single-user mode, 10Gi xGT data volume).
- [`values-license-manager.yaml`](values-license-manager.yaml) — enables the xGT License Manager service.

For FIPS images, set `fips.enabled=true` (see [FIPS Mode](#fips-mode)).

`values.yaml` is the canonical defaults file and documents every available option; you don't pass it with `-f` (it's loaded automatically).

Several configuration topics are not Kubernetes-specific — MongoDB hardening, OIDC, LLM model selection, ODBC drivers — and have dedicated guides shared with the Docker Compose install. This README covers the chart-side plumbing (which values to set, which Secrets to create); those guides cover the substance. They are linked from the relevant sections below and collected under [Related Guides](#related-guides).

## Prerequisites

- Kubernetes 1.21+ or OpenShift 4.x
- Helm 3.x
- PV provisioner support in the cluster

## Installation

```bash
helm install rocketgraph ./charts/rocketgraph
```

### OpenShift

```bash
helm install rocketgraph ./charts/rocketgraph --set openshift.enabled=true
```

This binds the release ServiceAccount to the `anyuid` SCC. The full stack's current startup configuration includes root and fixed-UID containers. Have the platform administrator review this permission. `anyuid` and FIPS address different requirements: selecting FIPS images does not require granting `anyuid`. For Mission Control, MongoDB and XGT, use the [restricted-v2 profile](#full-stack-with-openshift-restricted-v2) below. If your images and startup configuration support non-root execution, including any required fixed UID, the `nonroot` SCC is another option subject to cluster policy:

```bash
helm install rocketgraph ./charts/rocketgraph --set openshift.enabled=true --set openshift.scc=nonroot
```

After installing, expose the frontend and get the URL:

```bash
oc expose svc/<release-name>-frontend
oc get route <release-name>-frontend -o jsonpath='{.spec.host}'
```

### Full Stack with OpenShift restricted-v2

In chart 0.4.0, add this to your site values to run XGT, Mission Control and MongoDB without an `anyuid` grant:

```yaml
openshift:
  enabled: true
  scc: restricted-v2
fips:
  enabled: true
```

Mission Control currently requires `fips.enabled=true` with this profile. Helm rejects the non-FIPS combination because that frontend image uses different startup and writable paths. This requirement does not apply to XGT-only releases.

The chart creates a ServiceAccount, drops all capabilities, disables privilege escalation, selects `RuntimeDefault` seccomp and requires non-root execution. OpenShift supplies the namespace UID and volume group. Do not set fixed `runAsUser`, `runAsGroup`, `fsGroup` or `supplementalGroups` for active components. The bundled License Manager and in-container SSSD are not supported by this profile. Supply an XGT license file or external license server as described below.

Verify the admitted SCC after deployment. Helm does not remove SCC grants created separately by an administrator; a remaining broader grant can change which SCC admits the pods:

```bash
oc -n <namespace> get pods -l app.kubernetes.io/instance=<release> \
  -o custom-columns='NAME:.metadata.name,SCC:.metadata.annotations.openshift\.io/scc,UID:.spec.containers[0].securityContext.runAsUser'
```

Mission Control's frontend gets writable nginx runtime directories and listens on **8080/8443** inside its container. The Service still exposes its configured HTTP/HTTPS ports (80/443 by default), so existing Routes and Ingresses continue to target the Service. NetworkPolicies and health checks use the new container ports. HTTP, HTTPS and frontend mTLS retain the image's configuration generation, with the listeners adjusted before nginx starts. External redirects use `backend.env.MC_SSL_PORT` when supplied, otherwise the frontend Service's HTTPS port. Proxy headers use the frontend Service port, not the internal 8080/8443 listener; configure `backend.oidc.frontendUrl` for the actual public URL.

Backend and MongoDB retain their normal entrypoints. MongoDB's encryption-key init container also uses the assigned UID; the chart does not inject UID/GID 1001 in this profile. Use fresh PVCs or arrange an ownership migration for existing storage before enabling it. Optional backend plugin installation and custom ODBC mounts may need additional writable paths or prebuilt images; the profile does not make arbitrary package installation directories writable.

The [OpenShift test-server values](../../doc/openshift_test_server/values.yaml) use this profile with FIPS images, XGT TLS and MongoDB TLS. Replace their site-specific values and create the referenced Secrets before deploying. The tested image versions are XGT `2.7.1-fips`, Mission Control `2.7.0-fips` and Percona MongoDB `8.0.23`; custom images must support the same startup paths. Default installs keep the existing behavior unless this profile is explicitly selected.

### xGT with OpenShift restricted-v2

The same profile supports an **XGT-only release** with the namespace-assigned UID and group. Start with [`examples/xgt_openshift_restricted.yaml`](examples/xgt_openshift_restricted.yaml), edit the hostname, OAuth endpoints and group mappings, and create its referenced Secrets in the same namespace:

```bash
oc -n xgt create secret generic xgt-license --from-file=xgtd.lic=/path/to/license.lic
oc -n xgt create secret generic xgt-ssl \
  --from-file=server.cert.pem=/path/to/server.cert.pem \
  --from-file=server.key.pem=/path/to/server.key.pem
oc -n xgt create secret generic oidc-ca --from-file=oidc-ca.pem=/path/to/oidc-ca.pem
helm upgrade --install xgt-test ./charts/rocketgraph -n xgt \
  -f charts/rocketgraph/examples/xgt_openshift_restricted.yaml
```

The namespace must already exist, and the certificates and license must match your deployment. The example selects XGT `2.7.1-fips`, disables Mission Control and MongoDB, and sets `openshift.scc: restricted-v2`. This creates a ServiceAccount without an elevated SCC binding. The chart drops capabilities, disables privilege escalation, selects `RuntimeDefault` seccomp, and leaves UID/GID allocation to OpenShift. Do not supply fixed `runAsUser`, `runAsGroup` or `fsGroup` values for this profile.

The chart starts `/opt/xgtd/bin/xgtd` directly. This bypasses the image entrypoint's configuration-copying steps, which need permissions unavailable to an arbitrary UID. Supply a readable license through a Secret, the files PVC described below, or an external license server. The bundled license in the 2.7.1 image is behind a directory an arbitrary UID cannot traverse. In-container SSSD and the bundled License Manager are outside this profile; use OpenShift OAuth or Keycloak for LDAP-backed authentication.

Check the actual admission result after deployment:

```bash
oc -n xgt get pods -l app=xgt \
  -o custom-columns='NAME:.metadata.name,SCC:.metadata.annotations.openshift\.io/scc,UID:.spec.containers[0].securityContext.runAsUser'
```

This profile does not establish FIPS compliance for the complete deployment; the cluster, TLS configuration and other components still need the appropriate configuration.

### FIPS Mode

Set `fips.enabled=true` to use FIPS-compliant images in one step:

```bash
helm install rocketgraph ./charts/rocketgraph --set fips.enabled=true
```

Or in a values file:

```yaml
fips:
  enabled: true
```

It makes the following changes:

- **frontend, backend, xgt, license manager** — `-fips` is appended to the resolved image tag (e.g. `2.7.1` → `2.7.1-fips`).
- **mongodb** — switches to `docker.io/percona/percona-server-mongodb` (configurable via `fips.mongoImage.repository`/`.tag`).

`fips.enabled` only swaps the images.  Production FIPS deployments will typically also want:

- **MongoDB authentication** — see [With MongoDB Authentication](#with-mongodb-authentication).
- **MongoDB TLS** — see [MongoDB TLS](#mongodb-tls).  With `fips.enabled`, `--tlsFIPSMode` is added automatically when TLS is on.
- **Encryption at rest** — see [MongoDB Encryption at Rest](#mongodb-encryption-at-rest).

On OpenShift, the [restricted-v2 profile](#full-stack-with-openshift-restricted-v2) runs Percona with a namespace-assigned UID. Existing storage must be accessible to that identity; do not assume ownership from an earlier deployment will work unchanged.

### With xGT License (direct file)

Mount a single license file directly into xGT:

```bash
kubectl create secret generic xgt-license --from-file=xgtd.lic=/path/to/xgtd.lic -n <namespace>
helm install rocketgraph ./charts/rocketgraph --set openshift.enabled=true --set xgt.license.existingSecret=xgt-license
```

Or pass it inline:

```bash
helm install rocketgraph ./charts/rocketgraph --set-file xgt.license.data=/path/to/xgtd.lic
```

`xgt.license.data` means the license file's text, not database data or base64. Prefer `existingSecret` when another system manages the license; leave `data` empty in that case.

### Bring Your Own xGT Files

By default, the chart generates configuration in a ConfigMap, mounts license/TLS Secrets, and uses separate data/log PVCs. To manage all XGT files on an existing PVC, use [`examples/xgt_existing_files.yaml`](examples/xgt_existing_files.yaml). It selects the claim `xgt-files` and the optional parent directory `xgt-prod`:

```yaml
xgt:
  hostname: xgt-prod-0
  files:
    existingClaim: xgt-files
    subPath: xgt-prod
```

Pre-populate the claim with this layout. Remove the `xgt-prod/` parent if `subPath` is empty:

```text
xgt-prod/
  conf/
    xgtd.conf
    audit.xml
    grouplabel.csv
    label.csv
    oidc-ca.pem
    ssl/certs/server.cert.pem
    ssl/private/server.key.pem
  license/xgtd.lic
  data/
  log/
```

The four directories mount at `/conf`, `/license`, `/data` and `/log`. Configuration and license mounts are read-only. Copy and edit the [example configuration files](examples/xgt_files/), then supply your license and certificates. The example configuration enables TLS and OpenShift OAuth. The storage administrator must make the configuration, keys and license readable by the pod's assigned group, and data/log directories writable. Storage must support the pod's permissions and access mode; an existing claim is not automatically portable between nodes or namespaces.

```bash
helm upgrade --install xgt-prod ./charts/rocketgraph -n xgt \
  -f charts/rocketgraph/examples/xgt_existing_files.yaml
```

In this mode, the chart creates no XGT configuration, license/TLS Secrets, or data/log PVCs. It starts XGT directly and reads the supplied files. Configure TLS, OAuth, memory and label mappings in `xgtd.conf` and the other files; `xgt.extraConfig` and inline configuration do not apply. The chart rejects conflicting sources rather than silently ignoring them. Use the complete example on its own, not layered over a values file containing those sources. `xgt.hostname`, image, resources, service port and health-check settings still apply. Keep XGT's configured memory below the container limit.

To keep data and/or logs on separate existing PVCs, set the corresponding `xgt.persistence` claims. Each override takes precedence over that directory on the common files PVC:

```yaml
xgt:
  files:
    existingClaim: xgt-files
    subPath: xgt-prod  # Optional; applies only to this claim.
  persistence:
    data:
      existingClaim: xgt-data
    log:
      existingClaim: xgt-logs
```

Here, `xgt-prod/conf` and `xgt-prod/license` come from `xgt-files`, while the roots of `xgt-data` and `xgt-logs` mount at `/data` and `/log`. All claims must already exist in the release namespace. The chart does not create these PVCs or copy data between them.

| Existing-claim overrides | Directories kept on the common files PVC |
| --- | --- |
| Neither | `conf`, `license`, `data`, `log` |
| Data only | `conf`, `license`, `log` |
| Logs only | `conf`, `license`, `data` |
| Both | `conf`, `license` |

Only prepare the directories that remain on the common claim. Omit or clear an override to use that directory on the common claim again. See [`examples/xgt_files_separate_data.yaml`](examples/xgt_files_separate_data.yaml) for a complete example with just data separated. Plan file migration before changing claims on an existing release.

After changing configuration on the PVC, explicitly restart XGT:

```bash
oc -n xgt rollout restart deployment/xgt-prod-xgt
```

`/data` remains writable for loading and saving data as the assigned non-root user. For example, copy a CSV to the running server and load it into an existing frame from Python:

```bash
oc -n xgt exec -i deployment/xgt-prod-xgt -- sh -c 'cat > /data/people.csv' < people.csv
```

```python
frame.load("xgtd://people.csv")
```

Server paths are relative to the configured `/data` directory. Files on its PVC survive pod replacement; this does not automatically persist XGT's in-memory frames. Use the [data loading and saving APIs](https://docs.rocketgraph.com/user_ref/graphanalytics/data.html) for that.

For independent servers, use separate claims, or separate parent directories with storage that supports the required concurrent mounts. Never share the same data directory. Helm does not manage or delete an existing claim, and rolling back Helm does not roll back files on it. Changing an existing release from generated files to this mode requires a data migration and PVC retention plan before upgrading.

To manage only configuration externally, set `xgt.config.existingConfigMap` instead. It must contain `xgtd.conf`, `audit.xml`, `grouplabel.csv` and `label.csv`; other file mounts remain managed as usual. Set paths for license, TLS and OAuth CA in that configuration and restart after updates. In particular, a mounted license Secret is at `/license/xgtd.lic` and the OAuth CA mount is at `/etc/ssl/certs/oidc-ca.pem`.

### xGT Startup and Additional Mounts

Use values for deployment customizations so they can be reused on upgrades without editing templates:

```yaml
xgt:
  env:
    - name: SITE_NAME
      value: example
  extraVolumes:
    - name: imports
      persistentVolumeClaim:
        claimName: imports
  extraVolumeMounts:
    - name: imports
      mountPath: /data/imports
      readOnly: true
```

`xgt.command` and `xgt.args` accept Kubernetes command/argument lists. With a custom command, supply its complete arguments. Otherwise, `args` appends to the direct-start arguments in the restricted/PVC profiles, or is passed to the image entrypoint in the default profile. A custom command must preserve startup and health-port behavior. Extra mounts must use distinct names/paths and cannot replace chart mounts; use the existing-configuration or files-PVC options for that purpose.

Keep per-release settings in version-controlled values files and pass them again to `helm upgrade`. Review release notes and rendered manifests before upgrading. If you modify chart templates instead, maintain a fork and merge upstream changes yourself; Helm does not merge customer template edits into an upstream chart.

### With xGT License Manager

The License Manager is a standalone service that serves license files to xGT over port 6200, supporting multiple licenses and multiple xGT replicas. When enabled, `license.location` in xgtd.conf is set automatically.

Create a secret containing one or more license files (each key becomes a file under `/conf/licenses/`):

```bash
kubectl create secret generic xgt-licenses \
  --from-file=server1.lic \
  --from-file=server2.lic \
  -n <namespace>
```

Then enable the license manager:

```yaml
xgt:
  licenseManager:
    enabled: true
    licenseFiles:
      existingSecret: xgt-licenses
```

See [`values-license-manager.yaml`](values-license-manager.yaml) for a complete example you can pass with `-f`.

## Configuration Guides

Step-by-step guides for the chart's optional features.  Each one shows the values to set and any Secret or ConfigMap you need to create first.  For the complete list of every value the chart accepts, see [Values Reference](#values-reference).

### TLS / SSL

#### Frontend HTTPS

To enable HTTPS on the frontend, create a secret with your cert and key:

```bash
kubectl create secret generic frontend-tls --from-file=public.pem --from-file=private.pem -n <namespace>
helm install rocketgraph ./charts/rocketgraph --set frontend.tls.existingSecret=frontend-tls
```

On OpenShift, create a passthrough route to let nginx handle TLS:

```bash
oc create route passthrough <release-name>-frontend --service=<release-name>-frontend --port=https -n <namespace>
```

#### Frontend mTLS

To require client certificates, include a CA chain file in the secret:

```bash
kubectl create secret generic frontend-tls --from-file=public.pem --from-file=private.pem --from-file=chain.pem=ca.pem -n <namespace>
helm install rocketgraph ./charts/rocketgraph --set frontend.tls.existingSecret=frontend-tls
```

The frontend will automatically detect the `chain.pem` and switch to mTLS mode. Clients must present a certificate signed by the CA to connect.

#### xGT SSL

To enable SSL between the backend and xGT:

1. Generate a CA and server certificate for xGT:

```bash
openssl req -x509 -newkey rsa:2048 -keyout xgt-ca-key.pem -out xgt-ca.pem -days 365 -nodes -subj "/CN=xgtCA"
openssl req -newkey rsa:2048 -keyout xgt-key.pem -out xgt.csr -nodes -subj "/CN=<release-name>-xgt"
openssl x509 -req -in xgt.csr -CA xgt-ca.pem -CAkey xgt-ca-key.pem -CAcreateserial -out xgt-cert.pem -days 365
```

1. Create secrets for xGT (server cert + key) and the backend (CA cert to verify xGT):

```bash
kubectl create secret generic xgt-ssl --from-file=server.cert.pem=xgt-cert.pem --from-file=server.key.pem=xgt-key.pem -n <namespace>
kubectl create secret generic backend-tls --from-file=xgt-server.pem=xgt-ca.pem -n <namespace>
```

1. Install with SSL enabled. The `XGT_SERVER_CN` must match the CN used when generating the xGT certificate:

```bash
helm install rocketgraph ./charts/rocketgraph --set openshift.enabled=true --set xgt.ssl.enabled=true --set xgt.ssl.existingSecret=xgt-ssl --set backend.tls.existingSecret=backend-tls --set backend.env.XGT_SERVER_CN=<release-name>-xgt
```

#### xGT Server-side mTLS

To require clients to present a certificate when connecting to xGT (mutual TLS), include a CA chain in the xGT secret and provide client cert/key to the backend:

1. Generate a client certificate signed by your CA:

```bash
openssl req -newkey rsa:2048 -keyout proxy-key.pem -out proxy.csr -nodes -subj "/CN=backend-proxy"
openssl x509 -req -in proxy.csr -CA xgt-ca.pem -CAkey xgt-ca-key.pem -CAcreateserial -out proxy-cert.pem -days 365
```

1. Create the xGT secret with the server cert, key, and CA chain:

```bash
kubectl create secret generic xgt-ssl \
  --from-file=server.cert.pem=xgt-cert.pem \
  --from-file=server.key.pem=xgt-key.pem \
  --from-file=ca-chain.cert.pem=xgt-ca.pem \
  -n <namespace>
```

1. Create the backend secret with the xGT CA cert and client cert/key:

```bash
kubectl create secret generic backend-tls \
  --from-file=xgt-server.pem=xgt-ca.pem \
  --from-file=proxy-client-cert.pem=proxy-cert.pem \
  --from-file=proxy-client-key.pem=proxy-key.pem \
  -n <namespace>
```

1. Install with mTLS enabled on both sides:

```bash
helm install rocketgraph ./charts/rocketgraph \
  --set xgt.ssl.enabled=true \
  --set xgt.ssl.existingSecret=xgt-ssl \
  --set xgt.ssl.mtls=true \
  --set backend.tls.existingSecret=backend-tls \
  --set backend.tls.mtls=true \
  --set backend.env.XGT_SERVER_CN=<release-name>-xgt
```

Users must select **PKIAuth** as the auth type when logging in for the backend to present the client certificate to xGT.

### With MongoDB Authentication

The three MongoDB hardening features below — authentication, TLS, and encryption at rest — are explained in depth in the [MongoDB security guide](../../doc/mongodb_security.md), including how auth enforcement is decided, the upgrade path for a data volume that was initialised without auth, and troubleshooting. The sections here cover the chart values and Secrets; consult that guide for the reasoning and failure modes.

```bash
kubectl create secret generic mongodb-auth \
  --from-literal=mongodb-root-password=secretpass \
  -n <namespace>

helm install rocketgraph ./charts/rocketgraph \
  --set mongodb.auth.enabled=true \
  --set mongodb.auth.existingSecret=mongodb-auth
```

To verify auth is working, exec into the pod and confirm unauthenticated access is denied:

```bash
kubectl exec -it deployment/<release-name>-mongodb -n <namespace> -- mongosh --eval "db.adminCommand('listDatabases')"
```

This should fail with an auth error. Then verify credentials work:

```bash
kubectl exec -it deployment/<release-name>-mongodb -n <namespace> -- mongosh -u admin -p secretpass --authenticationDatabase admin --eval "db.adminCommand('listDatabases')"
```

### MongoDB TLS

Encrypts connections between the backend and MongoDB. MongoDB 5.0+ requires a CA cert even without mTLS.

#### 1. Generate a certificate

The certificate must include `localhost` and `127.0.0.1` in the SAN so that the in-pod health check probes can verify it:

```bash
openssl req -x509 -newkey rsa:2048 -nodes \
  -keyout mongodb-key.pem -out mongodb-cert.pem -days 365 \
  -subj "/CN=<release-name>-mongodb" \
  -addext "subjectAltName=DNS:<release-name>-mongodb,DNS:<release-name>-mongodb.<namespace>.svc.cluster.local,DNS:localhost,IP:127.0.0.1"
```

```powershell
# PowerShell (one line)
openssl req -x509 -newkey rsa:2048 -nodes -keyout mongodb-key.pem -out mongodb-cert.pem -days 365 -subj "/CN=<release-name>-mongodb" -addext "subjectAltName=DNS:<release-name>-mongodb,DNS:<release-name>-mongodb.<namespace>.svc.cluster.local,DNS:localhost,IP:127.0.0.1"
```

#### 2. Create the secret

mongod requires the cert and key concatenated into a single `server.pem` file:

```bash
cat mongodb-cert.pem mongodb-key.pem > server.pem
kubectl create secret generic mongodb-tls --from-file=server.pem=server.pem --from-file=ca.pem=mongodb-cert.pem -n <namespace>
```

```powershell
# PowerShell
Get-Content mongodb-cert.pem, mongodb-key.pem | Set-Content server.pem
kubectl create secret generic mongodb-tls --from-file=server.pem=server.pem --from-file=ca.pem=mongodb-cert.pem -n <namespace>
```

#### 3. Enable TLS

```yaml
mongodb:
  tls:
    enabled: true
    existingSecret: mongodb-tls
```

The backend mounts `ca.pem` from the secret and uses it to verify the MongoDB server certificate. A CA cert is required — the chart will fail at install time if `tls.enabled` is true without either `existingSecret` or `caCert` set.

The default `mode: requireTLS` forces all connections to use TLS. Use `preferTLS` to allow non-TLS clients during migration.

#### FIPS-Mode TLS

When `fips.enabled=true` (see [FIPS Mode](#fips-mode)) and TLS is on, mongod is started with `--tlsFIPSMode` automatically, enforcing FIPS-only cipher suites during the handshake.  `fips.enabled` also supplies the FIPS-capable Percona image, so no separate flag or image override is needed:

```yaml
fips:
  enabled: true
mongodb:
  tls:
    enabled: true
    existingSecret: mongodb-tls
```

#### MongoDB mTLS

To require the backend to present a client certificate, add `client.pem` (cert+key concatenated) to the secret and enable mTLS:

```bash
cat client-cert.pem client-key.pem > client.pem

kubectl create secret generic mongodb-tls \
  --from-file=server.pem=server.pem \
  --from-file=ca.pem=ca.pem \
  --from-file=client.pem=client.pem \
  -n <namespace>
```

```yaml
mongodb:
  tls:
    enabled: true
    existingSecret: mongodb-tls
    mtls: true
```

### MongoDB Encryption at Rest

Encrypts data files on disk using mongod's native WiredTiger encryption engine.

> **Requirement:** The standard `docker.io/library/mongo` image does not support encryption at rest. You must switch to **Percona Server for MongoDB** (or MongoDB Enterprise). The chart will fail at install time if `mongodb.encryption.enabled=true` is set without changing the image.

#### 1. Generate an encryption key

The key must be exactly 32 random bytes, base64-encoded:

```powershell
# PowerShell
$key = [Convert]::ToBase64String((1..32 | ForEach-Object { [byte](Get-Random -Max 256) }))
kubectl create secret generic mongodb-encryption --from-literal=encryption.key=$key -n <namespace>
```

```bash
# bash
kubectl create secret generic mongodb-encryption \
  --from-literal=encryption.key="$(openssl rand -base64 32)" \
  -n <namespace>
```

> **Important:** Store this key securely. If it is lost, the data cannot be recovered.

#### 2. Switch to Percona and enable encryption

```yaml
mongodb:
  image:
    repository: docker.io/percona/percona-server-mongodb
    tag: "latest"
  encryption:
    enabled: true
    existingSecret: mongodb-encryption
```

#### 3. Wipe the existing data volume

The encrypted storage engine cannot read unencrypted data files. Delete the PVC before deploying so MongoDB initializes a fresh encrypted database:

```bash
kubectl delete pvc -l app=mongodb -n <namespace>
```

Then install or upgrade:

```bash
helm upgrade rocketgraph ./charts/rocketgraph -f values.yaml -n <namespace>
```

### External MongoDB

To use an external or managed MongoDB (e.g. Atlas, DocumentDB) instead of deploying one,
create a secret with the connection URI and reference it. Mission Control keeps its data
in its own database (`MissionControl`) on that server — a path component in the URI acts
as the authentication database, not the application database:

```bash
kubectl create secret generic mongodb-external \
  --from-literal=mongodb-uri="mongodb://user:pass@external-host:27017/?authSource=admin" \
  -n <namespace>

helm install rocketgraph ./charts/rocketgraph \
  --set mongodb.enabled=false \
  --set mongodb.externalUriSecret=mongodb-external
```

Alternatively, pass the URI directly (not recommended — credentials are visible in the Deployment spec):

```bash
helm install rocketgraph ./charts/rocketgraph \
  --set mongodb.enabled=false \
  --set mongodb.externalUri='mongodb://user:pass@external-host:27017/?authSource=admin'
```

### External xGT

To connect to an external xGT server instead of deploying one:

```bash
helm install rocketgraph ./charts/rocketgraph \
  --set xgt.enabled=false \
  --set backend.env.MC_DEFAULT_XGT_HOST=xgt.example.com \
  --set backend.env.MC_DEFAULT_XGT_PORT=4367
```

### Separate xGT Releases with Fixed Hostnames

For a complete OpenShift LDAP/OAuth walkthrough with YAML and commands, see the [test-server guide](../../doc/openshift_test_server/README.md).

Chart **0.4.0** adds `xgt.hostname` and `missionControl.enabled`. A fixed container hostname supports a hostname-bound license while keeping xGT managed by Helm:

```yaml
xgt:
  enabled: true
  hostname: xgt-test-0
  license:
    existingSecret: xgt-license
```

The workload remains a one-replica Deployment. Kubernetes generates its pod name, while the operating-system hostname inside the container is `xgt-test-0`, including after pod replacement. This setting does not create a DNS endpoint: clients use the release's Service, such as `rocketgraph-xgt:4367`. Verify the hostname with:

```bash
oc -n xgt exec deployment/rocketgraph-xgt -- cat /proc/sys/kernel/hostname
```

For three independent servers, install one release per server. Start with the full test stack, then disable Mission Control and MongoDB in additional releases:

```bash
helm upgrade --install rocketgraph ./charts/rocketgraph -n xgt \
  -f site-values.yaml --set xgt.hostname=xgt-test-0

helm upgrade --install xgt-dev ./charts/rocketgraph -n xgt \
  -f site-values.yaml --set xgt.hostname=xgt-dev-0 \
  --set missionControl.enabled=false --set mongodb.enabled=false

helm upgrade --install xgt-prod ./charts/rocketgraph -n xgt \
  -f site-values.yaml --set xgt.hostname=xgt-prod-0 \
  --set missionControl.enabled=false --set mongodb.enabled=false
```

Create the namespace and referenced Secrets first. Keep `xgt.enabled=true` in all three releases. Each gets separate xGT configuration, Services and chart-created PVCs; avoid sharing an `existingClaim` between independent servers. Keep these settings on upgrades, preferably in per-release values files. Deleting a release also deletes its chart-created PVCs; plan backups and retention for persistent data.

The test release's Mission Control can connect to all three endpoints. Set its `backend.oidc.xgtAllowedHosts` to `rocketgraph-xgt:4367,xgt-dev-xgt:4367,xgt-prod-xgt:4367`. Provide licenses covering the chosen hostnames and TLS certificates covering the Service names. Mission Control must trust their issuing CAs; leave `backend.env.XGT_SERVER_CN` unset so each endpoint is checked against its own name.

`missionControl.enabled=false` suppresses frontend/backend workloads and their resources, but does not disable MongoDB automatically. xGT-only releases still honor `backend.oidc.caCertExistingSecret` or `backend.oidc.caCert` for the shared OIDC CA mount. All normal `xgt.*` settings continue to apply.

### LDAP Authentication

xGT supports LDAP authentication via PAM/SSSD. When enabled, the chart mounts an SSSD
config into the xGT container. The xGT entrypoint detects it and starts SSSD
automatically. No host-level LDAP configuration is required.

```bash
helm install rocketgraph ./charts/rocketgraph \
  --set xgt.ldap.enabled=true \
  --set xgt.ldap.uri=ldap://ldap.example.org \
  --set xgt.ldap.baseDn=dc=example\,dc=org
```

If your LDAP server requires a bind DN for searches, create a secret with the full sssd.conf
or use inline values (the chart creates a Secret automatically):

```bash
kubectl create secret generic xgt-ldap --from-file=sssd.conf=./sssd.conf -n <namespace>
helm install rocketgraph ./charts/rocketgraph \
  --set xgt.ldap.enabled=true \
  --set xgt.ldap.existingSecret=xgt-ldap
```

Alternatively, you can supply individual LDAP fields (the chart will generate `sssd.conf` for you):

```bash
helm install rocketgraph ./charts/rocketgraph \
  --set xgt.ldap.enabled=true \
  --set xgt.ldap.uri=ldap://ldap.example.org \
  --set xgt.ldap.baseDn=dc=example\,dc=org \
  --set xgt.ldap.bindDn=cn=admin\,dc=example\,dc=org \
  --set-string xgt.ldap.bindPassword=secret
```

> **Tip:** Avoid passing secrets via `--set` in production — they end up in shell history. Use `existingSecret` or a values file instead.

**Note:** Commas in `--set` values must be escaped with `\,` (e.g. `dc=example\,dc=org`).

By default, TLS is required. For `ldaps://` URIs this works automatically. For plain
`ldap://` with STARTTLS, add `--set xgt.ldap.startTls=true`. For non-TLS `ldap://`
connections (testing only), add `--set xgt.ldap.insecure=true`.

#### Custom SSSD Config

For advanced setups (Active Directory, custom schemas, etc.), provide a complete
`sssd.conf` instead of using the individual parameters:

```yaml
xgt:
  ldap:
    enabled: true
    sssdConfig: |
      [sssd]
      services = nss, pam
      domains = AD

      [pam]
      pam_trusted_users = 0

      [domain/AD]
      id_provider = ldap
      auth_provider = ldap
      ldap_uri = ldaps://ad.example.com
      ldap_search_base = dc=example,dc=com
      ldap_id_mapping = true
      ldap_user_name = sAMAccountName
```

When `sssdConfig` is set, the `uri`, `baseDn`, `bindDn`, `startTls`, and `insecure`
fields are all ignored.

> **Note:** `sssdConfig` is multiline — use a values file or `--set-file xgt.ldap.sssdConfig=my-sssd.conf` rather than `--set-string`.

### xGT Configuration

The chart provides sensible defaults for `xgtd.conf`, `grouplabel.csv`, and `label.csv`.
Any of these can be overridden.

#### Custom xgtd.conf Settings

Use `xgt.extraConfig` to override or add any `xgtd.conf` key:

```bash
helm install rocketgraph ./charts/rocketgraph \
  --set xgt.extraConfig."system\.max_memory"=16
```

Or in a values file:

```yaml
xgt:
  extraConfig:
    "system.max_memory": "16"
    "security.labelfile": "/conf/custom-labels.csv"
```

#### Custom Security Label Files

Override the contents of `grouplabel.csv` and `label.csv` using `--set-file`:

```bash
helm install rocketgraph ./charts/rocketgraph \
  --set-file xgt.config.grouplabelCsv=./grouplabel.csv \
  --set-file xgt.config.labelCsv=./label.csv
```

Defaults:

```
# grouplabel.csv        # label.csv
group,label             label
xgtd,xgtadmin           xgtadmin
```

### OIDC Authentication

The existing `OidcAuth` option supports both standard OIDC providers such as
Keycloak and **OpenShift OAuth2**. OpenShift's built-in OAuth server uses the
authorization-code flow; XGT validates its access tokens and reads identity and
groups through the OpenShift User API. Keep the `security.oidc`, `backend.oidc`
and `MC_OIDC_*` configuration names for both integrations.

To enable OIDC login, set `backend.env.XGT_AUTH_TYPES` and configure `xgt.extraConfig.security.oidc`. The backend discovers the issuer, client ID, and scopes from xGT when the issuer or client ID is unset. Supply confidential-client secrets and private CA certificates separately. Override the client ID when Mission Control has its own client; override `frontendUrl` only when the derived public URL is wrong.

See the [OIDC configuration guide](../../doc/oidc_configuration.md) for how the redirect URI is derived, the full environment-variable reference, and the security allowlists (`MC_XGT_ALLOWED_HOSTS`, `MC_OIDC_ALLOWED_ORIGINS`) — that guide includes Kubernetes and OpenShift examples, such as the wildcard patterns needed for StatefulSet pod hostnames and cluster subdomains.

#### Keycloak

Register a confidential client named `mission-control` with Standard flow enabled and callback `https://mc.example.com/api/login/oidc/callback`. Store its secret in `mission-control-oidc` under key `MC_OIDC_CLIENT_SECRET`. Keep the Python browser client `xgtd-client` public with PKCE `S256` and callback `http://127.0.0.1:8765/callback`. Mission Control 2.7.0 does not send PKCE, so do not require it on the confidential client.

```yaml
backend:
  env:
    XGT_AUTH_TYPES: "['OidcAuth']"
    MC_DEFAULT_XGT_PORT: '4367'
  oidc:
    clientId: mission-control
    existingSecret: mission-control-oidc

xgt:
  extraConfig:
    security.oidc:
      validation_mode: jwt
      issuer: https://idp.example.com/realms/xgt
      audience: xgtd-client
      client_id: xgtd-client
      username_claim: preferred_username
      groups_claim: groups
      scopes: openid profile email
```

Both clients need Group Membership and Audience mappers in their access tokens, with audience `xgtd-client` and claim `groups`. The backend discovers the issuer and scopes from xGT while using its own client ID. Add private-CA settings below if needed. For upstream HTTPS termination, set `frontend.tls.external: true`; if proxy headers produce the wrong origin, also set `backend.oidc.frontendUrl` to the public HTTPS URL.

#### OpenShift OAuth

This is OAuth2 authentication through `OidcAuth`, with
`validation_mode: openshift_userapi`. Mission Control needs the OAuthClient's
secret to exchange authorization codes for tokens. XGT validates the resulting
tokens through the User API and does not need that client secret. The
OAuthClient's name is the client ID; `existingSecret` below instead names the
Kubernetes Secret containing the client secret.

```yaml
frontend:
  tls:
    external: true  # HTTPS terminates at the edge Route.
backend:
  env:
    XGT_AUTH_TYPES: "['OidcAuth']"
    MC_DEFAULT_XGT_PORT: '4367'
  oidc:
    existingSecret: openshift-oauth-client
    caCertExistingSecret: oidc-ca
    tlsVerify: /etc/ssl/certs/oidc-ca.pem
    # Set only if the proxy derives the wrong public origin:
    frontendUrl: https://mc.apps.cluster.example.com

xgt:
  extraConfig:
    security.oidc:
      issuer: https://oauth-openshift.apps.cluster.example.com
      validation_mode: openshift_userapi
      client_id: <oauthclient-name>
      openshift_user_api_uri: https://api.cluster.example.com:6443/apis/user.openshift.io/v1/users/~
      username_claim: metadata.name
      scopes: user:info
      groups_claim: groups
```

Create `openshift-oauth-client` with key `MC_OIDC_CLIENT_SECRET`, matching the OAuthClient's secret. Create `oidc-ca` as shown below, with a CA bundle that trusts both the OAuth and User API endpoints. The OAuthClient must allow `user:info` in `scopeRestrictions` and contain `https://mc.apps.cluster.example.com/api/login/oidc/callback` in `redirectURIs`. Include the Python loopback callback if that client also uses this OAuthClient.

Issuer, client ID, and `user:info` are discovered from xGT. The callback is derived from the public frontend URL, so `redirectUri` need not also be set. Omit the CA settings when the endpoints are already trusted. See the [OIDC guide](../../doc/oidc_configuration.md#ldap-groups-and-automated-accounts) for LDAP group synchronization, automation, and login verification.

#### CA Certificates

If the identity provider uses a private or self-signed CA, create a secret and reference it.
The cert is automatically mounted into both the backend and xGT, and `security.oidc.ca_cert`
is injected into xGT's config automatically.

```bash
kubectl create secret generic oidc-ca --from-file=oidc-ca.pem=/path/to/ca.pem -n <namespace>
```

```yaml
backend:
  oidc:
    caCertExistingSecret: oidc-ca
    tlsVerify: /etc/ssl/certs/oidc-ca.pem
```

The mount supplies the certificate file; `tlsVerify` selects that file for backend HTTPS verification. Both are needed when the CA is not already trusted.

### Site Configuration

The backend supports site configuration files for customizing LLM providers, models,
and behavior. The `site_config.yml` is deep-merged with the base LLM config, allowing
you to add custom providers, override model defaults, or enable/disable models. The
`site_config.py` allows custom Python logic for LLM configuration (e.g. custom auth,
endpoint routing).

```bash
helm install rocketgraph ./charts/rocketgraph \
  --set-file backend.siteConfig.yml=./site_config.yml \
  --set-file backend.siteConfig.py=./site_config.py
```

The values above pass the files to the chart; what goes *inside* them is documented in the [site LLM configuration guide](../../doc/llm_site_config.md) — the full schema, the available models and templates, worked examples for internal OpenAI-compatible endpoints and local Ollama models, and the Python callback API. Ignore that guide's `MC_SITE_CONFIG_YML`/`MC_SITE_CONFIG_PY` environment variables, which are the Compose equivalent of these two `--set-file` flags; everything else applies unchanged.

### ODBC / IBM iAccess

To connect xGT to external databases via ODBC, enable the ODBC PVC and populate it with your driver files. Which files, and what belongs in the `odbcinst.ini` / `odbc.ini` you place alongside them, is covered by the [ODBC configuration guide](../../doc/odbc_configuration.md) — including the PostgreSQL and MariaDB drivers that ship preinstalled, the IBM i Access setup, and connection testing. Substitute this PVC for that guide's `MC_ODBC_PATH` host directory; the in-container paths and `.ini` contents are the same.

```bash
helm install rocketgraph ./charts/rocketgraph \
  --set backend.odbc.enabled=true \
  --set backend.env.MC_ODBC_LIBRARY_PATH=/opt/ibm/iaccess/lib64/
```

For IBM iAccess:

```bash
helm install rocketgraph ./charts/rocketgraph \
  --set backend.iaccess.enabled=true
```

### Backend-to-xGT mTLS

To require the backend to present a client certificate when connecting to xGT (mutual TLS),
include the proxy client cert and key in the backend TLS secret and set the corresponding
values so the chart injects the required environment variables:

```bash
kubectl create secret generic backend-tls \
  --from-file=xgt-server.pem=xgt-ca.pem \
  --from-file=proxy-client-cert.pem=proxy-cert.pem \
  --from-file=proxy-client-key.pem=proxy-key.pem \
  -n <namespace>

helm install rocketgraph ./charts/rocketgraph \
  --set backend.tls.existingSecret=backend-tls \
  --set backend.tls.mtls=true
```

Users must select **PKIAuth** as the auth type when logging in for the backend to present the client certificate. `BasicAuth` does not send client certificates.

## Values Reference

Every value the chart accepts, with its default.  For worked examples showing how to combine them, see [Configuration Guides](#configuration-guides).

### Images

| Parameter                   | Description        | Default                                          |
|-----------------------------|--------------------|--------------------------------------------------|
| `frontend.image.repository` | Frontend image     | `docker.io/rocketgraph/mission-control-frontend` |
| `frontend.image.tag`        | Frontend image tag | `Chart.appVersion`                               |
| `frontend.image.pullPolicy` | Pull policy        | `IfNotPresent`                                   |
| `backend.image.repository`  | Backend image      | `docker.io/rocketgraph/mission-control-backend`  |
| `backend.image.tag`         | Backend image tag  | `Chart.appVersion`                               |
| `backend.image.pullPolicy`  | Pull policy        | `IfNotPresent`                                   |
| `mongodb.image.repository`  | MongoDB image      | `docker.io/library/mongo`                        |
| `mongodb.image.tag`         | MongoDB image tag  | `8.0.23`                                         |
| `xgt.image.repository`      | xGT image          | `docker.io/rocketgraph/xgt`                      |
| `xgt.image.tag`             | xGT image tag      | `Chart.appVersion`                               |

### Replicas

| Parameter           | Description       | Default |
|---------------------|-------------------|---------|
| `frontend.replicas` | Frontend replicas | `1`     |
| `backend.replicas`  | Backend replicas  | `1`     |
| `mongodb.replicas`  | MongoDB replicas  | `1`     |
| `xgt.replicas`      | xGT replicas      | `1`     |

> **Note:** `backend`, `mongodb`, and `xgt` are locked to `replicas: 1` and enforced by a pre-install
> validation. The backend does not share session state across instances; MongoDB is deployed as a
> standalone node with no replica set; xGT has no data replication between instances. The frontend
> is the only component that can be scaled freely. To handle more load, deploy multiple independent
> chart releases and route users to a specific release.

### Services

| Parameter                    | Description           | Default     |
|------------------------------|-----------------------|-------------|
| `frontend.service.type`      | Frontend service type | `ClusterIP` |
| `frontend.service.httpPort`  | HTTP port             | `80`        |
| `frontend.service.httpsPort` | HTTPS port            | `443`       |
| `xgt.service.type`           | xGT service type      | `ClusterIP` |
| `xgt.port`                   | xGT port              | `4367`      |

### Ingress

An Ingress resource is included but disabled by default. Enable it to expose the frontend at a hostname through your cluster's ingress controller:

```yaml
ingress:
  enabled: true
  className: nginx
  annotations:
    cert-manager.io/cluster-issuer: letsencrypt-prod
  hosts:
    - host: rocketgraph.example.com
      paths:
        - path: /
          pathType: Prefix
  tls:
    - secretName: rocketgraph-tls
      hosts:
        - rocketgraph.example.com
```

The Ingress routes to the frontend service on port 80. The ingress controller terminates TLS before forwarding, so `frontend.tls` certificates are not needed when using Ingress TLS — but set `frontend.tls.external=true` so the backend knows users connect over HTTPS and marks session cookies `Secure`. The same applies to an edge-terminated OpenShift route.

| Parameter              | Description                                                | Default         |
|------------------------|------------------------------------------------------------|-----------------|
| `ingress.enabled`      | Create an Ingress resource                                 | `false`         |
| `ingress.className`    | `spec.ingressClassName` (e.g. `nginx`, `alb`)              | `""`            |
| `ingress.annotations`  | Annotations for the ingress controller                     | `{}`            |
| `ingress.hosts`        | List of host/path rules                                    | see values.yaml |
| `ingress.tls`          | TLS configuration (secretName + hosts)                     | `[]`            |

### TLS Parameters

| Parameter                     | Description                                                                                   | Default |
|-------------------------------|-----------------------------------------------------------------------------------------------|---------|
| `frontend.tls.existingSecret` | Secret with keys: `public.pem`, `private.pem`, optionally `chain.pem` for mTLS                | `""`    |
| `frontend.tls.publicCert`     | Inline public cert PEM                                                                        | `""`    |
| `frontend.tls.privateKey`     | Inline private key PEM                                                                        | `""`    |
| `frontend.tls.certChain`      | Inline cert chain PEM (enables mTLS)                                                          | `""`    |
| `frontend.tls.external`       | TLS terminated upstream (Ingress TLS / edge route); marks session cookies `Secure`           | `false` |
| `backend.tls.existingSecret`  | Secret with keys: `xgt-server.pem`, optionally `proxy-client-cert.pem`/`proxy-client-key.pem` | `""`    |
| `backend.tls.xgtServerCert`   | Inline xGT server CA cert PEM                                                                 | `""`    |
| `backend.tls.proxyClientCert` | Inline proxy client cert PEM                                                                  | `""`    |
| `backend.tls.proxyClientKey`  | Inline proxy client key PEM                                                                   | `""`    |
| `backend.tls.mtls`            | Enable mTLS for backend connections to xGT (requires `existingSecret` or inline cert+key)     | `false` |
| `xgt.ssl.enabled`             | Enable SSL on xGT server                                                                      | `false` |
| `xgt.ssl.existingSecret`      | Secret with keys: `server.cert.pem`, `server.key.pem`, optionally `ca-chain.cert.pem`         | `""`    |
| `xgt.ssl.cert`                | Inline xGT server cert PEM                                                                    | `""`    |
| `xgt.ssl.key`                 | Inline xGT server key PEM                                                                     | `""`    |
| `xgt.ssl.mtls`                | Require client certificates on xGT server (needs `ca-chain.cert.pem` in secret or `caCert`)   | `false` |
| `xgt.ssl.caCert`              | Inline CA cert PEM for validating client certs (`ca-chain.cert.pem`)                          | `""`    |

### Backend Environment

| Parameter                           | Description                                           | Default                                      |
|-------------------------------------|-------------------------------------------------------|----------------------------------------------|
| `backend.env.MC_DEFAULT_XGT_HOST`  | xGT hostname                                           | Auto-detected from release name              |
| `backend.env.MC_DEFAULT_XGT_PORT`  | xGT port                                               | `""`                                         |
| `backend.env.MC_SESSION_TTL`       | Session TTL                                            | `""`                                         |
| `backend.env.XGT_SERVER_CN`        | xGT server CN (required when SSL enabled)              | `""`                                         |
| `backend.env.XGT_AUTH_TYPES`       | Login methods (`[]` for single-user mode)              | `"['BasicAuth','FilePKIAuth','PKIAuth']"`    |
| `backend.env.MC_ODBC_LIBRARY_PATH` | ODBC library path                                      | `""`                                         |
| `backend.env.MC_PORT`              | Frontend HTTP port (used to derive OIDC redirect URI)  | `frontend.service.httpPort`                  |
| `backend.env.MC_SSL_PORT`          | Frontend HTTPS port (used to derive OIDC redirect URI) | `frontend.service.httpsPort`                 |
| `backend.siteConfig.yml`           | LLM config overrides (merged with base config)         | `""`                                         |
| `backend.siteConfig.py`            | Custom Python LLM config module                        | `""`                                         |

### OIDC Parameters

| Parameter                          | Description                                                                                    | Default |
|------------------------------------|------------------------------------------------------------------------------------------------|---------|
| `backend.oidc.issuer`              | Override OIDC issuer URL (auto-discovered from xGT if empty)                                   | `""`    |
| `backend.oidc.clientId`            | Override OAuth2 client ID (auto-discovered from xGT if empty)                                  | `""`    |
| `backend.oidc.clientSecret`        | Client secret — inline value creates a Secret                                                  | `""`    |
| `backend.oidc.existingSecret`      | Existing Secret with key `MC_OIDC_CLIENT_SECRET`                                               | `""`    |
| `backend.oidc.scopes`              | Optional scope override; uses xGT-advertised scopes during discovery when empty                | `""`    |
| `backend.oidc.frontendUrl`         | Override public frontend origin for post-login redirects and the derived callback              | `""`    |
| `backend.oidc.redirectUri`         | Override redirect URI sent to the IdP                                                          | `""`    |
| `backend.oidc.allowedOrigins`      | Comma-separated allowed origins (defense-in-depth, optional)                                   | `""`    |
| `backend.oidc.tlsVerify`           | `true`, `false`, or path to CA bundle for OIDC HTTP calls                                      | `""`    |
| `backend.oidc.caCert`              | Inline CA PEM — creates a Secret, mounted into backend and xGT at `/etc/ssl/certs/oidc-ca.pem` | `""`    |
| `backend.oidc.caCertExistingSecret`| Existing Secret with key `oidc-ca.pem`                                                         | `""`    |
| `backend.oidc.xgtAllowedHosts`     | xGT host:port allowlist (SSRF prevention). Defaults to internal xGT service.                   | `""`    |

### Persistence

| Parameter                            | Description            | Default |
|--------------------------------------|------------------------|---------|
| `mongodb.persistence.size`           | MongoDB volume size    | `1Gi`   |
| `mongodb.persistence.existingClaim`  | Use existing PVC       | `""`    |
| `xgt.persistence.data.size`          | xGT data volume size   | `10Gi`  |
| `xgt.persistence.data.existingClaim` | Use existing PVC       | `""`    |
| `xgt.persistence.log.size`           | xGT log volume size    | `1Gi`   |
| `xgt.persistence.log.existingClaim`  | Use existing PVC       | `""`    |
| `backend.odbc.enabled`               | Enable ODBC driver PVC | `false` |
| `backend.odbc.storageSize`           | ODBC volume size       | `1Gi`   |
| `backend.iaccess.enabled`            | Enable IBM iAccess PVC | `false` |
| `backend.iaccess.storageSize`        | iAccess volume size    | `1Gi`   |

### MongoDB

| Parameter                           | Description                                                                                                              | Default       |
|-------------------------------------|--------------------------------------------------------------------------------------------------------------------------|---------------|
| `mongodb.enabled`                   | Deploy MongoDB as part of the release                                                                                    | `true`        |
| `mongodb.externalUri`               | MongoDB connection URI when `mongodb.enabled=false`                                                                      | `""`          |
| `mongodb.externalUriSecret`         | Secret with key `mongodb-uri` (preferred over `externalUri`)                                                             | `""`          |
| `mongodb.auth.enabled`              | Enable MongoDB authentication                                                                                            | `false`       |
| `mongodb.auth.existingSecret`       | Secret with key: `mongodb-root-password` (the root user is always `rocketgraph`)                                         | `""`          |
| `mongodb.auth.rootPassword`         | Root password (ignored if existingSecret is set). The root user is always `rocketgraph`                                  | `""`          |
| `mongodb.tls.enabled`               | Enable TLS for MongoDB connections                                                                                       | `false`       |
| `mongodb.tls.existingSecret`        | Secret with keys: `server.pem` (cert+key); optional: `ca.pem`, `client.pem`                                              | `""`          |
| `mongodb.tls.cert`                  | Inline server cert PEM                                                                                                   | `""`          |
| `mongodb.tls.key`                   | Inline server key PEM                                                                                                    | `""`          |
| `mongodb.tls.caCert`                | Inline CA cert PEM — used by backend to verify server; required for mTLS                                                 | `""`          |
| `mongodb.tls.mode`                  | mongod TLS mode: `requireTLS`, `preferTLS`, `allowTLS`                                                                   | `requireTLS`  |
| `mongodb.tls.mtls`                  | Require backend to present a client cert (`client.pem` in secret)                                                        | `false`       |
| `mongodb.encryption.enabled`        | Enable encryption at rest — requires Percona or MongoDB Enterprise image (chart will fail if set with the default image) | `false`       |
| `mongodb.encryption.existingSecret` | Secret with key: `encryption.key`                                                                                        | `""`          |
| `mongodb.encryption.key`            | Inline encryption key                                                                                                    | `""`          |

### xGT Parameters

| Parameter                   | Description                          | Default        |
|-----------------------------|--------------------------------------|----------------|
| `xgt.enabled`               | Deploy xGT as part of the release    | `true`         |
| `xgt.hostname`              | Fixed container OS hostname for licensing; does not change the pod or Service name | `""` |
| `xgt.files.existingClaim`   | Common PVC for conf/license/data/log; separate data/log existing claims override their mounts | `""` |
| `xgt.files.subPath`         | Optional relative parent directory on the common files PVC; does not apply to separate data/log claims | `""` |
| `xgt.persistence.data.existingClaim` | Existing data PVC mounted at `/data`; takes precedence over the files PVC | `""` |
| `xgt.persistence.log.existingClaim` | Existing log PVC mounted at `/log`; takes precedence over the files PVC | `""` |
| `xgt.config.existingConfigMap` | Existing complete configuration ConfigMap | `""` |
| `xgt.command` / `xgt.args`  | Container command override / arguments | `[]` |
| `xgt.env`                  | Additional Kubernetes environment entries | `[]` |
| `xgt.extraVolumes` / `xgt.extraVolumeMounts` | Additional Kubernetes volumes / container mounts | `[]` |
| `xgt.config.grouplabelCsv`  | Override grouplabel.csv contents     | `""`           |
| `xgt.config.labelCsv`       | Override label.csv contents          | `""`           |
| `xgt.extraConfig`           | Extra xgtd.conf key-value overrides  | `{}`           |
| `xgt.ldap.enabled`          | Enable LDAP auth via SSSD            | `false`        |
| `xgt.ldap.existingSecret`   | Existing Secret with `sssd.conf` key | `""`           |
| `xgt.ldap.uri`              | LDAP server URI                      | `""`           |
| `xgt.ldap.baseDn`           | LDAP search base DN                  | `""`           |
| `xgt.ldap.bindDn`           | LDAP bind DN (optional)              | `""`           |
| `xgt.ldap.bindPassword`     | LDAP bind password (optional)        | `""`           |
| `xgt.ldap.startTls`         | Enable STARTTLS for LDAP             | `false`        |
| `xgt.ldap.insecure`         | Disable TLS entirely (testing only)  | `false`        |
| `xgt.ldap.sssdConfig`       | Raw sssd.conf (overrides above)      | `""`           |

### Other

| Parameter                    | Description                                                      | Default   |
|------------------------------|------------------------------------------------------------------|-----------|
| `imagePullSecrets`           | Pull secrets applied to every pod, for private or mirrored registries | `[]` |
| `missionControl.enabled`    | Deploy frontend/backend and their resources; disable MongoDB separately for an xGT-only release | `true` |
| `fips.enabled`               | Use FIPS images (`-fips` tags + Percona MongoDB); see FIPS Mode  | `false`   |
| `fips.mongoImage.repository` | FIPS MongoDB image repository                                    | `docker.io/percona/percona-server-mongodb` |
| `fips.mongoImage.tag`        | FIPS MongoDB image tag                                           | `8.0.23`  |
| `openshift.enabled`          | Create a ServiceAccount and configure the selected SCC profile | `false`   |
| `openshift.scc`              | `anyuid`, `nonroot`, or `restricted-v2` for XGT/Mission Control/MongoDB (no elevated binding) | `anyuid` |
| `networkPolicy.enabled`      | Restrict inter-component traffic with per-component policies     | `true`    |
| `xgt.license.existingSecret` | Secret with key `xgtd.lic` (direct file mount)                   | `""`      |
| `xgt.license.data`           | Inline license content (use `--set-file`)                        | `""`      |

### License Manager Parameters

| Parameter                                          | Description                                                                 | Default                                     |
|----------------------------------------------------|-----------------------------------------------------------------------------|---------------------------------------------|
| `xgt.licenseManager.enabled`                       | Enable the License Manager deployment                                       | `false`                                     |
| `xgt.licenseManager.image.repository`              | License Manager image                                                       | `docker.io/rocketgraph/xgt-license-manager` |
| `xgt.licenseManager.image.pullPolicy`              | Image pull policy                                                           | `IfNotPresent`                              |
| `xgt.licenseManager.image.tag`                     | License Manager image tag                                                   | `1.5.1`                                     |
| `xgt.licenseManager.licenseFiles.existingSecret`   | Secret whose keys are mounted as license files under `/conf/licenses/`      | `""`                                        |
| `xgt.licenseManager.licenseFiles.data`             | Map of filename to license content (creates a Secret)                       | `{}`                                        |
| `xgt.licenseManager.persistence.conf.size`         | PVC size for `/conf`                                                        | `1Gi`                                       |
| `xgt.licenseManager.persistence.conf.existingClaim`| Existing PVC for `/conf`                                                    | `""`                                        |
| `xgt.licenseManager.persistence.log.size`          | PVC size for `/log`                                                         | `1Gi`                                       |
| `xgt.licenseManager.persistence.log.existingClaim` | Existing PVC for `/log`                                                     | `""`                                        |
| `xgt.licenseManager.resources`                     | Resource requests/limits                                                    | `{}`                                        |

## Uninstallation

```bash
helm uninstall rocketgraph
```

Note: PersistentVolumeClaims are not deleted automatically. To remove data:

```bash
kubectl delete pvc -l app.kubernetes.io/instance=rocketgraph
```

## Related Guides

These guides apply to every deployment of Mission Control, not just Kubernetes and OpenShift. Their step-by-step examples are written for Docker Compose, so read host paths and `MC_*` environment variables as their chart equivalents — a PVC or Secret instead of a bind mount, a `backend.env.*` value instead of an `.env` line. The concepts, file formats, and troubleshooting apply unchanged.

| Guide | Covers | Chart equivalent |
|---|---|---|
| [MongoDB Security](../../doc/mongodb_security.md) | Authentication, TLS, mTLS, encryption at rest; enforcement rules and upgrade path | [With MongoDB Authentication](#with-mongodb-authentication), [MongoDB TLS](#mongodb-tls), [MongoDB Encryption at Rest](#mongodb-encryption-at-rest) |
| [OIDC Authentication](../../doc/oidc_configuration.md) | Redirect URI derivation, env vars, security allowlists, Keycloak and OpenShift examples | [OIDC Authentication](#oidc-authentication), [OIDC Parameters](#oidc-parameters) |
| [Site LLM Configuration](../../doc/llm_site_config.md) | `site_config.yml` schema, model and template reference, Python callback API | [Site Configuration](#site-configuration) |
| [ODBC Configuration](../../doc/odbc_configuration.md) | Driver files, `.ini` setup, PostgreSQL / MariaDB / IBM i, connection testing | [ODBC / IBM iAccess](#odbc--ibm-iaccess) |
| [Deployment Reference](../../doc/deployment_reference.md) | Per-container images, ports, volume mount paths, and env vars | Useful when writing custom manifests or debugging a pod spec |

The [main README](../../README.md) documents the Docker Compose and Podman install paths and carries the authoritative environment-variable table.
