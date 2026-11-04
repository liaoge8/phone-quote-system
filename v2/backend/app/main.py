from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
app = FastAPI(title=settings.app_name, version='1.0.0')
if settings.cors_origin_list:
    app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origin_list, allow_credentials=True, allow_methods=['GET', 'POST', 'PATCH'], allow_headers=['Authorization', 'Content-Type'])
@app.get('/api/health', tags=['系统'])
def health():
    return {'status': 'ok'}
