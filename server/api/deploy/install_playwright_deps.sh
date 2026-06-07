#!/bin/sh
set -eu

cat >/etc/apt/sources.list.d/debian.sources <<'EOF'
Types: deb
URIs: https://mirrors.tuna.tsinghua.edu.cn/debian/
Suites: trixie trixie-updates
Components: main
Signed-By: /usr/share/keyrings/debian-archive-keyring.pgp

Types: deb
URIs: https://mirrors.tuna.tsinghua.edu.cn/debian-security/
Suites: trixie-security
Components: main
Signed-By: /usr/share/keyrings/debian-archive-keyring.pgp
EOF

export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y --no-install-recommends \
  ca-certificates \
  wget \
  libasound2 \
  libatk-bridge2.0-0 \
  libatk1.0-0 \
  libcairo2 \
  libcups2 \
  libdbus-1-3 \
  libdrm2 \
  libgbm1 \
  libglib2.0-0 \
  libnspr4 \
  libnss3 \
  libpango-1.0-0 \
  libx11-6 \
  libx11-xcb1 \
  libxcb1 \
  libxcomposite1 \
  libxdamage1 \
  libxext6 \
  libxfixes3 \
  libxkbcommon0 \
  libxrandr2
