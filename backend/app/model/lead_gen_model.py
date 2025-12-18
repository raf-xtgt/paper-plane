"""
Data models for AI-powered lead generation system.

This module defines Pydantic models for the agentic lead generation pipeline,
including API request/response models, agent output schemas, and Kafka message formats.
"""

from pydantic import BaseModel, HttpUrl, Field, ConfigDict
from typing import Optional, Literal, List
from datetime import datetime
import uuid

# API Request/Response Models

class LeadGenRequest(BaseModel):
    """
    Request model for triggering lead generation pipeline.
    
    Attributes:
        city: Target city name for partner discovery
        market: Market vertical (Student Recruitment or Medical Tourism)
    """
    district: str = Field(..., min_length=1, description="Target name of district or state")
    city: str = Field(..., min_length=1, description="Target city name")
    market: Literal["Student Recruitment", "Medical Tourism"] = Field(
        ..., description="Market vertical for partner discovery"
    )


class LeadGenResponse(BaseModel):
    """
    Response model for lead generation API endpoint.
    
    Attributes:
        job_id: Unique identifier for tracking the pipeline execution
        status: Current status of the job (typically "processing")
        message: Human-readable status message
    """
    job_id: str = Field(..., description="Unique job identifier")
    status: str = Field(default="processing", description="Job status")
    message: str = Field(..., description="Status message")


# Agent Output Models

class PartnerContactDetails(BaseModel):
    """
    V2 contact schema for comprehensive contact extraction.
    
    Attributes:
        decision_maker: Name tied to contact information
        contact_info: Contact information (email, phone, social media URL)
        contact_channel: Channel type (WhatsApp, Email, Messenger, Instagram, PhoneNo, Others)
    """
    decision_maker: Optional[str] = Field(None, description="Decision-maker name")
    contact_info: Optional[str] = Field(None, description="Contact information")
    contact_channel: Optional[Literal["WhatsApp", "Email", "Messenger", "Instagram", "PhoneNo", "Others"]] = Field(
        None, description="Contact channel type"
    )


class PartnerDiscovery(BaseModel):
    """
    Output model for Scout Agent - discovered partner entities.
    
    Attributes:
        entity_name: Name of the discovered partner organization
        website_url: URL of the partner's website
        type: Type of entity (e.g., High School, Diagnostic Center)
    """
    entity_name: str = Field(..., description="Partner organization name")
    website_url: HttpUrl = Field(..., description="Partner website URL")
    type: str = Field(..., description="Entity type or category")


class PartnerEnrichment(BaseModel):
    """
    Output model for Researcher Agent - enriched partner data.
    
    Attributes:
        decision_maker: Name of the decision-maker (Principal, Director, etc.)
        contact_info: Direct contact information (email, phone, WhatsApp)
        contact_channel: Preferred contact channel (WhatsApp, Email, Messenger, Instagram, PhoneNo, Others)
        key_fact: One key fact for personalization (awards, branches, motto)
        verified_url: Verified website URL after scraping
        status: Enrichment status (complete or incomplete)
        all_contacts: All extracted contact details (V2 comprehensive contact data)
    """
    decision_maker: Optional[str] = Field(None, description="Decision-maker name")
    contact_info: Optional[str] = Field(None, description="Contact information")
    contact_channel: Optional[Literal["WhatsApp", "Email", "Messenger", "Instagram", "PhoneNo", "Others"]] = Field(
        None, description="Preferred contact channel"
    )
    key_fact: Optional[str] = Field(None, description="Key fact for personalization")
    verified_url: HttpUrl = Field(..., description="Verified website URL")
    status: Literal["complete", "incomplete"] = Field(
        ..., description="Enrichment completion status"
    )
    all_contacts: Optional[List[PartnerContactDetails]] = Field(
        None, description="All extracted contact details"
    )


class OutreachDraft(BaseModel):
    """
    Output model for Strategist Agent - generated outreach message.
    
    Attributes:
        draft_message: Personalized WhatsApp message draft (max 500 chars)
    """
    draft_message: str = Field(
        ..., 
        max_length=500, 
        description="Personalized outreach message"
    )

    model_config = ConfigDict(
        json_schema_extra={
            'properties': {
                'draft_message': {
                    'description': 'The outreach message to the partner business'
                },

            }
        }
    )


# Kafka Message Models


class PartnerContact(BaseModel):
    lead_guid:str
    name: str
    contact_info: str
    url: str
    class Config:
        frozen = True

class AIContext(BaseModel):
    """
    AI-generated context and insights for Kafka message.
    
    Attributes:
        key_insight: Key fact discovered about the partner
        draft_message: AI-generated outreach message draft
    """
    key_insight: Optional[str] = Field(None, description="Key insight about partner")
    draft_message: str = Field(..., description="Draft outreach message")


class SearchQuery(BaseModel):
    query: str


class PageMarkdown(BaseModel):
    """
    Crawled page data with markdown content.
    
    Attributes:
        page_url: URL of the crawled page
        markdown_content: Extracted content in markdown format
    """
    page_url: str = Field(..., description="URL of the crawled page")
    markdown_content: str = Field(..., description="Extracted content in markdown format")


class PageKeyFact(PageMarkdown):
    """
    Extended page data with extracted key facts.
    
    Inherits from PageMarkdown and adds key facts extraction.
    
    Attributes:
        page_url: URL of the crawled page (inherited)
        markdown_content: Extracted content in markdown format (inherited)
        key_facts: List of extracted key facts from the page content
    """
    key_facts: List[str] = Field(..., description="List of extracted key facts from the page content")


class ScrapedBusinessData(BaseModel):
    """
    Raw data extracted from Google Maps business card.
    """
    guid: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Unique identifier"
    )
    org_name: Optional[str] = Field(None, description="Organization name")
    primary_contact: Optional[str] = Field(None, description="Phone number")
    review_score: Optional[str] = Field(None, description="Review score")
    total_reviews: Optional[str] = Field(None, description="Total review count")
    website_url: Optional[str] = Field(None, description="Website URL")
    address: Optional[str] = Field(None, description="Physical address")


class PartnerProfile(ScrapedBusinessData):
    """
    Partner profile data for Kafka message, inheriting from ScrapedBusinessData.
    Extends the base scraped data with additional contact information and URLs.
    """
    emails: Optional[List[str]] = Field(
        None, description="List of email addresses found"
    )
    phone_numbers: Optional[List[str]] = Field(
        None, description="List of phone numbers found"
    )
    internal_urls: Optional[List[str]] = Field(
        None, description="List of internal URLs discovered"
    )
    external_urls: Optional[List[str]] = Field(
        None, description="List of external URLs discovered"
    )
    entity_type: Optional[str] = Field(
        None, description="Type of partner entity (e.g., 'vendor', 'client')"
    )
    lead_phase: Optional[str] = Field(
        None, description="Current phase in the lead pipeline (e.g., 'new', 'contacted')"
    )
    key_facts: Optional[List[PageKeyFact]] = Field(None, description="List of partner key facts")
    outreach_draft_message: Optional[OutreachDraft] = Field(None, description="Outreach draft message")

class LeadObject(BaseModel):
    """
    Complete lead data structure for Kafka "lead_generated" topic.

    This model represents the final output of the ADK pipeline,
    containing all discovered and enriched partner information.

    Attributes:
        event_type: Type of event (always "lead_discovered")
        timestamp: When the lead was generated
        source_agent: Source system identifier (e.g., "adk_v1")
        market: Market vertical
        city: Target city
        partner_profile: Partner organization details
        ai_context: AI-generated insights and message
    """
    event_type: str = Field(default="lead_discovered", description="Event type")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Event timestamp")
    source_agent: str = Field(default="adk_v1", description="Source agent identifier")
    market: str = Field(..., description="Market vertical")
    city: str = Field(..., description="Target city")
    partner_profile: PartnerProfile = Field(..., description="Partner details")
    ai_context: AIContext = Field(..., description="AI-generated context")

