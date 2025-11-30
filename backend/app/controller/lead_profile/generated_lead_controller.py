from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.util.api.db_config import get_db
from app.model.api.ppl_generated_lead import PPLGeneratedLeadCreate, PPLGeneratedLead
from app.service.lead_profile.generated_lead_service import GeneratedLeadService
import uuid

router = APIRouter(prefix="/generated_leads", tags=["Generated Leads"])
service = GeneratedLeadService()


@router.post("/", response_model=PPLGeneratedLead)
async def create_generated_lead(
    lead: PPLGeneratedLeadCreate,
    db: AsyncSession = Depends(get_db)
):
    """Create a new generated lead record."""
    db_lead = await service.create_generated_lead(db, lead)
    return db_lead


@router.get("/{guid}", response_model=PPLGeneratedLead)
async def get_generated_lead(
    guid: uuid.UUID,
    db: AsyncSession = Depends(get_db)
):
    """Retrieve a generated lead by GUID."""
    db_lead = await service.get_generated_lead_by_guid(db, guid)
    if not db_lead:
        raise HTTPException(status_code=404, detail="Generated lead not found")
    return db_lead


@router.get("/user/{user_guid}", response_model=list[PPLGeneratedLead])
async def get_user_generated_leads(
    user_guid: uuid.UUID,
    db: AsyncSession = Depends(get_db)
):
    """Retrieve all generated leads for a specific user."""
    leads = await service.get_generated_leads_by_user(db, user_guid)
    return leads
