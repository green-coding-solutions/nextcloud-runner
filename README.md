# Nextcloud Docker

This repository benchmarks Nextcloud with the Green Metrics Tool.

There are 3 usage scenario files.
```
usage_scenario_31.yml => which will benchmark the 31 branch with the latest apps for this release
usage_scenario_32.yml => which will benchmark the 32 branch with the latest apps for this release
usage_scenario_master.yml => this will benchmark the master branch of nextcloud server and all the apps
```

It also provides a way to build a Docker image for any version of Nextcloud which you can see in the `Dockerfile`


## Building a specific version

You can build a specific version of Nextcloud by providing the git hash of the desired version as a build argument.

```bash
docker build --build-arg GIT_REF=<git-hash> .
```

## Collabora Office

Please note that the Collabora Online office suite can only be installed and used on x86-based systems. It will not work on ARM-based architectures and crash with a cyptic error!
