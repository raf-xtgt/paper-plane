from sqlalchemy.ext.asyncio import AsyncSession
from app.model.api.ppl_lead_profile import PPLPartnerProfileCreate, PPLPartnerProfileDB

class LeadProfileService:
    async def create_lead_profile(self, db: AsyncSession, partner_profile: PPLPartnerProfileCreate) -> PPLPartnerProfileDB:
        """
        Creates a partner profile row in the database.
        """
        db_partner_profile = PPLPartnerProfileDB(**partner_profile.dict())
        db.add(db_partner_profile)
        await db.commit()
        await db.refresh(db_partner_profile)
        return db_partner_profile

