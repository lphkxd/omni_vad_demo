import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from fastapi.staticfiles import StaticFiles
from urllib.parse import urlparse
import requests
import os
from starlette.responses import Response
from starlette.types import Scope
from starlette.staticfiles import StaticFiles

class CacheControlledStaticFiles(StaticFiles):
    async def get_response(self, path: str, scope: Scope) -> Response:
        response = await super().get_response(path, scope)
        response.headers["Cache-Control"] = "public, max-age=0"
        return response

app = FastAPI()


# 或者方法2：更精确地只托管vad_test.html文件（需要自定义路由）
@app.get("/vad_test")
async def serve_vad_test():
    with open("vad_test.html", "r", encoding="utf-8") as f:
        html_content = f.read()
    return Response(content=html_content, media_type="text/html")



#uvicorn main:app --host 0.0.0.0 --reload
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)


#choco install mkcert
#mkcert -key-file key.pem -cert-file cert.pem localhost 127.0.0.1 ::1 192.168.50.250

#uvicorn main:app --host 0.0.0.0 --port 8000 --ssl-keyfile key.pem --ssl-certfile cert.pem

#https://192.168.50.250:8000/vad_test
