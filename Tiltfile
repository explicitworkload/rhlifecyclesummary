# Tiltfile

# 1. Load production compose + local dev override
docker_compose(['podman-compose.yaml', 'podman-compose.override.yaml'])


docker_build(
    'quay.io/jgoh/rhlifecyclesummary:latest',
    '.'
)