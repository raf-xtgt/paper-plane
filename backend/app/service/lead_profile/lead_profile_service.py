from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.model.api.pl_lead_profile import PPLPartnerProfileCreate, PPLPartnerProfileDB
import uuid

class LeadProfileService:
    async def create_lead_profile(self, db: AsyncSession, session: PPLPartnerProfileCreate) -> PPLPartnerProfileDB:
        """
        Creates a row in the database.
        """
        db_session = PPLPartnerProfileDB(**session.dict())
        db.add(db_session)
        await db.commit()
        await db.refresh(db_session)
        return db_session

