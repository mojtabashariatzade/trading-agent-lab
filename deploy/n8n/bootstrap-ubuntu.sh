#!/bin/sh
# Fresh-host provisioning only. No automatic removal of existing packages.
set -eu
[ "${1:-}" = "--fresh-server-approved" ] || { echo 'Approval required'; exit 2; }
[ "$(id -u)" = 0 ] || { echo 'Root via authorized SSH/sudo required'; exit 2; }
. /etc/os-release
[ "$ID" = ubuntu ] && [ "$VERSION_ID" = 24.04 ] || { echo 'This bootstrap targets fresh Ubuntu 24.04 only'; exit 2; }
if command -v docker >/dev/null 2>&1; then
    docker compose version >/dev/null
    exit 0
fi
for pkg in docker.io docker-compose docker-compose-v2 podman-docker containerd runc; do
    if dpkg-query -W -f='${Status}' "$pkg" 2>/dev/null | grep -q 'install ok installed'; then
        echo 'Existing container package detected. Reconcile manually; nothing removed.'
        exit 2
    fi
done
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq ca-certificates curl python3
install -m 0755 -d /etc/apt/keyrings
[ ! -e /etc/apt/sources.list.d/docker.sources ] || { echo 'Existing Docker source: review required'; exit 2; }
curl --proto '=https' --tlsv1.2 -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
chmod a+r /etc/apt/keyrings/docker.asc
cat > /etc/apt/sources.list.d/docker.sources <<EOF
Types: deb
URIs: https://download.docker.com/linux/ubuntu
Suites: noble
Components: stable
Architectures: $(dpkg --print-architecture)
Signed-By: /etc/apt/keyrings/docker.asc
EOF
apt-get update -qq
apt-get install -y -qq docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
systemctl enable --now docker
# Do not add n8n or any untrusted worker to the root-equivalent docker group.
docker compose version
