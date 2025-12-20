from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.model.api.ppl_lead_profile import PPLPartnerProfileCreate, PPLPartnerProfile
from app.util.api.db_config import get_db
from app.service.lead_profile.lead_profile_service import LeadProfileService
import uuid


router = APIRouter(
    prefix="/lead-profile",  
    tags=["Lead Profile"]    
)

lead_profile_service = LeadProfileService()

@router.post("/create", response_model=PPLPartnerProfile)
async def create_partner_profile(
    partner_profile: PPLPartnerProfileCreate,
    db: AsyncSession = Depends(get_db)
):
    """
    Create a new partner profile.
    """
    return await lead_profile_service.create_lead_profile(db=db, partner_profile=partner_profile)

