from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.parser import parse_and_store
from app.api.deps import get_session

router = APIRouter(prefix="/parse", tags=["parser"])



@router.post("/")
async def parse_endpoint(session: AsyncSession = Depends(get_session)) -> dict:
    created_count = await parse_and_store(session)
    return {"created": created_count}
