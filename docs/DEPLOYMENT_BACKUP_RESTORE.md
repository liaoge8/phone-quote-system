# 可迁移备份包与新服务器恢复

本方案面向 PostgreSQL 16 + Docker Compose 部署。一个备份压缩包包含数据库导出、政策截图文件、格式清单和 SHA-256 校验；包旁边另有一个 .sha256 文件用于校验整个包。

## Docker 环境备份

在维护窗口暂停所有写入（API/Worker），确认没有正在进行的截图上传，然后在项目目录执行：

```bash
mkdir -p backups
docker compose run --rm backup
```

Compose 会启动一次性 PostgreSQL 16 工具容器，连接内部数据库，并读取政策证据持久化卷。备份文件写入项目的 backups 目录。生成的 phone-quote-TIMESTAMP.tar.gz 和同名 .sha256 必须一起复制到独立存储。

不要仅备份 PostgreSQL；数据库和政策截图必须作为同一备份集。备份包包含业务数据和政策截图，应限制访问并加密存储/传输。

## 新服务器恢复

1. 安装 Docker 和 Docker Compose，复制项目部署文件到新服务器。
2. 将 .env.example 复制为 .env，设置全新的强数据库密码和 SECRET_KEY；安全配置 TLS 证书到 deploy/certs/fullchain.pem 与 privkey.pem。
3. 创建 backups 目录，将备份包及同名 .sha256 文件复制进去。
4. 先只启动全新的 PostgreSQL 数据库：

```bash
mkdir -p backups
docker compose up -d db
```

5. 确保这是新建的空数据库，且 Compose 的 policy_evidence 卷为空。执行恢复：

```bash
RESTORE_CONFIRM=RESTORE_TO_EMPTY_DATABASE docker compose run --rm -e RESTORE_CONFIRM=RESTORE_TO_EMPTY_DATABASE restore /backups/phone-quote-TIMESTAMP.tar.gz
```

恢复工具会先验证外部包校验值、包内文件校验值、备份格式、归档路径、空证据目录和空数据库，再恢复数据库与截图文件。它不会使用 pg_restore --clean，不会删除目标数据库中的现存表；发现目标非空会拒绝执行。

6. 恢复成功后启动完整服务：

```bash
docker compose up -d --build
docker compose logs -f api
```

7. 检查 /api/health、Alembic 版本、管理员/成员登录、商品、基础价格历史、政策价格、ST返利、政策截图下载（SHA-256）和 CSV 导出。验收通过后才开放业务写入。

## 安全边界

- 恢复必须针对全新空数据库和空证据卷，不能合并到现有系统。
- 备份前暂停写入，保证数据库与截图文件来自同一时间点。
- PostgreSQL 16 是当前目标版本；恢复时使用兼容的大版本。
- Nginx 只发布 80/443，数据库端口仅绑定到 127.0.0.1，API 不直接发布到公网。
- 脚本会校验完整性，但不提供加密、异地上传、保留周期或自动定时任务。
- 代码与 Compose 配置已提交，但仍需在隔离的 Docker + PostgreSQL 16 环境做端到端备份、恢复演练；未经演练不能称为生产恢复能力已验收。
- TLS 证书签发/续期、DNS、主机防火墙、首次管理员初始化和备份异地保存需按实际服务器环境完成。
