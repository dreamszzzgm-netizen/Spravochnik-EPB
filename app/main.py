import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.core.config import get_settings
from app.core.logging import configure_logging
from app.modules.buildings.routes import router as buildings_router
from app.modules.contracts.routes import reference_router as contracts_reference_router
from app.modules.contracts.routes import router as contracts_router
from app.modules.custom_fields.routes import router as custom_fields_router
from app.modules.identity.routes import router as identity_router
from app.modules.opo.reference_routes import router as reference_router
from app.modules.opo.routes import router as opo_router
from app.modules.organizations.routes import router as organizations_router
from app.modules.organizations.service import OrganizationLegalFormError
from app.modules.tasks.routes import router as tasks_router
from app.modules.technical_devices.routes import router as technical_devices_router
from app.modules.workflows.routes import router as workflows_router
from app.web.middleware import RequestContextMiddleware
from app.web.routes.health import router as health_router

settings = get_settings()
configure_logging(settings.log_level)

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    docs_url="/api/docs" if settings.app_env != "production" else None,
    redoc_url=None,
)
app.add_middleware(RequestContextMiddleware)


@app.exception_handler(OrganizationLegalFormError)
async def organization_legal_form_error_handler(
    request: Request, exc: OrganizationLegalFormError
) -> JSONResponse:
    del request
    return JSONResponse(status_code=422, content={"detail": str(exc)})


app.include_router(health_router)
app.include_router(identity_router)
app.include_router(organizations_router)
app.include_router(opo_router)
app.include_router(technical_devices_router)
app.include_router(buildings_router)
app.include_router(custom_fields_router)
app.include_router(reference_router)
app.include_router(contracts_router)
app.include_router(contracts_reference_router)
app.include_router(tasks_router)
app.include_router(workflows_router)


def run() -> None:
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000)


if __name__ == "__main__":
    run()
