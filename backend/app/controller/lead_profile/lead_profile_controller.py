from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.model.api.pl_lead_profile import PPLPartnerProfileCreate, PPLPartnerProfile
from app.util.api.db_config import get_db
from app.service.lead_profile.lead_profile_service import LeadProfileService
import uuid


router = APIRouter(
    prefix="/lead-profile",  
    tags=["Lead Profile"]    
)

lead_profile_service = LeadProfileService()

@router.post("/create", response_model=PPLPartnerProfile)
async def create_session(
    session: PPLPartnerProfileCreate,
    db: AsyncSession = Depends(get_db)
):
    """
    Create a new session.
    """
    print("new session")
    return await lead_profile_service.create_lead_profile(db=db, session=session)

