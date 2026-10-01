# XGT on OpenShift: LDAP Login and FIPS Deployment

Deployment planning guide

For a concrete first installation with commands and checkpoints, use the separate [test-server walkthrough](openshift_test_server/README.md).

**Proposed approach:** run XGT and Mission Control on OpenShift, use the existing LDAP directory through OpenShift browser login, and map OpenShift groups to XGT permissions. Automated applications use service-account tokens. The identity administrators manage LDAP integration; the XGT administrator manages application permissions.

```text
Human → Mission Control / Python browser login → OpenShift OAuth → LDAP
                                                      ↓ token
Client → XGT → OpenShift User API → username + groups → XGT labels

LDAP groups → scheduled OpenShift group sync → OpenShift Group objects
Automated job → service-account token → XGT → same User API validation
```

This integration is **OpenShift OAuth2 authentication**. The API remains `xgt.OidcAuth`, and configuration names remain `security.oidc`, `backend.oidc` and `MC_OIDC_*`. Mission Control or the Python browser client exchanges an authorization code for an access token. XGT validates that token through the OpenShift User API (`openshift_userapi`) to retrieve identity and groups; it does not use OIDC ID tokens or a standard UserInfo endpoint. The client secret belongs to the application obtaining the token, not XGT's token validation. See the [XGT authentication reference](https://docs.rocketgraph.com/sysadmin_guide/user_authentication.html#openshift).

## 1. Agree on the Deployment Inputs

**Owners: OpenShift administrator, identity administrator, XGT administrator, security/PKI team.**

| Input | Decision needed |
| --- | --- |
| Cluster | OpenShift version, existing FIPS configuration, namespace, capacity and storage class |
| Identity | LDAP endpoint, trusted CA, read-only bind account, user/group search schema and nested-group rules |
| Permissions | Directory groups for XGT administrators and regular users; separate automation permissions |
| Endpoints | Mission Control HTTPS URL, OpenShift OAuth URL, and reachable XGT endpoint for clients/jobs |
| License | License file and stable licensed hostname, with one XGT replica initially |
| Operations | Owners of group sync, certificate/secret rotation, token renewal and backups |

Example names throughout: application namespace `xgt`, automation namespace `xgt-jobs`, Helm release `rocketgraph`, OAuthClient `xgt-client`, and Mission Control `https://mc.apps.example.com`. Replace them consistently.

Example licensed hostnames are `demo-xgt-prod`, `demo-xgt-test`, and `demo-xgt-dev`; obtain a license covering the names used in your installation. Chart 0.4.0 adds `xgt.hostname` to set the container's licensed hostname while retaining Helm's Deployment. A release name alone does not set this hostname. Use a separate Helm release per independent XGT server, each with its own hostname, settings and storage. Additional releases can disable Mission Control and MongoDB and share the first release's Mission Control. The [test-server guide](openshift_test_server/README.md#optional-add-separate-dev-and-prod-xgt-releases) includes commands.

## 2. Establish the FIPS and TLS Requirements First

**Owners: OpenShift and security/PKI teams, with Rocketgraph support.**

Confirm that the target cluster was installed for FIPS operation. OpenShift documents FIPS as an installation-time choice; it cannot simply be enabled on an already deployed cluster. Follow the instructions for the customer's exact OpenShift version. [OpenShift FIPS guidance](https://docs.redhat.com/en/documentation/openshift_container_platform/4.20/html/installation_overview/installing-fips)

Select these image families through `fips.enabled: true`:

| Component | Images used in our compatibility test |
| --- | --- |
| XGT | `rocketgraph/xgt:2.7.1-fips` |
| Mission Control frontend | `rocketgraph/mission-control-frontend:2.7.0-fips` |
| Mission Control backend | `rocketgraph/mission-control-backend:2.7.0-fips` |
| MongoDB | `percona/percona-server-mongodb:8.0.23` |

Keep base XGT/Mission Control tags unsuffixed in Helm values; the chart appends `-fips`. The example values use the chart's default Percona image through `fips.enabled: true`, with no MongoDB image override. Pin an approved chart version and review its rendered image versions before installing or upgrading. The table records what we tested, not a claim that those are the latest approved production versions. [Chart FIPS settings](https://github.com/Rocketgraphai/rocketgraph/tree/main/charts/rocketgraph#fips-mode)

**FIPS images are one part of the deployment.** Confirm the validated cryptographic modules, supported operating environment and runtime configuration for each component with the vendors/security team. Include browser/OAuth HTTPS, verified LDAP TLS, XGT TLS, and MongoDB TLS. With both `fips.enabled` and `mongodb.tls.enabled`, this chart supplies MongoDB's `--tlsFIPSMode`; verify it starts successfully with the required cryptographic module active. [Percona FIPS guidance](https://docs.percona.com/percona-server-for-mongodb/8.0/fips.html)

Decide whether Route-to-frontend and frontend-to-backend traffic must also be encrypted. An edge Route terminates HTTPS at the router; neither it nor the FIPS image switch secures every internal hop. Include storage encryption in the design if required by the organization's policy.

**What our lab established:** login, groups, labels, queries and automation worked with the selected images. The lab host was not in FIPS mode, so this was not an end-to-end FIPS validation.

## 3. Connect LDAP to OpenShift and Schedule Group Sync

**Owners: identity and OpenShift administrators.**

1. Reuse the existing OpenShift LDAP identity provider if one is already configured. Otherwise configure the LDAP URL, read-only bind credentials, user attributes and trusted CA; test browser login first.
2. Choose the LDAP groups to import, for example `xgt-admins` and `xgt-users`.
3. Prepare an `LDAPSyncConfig` matching the actual directory schema and a whitelist containing the selected group identifiers expected by that configuration. Ensure synchronized usernames match the OpenShift login identities.
4. Preview and then apply the synchronization:

```sh
oc adm groups sync --sync-config=ldap_sync_config.yaml --whitelist=ldap_groups.txt
oc adm groups sync --sync-config=ldap_sync_config.yaml --whitelist=ldap_groups.txt --confirm
oc get groups xgt-admins xgt-users -o yaml
```

5. Assign an owner and schedule for recurring synchronization, with failure monitoring and a process for removed memberships/groups. Test both additions and removals.

For the CronJob, service account, permissions and setup commands, use the [group-sync walkthrough](openshift_test_server/README.md#4-preview-and-apply-group-sync). It starts suspended and can be enabled after a successful test run.

**LDAP password validation and LDAP group synchronization are separate.** Successful login does not mean groups have been imported. XGT reads the groups exposed by OpenShift; it does not perform this sync. [OpenShift group synchronization](https://docs.redhat.com/en/documentation/openshift_container_platform/4.20/html/authentication_and_authorization/ldap-syncing)

## 4. Register the Browser Login Client

**Owner: OpenShift administrator.**

Create an OAuthClient with a generated secret, the `user:info` scope restriction, and exact callback URLs:

```yaml
apiVersion: oauth.openshift.io/v1
kind: OAuthClient
metadata:
  name: xgt-client
secret: REPLACE_WITH_GENERATED_SECRET
grantMethod: prompt
scopeRestrictions:
  - literals: ["user:info"]
redirectURIs:
  - http://127.0.0.1:8765/callback
  - https://mc.apps.example.com/api/login/oidc/callback
```

The localhost callback is for Python browser login and must be reachable by the user's browser on the client machine. The HTTPS callback is for Mission Control. Provide the client secret securely to Mission Control and authorized Python clients; server discovery does not distribute credentials. Keep the completed manifest out of source control. [OpenShift OAuth client registration](https://docs.redhat.com/en/documentation/openshift_container_platform/4.20/html/authentication_and_authorization/configuring-oauth-clients)

## 5. Prepare the License, Configuration, Certificates and Storage

**Owners: XGT administrator and security/PKI team.**

Create the application namespace and these Secrets there before deployment. Names match the [companion Helm values](openshift_fips_values.example.yaml):

| Secret | Required keys / purpose |
| --- | --- |
| `xgt-license` | `xgtd.lic`: license matching the chosen hostname |
| `xgt-oauth-client` | `MC_OIDC_CLIENT_SECRET`: the OAuthClient secret |
| `oidc-ca` | `oidc-ca.pem`: CA bundle trusting the OpenShift OAuth and User API endpoints |
| `xgt-ssl` | `server.cert.pem`, `server.key.pem`: XGT server certificate and key |
| `backend-tls` | `xgt-server.pem`: CA used by Mission Control to verify XGT |
| `mongodb-tls` | `server.pem` (certificate plus private key), `ca.pem` |
| `mongodb-auth` | `mongodb-root-password`: generated database password; bundled chart user is `rocketgraph` |

Use certificates whose identities/SANs cover the actual service names used by clients, including `rocketgraph-xgt` and `rocketgraph-mongodb` for this example release. Supply the Mission Control Route certificate through the platform's approved process. Client workstations also need the appropriate CA trust.

The chart mounts the license at `/license/xgtd.lic`, XGT configuration at `/conf/xgtd.conf`, label files at `/conf/grouplabel.csv` and `/conf/label.csv`, and the OAuth/API CA bundle at `/etc/ssl/certs/oidc-ca.pem`. Provision persistent storage for XGT data/logs and MongoDB; agree on resource sizing and backups.

Have the platform administrator review the chart's service-account/SCC permissions. The full-stack example uses chart 0.4.0's [restricted-v2 profile](../charts/rocketgraph/README.md#full-stack-with-openshift-restricted-v2), which creates no elevated SCC binding and lets OpenShift assign UIDs/groups. XGT starts directly with mounted configuration/license, and Mission Control's frontend uses writable nginx directories and container ports 8080/8443. Backend and MongoDB use their existing entrypoints. FIPS image selection and SCC permissions are separate requirements. If the platform requires centralized file storage, see the [existing-files PVC example](../charts/rocketgraph/README.md#bring-your-own-xgt-files).

## 6. Configure and Deploy XGT and Mission Control

**Owner: XGT administrator, with OpenShift administrator support.**

Start with [openshift_fips_values.example.yaml](openshift_fips_values.example.yaml), replace the example endpoints/names, and add site-specific storage, resource sizing and workload configuration. Its essential settings are:

- **XGT:** `validation_mode: openshift_userapi`, the cluster User API URL, OAuth issuer/client ID, `username_claim: metadata.name`, `groups_claim: groups`, and `scopes: user:info`.
- **Authorization:** map `xgt-admins → xgtadmin`, `xgt-users → data-users`, and the dedicated automation namespace's service-account group to `automation`. Declare each label. Apply data-access labels to the relevant XGT namespaces/frames; assigning a label alone does not define which data requires it.
- **Mission Control:** enable `OidcAuth`, supply its OAuth secret, configure CA trust and XGT TLS. It discovers issuer, client ID and scopes from XGT. `frontendUrl` is only needed when the proxy-derived public URL is wrong; `redirectUri` is another optional override, not an additional required setting.
- **FIPS/TLS:** select the FIPS images, enable XGT TLS and MongoDB `requireTLS`, and use the agreed Route/internal-traffic design.

Render the chart for review before installing through the approved Helm/GitOps workflow:

```sh
helm template rocketgraph ./charts/rocketgraph \
  --namespace xgt -f doc/openshift_fips_values.example.yaml > rendered.yaml
```

The companion values are a review template, not a complete production manifest. Set `xgt.hostname` to the licensed name and add the HTTPS Route; verify the rendered images, mounts, TLS settings and SCC grant, then deploy. Confirm healthy pods/PVCs, DNS, certificate validation and network access to LDAP, OAuth, the User API, XGT and MongoDB as appropriate for each component.

For an existing MongoDB deployment, back it up and pause writers before a supported migration to Percona. Existing volume ownership may need a storage-specific migration to the new workload identity. The restricted profile uses namespace-assigned IDs, not a fixed UID 1001; verify access before switching an existing database. Fresh PVCs were tested, which does not establish compatibility with previously populated storage. Handle this as a controlled database migration, not a blanket permission change.

## 7. Provision Automated Access and Token Renewal

**Owners: job owner and OpenShift administrator.**

Create a service account in the dedicated automation namespace and issue an expiring token for the initial test:

```sh
oc create namespace xgt-jobs
oc -n xgt-jobs create serviceaccount xgt-automation
umask 077
oc -n xgt-jobs create token xgt-automation --duration=1h > xgt.token
```

The requested duration is subject to the cluster's token policy. Jobs use `xgt.BearerTokenAuth(token)` over an approved TLS connection to XGT. They do not need an interactive browser, LDAP user password, or OpenShift administrator credentials. For jobs in Kubernetes, arrange a projected service-account token with an audience accepted by this validation path; the application must reread refreshed token contents when creating new connections. External jobs need an authorized token issuer/renewal process and secure token delivery.

The example mapping `system:serviceaccounts:xgt-jobs → automation` applies to **every service account in that namespace**. Restrict who can create workloads/service accounts there and grant only the intended XGT permissions. Do not map the broad service-account group to `xgtadmin` by default. XGT labels and OpenShift RBAC are separate; add cluster permissions only for operations the job actually needs.

If the environment explicitly requires a manually created long-lived service-account token Secret, agree on secure storage, rotation and revocation ownership. It is an alternative to automatic short-lived token renewal, not a prerequisite for automation. Recheck XGT session behavior during token revocation/expiry tests.

## 8. Demonstrate and Accept the Installation

**Owners: application tester, identity administrator and security team.**

| Test | Expected outcome |
| --- | --- |
| Alice in `xgt-admins` and `xgt-users` logs in through Mission Control | Browser visits OpenShift; XGT reports Alice with `xgtadmin` and `data-users` |
| Bob only in `xgt-users` logs in | `data-users`, no XGT admin access; admin-only data access denied |
| Wrong LDAP password | Authentication rejected |
| Python `xgt.OidcAuth` login | Browser flow completes and connects to the intended TLS-protected XGT endpoint |
| Service-account job using `xgt.BearerTokenAuth` | Expected service-account identity and `automation` label; intended query succeeds |
| LDAP membership removed and group sync rerun | New XGT session loses that access; document behavior for existing sessions |
| Token/certificate renewal | Connections continue using refreshed material; expired/invalid credentials fail as expected |
| FIPS verification on target cluster | Platform and application crypto evidence accepted by security team, including MongoDB FIPS/TLS startup |

For each successful XGT connection, check `conn.userid`, `conn.is_admin`, `conn.get_user_labels()` and `conn.run_job("RETURN 1 AS ok").get_data()`; the query should return `[[1]]`. Record the owners and schedules for group sync, credential renewal, backups and upgrades before handoff.

## Alternative Authentication Methods

| Mechanism | When it fits | Additional responsibility |
| --- | --- | --- |
| **OpenShift OAuth backed by LDAP — proposed** | OpenShift already owns login and group management | LDAP group sync and OAuthClient registration |
| Keycloak OIDC backed by LDAP | Organization already uses Keycloak or needs a separate identity provider | LDAP federation/group claims, browser and service clients; Keycloak's own FIPS deployment must be validated separately |
| Host-managed SSSD with sockets mounted into XGT | Existing administrator-managed SSSD integration on controlled hosts | Host/socket permissions, PAM/NSS integration and pod scheduling dependencies |
| SSSD inside XGT | Simple, dedicated direct LDAP/password setup | SSSD configuration, CA/bind credentials and daemon lifecycle; does not reproduce a complex enterprise SSSD policy automatically |

The deployment decisions are the identity path, responsible administrators, licensed hostname, FIPS/TLS requirements, group mappings, and automation renewal mechanism. Once those are agreed, the deployment inputs above can be filled in and reviewed.
