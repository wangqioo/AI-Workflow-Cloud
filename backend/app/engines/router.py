"""Engine Gateway API endpoints."""

from fastapi import APIRouter, Depends

from ..auth.dependencies import get_current_user
from ..models.user import User
from .registry import get_registry

router = APIRouter(prefix="/api/engines", tags=["engines"])


@router.get("")
async def list_engines(user: User = Depends(get_current_user)):
    return {"engines": get_registry().list_engines()}


@router.get("/capabilities")
async def get_capabilities(user: User = Depends(get_current_user)):
    return {"capabilities": get_registry().get_capabilities()}


@router.get("/health")
async def get_health(user: User = Depends(get_current_user)):
    return {"services": get_registry().get_health()}
