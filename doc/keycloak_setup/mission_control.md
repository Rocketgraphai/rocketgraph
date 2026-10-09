[Keycloak Setup](README.md)

# Mission Control with Keycloak

Use these steps with an existing xGT Helm release configured as described in [Keycloak setup](README.md). Keep its images, license, hostname, storage, resource and TLS settings. All YAML needed here is included on this page and available to download.

## 1. Register the Mission Control Client

Create an OpenID Connect client named `mission-control`. Enable **Client authentication** and **Standard flow**; disable **Service account roles**, **Direct access grants** and **Implicit flow**. Mission Control 2.7.0 does not send PKCE, so do not require PKCE on this client.

Register the exact callback in **Valid redirect URIs**:

``` text
https://mc.example.com/api/login/oidc/callback
```

Replace the hostname with the HTTPS address people will open in their browser. Add the Audience and Group Membership mappers from the main guide to `mission-control-dedicated`: access tokens must contain audience `xgt` and the user's `groups`. Keep the default `profile` and `email` scopes.

Open **Credentials** and copy this client's generated secret. It is separate from the automation secret and the Keycloak administrator password.

## 2. Store the Client Secret

Download [mission_control_oidc_secret.yaml](examples/mission_control_oidc_secret.yaml) and replace the placeholder:

``` yaml
# Replace with this Keycloak client's generated secret before applying.
# Apply in the same namespace as the Mission Control Helm release.
apiVersion: v1
kind: Secret
metadata:
  name: mission-control-oidc
type: Opaque
stringData:
  MC_OIDC_CLIENT_SECRET: REPLACE_WITH_MISSION_CONTROL_CLIENT_SECRET
```

``` bash
oc -n YOUR_NAMESPACE apply -f examples/mission_control_oidc_secret.yaml
```

The chart passes `MC_OIDC_CLIENT_SECRET` to the backend. xGT still needs no client secret in JWT mode. Store real secrets through the deployment tool's secret management instead of committing them to a public repository.

## 3. Apply the Helm Values

Download [mission_control_values.yaml](examples/mission_control_values.yaml) and replace the public hostname:

``` yaml
# Merge with the release's existing values, keeping xGT OIDC, mappings,
# image/FIPS/SCC settings, license, hostname and storage configuration.
missionControl:
  enabled: true
frontend:
  tls:
    external: true  # HTTPS terminates at the OpenShift edge Route.
backend:
  env:
    XGT_AUTH_TYPES: "['OidcAuth']"
    MC_DEFAULT_XGT_PORT: "4367"
  oidc:
    clientId: mission-control
    existingSecret: mission-control-oidc
    # Replace with the public URL; also register its callback in Keycloak.
    frontendUrl: https://mc.example.com
mongodb:
  # For an external MongoDB, set false and retain its URI/Secret settings.
  enabled: true
```

``` bash
helm upgrade YOUR_RELEASE ../../charts/rocketgraph -n YOUR_NAMESPACE \
  -f YOUR_EXISTING_VALUES.yaml -f examples/keycloak_values.yaml \
  -f examples/mission_control_values.yaml
```

The backend discovers the issuer and scopes from xGT; `clientId` selects its own confidential client. `frontendUrl` sets the public origin explicitly in this example. Omit it when the deployment already derives the correct public URL. Separate issuer, scopes and redirect URI overrides are unnecessary here.

For an external configuration ConfigMap or files PVC, omit `examples/keycloak_values.yaml` and configure the mounted xGT OIDC settings directly. For a private CA, apply the chosen CA overlay from [HTTPS trust](https_trust.md) last, and apply its backend patch if using direct ConfigMap injection.

The example enables bundled MongoDB. If using an external database, retain `mongodb.enabled: false` and its `externalUriSecret` or `externalUri`. For an xGT in another release, set `backend.env.MC_DEFAULT_XGT_HOST` and `backend.oidc.xgtAllowedHosts` to its reachable endpoint. Backend-to-xGT TLS requires its own CA and, if enabled, mTLS client certificate/key; Keycloak's CA does not configure that connection.

## 4. Expose Mission Control with an HTTPS Route

Keep an existing HTTPS Route if it already serves the registered hostname. Otherwise download [mission_control_route.yaml](examples/mission_control_route.yaml) and replace the hostname and frontend Service name:

``` yaml
# Replace host and Service name. The hostname must be covered by the ingress
# certificate, or the administrator must configure a matching Route certificate.
apiVersion: route.openshift.io/v1
kind: Route
metadata:
  name: mission-control
spec:
  host: mc.example.com
  to:
    kind: Service
    name: YOUR_RELEASE-frontend
  port:
    targetPort: http
  tls:
    termination: edge
    insecureEdgeTerminationPolicy: Redirect
```

``` bash
oc -n YOUR_NAMESPACE apply -f examples/mission_control_route.yaml
```

The edge Route terminates HTTPS; `frontend.tls.external: true` tells the backend that users reach the frontend over HTTPS. If the frontend itself terminates HTTPS, retain its existing certificate settings instead.

The Route uses the ingress controller's default certificate. Choose a hostname covered by it or have an administrator configure the Route certificate. The browser must resolve that hostname and trust its certificate. xGT, the backend and the browser must also reach the Keycloak issuer hostname. These endpoints can use internal DNS; login does not require public internet access.

## 5. Check the Rollout and Sign In

``` bash
oc -n YOUR_NAMESPACE rollout status deployment/YOUR_RELEASE-backend
oc -n YOUR_NAMESPACE rollout status deployment/YOUR_RELEASE-frontend
oc -n YOUR_NAMESPACE get route mission-control
```

Open `https://mc.example.com`, sign in with a normal Keycloak or LDAP account, and run `RETURN 1 AS ok`. Check its mapped labels and expected data access. After replacing an existing client secret, restart the backend to reload it:

``` bash
oc -n YOUR_NAMESPACE rollout restart deployment/YOUR_RELEASE-backend
```

For invalid redirects, compare the registered URI with the actual callback. For audience or label errors, check this client's token mappers. For HTTPS errors, check the backend's Keycloak trust and the browser's trust separately.

For an air-gapped installation, obtain the chart, Python package, images and CA bundles beforehand, and point the image repositories to the internal registry. The YAML can also be applied through GitOps or a deployment pipeline; `oc` shows the equivalent manual operations.
