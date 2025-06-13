# Rocketgraph Mission Control

**Unveiling the power of data through intuitive and dynamic visualizations.**

Rocketgraph Mission Control is an innovative web application designed to revolutionize the way organizations visualize and interact with complex datasets.  The application offers a comprehensive suite of tools that facilitate the interactive exploration of data through graph-based visualizations.  It integrates powerful features such as dynamic data loading, customizable views, and an intuitive user interface, all tailored to enhance the user experience in data analysis and visualization.  Mission Control is designed to be responsive and user-friendly, ensuring seamless navigation and an enriching data interaction experience.

For organizations managing large and intricate datasets, particularly in critical sectors like defense cybersecurity, finance, and healthcare, Rocketgraph Mission Control stands as a pivotal tool.  It delivers high-performance analytics and insightful visual representations, enabling users to uncover hidden patterns, relationships, and trends in data.  This level of insight is crucial for decision-making and strategic planning in high-stakes environments.  The application's capacity to handle massive datasets efficiently makes it an invaluable asset for organizations seeking to transform their data into actionable intelligence, thereby fostering informed decisions and enhancing operational effectiveness.

Rocketgraph Mission Control is a web application for driving property graph workloads in the [Rocketgraph xGT server](https://docs.rocketgraph.com).

## Quick Installation

Perform these steps to install and run Rocketgraph Mission Control and Rocketgraph xGT on a server.

 1. Make sure Docker is running.  You may need to start (or install) a [Docker Desktop](https://docs.docker.com/desktop/) or [Docker Engine](https://docs.docker.com/engine/).  To verify that Docker is working, run the following command.  You should see information about the Docker environment.
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

## Installation

Rocketgraph Mission Control uses Docker Compose with these Docker images:
 - [rocketgraph/xgt](https://hub.docker.com/r/rocketgraph/xgt)
 - [rocketgraph/mission-control-frontend](https://hub.docker.com/r/rocketgraph/mission-control-frontend)
 - [rocketgraph/mission-control-backend](https://hub.docker.com/r/rocketgraph/mission-control-backend)
 - [mongo](https://hub.docker.com/_/mongo)

Rocketgraph Mission Control can be run using either Docker Desktop or Docker Engine only.  Further references to Docker Engine in the Installation section refer to a Docker Engine install without Docker Desktop.

### Configuration for the xGT Server

The Mission Control frontend, backend, and database containers must be run on the same host.  However, the xGT server can be run in the following ways:
 - In a Docker container as part of the Compose project.
 - In an isolated Docker container (separate from the Compose project) on the same host as Mission Control.
 - Installed from an RPM on the same host as Mission Control.
 - On a different host than Mission Control, either in a Docker container or installed from an RPM.

#### xGT as Part of the Compose Project

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

#### xGT in an Isolated Container on the Mission Control Host

Here is an example of starting the xGT server in an isolated container:
```bash
$ docker run --name xgt --detach --publish 4367:4367 \
    --volume /host/conf/dir:/conf \
    --volume /host/data/dir:/data \
    --volume /host/log/dir:/log \
    rocketgraph/xgt
```
This command exposes port 4367 to the host.  The xGT server listens on port 4367.  Exposing this port is required for Rocketgraph Mission Control to communicate with the isolated container.  The command also volume maps a config directory, a data directory, and a log directory.  Change the command to map only the directories you need and point to the correct host directories.  See the [documentation for running xGT in a Docker container](https://docs.rocketgraph.com/using_docker_image/index.html) for more details.

Comment out or delete the xgt section in the docker-compose.yml file.

Use the host's external IP as the hostname when logging into Rocketgraph Mission Control.

Another option for the login hostname is to use either `localhost` or `host.docker.internal`, but further configuration is required if using Docker Engine to run Rocketgraph Mission Control.  In that case, add the following lines in the backend section of the docker-compose.yml file:
```yaml
    extra_hosts:
      - "host.docker.internal:host-gateway"
```
Docker Desktop automatically provides the translation of "host.docker.internal" to the gateway IP of the default bridge network.  These lines add the translation in Docker Engine.  Mission Control translates "localhost" to "host.docker.internal" to provide a shorter more commonly understood hostname.

#### xGT Installed from an RPM on the Mission Control Host

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

After setting the value for "system.hostname" and starting the xGT server, comment out or delete the xgt section in the docker-compose.yml file.

Use the host's external IP as the hostname when logging into Rocketgraph Mission Control.

If the xGT server is configured for access via 127.0.0.1, another option for the login hostname is to use either `localhost` or `host.docker.internal`.  However, further configuration is required if using Docker Engine to run Rocketgraph Mission Control.  In that case, uncomment the following lines in the backend section of the docker-compose.yml file:
```yaml
    extra_hosts:
      - "host.docker.internal:host-gateway"
```
Docker Desktop automatically provides the translation of "host.docker.internal" to the gateway IP of the default bridge network.  These lines add the translation in Docker Engine.  Mission Control translates "localhost" to "host.docker.internal" to provide a shorter more commonly understood hostname.

#### xGT on a Different Host

The xGT server can be running on the other host either in a Docker container or installed from an RPM.

Comment out or delete the xgt section in the docker-compose.yml file.

Use the IP of the host where the xGT server is running as the hostname when logging into Rocketgraph Mission Control.

### Environment Variables

There are a number of environment variables that configure Mission Control and the xGT server.  Variables that start with MC_ configure Mission Control, while variables that start with XGT_ configure the server.  We suggest putting definitions of the environment variables in a .env file in the same directory as the docker-compose.yml file.  That way they will be available for all Docker Compose commands.

Here is an example .env file that sets up running the web server using SSL.

```dotenv
MC_SSL_PUBLIC_CERT=/directory/to/ssl/td-cert.pem
MC_SSL_PRIVATE_KEY=/directory/to/ssl/td-private-key.pem
```

The configurable environment variables are:

|Variable                |Volume Mapped|Description|
|------------------------|-|-----------|
|MC_VERSION              | |release version to pull/run, default is "latest"|
|MC_PORT                 | |alternative port for the http web server|
|MC_SSL_PORT             | |alternative port for the https web server|
|MC_DEFAULT_XGT_HOST     | |default login host for Mission Control|
|MC_DEFAULT_XGT_PORT     | |default login port for Mission Control|
|MC_ODBC_PATH            | |path to ODBC drivers for the connector|
|MC_MONGO_URI            | |location of the database used by Mission Control|
|MC_MONGODB_IMAGE        | |used to specify the mongodb image for Power10 installs|
|MC_SSL_PUBLIC_CERT      |Y|path to certificate on host to setup an https web server|
|MC_SSL_PRIVATE_KEY      |Y|path to private key on host to setup an https web server|
|MC_SSL_CERT_CHAIN       |Y|path to certificate chain used by the https web server to validate client certificates for mTLS|
|MC_SSL_PROXY_PUBLIC_CERT|Y|path to certificate on host to use as a proxy connection to the xGT server|
|MC_SSL_PROXY_PRIVATE_KEY|Y|path to private key on host to use as a proxy connection to the xGT server|
|XGT_VERSION             | |release version to pull/run, default is "latest"|
|XGT_PORT                | |port the xGT server should listen on|
|XGT_LICENSE_FILE        |Y|path to xGT license file|
|XGT_CONF_PATH           |Y|path to the configuration directory on host for the xGT server|
|XGT_DATA_PATH           |Y|path to the data directory on host for the xGT server|
|XGT_LOG_PATH            |Y|path to the log directory on host for the xGT server|
|XGT_AUTH_TYPES          | |sets xGT server authentication types available in Mission Control|
|XGT_SSL_SERVER_CERT     |Y|path to chain file on host for the xGT server’s certificate|
|XGT_SERVER_CN           | |common name on the xGT server’s certificate|

The variables that are volume mapped map point to a file or directory on the host that gets mapped to an expected location in the containers.

### Instructions

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

 1. If running the xGT server as part of the Compose project, setup a data directory using the environment variable XGT_DATA_PATH.  The default is ~/.xgt/data if XGT_DATA_PATH is not set.  For example:
    ```dotenv
    XGT_DATA_PATH=/path/to/data/dir
    ```

 1. (Optional) If running the xGT server as part of the Compose project, setup a configuration directory using the environment variable XGT_CONF_PATH.  The default is ~/.xgt/conf if XGT_CONF_PATH is not set.  For example:
    ```dotenv
    XGT_CONF_PATH=/path/to/conf/dir
    ```

 1. (Optional) If running the xGT server as part of the Compose project, setup a log directory using the environment variable XGT_LOG_PATH.  The default is ~/.xgt/log if XGT_LOG_PATH is not set.  For example:
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

 1. (Optional) Select the xGT server authentication types available to Mission Control users using the environment variable XGT_AUTH_TYPES.  The supported types are 'BasicAuth', which uses a username and password, and 'PKIAuth'.  The default is to support both types.  The value of XGT_AUTH_TYPES must be a string representing a JSON list of the selected types.  This example allows only username / password authentication:
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

## Database Connectivity

Rocketgraph Mission Control supports loading data from a database.  Refer to the [ODBC documentation](doc/ODBC_README.md) to connect to a database.

The supported databases are:
 - MongoDB
 - Oracle
 - SAP: ASE and IQ
 - Snowflake
 - Generic ODBC: Databricks, DB2, MySQL, and MariaDB

## Connect to a site-local LLM

There are many reasons users may prefer to use their own LLM.
Rocketgraph Mission Control can call out to a site-local LLM with a modest amount of configuration and Python scripting.

Refer to these detailed [instructions](doc/Site-Local-LLM.md).

## License

By downloading, installing or using any of these images you agree to the [license agreement](https://docs.rocketgraph.com/EULA/xGT_License_for_Containers.pdf) for this software.

As with all Docker images, these likely also contain other software which may be under other licenses (such as Bash, etc from the base distribution, along with any direct or indirect dependencies of the primary software being contained).

As for any pre-built image usage, it is the image user's responsibility to ensure that any use of this image complies with any relevant licenses for all software contained within.
