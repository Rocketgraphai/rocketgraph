# OIDC Authentication Configuration

> **Experimental:** OIDC authentication support is experimental and subject to
> change.

This guide explains how to configure Mission Control to authenticate users via
an external OpenID Connect (OIDC) identity provider such as Keycloak or
OpenShift.

## Overview

When OIDC is enabled, Mission Control performs the OAuth 2.0 authorization code
flow on behalf of the user.  After the user logs in at the identity provider,
Mission Control receives an access token and forwards it to the xGT server,
which validates the token and maps it to a user identity.

Mission Control can discover the OIDC issuer and client ID automatically from
the xGT server.  The redirect URI is derived server-side from the incoming
request hostname and the configured `MC_PORT`/`MC_SSL_PORT` values, so in most
cases no OIDC-specific configuration is required beyond setting
`XGT_AUTH_TYPES`.

## Quick Start

To enable OIDC login in Mission Control, set `XGT_AUTH_TYPES` in your `.env`
file:

```dotenv
XGT_AUTH_TYPES="['OidcAuth']"
```

If the xGT server is configured with `security.oidc.issuer` and
`security.oidc.client_id`, Mission Control will discover those values
automatically.

## Redirect URI

**Before Mission Control can complete an OIDC login, the redirect URI must be
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

If the derived URI does not match your deployment (e.g. an additional proxy
layer changes the public hostname), set `MC_OIDC_REDIRECT_URI` explicitly to
match what is registered with the IdP.

## Environment Variables

| Variable | Volume Mapped | Description |
|----------|:---:|-------------|
| `MC_OIDC_ISSUER` | | OIDC issuer URL (e.g. `https://keycloak.example.com/realms/xgt`). If empty, discovered from the xGT server. |
| `MC_OIDC_CLIENT_ID` | | OAuth2 client ID registered with the IdP. If empty, discovered from the xGT server. |
| `MC_OIDC_CLIENT_SECRET` | | Client secret for confidential clients. Leave empty for public clients. |
| `MC_OIDC_SCOPES` | | Space-separated OAuth2 scopes to request. Default: `openid profile email`. |
| `MC_OIDC_FRONTEND_URL` | | Override the frontend base URL used for post-login redirects. Derived server-side from the request hostname and `MC_PORT`/`MC_SSL_PORT` by default. Only needed when those values do not produce the correct public URL. |
| `MC_OIDC_REDIRECT_URI` | | Override the redirect URI sent to the IdP. Derived server-side from the request hostname and `MC_PORT`/`MC_SSL_PORT` by default. Only needed when those values do not produce the correct public URL. |
| `MC_OIDC_ALLOWED_ORIGINS` | | *(Optional defense-in-depth)* Comma-separated list of permitted frontend origins. Patterns may include `*` wildcards (e.g. `https://*.apps.cluster.example.com`). When set, OIDC login attempts from any non-matching origin are rejected. Leave unset to allow any origin. |
| `MC_XGT_ALLOWED_HOSTS` | | Comma-separated allowlist of permitted xGT servers as `host:port` pairs. Patterns may include `*` wildcards (e.g. `xgt-*.xgt.myns.svc.cluster.local:4367`). When set, connections to any non-matching host are rejected. Leave unset to allow any host. Recommended when the xGT host is user-supplied. |
| `MC_OIDC_TLS_VERIFY` | | TLS verification for OIDC HTTP calls. `true` (default) uses the system CA bundle. `false` disables verification. A file path uses that file as the CA bundle. |
| `MC_OIDC_CA_CERT` | Y | Path to a CA bundle PEM file on the host to trust for OIDC HTTPS calls. Mounted into the container automatically. |

## Security Allowlists

Two optional allowlists restrict which origins and xGT servers Mission Control
will accept.  Both support `*` wildcards, which is useful in Kubernetes and
OpenShift deployments where hostnames are dynamically assigned.

### MC_XGT_ALLOWED_HOSTS

Restricts which xGT servers Mission Control may connect to, preventing SSRF
attacks where a crafted login request points the backend at an unintended
internal host.  Values are `host:port` pairs.  When unset, any host is
accepted.

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
```

The file is volume-mapped into the container.  If the CA is already trusted by
the system, no additional configuration is needed.

To disable TLS verification entirely (not recommended for production):

```dotenv
MC_OIDC_TLS_VERIFY=false
```

## Keycloak Example

```dotenv
XGT_AUTH_TYPES="['OidcAuth']"
```

If `MC_OIDC_ISSUER` and `MC_OIDC_CLIENT_ID` are left empty, Mission Control
discovers them from the xGT server.  See the xGT sysadmin guide for full
Keycloak setup instructions.

## OpenShift Example

```dotenv
XGT_AUTH_TYPES="['OidcAuth']"
MC_OIDC_SCOPES=user:info
MC_OIDC_TLS_VERIFY=false
```

See the xGT sysadmin guide for full OpenShift setup instructions.
