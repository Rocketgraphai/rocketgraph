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

That's it. All components deploy with sensible defaults. See `values-simple.yaml` for the minimal configuration and `values.yaml` for all available options.

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

After installing, expose the frontend and get the URL:

```bash
oc expose svc/<release-name>-frontend
oc get route <release-name>-frontend -o jsonpath='{.spec.host}'
```

### With xGT License

Create a secret from your license file, then reference it:

```bash
kubectl create secret generic xgt-license --from-file=xgtd.lic=/path/to/xgtd.lic -n <namespace>
helm install rocketgraph ./charts/rocketgraph --set openshift.enabled=true --set xgt.license.existingSecret=xgt-license
```

Or pass it inline:

```bash
helm install rocketgraph ./charts/rocketgraph --set-file xgt.license.data=/path/to/xgtd.lic
```

### With MongoDB Authentication

```bash
kubectl create secret generic mongodb-auth \
  --from-literal=mongodb-root-username=admin \
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

### External MongoDB

To use an external or managed MongoDB (e.g. Atlas, DocumentDB) instead of deploying one,
create a secret with the connection URI and reference it:

```bash
kubectl create secret generic mongodb-external \
  --from-literal=mongodb-uri="mongodb://user:pass@external-host:27017/dbname" \
  -n <namespace>

helm install rocketgraph ./charts/rocketgraph \
  --set mongodb.enabled=false \
  --set mongodb.externalUriSecret=mongodb-external
```

Alternatively, pass the URI directly (not recommended — credentials are visible in the Deployment spec):

```bash
helm install rocketgraph ./charts/rocketgraph \
  --set mongodb.enabled=false \
  --set mongodb.externalUri=mongodb://user:pass@external-host:27017/dbname
```

### External xGT

To connect to an external xGT server instead of deploying one:

```bash
helm install rocketgraph ./charts/rocketgraph \
  --set xgt.enabled=false \
  --set backend.env.MC_DEFAULT_XGT_HOST=xgt.example.com \
  --set backend.env.MC_DEFAULT_XGT_PORT=4367
```

## Uninstallation

```bash
helm uninstall rocketgraph
```

Note: PersistentVolumeClaims are not deleted automatically. To remove data:

```bash
kubectl delete pvc -l app.kubernetes.io/instance=rocketgraph
```

## Advanced Configuration

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

The frontend will automatically detect the `chain.pem` and switch to mTLS mode.
Clients must present a certificate signed by the CA to connect.

#### xGT SSL

To enable SSL between the backend and xGT:

1. Generate a CA and server certificate for xGT:

```bash
openssl req -x509 -newkey rsa:2048 -keyout xgt-ca-key.pem -out xgt-ca.pem -days 365 -nodes -subj "/CN=xgtCA"
openssl req -newkey rsa:2048 -keyout xgt-key.pem -out xgt.csr -nodes -subj "/CN=<release-name>-xgt"
openssl x509 -req -in xgt.csr -CA xgt-ca.pem -CAkey xgt-ca-key.pem -CAcreateserial -out xgt-cert.pem -days 365
```

2. Create secrets for xGT (server cert + key) and the backend (CA cert to verify xGT):

```bash
kubectl create secret generic xgt-ssl --from-file=server.cert.pem=xgt-cert.pem --from-file=server.key.pem=xgt-key.pem -n <namespace>
kubectl create secret generic backend-tls --from-file=xgt-server.pem=xgt-ca.pem -n <namespace>
```

3. Install with SSL enabled. The `XGT_SERVER_CN` must match the CN used when generating the xGT certificate:

```bash
helm install rocketgraph ./charts/rocketgraph --set openshift.enabled=true --set xgt.ssl.enabled=true --set xgt.ssl.existingSecret=xgt-ssl --set backend.tls.existingSecret=backend-tls --set backend.env.XGT_SERVER_CN=<release-name>-xgt
```

#### xGT Server-side mTLS

To require clients to present a certificate when connecting to xGT (mutual TLS), include a CA
chain in the xGT secret and provide client cert/key to the backend:

1. Generate a client certificate signed by your CA:

```bash
openssl req -newkey rsa:2048 -keyout proxy-key.pem -out proxy.csr -nodes -subj "/CN=backend-proxy"
openssl x509 -req -in proxy.csr -CA xgt-ca.pem -CAkey xgt-ca-key.pem -CAcreateserial -out proxy-cert.pem -days 365
```

2. Create the xGT secret with the server cert, key, and CA chain:

```bash
kubectl create secret generic xgt-ssl \
  --from-file=server.cert.pem=xgt-cert.pem \
  --from-file=server.key.pem=xgt-key.pem \
  --from-file=ca-chain.cert.pem=xgt-ca.pem \
  -n <namespace>
```

3. Create the backend secret with the xGT CA cert and client cert/key:

```bash
kubectl create secret generic backend-tls \
  --from-file=xgt-server.pem=xgt-ca.pem \
  --from-file=proxy-client-cert.pem=proxy-cert.pem \
  --from-file=proxy-client-key.pem=proxy-key.pem \
  -n <namespace>
```

4. Install with mTLS enabled on both sides:

```bash
helm install rocketgraph ./charts/rocketgraph \
  --set xgt.ssl.enabled=true \
  --set xgt.ssl.existingSecret=xgt-ssl \
  --set xgt.ssl.mtls=true \
  --set backend.tls.existingSecret=backend-tls \
  --set backend.tls.mtls=true \
  --set backend.env.XGT_SERVER_CN=<release-name>-xgt
```

Users must select **PKIAuth** as the auth type when logging in for the backend to present
the client certificate to xGT.

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

#### Compatibility Mode

For older xGT images that don't have SSSD built in, enable compat mode. This installs
SSSD and configures PAM at container startup:

```bash
helm install rocketgraph ./charts/rocketgraph \
  --set xgt.ldap.enabled=true \
  --set compat.installSssd=true \
  --set xgt.ldap.uri=ldap://ldap.example.org \
  --set xgt.ldap.baseDn=dc=example\,dc=org
```

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

To enable OIDC login, set `XGT_AUTH_TYPES` and configure the xGT OIDC section.
In most cases the backend discovers the issuer and client ID automatically from xGT —
no `backend.oidc.*` overrides are needed.

#### Keycloak

```yaml
backend:
  env:
    XGT_AUTH_TYPES: "['OidcAuth']"

xgt:
  extraConfig:
    security.oidc:
      validation_mode: introspection
      issuer: https://idp.example.com/realms/xgt
      jwks_uri: https://idp.example.com/realms/xgt/protocol/openid-connect/certs
      audience: xgtd-client
      client_id: xgtd-client
      username_claim: preferred_username
      groups_claim: groups
      introspection_client_id: xgtd-introspection
      introspection_client_secret: <secret>
```

#### OpenShift

```yaml
backend:
  env:
    XGT_AUTH_TYPES: "['OidcAuth']"
  oidc:
    tlsVerify: "false"   # or provide caCertExistingSecret

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

The OAuthClient must have `https://<frontend-route>/api/login/oidc/callback` in its `redirectURIs` list.

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
```

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

### ODBC / IBM iAccess

To connect xGT to external databases via ODBC, enable the ODBC PVC and populate it with
your driver files:

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

Users must select **PKIAuth** as the auth type when logging in for the backend to present
the client certificate. `BasicAuth` does not send client certificates.

## Configuration

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
| `mongodb.image.tag`         | MongoDB image tag  | `latest`                                         |
| `xgt.image.repository`      | xGT image          | `docker.io/rocketgraph/xgt`                      |
| `xgt.image.tag`             | xGT image tag      | `Chart.appVersion`                               |

### Replicas

| Parameter           | Description       | Default |
|---------------------|-------------------|---------|
| `frontend.replicas` | Frontend replicas | `1`     |
| `backend.replicas`  | Backend replicas  | `1`     |
| `mongodb.replicas`  | MongoDB replicas  | `1`     |
| `xgt.replicas`      | xGT replicas      | `1`     |

> **Note:** Only the frontend is fully stateless and supports multiple replicas without limitation.
> The backend uses filesystem-based sessions and a per-pod JWT secret key — `sessionAffinity: ClientIP`
> is used to pin clients to a single pod, but this is best-effort and not guaranteed (e.g. behind a
> proxy or load balancer all clients may share the same source IP). xGT is an in-memory store with no
> replication support — multiple xGT replicas are independent instances with separate data.
> `sessionAffinity: ClientIP` pins clients to the same xGT pod so users do not need to manually
> specify an instance, though this is subject to the same best-effort caveats as the backend.
> For more reliable data isolation and load balancing, it is recommended to shard users across
> multiple independent chart deployments rather than using replicas.

### Services

| Parameter                    | Description           | Default     |
|------------------------------|-----------------------|-------------|
| `frontend.service.type`      | Frontend service type | `ClusterIP` |
| `frontend.service.httpPort`  | HTTP port             | `80`        |
| `frontend.service.httpsPort` | HTTPS port            | `443`       |
| `xgt.service.type`           | xGT service type      | `ClusterIP` |
| `xgt.port`                   | xGT port              | `4367`      |

### TLS Parameters

| Parameter                     | Description                                                                          | Default |
|-------------------------------|--------------------------------------------------------------------------------------|---------|
| `frontend.tls.existingSecret` | Secret with keys: `public.pem`, `private.pem`, optionally `chain.pem` for mTLS       | `""`    |
| `frontend.tls.publicCert`     | Inline public cert PEM                                                               | `""`    |
| `frontend.tls.privateKey`     | Inline private key PEM                                                               | `""`    |
| `frontend.tls.certChain`      | Inline cert chain PEM (enables mTLS)                                                 | `""`    |
| `backend.tls.existingSecret`  | Secret with keys: `xgt-server.pem`, optionally `proxy-client-cert.pem`/`proxy-client-key.pem` | `""`    |
| `backend.tls.xgtServerCert`   | Inline xGT server CA cert PEM                                                                  | `""`    |
| `backend.tls.proxyClientCert` | Inline proxy client cert PEM                                                                   | `""`    |
| `backend.tls.proxyClientKey`  | Inline proxy client key PEM                                                                    | `""`    |
| `backend.tls.mtls`            | Enable mTLS for backend connections to xGT (requires `existingSecret` or inline cert+key)     | `false` |
| `xgt.ssl.enabled`             | Enable SSL on xGT server                                                                       | `false` |
| `xgt.ssl.existingSecret`      | Secret with keys: `server.cert.pem`, `server.key.pem`, optionally `ca-chain.cert.pem`         | `""`    |
| `xgt.ssl.cert`                | Inline xGT server cert PEM                                                                     | `""`    |
| `xgt.ssl.key`                 | Inline xGT server key PEM                                                                      | `""`    |
| `xgt.ssl.mtls`                | Require client certificates on xGT server (needs `ca-chain.cert.pem` in secret or `caCert`)   | `false` |
| `xgt.ssl.caCert`              | Inline CA cert PEM for validating client certs (`ca-chain.cert.pem`)                          | `""`    |

### Backend Environment

| Parameter                           | Description                                        | Default                                      |
|-------------------------------------|----------------------------------------------------|----------------------------------------------|
| `backend.env.MC_DEFAULT_XGT_HOST`  | xGT hostname                                        | Auto-detected from release name              |
| `backend.env.MC_DEFAULT_XGT_PORT`  | xGT port                                            | `""`                                         |
| `backend.env.MC_SESSION_TTL`       | Session TTL                                         | `""`                                         |
| `backend.env.XGT_SERVER_CN`        | xGT server CN (required when SSL enabled)           | `""`                                         |
| `backend.env.XGT_AUTH_TYPES`       | Login methods (`[]` for single-user mode)           | `"['BasicAuth','FilePKIAuth','PKIAuth']"`    |
| `backend.env.MC_ODBC_LIBRARY_PATH` | ODBC library path                                   | `""`                                         |
| `backend.env.MC_PORT`              | Frontend HTTP port (used to derive OIDC redirect URI) | `frontend.service.httpPort`                |
| `backend.env.MC_SSL_PORT`          | Frontend HTTPS port (used to derive OIDC redirect URI) | `frontend.service.httpsPort`              |
| `backend.siteConfig.yml`           | LLM config overrides (merged with base config)      | `""`                                         |
| `backend.siteConfig.py`            | Custom Python LLM config module                     | `""`                                         |

### OIDC Parameters

| Parameter                          | Description                                                                                 | Default |
|------------------------------------|---------------------------------------------------------------------------------------------|---------|
| `backend.oidc.issuer`              | Override OIDC issuer URL (auto-discovered from xGT if empty)                               | `""`    |
| `backend.oidc.clientId`            | Override OAuth2 client ID (auto-discovered from xGT if empty)                              | `""`    |
| `backend.oidc.clientSecret`        | Client secret — inline value creates a Secret                                               | `""`    |
| `backend.oidc.existingSecret`      | Existing Secret with key `MC_OIDC_CLIENT_SECRET`                                            | `""`    |
| `backend.oidc.scopes`              | Space-separated OAuth2 scopes                                                               | `""`    |
| `backend.oidc.frontendUrl`         | Override frontend base URL for post-login redirects                                         | `""`    |
| `backend.oidc.redirectUri`         | Override redirect URI sent to the IdP                                                       | `""`    |
| `backend.oidc.allowedOrigins`      | Comma-separated allowed origins (defense-in-depth, optional)                               | `""`    |
| `backend.oidc.tlsVerify`           | `true`, `false`, or path to CA bundle for OIDC HTTP calls                                  | `""`    |
| `backend.oidc.caCert`              | Inline CA PEM — creates a Secret, mounted into backend and xGT at `/etc/ssl/certs/oidc-ca.pem` | `""`    |
| `backend.oidc.caCertExistingSecret`| Existing Secret with key `oidc-ca.pem`                                                     | `""`    |
| `backend.oidc.xgtAllowedHosts`     | xGT host:port allowlist (SSRF prevention). Defaults to internal xGT service.               | `""`    |

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

| Parameter                      | Description                                                        | Default |
|--------------------------------|--------------------------------------------------------------------|---------|
| `mongodb.enabled`              | Deploy MongoDB as part of the release                              | `true`  |
| `mongodb.externalUri`          | MongoDB connection URI when `mongodb.enabled=false`                | `""`    |
| `mongodb.externalUriSecret`    | Secret with key `mongodb-uri` (preferred over `externalUri`)       | `""`    |
| `mongodb.auth.enabled`         | Enable MongoDB authentication                                      | `false` |
| `mongodb.auth.existingSecret`  | Secret with keys: `mongodb-root-username`, `mongodb-root-password` | `""`    |
| `mongodb.auth.rootUsername`    | Root username (ignored if existingSecret is set)                   | `""`    |
| `mongodb.auth.rootPassword`    | Root password (ignored if existingSecret is set)                   | `""`    |

### xGT Configuration

| Parameter                   | Description                          | Default        |
|-----------------------------|--------------------------------------|----------------|
| `xgt.enabled`               | Deploy xGT as part of the release    | `true`         |
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

| Parameter                    | Description                                                      | Default |
|------------------------------|------------------------------------------------------------------|---------|
| `openshift.enabled`          | Create ServiceAccount with anyuid SCC                            | `false` |
| `networkPolicy.enabled`      | Restrict MongoDB access to backend only                          | `true`  |
| `compat.serviceNames`        | Simple service names for old frontend images                     | `false` |
| `compat.installSssd`         | Install SSSD at startup for old xGT images                       | `false` |
| `xgt.license.existingSecret` | Secret with key `xgtd.lic`                                       | `""`    |
| `xgt.license.data`           | Inline license content (use `--set-file`)                        | `""`    |
