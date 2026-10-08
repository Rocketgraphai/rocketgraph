[Keycloak Setup](README.md)

# HTTPS Trust for Keycloak

Python obtains tokens over HTTPS, while xGT fetches Keycloak's discovery information and signing keys over HTTPS. Mission Control's backend and the user's browser also connect to Keycloak when used. Check each component's trust separately. The Helm examples on this page use Rocketgraph chart **0.5.0**.

Skip the corresponding CA setting when that application already trusts the issuer's certificate. For a private company CA, the simplest Helm setup is an approved PEM bundle mounted through a Secret. Trust on an OpenShift node or in a browser does not establish trust inside the stock containers.

These public CA certificates are separate from JWT signing keys, client secrets and private keys. If a Route or proxy terminates Keycloak HTTPS, trust the CA that issued the certificate seen at that endpoint, and ensure the certificate covers the hostname in the issuer URL.

## 1. Obtain the Approved CA Bundle

Ask the Keycloak or PKI administrator for the public CA bundle in PEM format, including the trusted root and required intermediates. Save it as `keycloak-ca.pem`. A PEM certificate contains `BEGIN CERTIFICATE` and `END CERTIFICATE` lines; renaming another format to `.pem` does not convert it. A deliberately self-signed server certificate can itself be a trust anchor.

## 2. Configure the Python Machine and Browser

On the Python machine, put the approved bundle at a stable path:

``` bash
mkdir -p "$HOME/.config/rocketgraph"
cp ./keycloak-ca.pem "$HOME/.config/rocketgraph/keycloak-ca.pem"
```

Set `ca_cert_path` on `xgt.OidcAuth` or `xgt.OidcCredentialsAuth`, using the path on that machine:

``` python
auth = xgt.OidcAuth(
  flow = "auth_code",
  ca_cert_path = "~/.config/rocketgraph/keycloak-ca.pem")
```

The SDK expands `~`. The same parameter works on the automation authentication object. Copying the file alone does not configure trust. Import the approved CA into the browser's certificate store or the OS store it uses if needed; Python's setting does not configure the browser.

With SDK 2.7.1, if xGT TLS is enabled and `ca_cert_path` is omitted, the client uses `ssl_server_cert` for Keycloak HTTPS too. If that file trusts only xGT's CA, explicitly set `ca_cert_path` to a bundle that trusts Keycloak. This also applies to publicly issued Keycloak certificates: the explicit bundle must include their trusted CA roots. A bundle covering both endpoints works, but each connection can use its own bundle.

## 3. Mount the CA Through a Helm Secret

On the machine running `oc`, create the Secret in the application namespace. The source filename can vary; these examples use the default Secret key `oidc-ca.pem`:

``` bash
oc -n YOUR_NAMESPACE create secret generic keycloak-ca \
  --from-file=oidc-ca.pem=./keycloak-ca.pem \
  --dry-run=client -o yaml | oc -n YOUR_NAMESPACE apply -f -
```

Download [keycloak_ca_values.yaml](examples/keycloak_ca_values.yaml) or save this overlay:

``` yaml
# Simplest CA setup for Keycloak using a private company CA.
# Stock xGT/MC images do not include your company's private CA.
# Skip only if their application trust stores already trust Keycloak HTTPS.
# Requires Rocketgraph chart 0.5.0.
# Existing ConfigMap/files PVC: set ca_cert in the mounted xgtd.conf;
# omit keycloak_values.yaml from the Helm command and keep this overlay.
# First create Secret keycloak-ca with key oidc-ca.pem in the release namespace.
# Apply after the existing deployment values and keycloak_values.yaml.
# This mounts the public CA bundle in xGT and the Mission Control backend.
xgt:
  oidc:
    caCertExistingSecret: keycloak-ca
# Omit this backend section when Mission Control is disabled.
backend:
  oidc:
    caCert: ""
    caCertExistingSecret: keycloak-ca
    tlsVerify: /etc/ssl/certs/oidc-ca.pem
```

`xgt.oidc.caCertExistingSecret` mounts the bundle at `/etc/ssl/certs/oidc-ca.pem` in xGT. The chart fills in `security.oidc.ca_cert` in generated configuration when the field is absent; no `xgt.extraConfig` CA override is needed. For Mission Control, `backend.oidc.caCertExistingSecret` supplies its backend's mount, and `tlsVerify` selects that file for Keycloak HTTPS. Omit the backend settings when Mission Control is disabled.

To reuse a Secret with another CA key, set `xgt.oidc.secretKeys.caCert` and, when used, `backend.oidc.secretKeys.caCert` to that key name. Each component can use the same Secret or a different bundle. Mounting at an arbitrary path does not automatically configure application trust.

``` bash
helm upgrade YOUR_RELEASE ../../charts/rocketgraph -n YOUR_NAMESPACE \
  -f YOUR_EXISTING_VALUES.yaml -f examples/keycloak_values.yaml \
  -f examples/keycloak_ca_values.yaml
```

If an existing ConfigMap or files PVC supplies `xgtd.conf`, omit `examples/keycloak_values.yaml` and keep the CA Secret overlay. Set `security.oidc.ca_cert` in the mounted configuration to `/etc/ssl/certs/oidc-ca.pem` and edit its CSV files directly.

For a non-container xGT server, put the approved bundle at a readable path, set `security.oidc.ca_cert` to it, and restart xGT. The Python machine still uses its own local CA path.

## Alternative: Mount an OpenShift-Injected Bundle

Use this **instead of the CA Secret overlay** when the cluster's trusted bundle already includes the CA needed for the Keycloak endpoint. An administrator must register a missing company CA in cluster trust first. Injection does not automatically trust every Route certificate or install certificates in a pod.

Download [openshift_trusted_ca.yaml](examples/openshift_trusted_ca.yaml) and create the dedicated ConfigMap:

``` yaml
# Optional: ask OpenShift to populate the cluster's merged trusted CA bundle.
# Use a dedicated empty ConfigMap in the xGT namespace; OpenShift owns its data.
apiVersion: v1
kind: ConfigMap
metadata:
  name: trusted-ca-bundle
  labels:
    config.openshift.io/inject-trusted-cabundle: "true"
```

``` bash
oc -n YOUR_NAMESPACE apply -f examples/openshift_trusted_ca.yaml
oc -n YOUR_NAMESPACE get configmap trusted-ca-bundle \
  -o jsonpath='{.data.ca-bundle\.crt}'
```

The injection mechanism uses a **label**, not an annotation. Wait for a non-empty `ca-bundle.crt` containing the required CA. Do not add the service CA injection annotation to the same ConfigMap; it is a different trust bundle. See [OpenShift custom PKI](https://docs.redhat.com/en/documentation/openshift_container_platform/4.15/html/networking/configuring-a-custom-pki).

Download [openshift_ca_values.yaml](examples/openshift_ca_values.yaml) and apply it after the authentication overlay:

``` yaml
# Use only when trusted-ca-bundle includes the CA for the Keycloak endpoint.
# Apply after the deployment values and keycloak_values.yaml.
# Existing config/PVC: remove extraConfig and edit ca_cert in the mounted file.
xgt:
  oidc:
    caCert: ""
    caCertExistingSecret: ""
  extraConfig:
    security.oidc:
      ca_cert: /etc/keycloak-ca/ca-bundle.crt
  extraVolumes:
    - name: keycloak-trusted-ca
      configMap:
        name: trusted-ca-bundle
        items:
          - key: ca-bundle.crt
            path: ca-bundle.crt
  extraVolumeMounts:
    - name: keycloak-trusted-ca
      mountPath: /etc/keycloak-ca
      readOnly: true
backend:
  oidc:
    caCert: ""
    caCertExistingSecret: ""
    # Mission Control also requires backend_trusted_ca_patch.yaml.
    tlsVerify: /etc/keycloak-ca/ca-bundle.crt
```

``` bash
helm upgrade YOUR_RELEASE ../../charts/rocketgraph -n YOUR_NAMESPACE \
  -f YOUR_EXISTING_VALUES.yaml -f examples/keycloak_values.yaml \
  -f examples/openshift_ca_values.yaml
```

The xGT pod mounts the ConfigMap directly at `/etc/keycloak-ca`; xGT uses `/etc/keycloak-ca/ca-bundle.crt` explicitly. This avoids image-specific system trust-store paths. Merge existing extra volumes and mounts into these lists; Helm replaces lists when combining values files.

For external configuration, omit `examples/keycloak_values.yaml`, remove `xgt.extraConfig` from the CA overlay, and set the mounted OIDC `ca_cert` to `/etc/keycloak-ca/ca-bundle.crt` instead.

If Mission Control is enabled, also download [backend_trusted_ca_patch.yaml](examples/backend_trusted_ca_patch.yaml) and mount the same ConfigMap in its backend:

``` yaml
spec:
  template:
    spec:
      volumes:
        - name: keycloak-trusted-ca
          configMap:
            name: trusted-ca-bundle
            items:
              - key: ca-bundle.crt
                path: ca-bundle.crt
      containers:
        - name: backend
          volumeMounts:
            - name: keycloak-trusted-ca
              mountPath: /etc/keycloak-ca
              readOnly: true
```

``` bash
oc -n YOUR_NAMESPACE patch deployment YOUR_RELEASE-backend \
  --type=strategic --patch-file=examples/backend_trusted_ca_patch.yaml
```

The chart has no backend extra-volume setting. Keep this patch in your GitOps/deployment workflow and reapply it after Helm upgrades. The overlay's `backend.oidc.tlsVerify` points to the backend's mounted bundle. Skip the patch when Mission Control is disabled. This container mount does not configure trust on the Python machine or in the browser.

## Restart and Verify

Restart the applications after CA changes. The CA Secret method uses `subPath` mounts, so changing an existing Secret's contents alone does not refresh the mounted file:

``` bash
oc -n YOUR_NAMESPACE rollout restart deployment/YOUR_RELEASE-xgt
oc -n YOUR_NAMESPACE rollout restart deployment/YOUR_RELEASE-backend
```

Use the actual resource names, and omit the backend command for xGT-only releases. Confirm DNS and HTTPS from the Python machine:

``` bash
getent hosts keycloak.example.com
curl --fail --show-error --cacert ./keycloak-ca.pem \
  https://keycloak.example.com/realms/rocketgraph/.well-known/openid-configuration
```

An unknown issuer points to CA trust or an incomplete certificate chain; a hostname mismatch points to the certificate's names. A DNS failure needs a DNS fix, not another CA file. Keep HTTPS verification enabled.

Python → xGT and backend → xGT TLS protect different connections from Keycloak HTTPS. Use [Python connection TLS settings](https://docs.rocketgraph.com/user_ref/usingxgt/connecting_to_server.html#connect-via-ssl-encrypted-network-connection) and retain the deployment's xGT certificate settings; enabling OIDC does not enable TLS on port 4367. For SDK 2.7.1, explicitly set the Keycloak `ca_cert_path` when the xGT TLS CA bundle does not also trust Keycloak.
