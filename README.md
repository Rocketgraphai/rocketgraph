# Rocketgraph Mission Control

**Unveiling the power of data through intuitive and dynamic visualizations.**

Rocketgraph Mission Control is an innovative web application designed to revolutionize the way organizations visualize and interact with complex datasets.  The application offers a comprehensive suite of tools that facilitate the interactive exploration of data through graph-based visualizations.  It integrates powerful features such as dynamic data loading, customizable views, and an intuitive user interface, all tailored to enhance the user experience in data analysis and visualization.  Mission Control is designed to be responsive and user-friendly, ensuring seamless navigation and an enriching data interaction experience.

For organizations managing large and intricate datasets, particularly in critical sectors like defense cybersecurity, finance, and healthcare, Rocketgraph Mission Control stands as a pivotal tool.  It delivers high-performance analytics and insightful visual representations, enabling users to uncover hidden patterns, relationships, and trends in data.  This level of insight is crucial for decision-making and strategic planning in high-stakes environments.  The application's capacity to handle massive datasets efficiently makes it an invaluable asset for organizations seeking to transform their data into actionable intelligence, thereby fostering informed decisions and enhancing operational effectiveness.

Rocketgraph Mission Control is a web application for driving property graph workloads in the [Rocketgraph xGT server](https://docs.rocketgraph.com).

## Quick Start

Perform these steps to install and run Rocketgraph Mission Control and Rocketgraph xGT on a server.

These five steps bring up a default stack on a machine with internet access.  For a production install — air-gapped hosts, SSL certificates, custom data and log directories, or an xGT server that isn't part of the Compose project — follow [Full Installation](#full-installation) instead.

 1. Make sure Docker is running.  You may need to start (or install) a [Docker Desktop](https://docs.docker.com/desktop/) or [Docker Engine](https://docs.docker.com/engine/).  To verify that Docker is working, run the following command.  You should see information about the Docker environment.  If you are using Podman rather than Docker, read [Running Under Podman](#running-under-podman) first — a rootless install needs additional setup before these steps will work.
    ```bash
    $ docker info
    ```

 1. Copy the `docker-compose.yml` file from this repo to your server or laptop.

 1. If installing on IBM Power Series, create a `.env` file in the same directory as the `docker-compose.yml` file containing this line:
    ```env
    MC_MONGODB_IMAGE=ibmcom/mongodb-ppc64le
    ```

 1. Start Rocketgraph Mission Control and Rocketgraph xGT:
    ```bash
    $ docker compose up --detach
    ```

 1. Aim a browser to `localhost` on the system running this Docker application and log in to Mission Control.

## Supported Container Platforms

Mission Control runs on four container platforms.  All four deploy the same four containers — frontend, backend, xgt, and MongoDB — and support the same features; they differ only in how you configure and launch them.

| Platform | Deployed with | Start here |
|---|---|---|
| **Docker** (Desktop or Engine) | the `docker-compose*.yml` files in this repo | [Quick Start](#quick-start) above, or [Full Installation](#full-installation) |
| **Podman** (rootless or root) | the same Compose files, via `podman-compose` | [Running Under Podman](#running-under-podman) — read this first, then follow the Docker instructions |
| **Kubernetes** | the Helm chart in [`charts/rocketgraph/`](charts/rocketgraph/) | [Helm chart documentation](charts/rocketgraph/README.md) |
| **OpenShift** | the same Helm chart, with `openshift.enabled=true` | [OpenShift](charts/rocketgraph/README.md#openshift) in the Helm chart documentation |

The rest of this document covers the Compose-based platforms, Docker and Podman.

## In-Depth Guides

The guides below cover individual topics in depth.  The first four apply to every platform: their examples are written for Docker Compose and Podman, and each one notes the Kubernetes and OpenShift equivalent.

| Guide | What it covers |
|---|---|
| [MongoDB Security](doc/mongodb_security.md) | Authentication, TLS, mutual TLS, and encryption at rest for the bundled MongoDB |
| [OIDC Authentication](doc/oidc_configuration.md) | Signing users in through an external identity provider such as Keycloak or OpenShift |
| [Site LLM Configuration](doc/llm_site_config.md) | Which AI models Mission Control offers, their endpoints, and their credentials |
| [ODBC Configuration](doc/odbc_configuration.md) | Loading data from external databases — PostgreSQL, MariaDB, and IBM i (AS/400) |
| [Deployment Reference](doc/deployment_reference.md) | Per-container images, ports, volume paths, and environment variables — for orchestrators not listed above, or for debugging a running container |
| [Helm Chart](charts/rocketgraph/README.md) | Deploying on Kubernetes and OpenShift, and every value the chart accepts |

## Compose Files and Images

Rocketgraph Mission Control uses Docker Compose with these Docker images:
 - [rocketgraph/xgt](https://hub.docker.com/r/rocketgraph/xgt)
 - [rocketgraph/mission-control-frontend](https://hub.docker.com/r/rocketgraph/mission-control-frontend)
 - [rocketgraph/mission-control-backend](https://hub.docker.com/r/rocketgraph/mission-control-backend)
 - [mongo](https://hub.docker.com/_/mongo) or [percona](https://hub.docker.com/r/percona/percona-server-mongodb)

Three Compose files are provided:
 - `docker-compose.yml` — the base stack, used by default (`docker compose up -d`).
 - `docker-compose.fips.yml` — optional FIPS overlay (see [FIPS Deployment](#fips-deployment)).
 - `docker-compose.license-manager.yml` — optional xGT License Manager overlay (see [xGT License Manager](#xgt-license-manager)).

The overlays layer on top of the base — keep `docker-compose.yml` alongside them and combine with `-f`:

```bash
docker compose -f docker-compose.yml -f docker-compose.fips.yml up -d
```

Rocketgraph Mission Control can be run using either Docker Desktop or Docker Engine only.  Further references to Docker Engine in this document refer to a Docker Engine install without Docker Desktop.

The instructions in this document are written for Docker.  The same Compose files run under Podman and everything here applies there too — but a rootless Podman install has three additional constraints to handle first.  See [Running Under Podman](#running-under-podman).

## Configuration for the xGT Server

The Mission Control frontend, backend, and database containers must be run on the same host.  However, the xGT server can be run in the following ways:
 - In a Docker container as part of the Compose project.
 - In an isolated Docker container (separate from the Compose project) on the same host as Mission Control.
 - Installed from an RPM on the same host as Mission Control.
 - On a different host than Mission Control, either in a Docker container or installed from an RPM.

### xGT as Part of the Compose Project

The hostname to use when logging into Rocketgraph Mission Control is either `xgt`, the name of the service for the xGT server in the docker-compose.yml file, or the host's external IP.

xGT can be configured when run as part of the Compose project.  See the [documentation for running xGT in a Docker container](https://docs.rocketgraph.com/using_docker_image/index.html) for more details.  That page describes configuring xGT when running directly using Docker vs. Docker Compose, but the process when using Compose is similar.  One difference is that Docker Compose commands are used to start, stop, and restart containers.  For instance, restarting a container is done by the following where container_name is something like `rocketgraph-xgt-1`.

```bash
$ docker compose restart <container_name>
```

Another difference is that volume mapping is setup in the Compose file instead of command-line parameters to Docker.  The configuration, data, and log directories are mapped through the XGT_CONF_PATH, XGT_DATA_PATH, and XGT_LOG_PATH environment variables.  Any other needed volume mappings would be done by adding an extra line to the volumes section of the xgt service in the Compose file:

```yaml
  xgt:
    volumes:
      - /host/map/dir:/container/map/dir
```

### xGT in an Isolated Container on the Mission Control Host

Here is an example of starting the xGT server in an isolated container:
```bash
$ docker run --name xgt --detach --publish 4367:4367 \
    --volume /host/conf/dir:/conf \
    --volume /host/data/dir:/data \
    --volume /host/log/dir:/log \
    rocketgraph/xgt
```
This command exposes port 4367 to the host.  The xGT server listens on port 4367.  Exposing this port is required for Rocketgraph Mission Control to communicate with the isolated container.  The command also volume maps a config directory, a data directory, and a log directory.  Change the command to map only the directories you need and point to the correct host directories.  See the [documentation for running xGT in a Docker container](https://docs.rocketgraph.com/using_docker_image/index.html) for more details.

Comment out or delete the `xgt` service section in the docker-compose.yml file.

Use the host's external IP as the hostname when logging into Rocketgraph Mission Control.

Another option for the login hostname is to use either `localhost` or `host.docker.internal`, but further configuration is required if using Docker Engine to run Rocketgraph Mission Control.  In that case, add the following lines in the backend section of the docker-compose.yml file:
```yaml
    extra_hosts:
      - "host.docker.internal:host-gateway"
```
Docker Desktop automatically provides the translation of "host.docker.internal" to the gateway IP of the default bridge network.  These lines add the translation in Docker Engine.  Mission Control translates "localhost" to "host.docker.internal" to provide a shorter more commonly understood hostname.

### xGT Installed from an RPM on the Mission Control Host

The xGT server configuration variable `system.hostname` must be set appropriately when connecting Rocketgraph Mission Control to an RPM installed xGT.  See the [xGT configuration documentation](https://docs.rocketgraph.com/sysadmin_guide/configuration.html) for more details.  One option is to set "system.hostname" to the host's external IP.  If access on 127.0.0.1 is desired in addition to access via the host's external IP, set "system.hostname" to "0.0.0.0".

To setup access via 127.0.0.1 but no external access, the setup is slightly more complicated.  If using Docker Desktop to run Rocketgraph Mission Control, use the default value of "localhost" for "system.hostname".  If using Docker Engine to run Rocketgraph Mission Control, "system.hostname" must be set to the gateway IP of Docker's default bridge network.  The gateway IP is almost always "172.17.0.1".  To verify the gateway IP, do
```bash
$ docker network inspect bridge
```
Look for a section like this
```
        "IPAM": {
            "Driver": "default",
            "Options": null,
            "Config": [
                {
                    "Subnet": "172.17.0.0/16",
                    "Gateway": "172.17.0.1"
                }
            ]
        },
```
The gateway IP is the value for "Gateway".

After setting the value for "system.hostname" and starting the xGT server, comment out or delete the `xgt` service section in the docker-compose.yml file.

Use the host's external IP as the hostname when logging into Rocketgraph Mission Control.

If the xGT server is configured for access via 127.0.0.1, another option for the login hostname is to use either `localhost` or `host.docker.internal`.  However, further configuration is required if using Docker Engine to run Rocketgraph Mission Control.  In that case, uncomment the following lines in the backend section of the docker-compose.yml file:
```yaml
    extra_hosts:
      - "host.docker.internal:host-gateway"
```
Docker Desktop automatically provides the translation of "host.docker.internal" to the gateway IP of the default bridge network.  These lines add the translation in Docker Engine.  Mission Control translates "localhost" to "host.docker.internal" to provide a shorter more commonly understood hostname.

### xGT on a Different Host

The xGT server can be running on the other host either in a Docker container or installed from an RPM.

Comment out or delete the `xgt` service section in the docker-compose.yml file.

Use the IP of the host where the xGT server is running as the hostname when logging into Rocketgraph Mission Control.

## Environment Variables

There are a number of environment variables that configure Mission Control and the xGT server.  Variables that start with MC_ configure Mission Control, while variables that start with XGT_ configure the server.  We suggest putting definitions of the environment variables in a .env file in the same directory as the docker-compose.yml file.  That way they will be available for all Docker Compose commands.

Here is an example .env file that sets up running the web server using SSL.

```dotenv
MC_SSL_PUBLIC_CERT=/directory/to/ssl/td-cert.pem
MC_SSL_PRIVATE_KEY=/directory/to/ssl/td-private-key.pem
```

The configurable environment variables are:

### Container Images

|Variable                |Volume Mapped|Description|
|------------------------|-|-----------|
|MC_FRONTEND_IMAGE       | |image location for MC frontend; default is the version pinned in docker-compose.yml|
|MC_BACKEND_IMAGE        | |image location for MC backend; default is the version pinned in docker-compose.yml|
|MC_MONGODB_IMAGE        | |used to specify the mongodb image for Power10 installs|
|XGT_IMAGE               | |image location for XGT; default is the version pinned in docker-compose.yml|
|MC_LICENSE_MANAGER_IMAGE| |image for the optional xGT License Manager service (`docker-compose.license-manager.yml`); switch to the `-fips` tag for FIPS deployments|

### Web Server Ports and TLS

|Variable                |Volume Mapped|Description|
|------------------------|-|-----------|
|MC_PORT                 | |alternative host port for the http web server (default 80); must be ≥ 1024 under rootless Podman — see [Running Under Podman](#running-under-podman)|
|MC_SSL_PORT             | |alternative host port for the https web server (default 443); must be ≥ 1024 under rootless Podman — see [Running Under Podman](#running-under-podman)|
|MC_EXTERNAL_TLS         | |set to `true` when HTTPS is terminated by a proxy in front of Mission Control so session cookies are marked Secure; unnecessary when Mission Control serves HTTPS itself|
|MC_SSL_PUBLIC_CERT      |Y|path to certificate on host to setup an https web server|
|MC_SSL_PRIVATE_KEY      |Y|path to private key on host to setup an https web server|
|MC_SSL_CERT_CHAIN       |Y|path to certificate chain used by the https web server to validate client certificates for mTLS|

### xGT Server

|Variable                |Volume Mapped|Description|
|------------------------|-|-----------|
|XGT_PORT                | |port the xGT server should listen on|
|XGT_CONF_PATH           |Y|path to the configuration directory on host for the xGT server|
|XGT_DATA_PATH           |Y|path to the data directory on host for the xGT server|
|XGT_LOG_PATH            |Y|path to the log directory on host for the xGT server|
|XGT_AUTH_TYPES          | |sets xGT server authentication types available in Mission Control; unset offers all of BasicAuth, FilePKIAuth, and PKIAuth; `"[]"` runs single-user mode with no login|
|MC_DEFAULT_XGT_HOST     | |default login host for Mission Control|
|MC_DEFAULT_XGT_PORT     | |default login port for Mission Control|
|MC_XGT_ALLOWED_HOSTS    | |comma-separated allowlist of permitted xGT servers as `host:port` pairs; `*` wildcards supported (e.g. `xgt-*.xgt.myns.svc.cluster.local:4367`); when set, connections to any non-matching host are rejected; recommended when the xGT host is user-supplied (prevents SSRF)|

### Backend-to-xGT TLS

|Variable                |Volume Mapped|Description|
|------------------------|-|-----------|
|XGT_SSL_SERVER_CERT     |Y|path to chain file on host for the xGT server’s certificate|
|XGT_SERVER_CN           | |common name on the xGT server’s certificate|
|MC_SSL_PROXY_PUBLIC_CERT|Y|path to certificate on host to use as a proxy connection to the xGT server|
|MC_SSL_PROXY_PRIVATE_KEY|Y|path to private key on host to use as a proxy connection to the xGT server|

### MongoDB

|Variable                |Volume Mapped|Description|
|------------------------|-|-----------|
|MC_MONGO_URI            | |location of the database used by Mission Control; auto-constructed from `MC_MONGO_PASSWORD` when set, override directly to point at an external MongoDB|
|MC_MONGO_PASSWORD       | |MongoDB root password; set it to enable MongoDB auth (`--auth` + `?authSource=admin`). The root user is always `rocketgraph`; leave unset for no auth|
|MC_MONGO_TLS_ENABLED    | |set to `true` to enable TLS between the backend and MongoDB; requires `MC_MONGO_TLS_SERVER_PEM` and `MC_MONGO_TLS_CA_PEM`|
|MC_MONGO_TLS_MODE       | |mongod TLS server mode: `requireTLS` (default), `preferTLS`, or `allowTLS`; use `preferTLS`/`allowTLS` for migrations|
|MC_MONGO_MTLS_ENABLED   | |set to `true` to require client certs (mutual TLS); off by default (server-only TLS); needs `MC_MONGO_TLS_CLIENT_PEM`|
|MC_MONGO_TLS_SERVER_PEM |Y|path to MongoDB server cert+key PEM (concatenated); used when `MC_MONGO_TLS_ENABLED=true`|
|MC_MONGO_TLS_CLIENT_PEM |Y|path to the client cert+key PEM the backend presents under mTLS; required when mTLS is enabled|
|MC_MONGO_TLS_CA_PEM     |Y|path to MongoDB CA cert PEM; used when `MC_MONGO_TLS_ENABLED=true` (mounted into both mongodb and backend)|
|MC_MONGO_ENCRYPTION_ENABLED| |set to `true` to enable MongoDB application-level encryption at rest (FIPS overlay only — requires Percona)|
|MC_MONGO_ENCRYPTION_KEY_FILE|Y|path to a 32-byte base64-encoded key file; required when `MC_MONGO_ENCRYPTION_ENABLED=true`|

### Licensing

|Variable                |Volume Mapped|Description|
|------------------------|-|-----------|
|XGT_LICENSE_FILE        |Y|path to xGT license file (used when no license manager is enabled)|
|MC_LICENSE_MANAGER_CONF_PATH|Y|host config directory for the License Manager; place `.lic` files in its `licenses/` subdirectory (default `~/.rocketgraph/license-manager/conf`)|
|MC_LICENSE_MANAGER_LOG_PATH|Y|host log directory for the License Manager (default `~/.rocketgraph/license-manager/log`)|

### OIDC Authentication

|Variable                |Volume Mapped|Description|
|------------------------|-|-----------|
|MC_OIDC_ISSUER          | |*(experimental)* OIDC issuer URL; if empty, discovered from the xGT server|
|MC_OIDC_CLIENT_ID       | |*(experimental)* OAuth2 client ID; if empty, discovered from the xGT server|
|MC_OIDC_CLIENT_SECRET   | |*(experimental)* client secret for confidential OAuth2 clients|
|MC_OIDC_SCOPES          | |*(experimental)* space-separated OAuth2 scopes to request; default: `openid profile email`|
|MC_OIDC_FRONTEND_URL    | |*(experimental)* override the frontend base URL for post-login redirects; derived server-side from the request hostname and `MC_PORT`/`MC_SSL_PORT` by default|
|MC_OIDC_REDIRECT_URI    | |*(experimental)* override the redirect URI sent to the IdP; derived server-side from the request hostname and `MC_PORT`/`MC_SSL_PORT` by default|
|MC_OIDC_ALLOWED_ORIGINS | |*(experimental)* comma-separated list of permitted frontend origins; `*` wildcards supported (e.g. `https://*.apps.cluster.example.com`); optional defense-in-depth|
|MC_OIDC_TLS_VERIFY      | |*(experimental)* TLS verification for OIDC calls: `true` (default), `false`, or a path to a CA bundle|
|MC_OIDC_CA_CERT         |Y|*(experimental)* path to a CA bundle PEM file to trust for OIDC HTTPS calls|

### Database Connectivity (ODBC)

|Variable                |Volume Mapped|Description|
|------------------------|-|-----------|
|MC_ODBC_PATH            |Y|path to ODBC drivers for the connector|
|MC_ODBC_LIBRARY_PATH    | |directory for IBM i driver libraries|
|MC_IBM_IACCESS_PATH     |Y|root directory for IBM i Access Client|

### Site and LLM Configuration

|Variable                |Volume Mapped|Description|
|------------------------|-|-----------|
|MC_SITE_CONFIG_YML      |Y|path to site yaml config file|
|MC_SITE_CONFIG_PY       |Y|path to site python custom LLM config file|

### Sessions

|Variable                |Volume Mapped|Description|
|------------------------|-|-----------|
|MC_SESSION_TTL          | |seconds of user inactivity before an MC login expires; users get an idle warning dialog before being logged out|

The variables that are volume mapped map point to a file or directory on the host that gets mapped to an expected location in the containers.

## Full Installation

 1. Copy the `docker-compose.yml` file from this repo to your server or laptop.

 1. If the machine you want to run on doesn't have internet access, download all the Docker images on a machine connected to the internet.  The machine you download on must have the same architecture as the machine you want to run on.

    1. Download the Docker images.
       ```bash
       $ docker pull mongo
       $ docker pull rocketgraph/xgt
       $ docker pull rocketgraph/mission-control-frontend
       $ docker pull rocketgraph/mission-control-backend
       ```

    1. Save the Docker images to file.  Make sure to use the `<image>:<tag>` format to specify the image for the save command.  Otherwise you might have to manually add tags when loading later.
       ```bash
       $ docker save --output mongo.tar mongo:latest
       $ docker save --output xgt.tar rocketgraph/xgt:latest
       $ docker save --output mission-control-frontend.tar rocketgraph/mission-control-frontend:latest
       $ docker save --output mission-control-backend.tar rocketgraph/mission-control-backend:latest
       ```

    1. Copy the Docker image tar files to the machine they are to be installed on.

    1. Load the Docker images:
       ```bash
       $ docker load --input mongo.tar
       $ docker load --input xgt.tar
       $ docker load --input mission-control-frontend.tar
       $ docker load --input mission-control-backend.tar
       ```

 1. If you need docker image versions other than the pinned defaults, or to get them from somewhere other than Docker Hub, set the MC_FRONTEND_IMAGE, MC_BACKEND_IMAGE, MC_MONGODB_IMAGE, and XGT_IMAGE environment variables.  For example:
    ```dotenv
    MC_FRONTEND_IMAGE=10.0.1.10/rocketgraph/mission-control-frontend:<tag>
    MC_BACKEND_IMAGE=10.0.1.10/rocketgraph/mission-control-backend:<tag>
    MC_MONGODB_IMAGE=10.0.1.10/library/mongo:<tag>
    XGT_IMAGE=10.0.1.10/rocketgraph/xgt:<tag>
    ```

 1. If running the xGT server as part of the Compose project, setup a data directory using the environment variable XGT_DATA_PATH.  The default is ~/.rocketgraph/data if XGT_DATA_PATH is not set.  For example:
    ```dotenv
    XGT_DATA_PATH=/path/to/data/dir
    ```

 1. (Optional) If running the xGT server as part of the Compose project, setup a configuration directory using the environment variable XGT_CONF_PATH.  The default is ~/.rocketgraph/conf if XGT_CONF_PATH is not set.  For example:
    ```dotenv
    XGT_CONF_PATH=/path/to/conf/dir
    ```

 1. (Optional) If running the xGT server as part of the Compose project, setup a log directory using the environment variable XGT_LOG_PATH.  The default is ~/.rocketgraph/log if XGT_LOG_PATH is not set.  For example:
    ```dotenv
    XGT_LOG_PATH=/path/to/log/dir
    ```

 1. (Optional) Setup using SSL to connect from Mission Control to the xGT server.  The xGT server must also be configured to use SSL.  (See the [xGT configuration documentation](https://docs.rocketgraph.com/sysadmin_guide/configuration.html).)  Set the environment variables XGT_SSL_SERVER_CERT and XGT_SERVER_CN.  For example:
    ```dotenv
    XGT_SSL_SERVER_CERT=/directory/to/ssl/ca-chain.cert.pem
    XGT_SERVER_CN='Rocketgraph'
    ```

 1. (Optional) Setup certificates for connecting from the browser to Mission Control over https.  Set the environment variables MC_SSL_PUBLIC_CERT and MC_SSL_PRIVATE_KEY to the certificate and private key for the web server.  For example:
    ```dotenv
    MC_SSL_PUBLIC_CERT=/directory/to/ssl/td-public.pem
    MC_SSL_PRIVATE_KEY=/directory/to/ssl/td-private.pem
    ```

 1. (Optional) Set a default host and port for when a user first logs into Mission Control using the environment variables MC_DEFAULT_XGT_HOST and MC_DEFAULT_XGT_PORT.  These only affect the first time a user logs in as the host and port from the last login are cached in their browser after that.  If not set the defaults are “xgt” (for connecting to the xGT Docker image) and 4367 (default xGT server port).  For example:
    ```dotenv
    MC_DEFAULT_XGT_HOST=192.168.1.1
    MC_DEFAULT_XGT_PORT=4368
    ```

 1. (Optional) Select the xGT server authentication types available to Mission Control users using the environment variable XGT_AUTH_TYPES.  The supported types are 'BasicAuth', which uses a username and password, 'PKIAuth', which uses the PKI certificates set up in the browser, and 'FilePKIAuth', which uses certificate and key files selected at login.  When the variable is unset, all three types are offered.  An empty list runs Mission Control in single-user mode with no login — this is what the provided env.template sets.  The value of XGT_AUTH_TYPES must be a string representing a JSON list of the selected types.  This example allows only username / password authentication:
    ```dotenv
    XGT_AUTH_TYPES="['BasicAuth']"
    ```

 1. If upgrading, pull the latest versions of the Docker containers:
    ```bash
    $ docker compose pull
    ```

 1. Start Rocketgraph Mission Control:
    ```bash
    $ docker compose up --detach
    ```

 1. Aim a browser to the system running this Docker application and log in to Mission Control.

## Running Under Podman

The Compose files also work with `podman-compose`.  Follow [Full Installation](#full-installation) above, substituting `podman-compose` for `docker compose` throughout, and configure the xGT server and environment variables exactly as described there.

Two similarly named tools exist.  `podman-compose` (with a hyphen) is the standalone Python tool these instructions refer to.  `podman compose` (without one) is a Podman subcommand that delegates to whichever compose provider is installed on the machine — if that provider is Docker Compose, the Docker instructions apply as written.

Use `podman-compose` 1.6.0 or newer together with Podman 4.6.0 or newer.  The Compose files start the containers in dependency order using health checks, and older versions of either tool do not reliably enforce that ordering, so containers can start before the services they depend on are ready.

This section covers only what differs — three constraints, all of them consequences of running rootless: which host ports you can publish, who owns the mounted directories, and what happens at boot.  Read them before your first `podman-compose up`; the first two will otherwise stop the stack from starting.

### Host Ports

**Rootless Podman cannot publish host ports below 1024.**  Running rootless is the preferred way to use Podman, but the kernel reserves privileged ports for root, so an unprivileged `podman-compose up` cannot bind the host ports 80 and 443 that `docker-compose.yml` publishes by default.  Publish unprivileged ports instead by setting both in the `.env` file:

```dotenv
MC_PORT=8080
MC_SSL_PORT=8443
```

Mission Control is then reachable at `http://<host>:8080` and `https://<host>:8443`.

Nothing in Mission Control can move those back to 80 and 443 under a rootless install — publishing a privileged port requires privilege the container engine does not have.  To serve the standard ports from the host running the Mission Control containers, set up the mapping on the host yourself.  The options, roughly in order of how well they preserve the rootless security posture:

- **Reverse proxy.**  Run nginx or HAProxy on the host, listening on 80 and 443 and forwarding to 8080 and 8443.  If the proxy terminates TLS itself and forwards plain HTTP to 8080, also set `MC_EXTERNAL_TLS=true` so session cookies are marked `Secure`; if it passes TLS through to 8443, Mission Control terminates TLS itself and `MC_EXTERNAL_TLS` is unnecessary.
- **Kernel redirect or socket activation.**  An `iptables`/`nftables` `REDIRECT` rule (80 → 8080, 443 → 8443) moves the traffic with no extra process to run.  Alternatively, a systemd socket unit can hold the privileged listening socket and hand connections to the rootless container.  Both need root once, to install the rule or unit, not to run the containers.
- **Lower the unprivileged port floor.**  Setting `net.ipv4.ip_unprivileged_port_start=80` via `sysctl` lets rootless Podman bind 80 and 443 directly, so the default `MC_PORT`/`MC_SSL_PORT` values work unchanged.  This is host-wide: every unprivileged process on the machine gains the ability to bind those ports.
- **Run Podman as root.**  `sudo podman-compose up --detach` publishes 80 and 443 with no additional setup, at the cost of the isolation a rootless install provides.

One caveat applies to the first two options, which leave Mission Control's own ports unprivileged while the browser reaches it on 80 or 443.  Because the OIDC redirect URI is derived from `MC_PORT`/`MC_SSL_PORT` (see [OIDC Authentication](#oidc-authentication-experimental)), it will carry the internal port and will not match what the browser sees.  Set `MC_OIDC_FRONTEND_URL` (and `MC_OIDC_REDIRECT_URI` if the identity provider needs an exact value) to the externally visible URL.

### Volume Ownership

Rootless Podman runs containers inside a user namespace.  Your login UID maps to UID 0 (root) inside the container, and every other container UID maps to a value from the range assigned to you in `/etc/subuid`.  The consequence is that a host directory you own looks root-owned to a container process running as root — which works — but looks owned by `nobody` to a container process running as any other UID, which cannot write to it.

The stack bind-mounts these host directories read-write:

|Environment variable|Container path|Service|
|---|---|---|
|XGT_CONF_PATH|`/conf`|xgt|
|XGT_DATA_PATH|`/data`|xgt|
|XGT_LOG_PATH|`/log`|xgt|
|MC_LICENSE_MANAGER_CONF_PATH|`/conf`|license-manager (optional overlay)|
|MC_LICENSE_MANAGER_LOG_PATH|`/log`|license-manager (optional overlay)|

Any container running as a non-root UID needs its mounted directories chowned to that UID.  Today that is the license manager, whose image runs as uid 1000 (see the [deployment reference](doc/deployment_reference.md#xgt-license-manager)).  Do the chown from inside the user namespace:

```bash
podman unshare chown -R 1000:1000 \
    ~/.rocketgraph/license-manager/conf \
    ~/.rocketgraph/license-manager/log
```

`podman unshare` runs the command in the same user namespace the containers use, so the UID you name is the container-side UID and the files end up owned by the matching subuid on the host.  A plain `chown 1000:1000` run directly on the host sets the wrong owner and does not fix the problem.

The symptom of getting this wrong is a container that exits shortly after starting with a permission error on `/conf`, `/data`, or `/log`, or one that runs but never writes a log file.  Check with `podman-compose logs license-manager`.

Podman also accepts a `:U` volume option that chowns the mount contents to the container's UID automatically.  It is more convenient, but it rewrites the ownership of everything already in the directory, and `docker` rejects the option — adding it to a Compose file makes that file Podman-only.  Prefer `podman unshare chown` and keep the Compose files portable across both engines.

### Starting the Stack at Boot

Docker's daemon restarts containers that carry a `restart:` policy when the host boots.  Rootless Podman has no daemon — the containers belong to your user session and stop when that session ends, at logout as well as at reboot.  Two settings change that:

```bash
loginctl enable-linger "$USER"
systemctl --user enable --now podman-restart.service
```

`enable-linger` keeps your user manager running while you are logged out, and `podman-restart.service` starts your containers again after a reboot.

**The restart policies as shipped are not enough on their own.**  `podman-restart.service` only starts containers whose restart policy is `always`, and of the bundled services only `mongodb` sets that — `frontend` and `license-manager` use `on-failure`, while `backend` and `xgt` set no policy at all.  Those four will not come back after a reboot.  Raise the policies with a small override file:

```yaml
# docker-compose.podman.yml — layer after docker-compose.yml
services:
  frontend:
    restart: always
  backend:
    restart: always
  xgt:
    restart: always
```

```bash
podman-compose -f docker-compose.yml -f docker-compose.podman.yml up --detach
```

Add a `license-manager` entry to that override as well if you use the license-manager overlay, and place the override last on the command line so it applies after the service is defined.

For a production single-host install, prefer generating systemd units and letting systemd own the lifecycle instead: Quadlet (`.container` files under `~/.config/containers/systemd/`) is the current mechanism, and `podman generate systemd` still works but is deprecated.  Units also give you startup ordering and dependency control that Compose `restart:` policies do not.

Under rootful Podman (`sudo podman-compose`), enable the system-wide unit rather than the user one.  The same restart-policy caveat applies:

```bash
sudo systemctl enable --now podman-restart.service
```

## Kubernetes / OpenShift

Rocketgraph Mission Control can also be deployed on Kubernetes or OpenShift using the Helm chart in the [`charts/rocketgraph/`](charts/rocketgraph/) directory.  Refer to the [Helm chart documentation](charts/rocketgraph/README.md) for installation and configuration instructions, including OpenShift-specific setup, TLS, OIDC, LDAP, and more.

For other container orchestration platforms, the [deployment reference](doc/deployment_reference.md) documents each container's images, ports, volumes, and environment variables.

## Features and Operations

These sections cover optional features and routine operations for the Compose-based install.  Several have Kubernetes and OpenShift equivalents documented in the [Helm chart documentation](charts/rocketgraph/README.md).

### MongoDB Security

The bundled MongoDB ships with no authentication and no TLS by default; the `database-network` is marked `internal: true`, so MongoDB is unreachable from outside the Compose project.  Several opt-in hardening mechanisms are available, all configured in `.env`:

- **Authentication** — set `MC_MONGO_PASSWORD` (the root user is always `rocketgraph`).
- **TLS in transit** — `MC_MONGO_TLS_ENABLED` plus a server cert and CA (single-host installs don't need it — traffic stays on the internal network).
- **Mutual TLS** — require clients to present a certificate.
- **Encryption at rest** — available in FIPS deployments via Percona.

See the [MongoDB security guide](doc/mongodb_security.md) for step-by-step setup, certificate generation, verification, and troubleshooting.

### FIPS Deployment

For FIPS 140-2 environments, the `docker-compose.fips.yml` overlay swaps the bundled images to their FIPS variants — Percona Server for MongoDB, and `-fips`-tagged frontend, backend, and xgt images:

```bash
docker compose -f docker-compose.yml -f docker-compose.fips.yml up -d
```

When MongoDB TLS is enabled (see [MongoDB Security](#mongodb-security)), mongod is additionally started with `--tlsFIPSMode` to enforce FIPS-only cipher suites, and Percona's encryption at rest becomes available via `MC_MONGO_ENCRYPTION_ENABLED`.  For the xGT License Manager under FIPS, set `MC_LICENSE_MANAGER_IMAGE` to its `-fips` tag.

### xGT License Manager

By default xGT reads a single license from the file at `XGT_LICENSE_FILE`.  For deployments that need multiple licenses or live license updates without restarting xGT, the optional [`docker-compose.license-manager.yml`](docker-compose.license-manager.yml) overlay runs a dedicated license-manager service that serves licenses to xGT over port 6200.

The License Manager uses host bind mounts for its config and log directories, the same pattern as the xGT service.  License files live under the config directory in a `licenses/` subdirectory (`MC_LICENSE_MANAGER_CONF_PATH` defaults to `~/.rocketgraph/license-manager/conf`, so by default that is `~/.rocketgraph/license-manager/conf/licenses/`).

Setup:

```bash
# 1. Put your .lic files in the manager's licenses directory
mkdir -p ~/.rocketgraph/license-manager/conf/licenses
cp /path/to/*.lic ~/.rocketgraph/license-manager/conf/licenses/

# 2. In your xgtd.conf (under XGT_CONF_PATH), tell xgt where to find the manager:
#    license.location: 6200@license-manager

# 3. Run with the overlay:
docker compose -f docker-compose.yml -f docker-compose.license-manager.yml up -d
```

To use directories elsewhere, set `MC_LICENSE_MANAGER_CONF_PATH` and `MC_LICENSE_MANAGER_LOG_PATH` in `.env`.

For FIPS deployments, also set `MC_LICENSE_MANAGER_IMAGE` to the `-fips` variant of the license-manager image.  The overlay composes with `docker-compose.fips.yml` cleanly — both can be passed via `-f`.

### Database Maintenance

The [`scripts/`](scripts/README.md) directory has helper scripts for operating the bundled MongoDB:

- `db_dump.sh` / `db_restore.sh` — back up and restore the database (also used to migrate between MongoDB Community and Percona).
- `edit_user_profile.sh` — read or edit Mission Control user profiles.
- `generate_mongo_certs.sh` — generate the CA chain and server/client certificates for MongoDB TLS and mTLS.

See the [scripts documentation](scripts/README.md) for usage and `.env` requirements.

### Database Connectivity

Rocketgraph Mission Control supports loading data from a database.  Refer to the [ODBC documentation](doc/odbc_configuration.md) for connection instructions.

Rocketgraph comes preinstalled with PostgreSQL and MariaDB ODBC drivers.

Additional databases can be connected by installing the appropriate ODBC driver, including:
 - MongoDB
 - Oracle
 - SAP: ASE and IQ
 - Snowflake
 - Generic ODBC: Databricks, DB2, MySQL

### LLM Configuration

Rocketgraph Mission Control is configured to support a set of common LLMs out of the box.
It also has the ability to add a new LLM and modify the existing LLMs for your site via a yaml configuration file or a python configuration file.

Refer to these detailed [instructions](doc/llm_site_config.md).

### OIDC Authentication (Experimental)

Mission Control has experimental support for authenticating users via an
external OpenID Connect (OIDC) identity provider such as Keycloak or
OpenShift OAuth.

Refer to the [OIDC configuration guide](doc/oidc_configuration.md) for setup
instructions.

## License

By downloading, installing or using any of these images you agree to the [license agreement](https://docs.rocketgraph.com/EULA/xGT_License_for_Containers.pdf) for this software.

As with all Docker images, these likely also contain other software which may be under other licenses (such as Bash, etc from the base distribution, along with any direct or indirect dependencies of the primary software being contained).

As for any pre-built image usage, it is the image user's responsibility to ensure that any use of this image complies with any relevant licenses for all software contained within.
