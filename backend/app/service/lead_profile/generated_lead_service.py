from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.model.api.ppl_generated_lead import PPLGeneratedLeadCreate, PPLGeneratedLeadDB
import uuid


class GeneratedLeadService:
    async def create_generated_lead(
        self, 
        db: AsyncSession, 
        lead: PPLGeneratedLeadCreate
    ) -> PPLGeneratedLeadDB:
        """
        Creates a generated lead row in the database.
        """
        db_lead = PPLGeneratedLeadDB(**lead.dict())
        db.add(db_lead)
        await db.commit()
        await db.refresh(db_lead)
        return db_lead

    async def get_generated_lead_by_guid(
        self, 
        db: AsyncSession, 
        guid: uuid.UUID
    ) -> PPLGeneratedLeadDB | None:
        """
        Retrieves a generated lead by GUID.
        """
        result = await db.execute(
            select(PPLGeneratedLeadDB).where(PPLGeneratedLeadDB.guid == guid)
        )
        return result.scalar_one_or_none()

    async def get_generated_leads_by_user(
        self, 
        db: AsyncSession, 
        user_guid: uuid.UUID
    ) -> list[PPLGeneratedLeadDB]:
        """
        Retrieves all generated leads for a specific user.
        """
        result = await db.execute(
            select(PPLGeneratedLeadDB)
            .where(PPLGeneratedLeadDB.user_guid == user_guid)
            .order_by(PPLGeneratedLeadDB.created_date.desc())
        )
        return result.scalars().all()
