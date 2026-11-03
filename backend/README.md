# 手机报价管理系统 · 后端 v1

FastAPI + SQLAlchemy 2.0 + Pydantic v2，默认 SQLite，开箱即用。

## 功能（对应前端业务逻辑）

- 密码登录（JWT，密码默认 `8888`，与前端演示一致）
- 商品 CRUD：品牌 / 型号 / 介绍 / 卖点 / 配置 / 颜色 / 虚拟价（首次进货价）
- 价格记录：只追加不覆盖（虚拟价 / 正常价 / 调价 / 政策价 / 官网价 / 官网优惠后价）
- 本月政策价：政策价即最终报价，附政策解释
- 国补计算：官网价 > 6000 不可享；否则补贴 = min(官网价 × 15%, 500)
- 入网台账 CRUD（情报中心置顶用）
- 销量存档 + 两月同比/环比对比
- 爬虫骨架（TENAA 占位）、APScheduler 每日 02:00 定时任务、LLM 客户端（DeepSeek 兼容接口）

## 本地运行

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # 按需修改 ADMIN_PASSWORD / SECRET_KEY
uvicorn app.main:app --reload --port 8000
```

打开 http://127.0.0.1:8000/docs 看交互式接口文档。

## 冒烟测试

```bash
python test_smoke.py
```

## Docker 运行

```bash
cd backend
docker compose up --build -d
```

## 切 PostgreSQL

1. `pip install psycopg2-binary`（或写入 requirements.txt）
2. `.env` 中设置：
   `DATABASE_URL=postgresql+psycopg2://user:password@localhost:5432/phone_quote`
3. 重启服务（`init_db` 会自动建表）

## 目录结构

```
backend/
├── app/
│   ├── main.py            # FastAPI 入口
│   ├── core/              # 配置 / JWT / 鉴权依赖
│   ├── db/                # 引擎、会话、建表
│   ├── models/            # SQLAlchemy 模型
│   ├── schemas/           # Pydantic 请求/响应模型
│   ├── routers/           # auth / products / intel / sales
│   ├── crawler/           # 爬虫基类 + TENAA 占位
│   ├── llm/               # 大模型客户端（OpenAI 兼容）
│   └── scheduler.py       # APScheduler 每日 02:00 爬虫任务
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
├── .env.example
└── test_smoke.py
```
