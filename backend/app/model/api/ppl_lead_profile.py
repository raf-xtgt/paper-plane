from sqlalchemy import Column, String, Text, DateTime, func, JSON, Float
from sqlalchemy.dialects.postgresql import UUID
import uuid
from pydantic import BaseModel, Field, HttpUrl
from datetime import datetime
from typing import Optional, List
from app.util.api.db_config import Base

class PPLPartnerProfileDB(Base):
    __tablename__ = "ppl_partner_profile"

    guid = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_name = Column(String(255), nullable=True)
    primary_contact = Column(String(255), nullable=True)
    review_score = Column(String(50), nullable=True)
    total_reviews = Column(String(50), nullable=True)
    website_url = Column(Text, nullable=True)
    address = Column(Text, nullable=True)
    emails = Column(JSON, nullable=True)  # List of email addresses
    phone_numbers = Column(JSON, nullable=True)  # List of phone numbers
    internal_urls = Column(JSON, nullable=True)  # List of internal URLs
    external_urls = Column(JSON, nullable=True)  # List of external URLs
    entity_type = Column(String(255), nullable=True)
    lead_phase = Column(String(100), nullable=True)
    key_facts = Column(JSON, nullable=True)  # List of key facts
    outreach_draft_message = Column(Text, nullable=True)
    user_guid = Column(UUID(as_uuid=True), index=True)
    created_date = Column(DateTime(timezone=True), server_default=func.now())
    last_update = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

class PPLPartnerProfileBase(BaseModel):
    org_name: Optional[str] = None
    primary_contact: Optional[str] = None
    review_score: Optional[str] = None
    total_reviews: Optional[str] = None
    website_url: Optional[str] = None
    address: Optional[str] = None
    emails: Optional[List[str]] = None
    phone_numbers: Optional[List[str]] = None
    internal_urls: Optional[List[str]] = None
    external_urls: Optional[List[str]] = None
    entity_type: Optional[str] = None
    lead_phase: Optional[str] = None
    key_facts: Optional[List[str]] = None
    outreach_draft_message: Optional[str] = None
    user_guid: Optional[uuid.UUID] = None

class PPLPartnerProfileCreate(PPLPartnerProfileBase):
    pass

class PPLPartnerProfileUpdate(PPLPartnerProfileBase):
    """
    Model for updating partner profiles - all fields are optional
    """
    pass

class PPLPartnerProfile(PPLPartnerProfileBase):
    guid: uuid.UUID
    created_date: datetime
    last_update: datetime

    class Config:
        from_attributes = True