"""
Lead Generation Controller - FastAPI endpoint for triggering AI-powered lead discovery.

This controller exposes a REST API endpoint that triggers the ADK pipeline
asynchronously and returns immediately with a job identifier for tracking.
"""

import uuid
import asyncio
import logging
from fastapi import Depends, APIRouter, HTTPException
from app.model.lead_gen_model import LeadGenRequest, LeadGenResponse, SearchQuery
from app.service.agents.lead_gen_service import LeadGenPipeline
from app.service.agents.scout.scout_agent_helper import scrape_google_maps
from sqlalchemy.ext.asyncio import AsyncSession
from app.util.api.db_config import get_db

# Configure logging
logger = logging.getLogger("lead_gen_controller")

# Create router with prefix and tags
router = APIRouter(
    prefix="/agents",
    tags=["Lead Generation"]
)

# Initialize pipeline (singleton pattern)
pipeline = LeadGenPipeline()


@router.post("/lead-gen", response_model=LeadGenResponse)
async def trigger_lead_generation(request: LeadGenRequest, dbConn: AsyncSession = Depends(get_db)):
    """
    Trigger AI-powered lead generation pipeline for a specific city and market.
    
    This endpoint validates the request, generates a unique job ID, and triggers
    the ADK pipeline asynchronously in the background. It returns immediately
    with the job ID and status "processing".
    
    The pipeline will:
    1. Scout Agent: Discover 3-10 potential channel partners
    2. Researcher Agent: Enrich partners with contact details
    3. Strategist Agent: Generate personalized outreach messages
    4. Publish results to Kafka "lead_generated" topic
    
    Args:
        request: LeadGenRequest containing city and market parameters
        
    Returns:
        LeadGenResponse with job_id, status, and message
        
    Raises:
        HTTPException 400: If validation fails (empty city, invalid market)
        HTTPException 500: If system error occurs during job creation
        
    Example:
        POST /api/ppl/agents/lead-gen
        {
            "city": "Dubai",
            "market": "Student Recruitment"
        }
        
        Response:
        {
            "job_id": "550e8400-e29b-41d4-a716-446655440000",
            "status": "processing",
            "message": "Lead generation pipeline started for Dubai (Student Recruitment)"
        }
    """
    try:
        # Validate city parameter (non-empty and not just whitespace)
        if not request.city or not request.city.strip():
            logger.warning(
                f"Validation error: City parameter is empty or contains only whitespace"
            )
            raise HTTPException(
                status_code=400,
                detail="City parameter cannot be empty or contain only whitespace"
            )
        
        # Validate market parameter (enum validation handled by Pydantic)
        # This is a safety check in case Pydantic validation is bypassed
        valid_markets = ["Student Recruitment", "Medical Tourism"]
        if request.market not in valid_markets:
            logger.warning(
                f"Validation error: Invalid market value '{request.market}'"
            )
            raise HTTPException(
                status_code=400,
                detail=f"Invalid market value. Market must be one of: {', '.join(valid_markets)}"
            )
        
        # Generate unique job_id using uuid4
        job_id = str(uuid.uuid4())
        
        logger.info(
            f"Lead generation request received - "
            f"job_id: {job_id}, city: {request.city.strip()}, market: {request.market}"
        )
        
        # Trigger pipeline asynchronously in background
        # Use asyncio.create_task to run without blocking the response
        asyncio.create_task(
            pipeline.run_async(
                job_id=job_id,
                city=request.city.strip(),
                market=request.market,
                district=request.district,
            )
        )
        
        logger.info(
            f"Pipeline triggered in background - "
            f"job_id: {job_id}, city: {request.city.strip()}, market: {request.market}"
        )
        
        # Return immediate response with job_id and status "processing"
        return LeadGenResponse(
            job_id=job_id,
            status="processing",
            message=f"Lead generation pipeline started for {request.city.strip()} ({request.market})"
        )
        
    except HTTPException:
        # Re-raise HTTP exceptions (validation errors)
        raise
        
    except Exception as e:
        # Log unexpected errors and return 500
        logger.error(
            f"System error while triggering lead generation - "
            f"city: {getattr(request, 'city', 'N/A')}, "
            f"market: {getattr(request, 'market', 'N/A')}, "
            f"error: {str(e)}",
            exc_info=True
        )
        raise HTTPException(
            status_code=500,
            detail="Internal server error: Failed to start lead generation pipeline. Please try again later."
        )


@router.post("/scrape")
async def scrape_gmaps(request: SearchQuery):
    query=request.query
    scraped_data = await scrape_google_maps(query)
    print("\n--- FINAL OUTPUT (Newark) ---")
    print(scraped_data)
    return scraped_data

        
    
