from sqlalchemy import Column, String, Text, DateTime, func
from sqlalchemy.dialects.postgresql import UUID
import uuid
from pydantic import BaseModel, Field
from datetime import datetime
from app.util.api.db_config import Base

class PPLPartnerProfileDB(Base):
    __tablename__ = "ppl_partner_profile"

    guid = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    url = Column(Text)
    contact_person = Column(String(255), nullable=True)
    contact_method= Column(String(255), nullable=True)
    contact_channel = Column(String(255), nullable=True)
    entity_type = Column(String(255), nullable=True)
    user_guid = Column(UUID(as_uuid=True), index=True)
    created_date = Column(DateTime(timezone=True), server_default=func.now())
    last_update = Column(DateTime(timezone=True),  server_default=func.now(), onupdate=func.now())

class PPLPartnerProfileBase(BaseModel):
    name: str
    url: str | None = None
    contact_person: str | None = None
    contact_method: str | None = None
    contact_channel: str | None = None
    entity_type: str | None = None
    user_guid:  uuid.UUID | None = None

class PPLPartnerProfileCreate(PPLPartnerProfileBase):
    pass

class PPLPartnerProfile(PPLPartnerProfileBase):
    guid: uuid.UUID
    created_date: datetime
    last_update: datetime

    class Config:
        orm_mode = True