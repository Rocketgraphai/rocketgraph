# ODBC Configuration for Rocketgraph Mission Control

This document provides detailed instructions on how to configure ODBC (Open Database Connectivity) support for the Rocketgraph Mission Control application. ODBC support enables Mission Control to interact with various database systems via ODBC drivers.

> **Note:** This guide covers configuration for both MariaDB and IBM i (AS/400). Please follow the steps specific to your database.

## Environment Variables

ODBC configuration relies on environment variables, typically set in a `.env` file in your project root. The `.env` file uses the format:
```
VARIABLE_NAME=value
```
Below is a summary of the key environment variables:

| Variable Name         | Used For | Example Value                  | Description                                         |
|----------------------|----------|-------------------------------|-----------------------------------------------------|
| MC_ODBC_PATH         | All      | ./odbc                        | Directory containing ODBC ini files                  |
| MC_ODBC_LIBRARY_PATH | IBM i    | /opt/ibm/iaccess/lib64/       | Directory for IBM i driver libraries                 |
| MC_IBM_IACCESS_PATH  | IBM i    | /opt/ibm/iaccess/             | Root directory for IBM i Access Client               |

Set the relevant variables for the database you are configuring. Further details and examples are provided in each database section.

## Preparing ODBC Configuration Files

To enable ODBC support, the `odbc.ini` and `odbcinst.ini` files need to be set up along with the necessary ODBC drivers. The ODBC files and drivers need to be placed in a directory that will be volume mounted to the backend Mission Control Docker container.

---

## MariaDB Setup

This section describes how to configure ODBC for MariaDB. For IBM i systems, see the [IBM Db2 on IBM i](#connecting-to-ibm-db2-on-ibm-i-as400) section.

MariaDB has an ODBC driver called `libmaodbc.so`, which requires a library file called `libmariadb.so.3` to work.

Follow these steps to prepare and configure the files:

1. **Set up the ODBC Files and Drivers:**
   - Prepare the `odbc.ini` and `odbcinst.ini` files. These files contain the configurations needed to establish database connections and should be set up according to the specific requirements of your environment.
   - Obtain ODBC drivers compatible with Debian 11 and your host machine's architecture (e.g., x86_64, aarch64, or ppc64le).
   - The drivers and initialization files are mounted to `/odbc` in the Docker container.
   - The `odbc.ini` file contains a Data Source Name (DSN) and connection information such as the driver, server, port, user, password, etc:
     ```ini
     [MariaDB-Server]
     Description = MariaDB server
     Driver = MariaDB
     Server = 192.168.50.173
     Port = 3306
     Option = 3
     ```
     This is similar to a typical `odbc.ini`.

   - The `odbcinst.ini` file contains driver information. It must point to the location where the driver is mounted in the container:
     ```ini
     [MariaDB]
     Description = ODBC Driver for MariaDB
     Driver = /odbc/libmaodbc.so
     FileUsage = 1
     ```
     The `Driver = MariaDB` line in the `odbc.ini` file indicates use of the driver above.

2. **Double Check the Driver Path:**
   - In the `odbcinst.ini` file, ensure that the driver paths are correctly pointed to within the Docker container:
     ```ini
     Driver = /odbc/libmaodbc.so
     ```
   - This path refers to where the driver will be located inside the container, not on the host machine.

3. **Set up the Docker Volume:**
   - Place the `odbc.ini`, `odbcinst.ini`, and driver files in a directory on the host machine. For example, `./odbc`.
   - For MariaDB, the driver files `libmaodbc.so` and `libmariadb.so.3` should be placed into `./odbc` along with the initialization files.
   - All the files must be directly in the directory on the host machine and not in subdirectories.
   - Set the environment variable `MC_ODBC_PATH` to the directory where the driver files are placed. We suggest setting the environment variable in a `.env` file. An example entry in a `.env` file:
     ```bash
     MC_ODBC_PATH=./odbc
     ```

## Connecting to IBM Db2 on IBM i (AS/400)

Rocketgraph also supports IBM i (AS/400) systems via ODBC.

IBM i access requires `odbc.ini`, `odbcinst.ini` files, and the driver folder for installation. The drivers and ini files will be mounted to separate locations.

### 1. **Install IBM i Access ODBC Drivers**

- Download the **ppc64le** drivers from the [IBM i Access Client Solutions](https://www.ibm.com/support/pages/ibm-i-access-client-solutions) page.
  - Click the **"Downloads for IBM i Access Client Solutions"** link.
  - Sign in with your IBMid.
  - Download the archive named:
    **`ACS Linux App Pkg`** (`IBMiAccess_v1r1_LinuxAP.zip`)
- Extract the archive:
  ```bash
  unzip IBMiAccess_v1r1_LinuxAP.zip -d iaccess
  ```
- You now have two options:

#### **Option A: Install using RPM (system install)**

```bash
dnf install iaccess/ppc64le/ibm-iaccess-1.1.0.28-1.0.ppc64le.rpm
```

- This installs the ODBC drivers to:
  ```
  /opt/ibm/iaccess
  ```

#### **Option B: Extract `.deb` manually (local installs)**

```bash
dpkg-deb -x iaccess/ppc64le/ibm-iaccess-1.1.0.28-1.0.ppc64el.deb tmp
```

- Move the driver directory somewhere permanent:
  ```bash
  mkdir -p ~/iaccess
  cp -r tmp/opt/ibm/iaccess/* ~/iaccess/
  rm -rf tmp
  ```
- This places the drivers at `~/iaccess`.

### 2. **Set Environment Variables**

Update your `.env` file or environment variables to reflect the location where the drivers were installed or extracted:

If you used the RPM:
```env
MC_ODBC_LIBRARY_PATH=/opt/ibm/iaccess/lib64/
MC_IBM_IACCESS_PATH=/opt/ibm/iaccess/
```

If you used the extracted `.deb` instead:
```env
MC_ODBC_LIBRARY_PATH=~/iaccess/lib64/
MC_IBM_IACCESS_PATH=~/iaccess/
```

### 3. **ODBC Directory Setup:**

- **Create an `odbc.ini`**
  ```ini
  [IBMi]
  Description = IBM i Access ODBC connection
  Driver = IBM i Access ODBC Driver 64-bit
  System = 172.20.28.50
  UserID = myUsername
  Password = myPassword
  ```
  This should be similar to a typical `odbc.ini`.

- **Create an `odbcinst.ini`**
  ```ini
  [IBM i Access ODBC Driver 64-bit]
  Description=IBM i Access for Linux 64-bit ODBC Driver
  Driver=/opt/ibm/iaccess/lib64/libcwbodbc.so
  Setup=/opt/ibm/iaccess/lib64/libcwbodbcs.so
  Threading=0
  DontDLClose=1
  UsageCount=1
  ```
- Ensure the `Driver` and `Setup` fields in your `odbcinst.ini` reference shared library files located in the path defined by `MC_ODBC_LIBRARY_PATH` (either in your `.env` file or exported as an environment variable).
- Place `odbc.ini` and `odbcinst.ini` directly in a directory on the host machine, such as `./odbc`. These files **must not** be in subdirectories.
- Set the `MC_ODBC_PATH` variable in your `.env` file (or as an environment variable) to the path of the directory containing these `.ini` files.
  ```env
  MC_ODBC_PATH=./odbc
  ```

For IBM i, you should have 3 environment variables set:
```env
MC_ODBC_LIBRARY_PATH=/opt/ibm/iaccess/lib64/
MC_IBM_IACCESS_PATH=/opt/ibm/iaccess/
MC_ODBC_PATH=./odbc
```

## Testing the Configuration

To verify that ODBC is set up correctly:

- Start Rocketgraph Mission Control.
- In the Mission Control app "Settings" menu, add a connection to the database using the DSNs or driver specified in `odbc.ini` or `odbcinst.ini`.
- For example, for MariaDB:
  `Driver={MariaDB};Server=127.0.0.1;Port=3306;Database=test;Uid=test;Pwd=foo;`
- In the Mission Control app "Upload" tab, perform a test query to ensure the connection is successfully established.

## Troubleshooting

If you encounter issues with ODBC connectivity:

- Read the error messages returned by the upload process. They will usually indicate the general issue.
- Ensure that file permissions for `odbc.ini`, `odbcinst.ini`, and the driver files allow them to be read by the Docker container.
- Check that the driver paths in `odbcinst.ini` accurately reflect their mounted location in the Docker container.
- Make sure the driver files are for Debian 11 and the host system's architecture.
- Review the Docker container logs for any ODBC-related errors:
  ```bash
  docker logs backend
  ```

## Advanced Troubleshooting

If the driver still isn't being found by the ODBC Manager, it may mean that all the library dependencies aren't being resolved. To determine what is going wrong, inspect the library in the container:

1. Find the backend container ID:
   ```bash
   docker container ls
   ```
2. Connect to the container:
   ```bash
   sudo docker exec -it YOUR_CONTAINER_ID /bin/bash
   ```
3. Inspect the library:
   ```bash
   ldd /odbc/driver.so
   ```
4. If the `ldd` command fails, it means the driver is for the wrong architecture.
   Otherwise, the `ldd` command will list the dependencies, which will look something like this:
   ```bash
   linux-vdso.so.1 (0x00007ffd5f7b4000)
   libmariadb.so.3 => not found
   libodbcinst.so.2 => /usr/lib/x86_64-linux-gnu/libodbcinst.so.2 (0x00007f87e6bf9000)
   ```
   Notice the missing library. In this case, all the needed libraries weren't put in the `./odbc` directory.

For further details and support, refer back to the main [README](../README.md) or contact [support@rocketgraph.com](mailto:support@rocketgraph.com).
