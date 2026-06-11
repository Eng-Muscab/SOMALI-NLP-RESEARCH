from fastapi import APIRouter
from ..controllers import (
    auth_controller,
    dataset_controller,
    experiments_controller,
    health_controller,
    predict_controller,
)

router = APIRouter()
router.include_router(health_controller.router)
router.include_router(auth_controller.router)
router.include_router(predict_controller.router)
router.include_router(dataset_controller.router)
router.include_router(experiments_controller.router)
