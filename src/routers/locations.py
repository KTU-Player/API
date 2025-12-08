from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..database import get_db_session
from ..models.location import Country
from ..schemas import location_schema

router = APIRouter(prefix="/countries", tags=["Countries"])


@router.get("", response_model=list[location_schema.Country])
async def get_all_countries(db: AsyncSession = Depends(get_db_session)):
    """
    Get a list of all countries.
    This endpoint is not authenticated and can be used for populating
    UI elements like registration forms.
    """
    result = await db.execute(
        select(Country)
        .options(selectinload(Country.continent))
        .order_by(Country.country_name)
    )
    countries = result.scalars().all()
    return countries
