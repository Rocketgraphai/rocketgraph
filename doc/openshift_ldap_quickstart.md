# OpenShift and LDAP Quickstart

Use OpenShift to authenticate LDAP users, then map their OpenShift groups to xGT labels. Automated jobs use OpenShift service-account tokens. xGT does not connect directly to LDAP in this configuration.

Experimental: OIDC authentication may change in future releases.

This checklist is for the OpenShift and xGT administrators. It assumes an existing LDAP directory, permission to configure OpenShift authentication, and an xGT 2.7.1 deployment using version **0.5.0** of the [Rocketgraph Helm chart](https://github.com/Rocketgraphai/rocketgraph/tree/main/charts/rocketgraph). Replace example hostnames, namespace `xgt`, and group names with your own. For the full configuration reference, see [xGT OpenShift reference](https://docs.rocketgraph.com/sysadmin_guide/user_authentication.html#openshift).

For a complete test deployment with LDAP provider and group-sync YAML, follow the [OpenShift test-server guide](openshift_test_server/README.md). For Keycloak-issued tokens instead, see [Keycloak Setup](keycloak_setup/README.md).

## 1. Connect LDAP and Synchronize Groups

Configure an LDAP identity provider in OpenShift with the directory URL, bind credentials, user attributes, and trusted CA. Prepare an `LDAPSyncConfig` matching the directory schema and a whitelist of the groups to import. Preview the changes, then apply them as an authorized administrator:

``` shell
oc adm groups sync --sync-config=ldap-sync.yaml --whitelist=groups.txt
oc adm groups sync --sync-config=ldap-sync.yaml --whitelist=groups.txt --confirm
```

For a simple access test, use LDAP users Alice and Bob: put Alice in `xgt-admins` and `xgt-users`, and Bob only in `xgt-users`. Confirm their memberships in OpenShift's Group objects. Password checks and group sync are separate; schedule synchronization or rerun it after directory changes, then start new xGT sessions.

## 2. Register the OAuth Client and Prepare Mounts

Register an OpenShift OAuthClient named `xgt-client` with a generated secret, `user:info` in `scopeRestrictions`, and these `redirectURIs`:

- `http://127.0.0.1:8765/callback` for Python browser login.
- `https://mc.apps.example.com/api/login/oidc/callback` if using Mission Control.

The OAuthClient manifest is in [xGT OpenShift reference](https://docs.rocketgraph.com/sysadmin_guide/user_authentication.html#openshift). Supply its secret separately to Python clients and Mission Control; discovery does not provide credentials.

In the application namespace, prepare Secret `xgt-license` with the default key `xgtd.lic`, Secret `xgt-oauth-client` with default key `MC_OIDC_CLIENT_SECRET`, and Secret `oidc-ca` with default key `oidc-ca.pem`. For existing Secrets with other keys, set `xgt.license.secretKey`, `backend.oidc.secretKeys.clientSecret`, `xgt.oidc.secretKeys.caCert` and `backend.oidc.secretKeys.caCert` as appropriate. The CA bundle must trust the OAuth and OpenShift User API endpoints. The chart mounts these and its configuration:

| Content                   | Container path                               |
|---------------------------|----------------------------------------------|
| License                   | `/license/xgtd.lic`                          |
| Server configuration      | `/conf/xgtd.conf`                            |
| Group mappings and labels | `/conf/grouplabel.csv` and `/conf/label.csv` |
| Trusted CA bundle         | `/etc/ssl/certs/oidc-ca.pem`                 |
| Persistent data           | `/data`                                      |

Set `xgt.hostname` to a hostname covered by the license. The chart sets the container's OS hostname without changing the generated Pod or Service name; no custom StatefulSet is needed. Replace `demo-xgt-test` below with your licensed hostname, and have the OpenShift administrator approve the images' SCC requirements.

## 3. Configure xGT and Mission Control

Merge these settings into the deployment's Helm values and apply them using the chart's installation or upgrade instructions:

``` yaml
xgt:
  hostname: demo-xgt-test  # Replace with your licensed hostname.
  image:
    tag: 2.7.1
  license:
    existingSecret: xgt-license
  oidc:
    caCertExistingSecret: oidc-ca
  config:
    grouplabelCsv: |
      group,label
      xgtd,xgtadmin
      xgt-admins,xgtadmin
      xgt-users,data-users
    labelCsv: |
      label
      xgtadmin
      data-users
  extraConfig:
    security.oidc:
      issuer: https://oauth-openshift.apps.example.com
      client_id: xgt-client
      validation_mode: openshift_userapi
      openshift_user_api_uri: https://kubernetes.default.svc/apis/user.openshift.io/v1/users/~
      username_claim: metadata.name
      groups_claim: groups
      scopes: user:info
frontend:
  tls:
    external: true  # For an HTTPS edge Route.
backend:
  env:
    XGT_AUTH_TYPES: "['OidcAuth']"
    MC_DEFAULT_XGT_PORT: '4367'
  oidc:
    existingSecret: xgt-oauth-client
    caCertExistingSecret: oidc-ca
    tlsVerify: /etc/ssl/certs/oidc-ca.pem
    # Set only if proxy headers produce the wrong public URL:
    frontendUrl: https://mc.apps.example.com
```

`xgt.oidc` supplies xGT's CA mount and fills in `security.oidc.ca_cert` in generated configuration; `backend.oidc` supplies Mission Control's own CA mount. Omit the CA settings when both endpoints are already trusted. Mission Control discovers the issuer, client ID, and `user:info` from xGT. Its callback is derived from the frontend URL; `redirectUri` is an optional override. Configure the HTTPS Route and DNS for the public Mission Control hostname.

### Using FIPS Images

To select the chart's FIPS image variants, add this to the Helm values:

``` yaml
fips:
  enabled: true
```

Keep the base image tags without a `-fips` suffix; the chart adds it to xGT and Mission Control tags, for example `2.7.1-fips` and `2.7.0-fips`. The bundled MongoDB image switches to `percona/percona-server-mongodb`. An external MongoDB server must be configured separately.

Image selection alone does not establish FIPS compliance. Verify the host's FIPS mode and the applications' active crypto-provider configuration, and configure TLS for the required connections. When both `fips.enabled` and `mongodb.tls.enabled` are true, the chart adds `--tlsFIPSMode` to MongoDB; provide the required certificates and CA as described in the [Helm FIPS guide](https://github.com/Rocketgraphai/rocketgraph/tree/main/charts/rocketgraph#fips-mode). The OIDC settings above still apply. Repeat the human and automated login, label, and query checks after switching images.

> [!NOTE]
> **Existing MongoDB volume migration:** Back up the database before replacing Community MongoDB with Percona, and pause applications writing to it during migration. The Percona image uses UID 1001. Existing database files owned by another UID can prevent WiredTiger from starting even with `fsGroup` set. If this occurs, migrate ownership on the database volume to the image's UID using an administrator-approved procedure. This is a migration step for affected volumes, not a requirement to change permissions on every install.

## 4. Provision Automated Access

An administrator can issue an expiring token for a service account:

``` shell
oc -n xgt create serviceaccount xgt-automation
umask 077
oc -n xgt create token xgt-automation --duration=1h > xgt.token
```

Store the token in the job's secret store and use `xgt.BearerTokenAuth`. Renew it before new connections after expiry; see [OpenShift service accounts](https://docs.rocketgraph.com/sysadmin_guide/user_authentication.html#service-accounts) for rotating tokens and the long-lived Secret alternative.

To grant an automation label, add `system:serviceaccounts:xgt,automation` to `grouplabelCsv` and `automation` to `labelCsv`. This grants the label to every service account in namespace `xgt`. Mapping that group to `xgtadmin` instead grants all of them xGT administration. These groups come from OpenShift, not LDAP.

## 5. Log In and Verify

In Mission Control, choose OIDC login, select the LDAP provider on the OpenShift page, and sign in as Alice or Bob. Alice should be an xGT administrator and Bob should have `data-users` without `xgtadmin`. Neither mapping grants OpenShift cluster administration.

For Python browser login and automated token login, use the examples in [Python OpenShift login examples](https://docs.rocketgraph.com/user_ref/usingxgt/connecting_to_server.html#openshift-login). Clients need a reachable xGT endpoint or an authorized tunnel; configuring OIDC does not open a network path. Configure connection TLS as described in [Python connection TLS settings](https://docs.rocketgraph.com/user_ref/usingxgt/connecting_to_server.html#connect-via-ssl-encrypted-network-connection).

After connecting, check:

``` python
print(conn.userid)
print(conn.is_admin)
print(conn.get_user_labels())
print(conn.run_job("RETURN 1 AS ok").get_data())
```

Expect `[[1]]` from the query. Also verify rejection of an incorrect password and denial of admin-only data to Bob. Check the automation identity and labels separately. Missing LDAP labels call for checking OpenShift group sync and the xGT label files.
