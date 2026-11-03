# 手机报价管理系统后端 v1
FROM python:3.12-slim

WORKDIR /code

# 先装依赖（利用 Docker 层缓存）
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

# 默认用 SQLite，数据文件落在 /code/data
ENV DATABASE_URL=sqlite:///./data.db

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
