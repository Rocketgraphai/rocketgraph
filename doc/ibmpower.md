# Installing Docker on RHEL 9.x for Power10

This guide explains how to replace Podman with Docker CE on RHEL 9.x systems running on IBM Power10 architecture.

## Prerequisites

- RHEL 9.x running on IBM Power10 (ppc64le architecture)
- Root or sudo access
- Internet connectivity

## Installation Steps

### 1. Remove Existing Container Engines

Remove any previous Docker or Podman installations:

```bash
# Remove any old docker installations
sudo dnf remove docker docker-common docker-selinux docker-engine-selinux docker-engine

# Remove podman and related packages
sudo dnf remove podman podman-docker container-selinux containers-common podman-catatonit
```

### 2. Install Dependencies

```bash
sudo dnf install -y yum-utils device-mapper-persistent-data lvm2
```

### 3. Configure Docker Repository

Add the Docker CE repository and configure for ppc64le:

```bash
# Add Docker repository
sudo dnf config-manager --add-repo https://download.docker.com/linux/rhel/docker-ce.repo

# Edit repository configuration
sudo vi /etc/yum.repos.d/docker-ce.repo
```

Update the `baseurl` line to include ppc64le architecture:
```ini
baseurl=https://download.docker.com/linux/rhel/$releasever/$basearch/stable arch=ppc64le
```

### 4. Install Docker CE

```bash
sudo dnf install docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
```

### 5. Configure Docker Service

```bash
# Start Docker service
sudo systemctl start docker

# Enable Docker to start on boot
sudo systemctl enable docker
```

### 6. Configure User Permissions

```bash
# Add current user to docker group
sudo usermod -aG docker $USER
```

> **Note:** Log out and back in for the group changes to take effect.

### 7. Verify Installation

```bash
# Test Docker installation
docker run hello-world

# Check Docker service status
sudo systemctl status docker

# Verify Docker version
docker version

# Check Docker system information
docker info
```

## Troubleshooting

If you encounter issues, check the Docker daemon logs:

```bash
sudo journalctl -u docker
```

### Common Issues

- If services don't start properly after installation, try rebooting the system
- Ensure all ports required by Docker are available
- Verify network connectivity to Docker repositories

## Additional Resources

- [Docker Documentation](https://docs.docker.com/)
- [RHEL Documentation](https://access.redhat.com/documentation/en-us/red_hat_enterprise_linux/9)
- [IBM Power Systems Documentation](https://www.ibm.com/docs/en/power9)