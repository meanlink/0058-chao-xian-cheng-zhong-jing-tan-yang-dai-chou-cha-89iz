from fastapi import APIRouter
from shore_routes import router as router_0
from weigh_routes import router as router_1
from witness_routes import router as router_2
from haul_routes import router as router_3
from coast_seed import seed
from haul_worker import run as run_job

router = APIRouter(prefix="/api")
router.include_router(router_0)
router.include_router(router_1)
router.include_router(router_2)
router.include_router(router_3)
