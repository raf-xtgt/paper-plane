from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete
from sqlalchemy.orm import selectinload
from app.model.api.ppl_lead_profile import PPLPartnerProfileCreate, PPLPartnerProfileDB, PPLPartnerProfileUpdate
from typing import Optional, List, AsyncGenerator, Union
import uuid

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

    async def get_lead_profile(self, db: AsyncSession, profile_guid: uuid.UUID) -> Optional[PPLPartnerProfileDB]:
        """
        Retrieves a partner profile by GUID.
        """
        result = await db.execute(
            select(PPLPartnerProfileDB).where(PPLPartnerProfileDB.guid == profile_guid)
        )
        return result.scalar_one_or_none()

    async def get_lead_profiles_by_user(self, db: AsyncSession, user_guid: uuid.UUID, limit: int = 100, offset: int = 0) -> List[PPLPartnerProfileDB]:
        """
        Retrieves partner profiles for a specific user with pagination.
        """
        result = await db.execute(
            select(PPLPartnerProfileDB)
            .where(PPLPartnerProfileDB.user_guid == user_guid)
            .order_by(PPLPartnerProfileDB.created_date.desc())
            .limit(limit)
            .offset(offset)
        )
        return result.scalars().all()

    async def update_lead_profile(self, db: AsyncSession, profile_guid: uuid.UUID, partner_profile: Union[PPLPartnerProfileCreate, PPLPartnerProfileUpdate]) -> Optional[PPLPartnerProfileDB]:
        """
        Updates a partner profile by GUID.
        """
        # First check if the profile exists
        existing_profile = await self.get_lead_profile(db, profile_guid)
        if not existing_profile:
            return None

        # Update the profile
        update_data = partner_profile.dict(exclude_unset=True)
        await db.execute(
            update(PPLPartnerProfileDB)
            .where(PPLPartnerProfileDB.guid == profile_guid)
            .values(**update_data)
        )
        await db.commit()
        
        # Return the updated profile
        return await self.get_lead_profile(db, profile_guid)

    async def delete_lead_profile(self, db: AsyncSession, profile_guid: uuid.UUID) -> bool:
        """
        Deletes a partner profile by GUID.
        Returns True if deleted, False if not found.
        """
        # First check if the profile exists
        existing_profile = await self.get_lead_profile(db, profile_guid)
        if not existing_profile:
            return False

        await db.execute(
            delete(PPLPartnerProfileDB).where(PPLPartnerProfileDB.guid == profile_guid)
        )
        await db.commit()
        return True

    async def stream_lead_profiles(self, db: AsyncSession, user_guid: Optional[uuid.UUID] = None, batch_size: int = 50) -> AsyncGenerator[List[PPLPartnerProfileDB], None]:
        """
        Streams partner profiles in batches for efficient processing.
        If user_guid is provided, filters by user. Otherwise returns all profiles.
        """
        offset = 0
        
        while True:
            query = select(PPLPartnerProfileDB).order_by(PPLPartnerProfileDB.created_date.desc())
            
            if user_guid:
                query = query.where(PPLPartnerProfileDB.user_guid == user_guid)
            
            query = query.limit(batch_size).offset(offset)
            
            result = await db.execute(query)
            batch = result.scalars().all()
            
            if not batch:
                break
                
            yield batch
            offset += batch_size

    async def get_all_lead_profiles(self, db: AsyncSession, user_guid: Optional[uuid.UUID] = None) -> List[PPLPartnerProfileDB]:
        """
        Convenience method to get all profiles at once (use with caution for large datasets).
        """
        all_profiles = []
        async for batch in self.stream_lead_profiles(db, user_guid):
            all_profiles.extend(batch)
        return all_profiles

