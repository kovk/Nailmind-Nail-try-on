#!/bin/sh
set -eu

APP_DIR="${1:-/opt/nailmind}"
mkdir -p "$APP_DIR/data" "$APP_DIR/models"
cp docker-compose.remote.yml "$APP_DIR/docker-compose.yml"
cp .env.remote "$APP_DIR/.env"
cd "$APP_DIR"
docker login --username=s1ngleT crpi-j8uhehfe8m5fvjw2.cn-hangzhou.personal.cr.aliyuncs.com
docker compose pull
docker compose up -d
docker compose ps
