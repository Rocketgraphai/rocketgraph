# OIDC and OpenShift OAuth2 Authentication

> **Experimental:** OIDC authentication support is experimental and subject to
> change.

This guide covers OpenID Connect (OIDC) providers such as Keycloak and the
built-in OpenShift OAuth2 server. Both use the same Rocketgraph authentication
interfaces, but their token validation and identity lookup differ.

| Provider | Login and identity handling |
| --- | --- |
| Keycloak | OIDC provider; in this guide, XGT validates signed JWT access tokens and reads their username/group claims. |
| OpenShift's built-in OAuth server | OAuth2 authorization-code login; XGT presents the access token to the OpenShift User API to validate it and retrieve the user's identity and groups. This integration does not use OIDC ID tokens or a standard OIDC UserInfo endpoint. |

For OpenShift, keep the existing names `OidcAuth`, `security.oidc`,
`backend.oidc`, `MC_OIDC_*` and `/api/login/oidc/callback`. They are the API,
configuration and endpoint names for the shared implementation; do not rename
them to `OAuthAuth`, `security.oauth` or similar. Here, “OpenShift OAuth2” refers
specifically to the built-in OAuth server and `openshift_userapi` validation.

> **Applies to all deployments.**  The `MC_OIDC_*` variables below are set in
> `.env` for Docker Compose and Podman installs, and through the typed
> `backend.oidc.*` values for Kubernetes and OpenShift. Set `XGT_AUTH_TYPES`
> through `backend.env.XGT_AUTH_TYPES` — see
> [OIDC Authentication](../charts/rocketgraph/README.md#oidc-authentication) in the
> Helm chart documentation for the chart-side values and Secret wiring.

## Overview

With `OidcAuth` enabled, Mission Control performs the OAuth2 authorization-code
flow on behalf of the user. The browser returns to its backend with a temporary
authorization code. The backend exchanges that code for an access token, using
the registered client ID and client secret for the confidential clients in
these examples. It then presents the access token to XGT.

For OpenShift, the responsibilities are:

```text
Browser → OpenShift login (LDAP) → authorization code → Mission Control
Mission Control + client secret → OpenShift token endpoint → access token
Mission Control + access token → XGT → OpenShift User API → identity + groups
XGT group-to-label mappings → permissions on XGT data
```

The client secret authenticates the application obtaining a token. XGT's
`openshift_userapi` mode only validates an already-issued token and therefore
does not need that secret. A Python client using the same secret-backed
OAuthClient for browser login performs its own code exchange and needs the
secret too. A client presenting an existing service-account token with
`xgt.BearerTokenAuth` does not perform that exchange.

Mission Control discovers the issuer, client ID, and advertised scopes from xGT when the issuer or client ID is unset. Discovery does not supply client secrets or private CA certificates. The callback is derived from the public frontend origin unless overridden.

| Setting | When to Supply It |
| --- | --- |
| `XGT_AUTH_TYPES="['OidcAuth']"` | Enable browser login for OIDC or OpenShift OAuth2. |
| Client secret | Required for the secret-backed OpenShift OAuthClient and confidential Keycloak Mission Control client used in this guide. |
| CA mount and TLS verification path | Required when the provider's CA is not already trusted. |
| Issuer / client ID / scopes | Override discovery when needed, such as a separate Mission Control client ID. If both issuer and client ID are explicit, supply provider-specific scopes explicitly too. |
| Frontend URL | Override when proxy headers produce the wrong public origin, including an HTTP URL behind HTTPS termination. |
| Redirect URI | Override only when the callback must differ from `<frontend-origin>/api/login/oidc/callback`. |
| Allowed origins | Optional restriction on accepted frontend origins. |

## Quick Start

To enable either browser-login integration, set `XGT_AUTH_TYPES` in your `.env`
file:

```dotenv
XGT_AUTH_TYPES="['OidcAuth']"
```

Configure `security.oidc` on xGT, register the callback below, and supply the client secret and CA settings required by the provider. See the [Keycloak](#keycloak-example) and [OpenShift](#openshift-example) examples.

## Redirect URI

**Before Mission Control can complete browser login, the redirect URI must be
registered with the identity provider.**

The redirect URI is derived server-side as `{origin}/api/login/oidc/callback`,
where the origin is constructed from the incoming request hostname and the
`MC_PORT`/`MC_SSL_PORT` environment variables.  For example, if users access
Mission Control at `https://mc.example.com`, register the following with the
IdP:

```
https://mc.example.com/api/login/oidc/callback
```

- **Keycloak:** add this URI to the client's *Valid redirect URIs* list.
- **OpenShift:** add this URI to the OAuthClient's `redirectURIs` list.

If a proxy changes the apparent scheme or hostname, set `MC_OIDC_FRONTEND_URL` to the public HTTPS origin. This fixes both the post-login destination and the derived callback. A separate `MC_OIDC_REDIRECT_URI` is only needed to override that callback. For HTTPS terminated upstream, also set `MC_EXTERNAL_TLS=true` in Compose or `frontend.tls.external: true` in Helm so session cookies are marked Secure.

## Environment Variables

| Variable | Volume Mapped | Description |
|----------|:---:|-------------|
| `MC_OIDC_ISSUER` | | OIDC issuer URL (e.g. `https://keycloak.example.com/realms/xgt`). If empty, discovered from the xGT server. |
| `MC_OIDC_CLIENT_ID` | | OAuth2 client ID registered with the IdP. If empty, discovered from the xGT server. |
| `MC_OIDC_CLIENT_SECRET` | | Client secret for confidential clients. Leave empty for public clients. |
| `MC_OIDC_SCOPES` | | Optional space-separated override. During xGT discovery, uses the advertised scopes if unset, such as `user:info` for OpenShift. When bypassing discovery, set the provider's required scopes explicitly. |
| `MC_OIDC_FRONTEND_URL` | | Override the public frontend origin used for post-login redirects and the derived callback. Otherwise derived from request/proxy headers and `MC_PORT`/`MC_SSL_PORT`. |
| `MC_OIDC_REDIRECT_URI` | | Override the redirect URI sent to the IdP. Derived server-side from the request hostname and `MC_PORT`/`MC_SSL_PORT` by default. Only needed when those values do not produce the correct public URL. |
| `MC_OIDC_ALLOWED_ORIGINS` | | *(Optional defense-in-depth)* Comma-separated list of permitted frontend origins. Patterns may include `*` wildcards (e.g. `https://*.apps.cluster.example.com`). When set, OIDC login attempts from any non-matching origin are rejected. Leave unset to allow any origin. |
| `MC_XGT_ALLOWED_HOSTS` | | Comma-separated allowlist of permitted xGT servers as `host:port` pairs. Patterns may include `*` wildcards (e.g. `xgt-*.xgt.myns.svc.cluster.local:4367`). When set, connections to any non-matching host are rejected. Leave unset to allow any host. Recommended when the xGT host is user-supplied. |
| `MC_OIDC_TLS_VERIFY` | | TLS verification for OIDC HTTP calls. `true` (default) uses the system CA bundle. `false` disables verification. A file path uses that file as the CA bundle. |
| `MC_OIDC_CA_CERT` | Y | Compose host path for the CA bundle mounted at `/etc/ssl/certs/oidc-ca.pem`. Also set `MC_OIDC_TLS_VERIFY` to the container path. In Helm, use `backend.oidc.caCertExistingSecret` and `backend.oidc.tlsVerify`. |

## Security Allowlists

Two optional allowlists restrict which origins and xGT servers Mission Control
will accept.  Both support `*` wildcards, which is useful in Kubernetes and
OpenShift deployments where hostnames are dynamically assigned.

### MC_XGT_ALLOWED_HOSTS

Restricts which xGT servers Mission Control may connect to, preventing SSRF
attacks where a crafted login request points the backend at an unintended
internal host.  Values are `host:port` pairs.  When unset, any host is
accepted. The Helm chart defaults this allowlist to its internal xGT service when `xgt.enabled=true`; set it explicitly for an external xGT endpoint.

```dotenv
# Fixed deployment
MC_XGT_ALLOWED_HOSTS=xgt:4367

# Kubernetes StatefulSet — wildcard pod hostname
MC_XGT_ALLOWED_HOSTS=xgt-*.xgt.myns.svc.cluster.local:4367
```

### MC_OIDC_ALLOWED_ORIGINS (optional defense-in-depth)

Restricts which browser origins may initiate an OIDC login.  Because the
redirect URI is derived server-side from `MC_PORT`/`MC_SSL_PORT` and the
request hostname (not from any user-supplied value), this setting is not
required to prevent token theft.  It is available as an extra layer of
defense — for example to prevent unexpected frontends from initiating OIDC
flows in a multi-tenant or Kubernetes environment.  When unset, any origin is
accepted.

```dotenv
# Fixed deployment
MC_OIDC_ALLOWED_ORIGINS=https://mc.example.com

# Kubernetes / OpenShift — wildcard subdomain
MC_OIDC_ALLOWED_ORIGINS=https://*.apps.cluster.example.com
```

## TLS / CA Certificates

If the identity provider uses a private or self-signed CA certificate, point
Mission Control at the CA bundle using `MC_OIDC_CA_CERT`:

```dotenv
MC_OIDC_CA_CERT=/path/to/ca-bundle.pem
MC_OIDC_TLS_VERIFY=/etc/ssl/certs/oidc-ca.pem
```

The first value selects the host file to mount; the second tells the backend to verify HTTPS using that file inside the container. If the CA is already trusted by the system, omit both. For Helm, use a Secret with key `oidc-ca.pem` as shown in the [chart's CA example](../charts/rocketgraph/README.md#ca-certificates).

## Keycloak Example

Use a separate confidential client, such as `mission-control`, with **Client authentication** and **Standard flow** enabled. Register `https://mc.example.com/api/login/oidc/callback`. Add Group Membership and Audience mappers to its access tokens, using the groups claim and audience configured on xGT.

Mission Control 2.7.0 does not send a PKCE challenge; do not require PKCE for this confidential client. Keep the separate Python browser client public with PKCE `S256` required and callback `http://127.0.0.1:8765/callback`.

```dotenv
XGT_AUTH_TYPES="['OidcAuth']"
MC_OIDC_CLIENT_ID=mission-control
MC_OIDC_CLIENT_SECRET=<mission-control-client-secret>
```

Leave the issuer and scopes unset to discover them from xGT. Supply private-CA settings if needed and `MC_OIDC_FRONTEND_URL=https://mc.example.com` if the derived origin is wrong. In Helm, use `backend.oidc.clientId` and `existingSecret` instead of embedding the client secret in values. See the [Helm example](../charts/rocketgraph/README.md#keycloak).

## OpenShift Example

This example uses **OpenShift OAuth2**, through the existing `OidcAuth` interface.
An OpenShift `OAuthClient` is a cluster-wide application registration. Its
`metadata.name` is the client ID, and its `secret` authenticates the application
at the token endpoint. It is separate from the namespaced Kubernetes Secret
referenced by `backend.oidc.existingSecret`, which stores that same secret value
under `MC_OIDC_CLIENT_SECRET` for Mission Control to read.

Three settings that can otherwise be confused:

| Setting | Meaning |
| --- | --- |
| `scopeRestrictions: [{literals: [user:info]}]` on the OAuthClient | Allows this application to request the `user:info` scope. |
| `security.oidc.scopes: user:info` on XGT | Advertises which scope browser-login clients should request. Scope permission alone does not request it. |
| `grantMethod: prompt` on the OAuthClient | Asks the user to approve access when consent has not already been granted. It does not select the OAuth grant type or force password entry. |

Mission Control uses the authorization-code grant; the Python example selects
it with `xgt.OidcAuth(flow='auth_code', ...)`. Both request `user:info` in this
setup. XGT's own group-to-label mappings determine data permissions, so users
with the same OAuth scope can have different XGT privileges.

For a complete installation with LDAP login, group synchronization, FIPS images and automation tokens, follow the [OpenShift test-server guide](openshift_test_server/README.md).

```dotenv
XGT_AUTH_TYPES="['OidcAuth']"
MC_OIDC_CLIENT_SECRET=<openshift-oauthclient-secret>
MC_OIDC_CA_CERT=/path/to/openshift-ca.pem
MC_OIDC_TLS_VERIFY=/etc/ssl/certs/oidc-ca.pem
```

Configure xGT with `validation_mode: openshift_userapi` and `scopes: user:info`. Leave Mission Control's issuer, client ID, and scopes unset to discover them from xGT. The OAuthClient needs `user:info` in `scopeRestrictions` and the HTTPS Mission Control callback in `redirectURIs`. For edge Routes, use external TLS and override the frontend origin if necessary as described above. See the [Helm example](../charts/rocketgraph/README.md#openshift-oauth).

## LDAP Groups and Automated Accounts

LDAP validates user passwords through the provider. Group synchronization and xGT authorization need separate configuration:

| Provider | Group Path to xGT | Automated Login |
| --- | --- | --- |
| OpenShift | Synchronize selected LDAP groups with `oc adm groups sync`; xGT reads membership from the OpenShift User API. | Provision a Kubernetes service-account token and use `xgt.BearerTokenAuth`. |
| Keycloak | Configure LDAP federation and an LDAP group mapper; add a Group Membership protocol mapper to each client issuing xGT access tokens. | Use a separate confidential client with service accounts enabled and `xgt.OidcCredentialsAuth`. |

For either provider, map group names in `grouplabel.csv` to labels declared in `label.csv`. Set up recurring synchronization or rerun it after LDAP changes, then reconnect. Assign automation memberships deliberately; they do not inherit LDAP users' groups. See [xGT authentication setup](https://docs.rocketgraph.com/sysadmin_guide/user_authentication.html) for provider configuration, label mappings, and token provisioning.

## Verify the Setup

Test an LDAP user mapped to `xgtadmin` (Alice) and a regular user (Bob) through Mission Control. Check the returned identity and permissions, run `RETURN 1 AS ok`, and verify that Bob cannot access admin-only data. Confirm an incorrect password is rejected. For Python and automated connections, check `conn.userid`, `conn.is_admin`, and `conn.get_user_labels()`, then run `conn.run_job("RETURN 1 AS ok").get_data()` and expect `[[1]]`.
