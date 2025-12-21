from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from app.model.api.ppl_lead_profile import PPLPartnerProfileCreate, PPLPartnerProfile, PPLPartnerProfileUpdate
from app.model.api.api_response.api_response import ApiResponse
from app.util.api.db_config import get_db
from app.service.lead_profile.lead_profile_service import LeadProfileService
from typing import List, Optional
import uuid
import json


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

@router.get("/listing", response_model=ApiResponse[List[PPLPartnerProfile]])
async def get_all_partner_profiles(
    limit: Optional[int] = Query(None, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db)
):
    """
    Get all partner profiles. Optionally filter by user_guid with pagination support.
    """
    print("Lead profile listing")
    try:
        profiles_db = await lead_profile_service.get_lead_profiles_list(
            db=db,  limit=limit, offset=offset
        )
        # Convert SQLAlchemy models to Pydantic models
        profiles = [PPLPartnerProfile.model_validate(profile) for profile in profiles_db]
        return ApiResponse.success(profiles)
    except Exception as e:
        return ApiResponse.error(f"Failed to retrieve partner profiles: {str(e)}")

@router.get("/{profile_guid}", response_model=PPLPartnerProfile)
async def get_partner_profile(
    profile_guid: uuid.UUID,
    db: AsyncSession = Depends(get_db)
):
    """
    Get a partner profile by GUID.
    """
    profile = await lead_profile_service.get_lead_profile(db=db, profile_guid=profile_guid)
    if not profile:
        raise HTTPException(status_code=404, detail="Partner profile not found")
    return profile

@router.get("/user/{user_guid}", response_model=List[PPLPartnerProfile])
async def get_partner_profiles_by_user(
    user_guid: uuid.UUID,
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db)
):
    """
    Get partner profiles for a specific user with pagination.
    """
    return await lead_profile_service.get_lead_profiles_by_user(
        db=db, user_guid=user_guid, limit=limit, offset=offset
    )

@router.put("/{profile_guid}", response_model=PPLPartnerProfile)
async def update_partner_profile(
    profile_guid: uuid.UUID,
    partner_profile: PPLPartnerProfileUpdate,
    db: AsyncSession = Depends(get_db)
):
    """
    Update a partner profile by GUID.
    """
    updated_profile = await lead_profile_service.update_lead_profile(
        db=db, profile_guid=profile_guid, partner_profile=partner_profile
    )
    if not updated_profile:
        raise HTTPException(status_code=404, detail="Partner profile not found")
    return updated_profile

@router.delete("/{profile_guid}")
async def delete_partner_profile(
    profile_guid: uuid.UUID,
    db: AsyncSession = Depends(get_db)
):
    """
    Delete a partner profile by GUID.
    """
    deleted = await lead_profile_service.delete_lead_profile(db=db, profile_guid=profile_guid)
    if not deleted:
        raise HTTPException(status_code=404, detail="Partner profile not found")
    return {"message": "Partner profile deleted successfully"}
