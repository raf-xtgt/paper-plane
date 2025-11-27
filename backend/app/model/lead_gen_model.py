"""
Data models for AI-powered lead generation system.

This module defines Pydantic models for the agentic lead generation pipeline,
including API request/response models, agent output schemas, and Kafka message formats.
"""

from pydantic import BaseModel, HttpUrl, Field
from typing import Optional, Literal
from datetime import datetime


# API Request/Response Models

class LeadGenRequest(BaseModel):
    """
    Request model for triggering lead generation pipeline.
    
    Attributes:
        city: Target city name for partner discovery
        market: Market vertical (Student Recruitment or Medical Tourism)
    """
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
        key_fact: One key fact for personalization (awards, branches, motto)
        verified_url: Verified website URL after scraping
        status: Enrichment status (complete or incomplete)
    """
    decision_maker: Optional[str] = Field(None, description="Decision-maker name")
    contact_info: Optional[str] = Field(None, description="Contact information")
    key_fact: Optional[str] = Field(None, description="Key fact for personalization")
    verified_url: HttpUrl = Field(..., description="Verified website URL")
    status: Literal["complete", "incomplete"] = Field(
        ..., description="Enrichment completion status"
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


# Kafka Message Models

class PartnerProfile(BaseModel):
    """
    Partner profile data for Kafka message.
    
    Attributes:
        name: Partner organization name
        url: Partner website URL
        contact_person: Name of the contact person
        contact_method: Contact method (email, phone, WhatsApp)
        entity_type: Type of partner entity
    """
    name: str = Field(..., description="Partner name")
    url: HttpUrl = Field(..., description="Partner website")
    contact_person: Optional[str] = Field(None, description="Contact person name")
    contact_method: Optional[str] = Field(None, description="Contact method")
    entity_type: str = Field(..., description="Entity type")


class AIContext(BaseModel):
    """
    AI-generated context and insights for Kafka message.
    
    Attributes:
        key_insight: Key fact discovered about the partner
        draft_message: AI-generated outreach message draft
    """
    key_insight: Optional[str] = Field(None, description="Key insight about partner")
    draft_message: str = Field(..., description="Draft outreach message")


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
