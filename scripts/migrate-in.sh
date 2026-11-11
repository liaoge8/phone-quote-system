#!/usr/bin/env bash
# 新服务器执行：bash scripts/migrate-in.sh /path/to/phone-quote-<时间戳>.tar.gz
# 要求: 备份包与同名 .sha256 在一起；项目根目录已有 .env
set -Eeuo pipefail
package="${1:?用法: bash scripts/migrate-in.sh /path/to/phone-quote-<时间戳>.tar.gz}"
package="$(readlink -f "$package")"
[[ -f "$package" ]] || { echo "备份包不存在: $package"; exit 1; }
[[ -f "$package.sha256" ]] || { echo "缺少校验文件: $package.sha256（需与备份包一起从旧服务器带来）"; exit 1; }
cd "$(dirname "$0")/.."
[[ -f .env ]] || { echo "项目根目录缺少 .env（先从旧服务器复制，或参照 .env.example 填写）"; exit 1; }
mkdir -p backups
cp -a "$package" "$package.sha256" backups/
name="$(basename "$package")"
echo "[1/4] 启动空数据库..."
docker compose up -d db
echo "[2/4] 恢复数据库与政策截图（自动校验 SHA-256、备份格式与空库）..."
RESTORE_CONFIRM=RESTORE_TO_EMPTY_DATABASE docker compose run --rm -e RESTORE_CONFIRM=RESTORE_TO_EMPTY_DATABASE restore "/backups/$name"
echo "[3/4] 构建并启动全部服务..."
docker compose up -d --build
echo "[4/4] 健康检查..."
sleep 5
docker compose exec -T api curl -fsS http://127.0.0.1:8000/api/health
echo
echo "恢复完成。请用管理员账号登录抽查: 商品 / 价格历史 / 政策截图下载 / CSV 导出，验收通过后再开放访问。"