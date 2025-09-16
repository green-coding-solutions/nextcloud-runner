# Nextcloud Docker

This repository provides a way to build a Docker image for any version of Nextcloud.

You can also use the Green Metrics Tool to benchmark Nextcloud

# Setup

As the nextcloud install is quite larege we don't ship with this. So you will need to

git clone https://github.com/nextcloud/server.git nextcloud

before building the containers

## Building a specific version

You can build a specific version of Nextcloud by providing the git hash of the desired version as a build argument.

```bash
docker build --build-arg GIT_REF=<git-hash> .
```

## Collabora Office

Please note that the Collabora Online office suite can only be installed and used on x86-based systems. It will not work on ARM-based architectures and crash with a cyptic error!
