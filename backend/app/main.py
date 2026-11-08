from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import categories, me, transactions
from app.config import get_settings
from app.errors import ConsentRequiredError, DomainError, InvalidInputError, NotFoundError

_STATUS: dict[type[DomainError], int] = {
    NotFoundError: 404,
    InvalidInputError: 422,
    ConsentRequiredError: 403,
}


async def _domain_error_handler(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, DomainError)
    return JSONResponse(status_code=_STATUS.get(type(exc), 400), content={"detail": exc.message})


def create_app() -> FastAPI:
    app = FastAPI(title="Asystent finansowy AI", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=get_settings().cors_origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_exception_handler(DomainError, _domain_error_handler)
    app.include_router(me.router)
    app.include_router(categories.router)
    app.include_router(transactions.router)

    @app.get("/health", tags=["system"])
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
