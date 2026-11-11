#!/usr/bin/env bash
# 旧服务器执行：生成最新备份包，并输出迁移清单与传输命令
set -Eeuo pipefail
cd "$(dirname "$0")/.."
mkdir -p backups
docker compose --profile tools run --rm backup
latest="$(ls -t backups/phone-quote-*.tar.gz | head -n1)"
echo "=============================================="
echo "备份包已生成: $latest"
echo "迁移到新服务器需要带走（缺一不可）:"
echo "  1. $(basename "$latest")"
echo "  2. $(basename "$latest").sha256"
echo "  3. .env            原样带走可保留 SECRET_KEY，成员无需重新登录"
echo "  4. deploy/certs/   沿用同一域名证书时带走"
echo "传输示例:"
echo "  scp '$latest' '$latest.sha256' .env user@新服务器IP:/opt/phone-quote/"
echo "新服务器上执行:"
echo "  bash scripts/migrate-in.sh /opt/phone-quote/$(basename "$latest")"