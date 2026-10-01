# Test Server: OpenShift, LDAP Login and FIPS Images

Follow these steps for a fresh test installation on an existing OpenShift cluster and LDAP directory. Edit the supplied YAML, create Secrets with `oc`, and install with Helm and `oc apply`. Python is used only to demonstrate XGT login.

**Authentication terminology:** this walkthrough uses **OpenShift OAuth2**.
The Python API and Mission Control still call the shared authentication option
`OidcAuth`, and settings remain under `security.oidc`, `backend.oidc` and
`MC_OIDC_*`. OpenShift returns an OAuth access token; XGT validates it through
the OpenShift User API to obtain identity and groups. This flow does not use
OIDC ID tokens or a standard OIDC UserInfo endpoint.

**Deployment:** Helm manages XGT, Mission Control and MongoDB. Set `xgt.hostname: xgt-test-0` for the licensed container hostname. The Kubernetes pod name remains generated. Optional separate releases provide dev and prod XGT servers with their own configuration and storage, sharing Mission Control.

**Requires chart 0.4.0 or later; the commands below use the chart in this repository.** Rendering has been checked, and an isolated XGT 2.7.1 FIPS-image release passed license validation, OpenShift token login and a query. Its fixed hostname and a file on its data volume survived pod replacement. The complete installation below has not been deployed to a fresh cluster. The [deployment planning guide](../openshift_fips_deployment.md) covers the architecture and FIPS verification responsibilities.

The full chart was also tested under `restricted-v2` with namespace-assigned UIDs, Mission Control HTTPS/mTLS, MongoDB TLS/mTLS and encryption at rest, and XGT TLS/token authentication. This used fresh PVCs and temporary test certificates; existing-volume migration, optional backend plugin installation and end-to-end FIPS compliance require separate validation.

## Files to Edit

| File | What to change |
| --- | --- |
| [namespaces.yaml](namespaces.yaml) | Fixed test namespaces and automation account; normally leave unchanged |
| [ldap_provider.yaml](ldap_provider.yaml) | LDAP URL, bind DN and user attributes; a fragment to append to cluster OAuth settings |
| [ldap_sync_config.yaml](ldap_sync_config.yaml), [ldap_groups.txt](ldap_groups.txt) | Directory searches, membership attributes and the two selected group DNs |
| [ldap_sync.yaml](ldap_sync.yaml) | Approved OpenShift CLI image; contains sync RBAC and a suspended CronJob |
| [oauth_client.yaml](oauth_client.yaml) | Mission Control callback; fill the secret only in a private copy |
| [values.yaml](values.yaml) | XGT hostname, OAuth issuer, group-to-label mappings, images, resources/storage, Mission Control URL and MongoDB settings |
| [route.yaml](route.yaml) | Public Mission Control hostname |
| [login.py](login.py) | Ready-to-run browser/token login and data-permission demonstration |

Example names are `xgt-demo` (application namespace), `xgt-demo-jobs` (automation namespace), `xgt-demo-ldap-sync` (sync namespace), and `rocketgraph` (Helm release). Keep these names for the walkthrough. All commands run from this directory in **Bash**, with `oc` already logged in as an authorized administrator. Use an approved repository revision containing chart 0.4.0 or later.

## 1. Confirm the Prerequisites

```sh
cd doc/openshift_test_server
umask 077
mkdir -p .private
oc whoami
oc whoami --show-server
oc get nodes
oc get storageclass
```

Get a license for `xgt-test-0`, directory access details, and two LDAP test users:

| User | LDAP memberships | Expected XGT access |
| --- | --- | --- |
| Alice | Admin and users groups | `xgtadmin`, `data-users` |
| Bob | Users group only | `data-users`, no admin access |

The sync configuration maps the two selected LDAP DNs to OpenShift names `xgt-admins` and `xgt-users`. Agree ownership of these cluster-wide groups before changing them. The supplied schema expects group member DNs and user `uid` attributes; adapt it if the directory differs.

The example requests about 3 GiB of application memory and 16 GiB of persistent storage, plus cluster overhead. If no suitable default storage class exists, set `xgt.persistence.data.storageClassName`, `xgt.persistence.log.storageClassName` and `mongodb.persistence.storageClassName` in `values.yaml`.

For a FIPS deployment, the platform must already be prepared for FIPS, and the security team must verify each application's approved crypto modules/runtime. Image tags alone do not establish compliance. OpenShift FIPS is an installation-time choice. [OpenShift FIPS guidance](https://docs.redhat.com/en/documentation/openshift_container_platform/4.20/html/installation_overview/installing-fips)

**Expected:** cluster, storage, license, LDAP accounts, image versions and FIPS requirements are agreed.

## 2. Supply Files and Create the Namespaces

Copy the license and directory inputs from their secure locations:

```sh
cp /secure/path/xgtd.lic .private/xgtd.lic
cp /secure/path/ldap-ca.crt .private/ldap-ca.crt
cp /secure/path/ldap-bind-password .private/ldap-bind-password
oc apply -f namespaces.yaml
```

The password file contains only the read-only LDAP bind password, without a trailing newline. For the usual cluster-managed OAuth/API certificates, collect the trust bundle using `oc`:

```sh
oc -n openshift-config-managed get configmap default-ingress-cert \
  -o jsonpath='{range .data.*}{.}{"\n"}{end}' > .private/oauth-ca.pem
oc -n openshift-config-managed get configmap kube-root-ca.crt \
  -o jsonpath='{range .data.*}{.}{"\n"}{end}' > .private/api-ca.pem
cat .private/oauth-ca.pem .private/api-ca.pem > .private/oidc-ca.pem
```

Check these commands succeeded. If custom endpoint certificates use other CAs, obtain the correct bundle from the platform administrator instead.

For the FIPS target, obtain approved certificates and keys from PKI:

```sh
cp /secure/path/xgt-cert.pem .private/xgt-cert.pem
cp /secure/path/xgt-key.pem .private/xgt-key.pem
cp /secure/path/xgt-ca.pem .private/xgt-ca.pem
cp /secure/path/mongodb-cert.pem .private/mongodb-cert.pem
cp /secure/path/mongodb-key.pem .private/mongodb-key.pem
cp /secure/path/mongodb-ca.pem .private/mongodb-ca.pem
```

XGT's certificate must cover `rocketgraph-xgt`; MongoDB's must cover `rocketgraph-mongodb`. Include namespace-qualified service DNS names where used. The Route hostname must be covered by the router certificate, or its own certificate must be supplied.

For a disposable functional test, the optional `bash make_test_certificates.sh` command produces the six server certificate/key files instead of the PKI copy commands. It is not evidence of a FIPS-approved key-generation process. Do not run it over existing certificates.

**Expected:** private files exist; test namespaces are created. Keep `.private/` out of source control.

## 3. Configure OpenShift LDAP Login

Skip this step if the existing OpenShift LDAP provider already authenticates the test users. Otherwise create its inputs:

```sh
oc -n openshift-config create secret generic xgt-demo-ldap-bind \
  --from-file=bindPassword=.private/ldap-bind-password
oc -n openshift-config create configmap xgt-demo-ldap-ca \
  --from-file=ca.crt=.private/ldap-ca.crt
oc get oauth cluster -o yaml > .private/oauth-before.yaml
oc edit oauth cluster
```

In the editor, append the edited entry from `ldap_provider.yaml` under `spec.identityProviders`. **Preserve the existing entries.** This file is a provider fragment, not a standalone object for `oc apply`.

```sh
oc get clusteroperator authentication
```

Wait for the operator to be healthy, then authenticate as Alice and Bob through the OpenShift console in separate browser sessions. They need not have permission to inspect cluster resources.

**Expected:** both LDAP passwords authenticate before XGT is installed. Note their resulting OpenShift usernames; group sync must produce the same names.

## 4. Preview and Apply Group Sync

Edit `ldap_sync_config.yaml`, `ldap_groups.txt` and the CLI image in `ldap_sync.yaml`. Keep the CronJob suspended. Create its inputs and RBAC:

```sh
oc -n xgt-demo-ldap-sync create secret generic ldap-bind \
  --from-file=bindPassword=.private/ldap-bind-password
oc -n xgt-demo-ldap-sync create configmap ldap-ca \
  --from-file=ca.crt=.private/ldap-ca.crt
oc -n xgt-demo-ldap-sync create configmap ldap-sync-config \
  --from-file=sync.yaml=ldap_sync_config.yaml --from-file=groups.txt=ldap_groups.txt \
  --dry-run=client -o yaml | oc apply -f -
oc apply -f ldap_sync.yaml
```

Use the standard CLI to make a preview Job from the CronJob:

```sh
oc -n xgt-demo-ldap-sync create job --from=cronjob/xgt-demo-ldap-sync \
  xgt-sync-preview --dry-run=client -o yaml > .private/preview-job.yaml
```

Open `.private/preview-job.yaml` and **remove the `- --confirm` argument**. Then run the preview:

```sh
oc apply -f .private/preview-job.yaml
oc -n xgt-demo-ldap-sync wait --for=condition=complete job/xgt-sync-preview --timeout=330s
oc -n xgt-demo-ldap-sync logs job/xgt-sync-preview
```

After checking the proposed users and groups, create a confirmed Job from the unchanged CronJob:

```sh
oc -n xgt-demo-ldap-sync create job --from=cronjob/xgt-demo-ldap-sync xgt-sync-first
oc -n xgt-demo-ldap-sync wait --for=condition=complete job/xgt-sync-first --timeout=330s
oc -n xgt-demo-ldap-sync logs job/xgt-sync-first
oc get groups xgt-admins xgt-users -o yaml
```

**Expected:** Alice is in both groups and Bob only in `xgt-users`. This job runs inside the cluster, so the workstation needs no direct LDAP connection. The sync service account's group permissions are cluster-wide; the whitelist restricts the command, not RBAC. Protect its workload and configuration. [OpenShift group-sync procedure](https://docs.redhat.com/en/documentation/openshift_container_platform/4.20/html/authentication_and_authorization/ldap-syncing)

## 5. Register the OAuth Client

An OpenShift `OAuthClient` is a cluster-wide **application registration**. It
identifies the application requesting tokens and records its client secret,
permitted scopes and callback URLs. In this example, Mission Control and the
Python browser-login client share that registration. XGT receives the resulting
bearer token and validates it through the OpenShift User API.

These similarly named items have different roles:

| Item | Role |
| --- | --- |
| `OAuthClient` named `xgt-demo-client` | The application registration in OpenShift; its name is the client ID |
| XGT setting `client_id: xgt-demo-client` | Advertises that registration's ID to clients starting browser login |
| `Secret` named `xgt-oauth-client` | A separate, namespaced Kubernetes Secret that supplies the client secret to Mission Control |
| `backend.oidc.existingSecret: xgt-oauth-client` | References that Kubernetes Secret, not the OAuthClient resource |

The secret value in the OAuthClient must match the value stored under
`MC_OIDC_CLIENT_SECRET` in the Kubernetes Secret created in step 6. XGT's
`openshift_userapi` token validation does not require this client secret.
This registration does not configure LDAP, synchronize groups, or assign XGT
permissions; those are separate steps.

The login grant is `authorization_code` (`flow='auth_code'` in `login.py`).
`grantMethod: prompt` controls consent when access has not already been granted;
it does not select the grant type or force password entry. The OAuthClient
allows `user:info` via `scopeRestrictions`; XGT advertises it via
`xgt.extraConfig.security.oidc.scopes`, and the login client requests it. That
scope permits user-information lookup; XGT group-to-label mappings determine
which data the user can access.

Mission Control exchanges the returned authorization code for an access token
using the client secret. The Python browser client does the same independently.
XGT receives the token after this exchange, so its `openshift_userapi` validation
needs the token and CA trust, not the application's client secret. Automated
clients using an existing service-account token skip the code exchange.

Generate the client secret once and make a private copy of the manifest:

```sh
openssl rand -hex 32 | tr -d '\n' > .private/oauth-client-secret
cp oauth_client.yaml .private/oauth_client.yaml
```

In an editor, copy the secret from `.private/oauth-client-secret` into the private manifest's `secret` field. Set the correct Mission Control callback URL. Keep the local Python callback unchanged. Then apply:

```sh
oc apply -f .private/oauth_client.yaml
oc get oauthclient xgt-demo-client -o jsonpath='{.redirectURIs}'
```

**Expected:** `user:info` is allowed; the callbacks are `http://127.0.0.1:8765/callback` and the Mission Control URL plus `/api/login/oidc/callback`. Do not regenerate the secret on routine reruns. [OAuthClient registration](https://docs.redhat.com/en/documentation/openshift_container_platform/4.20/html/authentication_and_authorization/configuring-oauth-clients)

## 6. Create Application Secrets

Generate the MongoDB password once for the fresh database, then create the seven Secrets:

```sh
openssl rand -hex 32 | tr -d '\n' > .private/mongodb-password
cat .private/mongodb-cert.pem .private/mongodb-key.pem > .private/mongodb-server.pem
oc -n xgt-demo create secret generic xgt-license --from-file=xgtd.lic=.private/xgtd.lic
oc -n xgt-demo create secret generic xgt-oauth-client \
  --from-file=MC_OIDC_CLIENT_SECRET=.private/oauth-client-secret
oc -n xgt-demo create secret generic oidc-ca --from-file=oidc-ca.pem=.private/oidc-ca.pem
oc -n xgt-demo create secret generic xgt-ssl \
  --from-file=server.cert.pem=.private/xgt-cert.pem \
  --from-file=server.key.pem=.private/xgt-key.pem
oc -n xgt-demo create secret generic backend-tls --from-file=xgt-server.pem=.private/xgt-ca.pem
oc -n xgt-demo create secret generic mongodb-tls \
  --from-file=server.pem=.private/mongodb-server.pem --from-file=ca.pem=.private/mongodb-ca.pem
oc -n xgt-demo create secret generic mongodb-auth \
  --from-file=mongodb-root-password=.private/mongodb-password
oc -n xgt-demo get secrets
```

**Expected:** all seven Secrets exist. These are first-install commands; on reruns reuse them. Do not regenerate the password for an initialized database. Store the private inputs securely for renewal and recovery.

## 7. Edit the Application Configuration and Deploy

In `values.yaml`, set the actual OAuth issuer under `xgt.extraConfig.security.oidc` and set `backend.oidc.frontendUrl` to the public Mission Control URL. This URL must match `route.yaml` and the callback registered in step 5.

`xgt.config` contains the group-to-label mappings; `xgt.extraConfig` holds server settings. Keep `xgt.enabled: true` and `xgt.hostname: xgt-test-0`. Helm's `fips.enabled: true` selects the XGT/Mission Control FIPS images and the chart's default Percona MongoDB image; no MongoDB image override is needed. Base XGT/Mission Control tags stay unsuffixed. Use an approved chart revision and review the rendered images before installing or upgrading.

```sh
helm template rocketgraph ../../charts/rocketgraph \
  -n xgt-demo -f values.yaml > .private/helm-rendered.yaml
```

Review the rendered resources: this example selects `restricted-v2`, creates no elevated SCC grant and leaves UID/GID assignment to OpenShift. The frontend Service retains ports 80/443 and targets container ports 8080/8443. Then install:

```sh
helm upgrade --install rocketgraph ../../charts/rocketgraph \
  -n xgt-demo -f values.yaml --wait --timeout=10m
oc -n xgt-demo get pods,pvc
oc -n xgt-demo exec deployment/rocketgraph-xgt -- cat /proc/sys/kernel/hostname
```

**Expected:** four ready application pods, bound PVCs, and hostname `xgt-test-0`. XGT uses TLS; MongoDB uses authentication, required TLS and `--tlsFIPSMode`. Check logs and the actual crypto configuration for FIPS acceptance; do not disable verification to pass the test.

All application workloads are managed with Helm. After editing XGT settings or mappings in `values.yaml`, rerun the same `helm upgrade --install` command. The chart's configuration checksum triggers a new XGT pod. External Secret changes may require a rollout restart.

### Optional: Add Separate Dev and Prod XGT Releases

Use one Helm release per XGT server. These are independent servers, not replicas or an HA cluster. Each receives separate configuration, Services and data/log PVCs. The commands below reuse the test settings; add a per-environment values file when settings differ.

First ensure the license covers `xgt-dev-0` and `xgt-prod-0`. XGT TLS certificates must cover each release's Service name. The optional test certificate script includes all three names. For separate production certificates, create separate Secrets and override `xgt.ssl.existingSecret`; include their issuing CAs in Mission Control's `backend-tls` trust bundle. Override `xgt.license.existingSecret` if licenses are separate.

```sh
helm upgrade --install xgt-dev ../../charts/rocketgraph \
  -n xgt-demo -f values.yaml \
  --set missionControl.enabled=false --set mongodb.enabled=false \
  --set xgt.hostname=xgt-dev-0 --wait --timeout=10m

helm upgrade --install xgt-prod ../../charts/rocketgraph \
  -n xgt-demo -f values.yaml \
  --set missionControl.enabled=false --set mongodb.enabled=false \
  --set xgt.hostname=xgt-prod-0 --wait --timeout=10m
```

| Helm release | Licensed container hostname | XGT endpoint | Includes Mission Control/MongoDB |
| --- | --- | --- | --- |
| `rocketgraph` | `xgt-test-0` | `rocketgraph-xgt:4367` | Yes |
| `xgt-dev` | `xgt-dev-0` | `xgt-dev-xgt:4367` | No |
| `xgt-prod` | `xgt-prod-0` | `xgt-prod-xgt:4367` | No |

`xgt.enabled` stays `true` for all three. The shared Mission Control's `backend.oidc.xgtAllowedHosts` already lists these endpoints. Leave `backend.env.XGT_SERVER_CN` unset so TLS checks each selected endpoint's certificate identity. XGT-only releases still use `backend.oidc.caCertExistingSecret` to mount the OAuth/API CA bundle.

Keep the release-specific settings on subsequent upgrades, preferably in version-controlled values files. Each additional XGT requests 2 GiB of memory and 11 GiB of storage with this example. Uninstalling a release also deletes the PVCs created by this chart; arrange backups and volume retention before storing data you need to keep.

## 8. Publish Mission Control

```sh
oc apply -f route.yaml
oc -n xgt-demo get route mission-control
```

The supplied edge Route encrypts browser-to-router traffic. Router-to-frontend and frontend-to-backend traffic is HTTP in this example. If those hops must be encrypted, use the approved internal TLS design before proceeding. FIPS image selection does not change those connections.

Open the HTTPS URL and sign in through OpenShift, selecting the LDAP provider. If the Mission Control login form is shown, choose `OidcAuth` (the existing option name for OpenShift OAuth2). If asked for an XGT endpoint, use `rocketgraph-xgt:4367`. Test Alice and Bob separately.

**Expected:** Alice is an XGT administrator; Bob has `data-users` without `xgtadmin`. Mission Control discovers the issuer/client ID/scopes from XGT; the OAuth secret and CA are supplied separately. `frontendUrl` is the public Mission Control URL override, not the OpenShift login URL.

## 9. Test Python Login and Data Permissions

Python is needed only for this client demonstration:

```sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements.txt
```

In a second terminal, open an administrator-authorized tunnel:

```sh
oc -n xgt-demo port-forward service/rocketgraph-xgt 14367:4367 --address=127.0.0.1
```

From the browser's workstation, with the virtual environment active:

```sh
python login.py --demo create
python login.py --demo read
```

Choose Alice to create the sample table. Repeat the read command as Alice and Bob, signing out of the OpenShift browser session between identities. The browser must reach the local callback on port 8765.

**Expected:** Alice reads `[[42]]` from the admin-only table; Bob gets an expected denial. The script also prints identity, labels, administrator status and `[[1]]` from a basic query. It verifies XGT TLS through the tunnel.

To test an optional dev/prod server instead, tunnel its Service and pass its certificate name, for example `python login.py --server-name xgt-dev-xgt`. Each server has its own demo data.

## 10. Test an Automated Account

```sh
oc -n xgt-demo-jobs create token xgt-automation --duration=1h > .private/xgt.token
python login.py --token-file .private/xgt.token
python login.py --token-file .private/xgt.token --demo read
```

**Expected:** identity `system:serviceaccount:xgt-demo-jobs:xgt-automation`, label `automation`, successful basic query, no admin access and denied admin-only data access. No browser or LDAP password is used. Actual token lifetime follows cluster policy.

This demonstration uses the administrator's tunnel. Real jobs need an approved network path and token renewal. The chart's default XGT NetworkPolicy permits connections to the XGT port from any source; review that policy against your client-access requirements. The namespace-wide automation label applies to every service account in `xgt-demo-jobs`.

## 11. Show Membership Changes and Turn On Scheduled Sync

Have the LDAP administrator add Bob to the admin group using the directory UI or the supplied [add-membership LDIF](bob_add_admin.ldif.example). For the LDIF approach, edit the actual DNs and use an authorized LDAP account:

```sh
LDAPTLS_CACERT="$PWD/.private/ldap-ca.crt" LDAPTLS_REQCERT=demand \
  ldapmodify -x -H ldaps://YOUR_LDAP_HOST:636 -D 'YOUR_LDAP_ADMIN_DN' -W \
  -f bob_add_admin.ldif.example
oc -n xgt-demo-ldap-sync create job --from=cronjob/xgt-demo-ldap-sync xgt-sync-add
oc -n xgt-demo-ldap-sync wait --for=condition=complete job/xgt-sync-add --timeout=330s
python login.py --demo read
```

Choose Bob: a fresh session should now have admin access. Restore his original membership using [bob_remove_admin.ldif.example](bob_remove_admin.ldif.example) with the same `ldapmodify` command, run another sync Job named `xgt-sync-remove`, and verify that a fresh Bob session is denied. Use a new Job name for each repeat. Also test rejection of an incorrect password.

To enable the 15-minute schedule, change `spec.suspend` to `false` in `ldap_sync.yaml`:

```sh
oc apply -f ldap_sync.yaml
oc -n xgt-demo-ldap-sync get cronjobs,jobs
```

For new groups, update `ldap_groups.txt`, the sync name mappings and XGT label mappings, then recreate/update the sync ConfigMap with the step 4 `--dry-run=client` command and upgrade each affected Helm release with its values. Removing a whitelist entry does not delete the existing OpenShift Group. Assign ownership for group removal, alerts, credential renewal and existing-session revocation behavior.

Log in as Alice to remove the demo data, then close the tunnel:

```sh
python login.py --demo cleanup
```

## Troubleshooting

```sh
oc -n xgt-demo get events --sort-by=.lastTimestamp
oc -n xgt-demo describe pods -l app=xgt,app.kubernetes.io/instance=rocketgraph
oc -n xgt-demo logs deployment/rocketgraph-xgt --tail=50
oc -n xgt-demo logs deployment/rocketgraph-backend --tail=100
oc -n xgt-demo logs deployment/rocketgraph-mongodb --tail=100
oc -n xgt-demo-ldap-sync get jobs,pods
```

Check LDAP login before group sync, group membership before XGT labels, and certificate trust/network access before OAuth callbacks. This is a fresh installation, not a database migration. The earlier lab validated image compatibility and authentication, not an end-to-end FIPS environment.
