#!/usr/bin/env bash
# 安装每日 03:00 自动备份（保留 14 天自动清理），幂等可重复执行
set -Eeuo pipefail
project_dir="$(cd "$(dirname "$0")/.." && pwd)"
mkdir -p "$project_dir/backups"
line="0 3 * * * cd $project_dir && docker compose --profile tools run --rm backup >> backups/cron.log 2>&1; find $project_dir/backups -name 'phone-quote-*.tar.gz*' -mtime +14 -delete"
( crontab -l 2>/dev/null | grep -vF 'phone-quote-backup'; echo "$line # phone-quote-backup" ) | crontab -
echo "定时备份已安装（每天 03:00，保留 14 天）:"
crontab -l | grep phone-quote-backup