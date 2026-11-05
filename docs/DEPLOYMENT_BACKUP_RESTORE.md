# 生产备份与恢复操作规程（报价系统 v1）

本规程覆盖 PostgreSQL 16 数据库和政策截图文件。**数据库备份与 `POLICY_EVIDENCE_DIR` 证据目录必须使用同一时间点的备份集**，不能只备数据库。

## 备份前提

- 在生产环境配置 `DATABASE_URL`、`POLICY_EVIDENCE_DIR`、`BACKUP_DIR`。
- `POLICY_EVIDENCE_DIR` 必须挂载到持久化卷，不能放在容器可写层。
- 备份目标应位于独立磁盘或受控远端存储，并限制访问权限。
- 先进入维护窗口，暂停 API 写入（至少暂停政策价创建、截图上传及其他数据库写操作）；确认没有正在进行的上传，再执行备份。这样避免数据库与文件目录时间点不一致。
- 备份完成后恢复服务。

## 执行备份

在具备 PostgreSQL 客户端工具的受控主机上执行：

```bash
export DATABASE_URL='postgresql://...'
export POLICY_EVIDENCE_DIR='/持久化卷/policy-evidence'
export BACKUP_DIR='/安全备份卷/phone-quote-system'
bash scripts/backup.sh
```

脚本生成同一目录下的 `database.dump`、`policy-evidence.tar.gz` 和 `SHA256SUMS`。三个文件必须作为一个备份集保存。不要把密钥或数据库连接串写入仓库。

## 恢复演练

1. 准备隔离的 PostgreSQL 16 恢复库和空的证据持久化目录；不要直接对生产库演练。
2. 进入维护窗口并停止目标环境的 API/Worker 写入。
3. 校验备份集：

```bash
cd /备份集目录
sha256sum -c SHA256SUMS
```

4. 恢复数据库（以下命令会清理目标库中的现有对象，只能对确认无误的空白/隔离目标库执行）：

```bash
pg_restore --clean --if-exists --no-owner --no-acl --dbname="$DATABASE_URL" database.dump
```

5. 恢复截图文件到与 `POLICY_EVIDENCE_DIR` 相同的目录层级。备份包内保存的是证据目录本身：

```bash
mkdir -p "$(dirname "$POLICY_EVIDENCE_DIR")"
tar -C "$(dirname "$POLICY_EVIDENCE_DIR")" -xzf policy-evidence.tar.gz
```

6. 确认应用配置指向恢复后的证据目录，运行 Alembic 版本检查，并启动 API。
7. 通过登录后的政策截图下载接口逐条抽查；接口会比对上传时保存的 SHA-256，发现缺失或损坏时返回错误，不会把损坏文件当作正常证据提供。
8. 完成商品、价格历史、政策价、ST返利、成员登录和 CSV 导出抽查后，才允许恢复业务写入。

## 恢复验收与保留要求

- 数据库中每条 `policy_evidence` 记录都应能找到对应存储键文件。
- 文件实际 SHA-256 必须等于数据库 `sha256` 字段。
- 记录中的文件名、MIME、大小、上传人、上传时间应保留。
- 备份应定期执行，并定期在隔离环境完成恢复演练；仅有备份文件不等于恢复能力已验证。
- 备份保留周期、异地副本、加密密钥托管和 RPO/RTO 尚需由部署负责人确定。

## 当前部署边界

本仓库尚未通过本规程的生产恢复演练。本规程不授权直接改动生产服务器，也不代表当前 Docker、Nginx、Worker 或 PostgreSQL 部署配置已完成验收。上线前必须逐项验证实际部署文件与运行环境。
