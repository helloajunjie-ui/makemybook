"""
run.py — PyInstaller 入口点
=============================
启动 Uvicorn 服务器，绑定到 0.0.0.0:8000。
"""
import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
    )
