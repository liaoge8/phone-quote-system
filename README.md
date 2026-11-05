# 手机报价档案系统

本项目是内部手机价格档案系统，不是销售平台或进销存系统。当前开发工作在 `rebuild/v1-core` 分支进行。

## 当前范围

- 手机商品档案
- 普通价格记录、历史查询及价格追溯
- 多条月内政策价记录：每次政策发布、补充或调整独立建档
- 政策解读及宣贯截图证据保存
- 价格对比、CSV 导出
- 成员权限、管理员操作及审计日志

进销存将在未来作为独立系统另行规划，不属于本项目当前范围。

## 技术栈

- FastAPI、SQLAlchemy 2、Pydantic v2
- Alembic 数据库迁移
- SQLite 开发环境，PostgreSQL 16 生产环境
- 原生 HTML / CSS / JavaScript 前端

## 本地开发

后端目录：`v2/backend`

安装依赖并配置环境变量后，在后端目录执行：

```bash
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

配置至少包括 `SECRET_KEY`（不少于32字符）和数据库连接 `DATABASE_URL`。政策截图默认保存到 `./data/policy-evidence`，可通过 `POLICY_EVIDENCE_DIR` 指定其他目录。

## 政策截图持久化要求

- JPG、PNG、WEBP；单张最大 10MB。
- 文件不存入 Git 仓库，使用随机文件名保存；数据库记录原文件名、SHA-256、大小、上传人和时间。
- 部署时必须将 `POLICY_EVIDENCE_DIR` 指向持久化磁盘或卷。
- 必须同时备份数据库和政策证据目录；恢复时两者需要匹配。
- 不得把证据目录作为临时容器层存储，否则容器重建可能丢失截图。

## 文档

- `docs/REBUILD_V1_PLAN.md`：V1 重建计划及系统边界。
- `docs/POLICY_PRICE_V1_ASSUMPTIONS.md`：多条政策记录、政策解读及证据截图的第一版规则与假设。

## 安全与上线约束

- 只在 `rebuild/v1-core` 开发，不提前合并 `main`。
- 不在未经备份、验收和明确批准的情况下操作生产环境。
- 生产环境必须使用 HTTPS，并执行备份恢复演练。
