from sqlalchemy import Column, String, Text, DateTime, JSON, func
from sqlalchemy.dialects.postgresql import UUID
import uuid
from pydantic import BaseModel
from datetime import datetime
from app.util.api.db_config import Base


class PPLGeneratedLeadDB(Base):
    __tablename__ = "ppl_generated_lead"

    guid = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    partner_profile_guid = Column(UUID(as_uuid=True), nullable=True, index=True)
    user_guid = Column(UUID(as_uuid=True), nullable=True, index=True)
    market = Column(String(255), nullable=True)
    city = Column(String(255), nullable=True)
    source_agent = Column(String(255))
    key_insight = Column(Text)
    draft_message = Column(Text)
    notification_data = Column(JSON)
    status = Column(String(50), default="pending")
    created_date = Column(DateTime(timezone=True), server_default=func.now())
    last_update = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class PPLGeneratedLeadBase(BaseModel):
    partner_profile_guid: uuid.UUID
    user_guid: uuid.UUID
    market: str
    city: str
    source_agent: str | None = None
    key_insight: str | None = None
    draft_message: str | None = None
    notification_data: dict | None = None
    status: str = "pending"


class PPLGeneratedLeadCreate(PPLGeneratedLeadBase):
    pass


class PPLGeneratedLead(PPLGeneratedLeadBase):
    guid: uuid.UUID
    created_date: datetime
    last_update: datetime

    class Config:
        orm_mode = True
