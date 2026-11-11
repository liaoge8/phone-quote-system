# Docker 部署、备份与新服务器恢复

## 后台备份管理

管理员登录系统后可在“备份与恢复文件”区域：
- 点击“立即生成备份”，生成数据库 + 政策截图的完整备份包；
- 点击“下载”将备份包直接保存到电脑；
- 上传已有 .tar.gz 备份包，后台会检查格式、路径和包内 SHA-256，然后保存到服务器持久化备份卷；
- 查看备份列表并删除不需要的备份文件。

备份管理 API 仅管理员可用。所有生成、上传和删除动作都会写入审计日志。上传只做完整性校验和安全暂存，**不会自动覆盖当前运行数据库**。这是为了避免把错误备份直接恢复到正在使用的报价系统。

## 命令行备份（可选）

在维护窗口暂停所有写入后：

```bash
mkdir -p backups
docker compose run --rm backup
```

该命令会把备份写到主机项目目录的 backups 文件夹。后台生成的备份同样保存在该目录（`./backups` 统一挂载），可直接通过后台下载或服务器文件传输带走。

## 每日自动备份

在部署机上执行一次（幂等，可重复执行）：

```bash
bash scripts/install-cron.sh
```

会在每天 03:00 自动生成备份包写入 `backups/`，并自动清理 14 天前的备份，日志在 `backups/cron.log`。

## 一键迁移到新服务器

前提：新服务器已安装 Docker 与 Docker Compose。

1. 旧服务器生成备份包并输出传输清单：

```bash
bash scripts/migrate-out.sh
```

2. 按清单把备份包、`.sha256` 校验文件和 `.env`（可选 `deploy/certs/`）传到新服务器。
3. 新服务器把项目部署文件放好（git clone 或复制仓库），把 `.env` 放到项目根目录，然后执行：

```bash
bash scripts/migrate-in.sh /path/to/phone-quote-<时间戳>.tar.gz
```

脚本会自动完成：启动空数据库 → SHA-256 校验并恢复数据库与政策截图 → 构建启动全部服务 → 健康检查。之后按下方验收清单抽查再开放访问。

## 新服务器恢复

1. 安装 Docker 和 Docker Compose，复制项目部署文件到新服务器。
2. 将 .env.example 复制为 .env，设置全新的强数据库密码和 SECRET_KEY；安全配置 TLS 证书到 deploy/certs/fullchain.pem 与 privkey.pem。
3. 在旧服务器后台下载备份包，复制到新服务器项目的 backups 目录（或在新服务器后台上传该备份包）。
4. 先只启动新服务器的空 PostgreSQL 数据库：

```bash
docker compose up -d db
```

5. 如果备份文件在主机 backups 目录，先将它复制进 restore 容器可见的备份卷，或使用后台上传让它进入 backup_archives 卷。后台上传后的文件名可在后台列表中看到。
6. 对后台上传的文件执行恢复：

```bash
RESTORE_CONFIRM=RESTORE_TO_EMPTY_DATABASE docker compose run --rm -e RESTORE_CONFIRM=RESTORE_TO_EMPTY_DATABASE restore /backups/备份文件名.tar.gz
```

如果使用主机目录中的备份包，可先将包和同名 .sha256 放入 backup_archives 卷，或通过后台上传后再执行以上命令。

恢复工具会先验证外部包校验值、包内文件校验值、备份格式、归档路径、空证据目录和空数据库，再恢复数据库与截图文件。它不会使用 pg_restore --clean，不会删除目标数据库中的现存表；发现目标非空会拒绝执行。

7. 恢复成功后启动完整服务：

```bash
docker compose up -d --build
docker compose logs -f api
```

8. 检查 /api/health、管理员/成员登录、商品、基础价格历史、政策价格、ST返利、政策截图下载（SHA-256）和 CSV 导出。验收通过后才开放业务写入。

## 安全边界

- 恢复必须针对全新空数据库和空证据卷，不能合并到现有系统。
- 备份前暂停写入，保证数据库与截图文件来自同一时间点。
- PostgreSQL 16 是当前目标版本；恢复时使用兼容的大版本。
- Nginx 只发布 80/443，数据库端口仅绑定到 127.0.0.1，API 不直接发布到公网。
- 备份包含业务数据和政策截图，应限制下载权限并加密存储/传输。
- 后台上传上限 1GB；超大备份建议走安全的服务器文件传输流程。
- 脚本会校验完整性，但不提供加密、异地上传、保留周期或自动定时任务。
- 代码已加入后台备份管理，但仍需在隔离 Docker + PostgreSQL 16 环境做端到端备份、上传、恢复演练；未经演练不能称为生产恢复能力已验收。
