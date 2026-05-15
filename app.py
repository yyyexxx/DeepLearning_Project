"""FastAPI 应用入口。智能发票识别与自动报销填单系统。"""

import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from config import BASE_DIR
from db.models import init_db
from web.routes import router


def create_app() -> FastAPI:
    app = FastAPI(title="智能发票识别与自动报销填单系统", version="1.0.0")

    # Jinja2 模板
    templates = Jinja2Templates(directory=str(BASE_DIR / "web" / "templates"))
    app.state.templates = templates

    # 静态文件
    static_dir = BASE_DIR / "web" / "static"
    static_dir.mkdir(parents=True, exist_ok=True)
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    # 任务数据存储（内存中，用于流程各阶段传递数据）
    app.state.tasks = {}

    # 路由
    app.include_router(router)

    # 初始化数据库
    init_db()

    return app


app = create_app()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="127.0.0.1", port=8000, reload=True)
