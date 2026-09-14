import uvicorn
from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware


def load_domain_routers() -> list[APIRouter]:
    from knowledge.api.import_router import router as import_router
    from knowledge.api.metrics_router import router as metrics_router
    from knowledge.api.query_router import router as query_router

    return [import_router, query_router, metrics_router]


def create_app() -> FastAPI:
    app = FastAPI(title="知识库管理平台", version="v1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    api = APIRouter(prefix="/api")

    @api.get("/health")
    def health():
        return {"status": "healthy", "service": "kb-platform"}

    app.include_router(api)
    for router in load_domain_routers():
        app.include_router(router, prefix="/api")
    return app


if __name__ == "__main__":
    uvicorn.run(create_app(), host="0.0.0.0", port=8000, log_level="info")
