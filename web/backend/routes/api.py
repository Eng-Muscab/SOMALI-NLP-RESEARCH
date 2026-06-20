from fastapi import APIRouter
from ..controllers import (
    admin_controller,
    analytics_controller,
    auth_controller,
    dataset_controller,
    experiments_controller,
    health_controller,
    predict_controller,
    models_controller,
    metrics_controller,
    train_controller,
)

router = APIRouter()
router.include_router(health_controller.router)
router.include_router(auth_controller.router)
router.include_router(predict_controller.router)
router.include_router(admin_controller.router)
router.include_router(analytics_controller.router)
router.include_router(dataset_controller.router)
router.include_router(experiments_controller.router)
router.include_router(models_controller.router)
router.include_router(metrics_controller.router)
router.include_router(train_controller.router)
