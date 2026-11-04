# 手机报价档案系统 V1（重建版）

此目录为全新后端，不覆盖仓库旧版代码。当前处于开发阶段，尚未部署生产环境。

## 本地启动

```bash
cd v2/backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

请编辑 `.env`，将 `SECRET_KEY` 替换为至少 32 字节的随机密钥。然后执行：

```bash
alembic upgrade head
uvicorn app.main:app --reload
```

健康检查：`GET /api/health`

首次创建管理员：仅在临时设置 `ALLOW_FIRST_ADMIN_BOOTSTRAP=true` 时开放隐藏接口 `POST /api/bootstrap/first-admin?username=...&password=...`。初始化成功后立即移除该环境变量并重启服务。不要将密码写入代码、提交到仓库或发到聊天中。

## 当前实现

- SQLAlchemy 2 模型：users、products、price_records、audit_logs。
- 金额使用 `NUMERIC(12,2)` / Decimal。
- 价格记录不提供更新或删除接口；管理员只能作废并填写原因。
- 商品停用保留历史，价格记录外键使用 `ON DELETE RESTRICT`。
- scrypt 密码哈希、JWT HS256（uid/role/ep）、token_epoch 会话失效。
- Alembic 显式迁移；API 启动不自动建表，不启动定时任务。

## 重要边界

用户提供的 v1.0 规范在 price_records DDL 中途截断。此处字段为满足已明确的追加写入、记录人、时间、作废追溯要求所作的最小工程设计，需在最终业务 DDL 补齐后复核。月度政策、销量、入网台账、快照 revision、审计 denied 记录、CSV、Worker 与前端尚未完成。当前测试尚未在 CI 或服务器执行。
