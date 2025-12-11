"""
Navigator Agent for intelligent web crawling and contact extraction.

This agent bridges the Scout Agent and Researcher Agent in the PaperPlane lead
generation pipeline. It uses Crawl4AI with Playwright to render dynamic JavaScript
content and extract decision-maker contact information from business websites.
"""

import os
import logging
import asyncio
from typing import List, Optional, Dict, Any
import google.generativeai as genai
from app.model.lead_gen_model import ScrapedBusinessData, PartnerEnrichment
from app.service.agents.navigator.navigator_web_crawler import NavigatorWebCrawler
from app.service.agents.navigator.navigator_content_extractor import NavigatorContentExtractor
import re
from pydantic import ValidationError

# Configure logging
logger = logging.getLogger("lead_gen_pipeline.navigator")

# Configure Gemini API
genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))


class NavigatorAgent:
    """
    Navigator Agent for intelligent web crawling and contact extraction.
    
    Uses Crawl4AI with Playwright to render dynamic content and extract
    decision-maker contact information using Gemini Flash LLM.
    """
    
    def __init__(self):
        """Initialize Navigator Agent with Crawl4AI and Gemini Flash model."""
        # Configuration from environment variables
        self.model_name = os.getenv("ADK_MODEL_FLASH", "gemini-2.0-flash-exp")
        self.temperature = float(os.getenv("NAVIGATOR_TEMPERATURE", "0.1"))
        self.timeout = int(os.getenv("NAVIGATOR_TIMEOUT", "180"))
        self.page_timeout = int(os.getenv("NAVIGATOR_PAGE_TIMEOUT", "90"))
        self.max_retries = int(os.getenv("NAVIGATOR_MAX_RETRIES", "3"))
        self.concurrent_limit = int(os.getenv("NAVIGATOR_CONCURRENT_LIMIT", "5"))
        
        # Initialize Gemini model with proper configuration
        self.model = genai.GenerativeModel(
            model_name=self.model_name,
            generation_config={
                "temperature": self.temperature,
                "top_p": 0.95,
                "top_k": 40,
                "max_output_tokens": 1024,
                "response_mime_type": "application/json"
            }
        )
        
        # Initialize components
        self.web_crawler = NavigatorWebCrawler(
            page_timeout=self.page_timeout,
            max_retries=self.max_retries
        )
        self.content_extractor = NavigatorContentExtractor(self.model)
        self.data_validator = DataValidator()
        
        logger.info(f"Navigator Agent initialized with model: {self.model_name}")
    
    async def navigate_and_extract_batch(
        self, 
        scraped_data: List[ScrapedBusinessData]
    ) -> List[PartnerEnrichment]:
        """
        Process multiple partners asynchronously.
        
        Args:
            scraped_data: List of ScrapedBusinessData from Scout Agent
            
        Returns:
            List of PartnerEnrichment objects
        """
        if not scraped_data:
            logger.warning("No scraped data provided for batch processing")
            return []
        
        # Filter data with valid website URLs
        valid_data = [data for data in scraped_data if data.website_url]
        logger.info(f"Starting batch processing of {len(valid_data)} partners with valid URLs")
        
        if not valid_data:
            logger.warning("No partners with valid website URLs found")
            return []
        
        # Create semaphore to limit concurrent processing
        semaphore = asyncio.Semaphore(self.concurrent_limit)
        
        async def process_with_semaphore(data: ScrapedBusinessData, index: int) -> PartnerEnrichment:
            """Process single partner with semaphore control."""
            async with semaphore:
                try:
                    return await self.navigate_and_extract(
                        website_url=data.website_url,
                        entity_name=data.org_name or f"Partner_{index}"
                    )
                except Exception as e:
                    logger.error(f"Failed to process partner {index} ({data.org_name}): {e}")
                    # Return incomplete enrichment for failed processing
                    return PartnerEnrichment(
                        verified_url=data.website_url,
                        status="incomplete"
                    )
        
        # Process all partners concurrently with limit
        tasks = [
            process_with_semaphore(data, i) 
            for i, data in enumerate(valid_data)
        ]
        
        # Execute all tasks and collect results
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Process results and handle any remaining exceptions
        enrichments = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Unexpected exception for partner {i}: {result}")
                # Create fallback incomplete enrichment
                try:
                    enrichments.append(PartnerEnrichment(
                        verified_url=valid_data[i].website_url,
                        status="incomplete"
                    ))
                except Exception as fallback_error:
                    logger.error(f"Failed to create fallback enrichment: {fallback_error}")
            else:
                enrichments.append(result)
        
        successful_count = sum(1 for e in enrichments if e.status == "complete")
        logger.info(
            f"Completed batch processing: {len(enrichments)} total, "
            f"{successful_count} successful, {len(enrichments) - successful_count} incomplete"
        )
        return enrichments
    
    async def navigate_and_extract(
        self, 
        website_url: str, 
        entity_name: str
    ) -> PartnerEnrichment:
        """
        Process single partner with crawling and extraction.
        
        Args:
            website_url: Website URL to crawl
            entity_name: Name of the entity/organization
            
        Returns:
            PartnerEnrichment object with extracted data
        """
        start_time = asyncio.get_event_loop().time()
        logger.info(f"Processing {entity_name} at {website_url}")
        
        try:
            # Apply timeout to the entire processing operation
            async with asyncio.timeout(self.timeout):
                # Step 1: Crawl website and get content
                markdown_content, verified_url = await self.web_crawler.crawl_website(
                    website_url, entity_name
                )
                
                # Step 2: Extract contact information using LLM
                extracted_data = await self.content_extractor.extract_contact_info(
                    markdown_content, entity_name, verified_url
                )
                
                # Step 3: Validate and create PartnerEnrichment
                enrichment = self.data_validator.validate_partner_enrichment(
                    extracted_data, verified_url
                )
                
                duration = asyncio.get_event_loop().time() - start_time
                logger.info(
                    f"Successfully processed {entity_name} in {duration:.2f}s - "
                    f"Status: {enrichment.status}"
                )
                
                return enrichment
            
        except asyncio.TimeoutError:
            logger.error(f"Timeout processing {entity_name} after {self.timeout}s")
            return PartnerEnrichment(
                verified_url=website_url,
                status="incomplete"
            )
        except Exception as e:
            logger.error(f"Error processing {entity_name}: {e}")
            return PartnerEnrichment(
                verified_url=website_url,
                status="incomplete"
            )


class DataValidator:
    """
    Validation and normalization of extracted data.
    """
    
    def __init__(self):
        """Initialize DataValidator."""
        self.email_pattern = re.compile(
            r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        )
        logger.debug("DataValidator initialized")
    
    def validate_email(self, email: str) -> bool:
        """Validate email format using regex."""
        if not email:
            return False
        return bool(self.email_pattern.match(email.strip()))
    
    def normalize_phone(self, phone: str) -> str:
        """Normalize phone number format."""
        if not phone:
            return phone
        
        # Remove all non-digit characters except +
        normalized = re.sub(r'[^\d+]', '', phone)
        return normalized
    
    def determine_contact_channel(self, contact_info: str) -> str:
        """Classify contact information into appropriate channel."""
        if not contact_info:
            return "Other"
        
        contact_lower = contact_info.lower()
        
        if '@' in contact_info and self.validate_email(contact_info):
            return "Email"
        elif any(keyword in contact_lower for keyword in ['whatsapp', 'wa.me', 'wa.link']):
            return "WhatsApp"
        elif any(keyword in contact_lower for keyword in ['instagram', 'insta', 'ig']):
            return "Instagram"
        elif any(keyword in contact_lower for keyword in ['messenger', 'fb', 'facebook']):
            return "Messenger"
        elif re.search(r'[\d+\-\(\)\s]{7,}', contact_info):
            return "PhoneNo"
        else:
            return "Other"
    
    def validate_partner_enrichment(
        self, 
        data: Dict[str, Any], 
        verified_url: str
    ) -> PartnerEnrichment:
        """Create and validate PartnerEnrichment object."""
        try:
            # Normalize contact info if present
            contact_info = data.get("contact_info")
            if contact_info and data.get("contact_channel") == "PhoneNo":
                contact_info = self.normalize_phone(contact_info)
            
            # Determine contact channel if not provided or validate existing
            contact_channel = data.get("contact_channel")
            if contact_info and not contact_channel:
                contact_channel = self.determine_contact_channel(contact_info)
            
            # Create PartnerEnrichment object
            enrichment = PartnerEnrichment(
                decision_maker=data.get("decision_maker"),
                contact_info=contact_info,
                contact_channel=contact_channel,
                key_fact=data.get("key_fact"),
                verified_url=verified_url,
                status=data.get("status", "incomplete")
            )
            
            return enrichment
            
        except ValidationError as e:
            logger.error(f"Validation error creating PartnerEnrichment: {e}")
            # Return minimal valid object
            return PartnerEnrichment(
                verified_url=verified_url,
                status="incomplete"
            )
        except Exception as e:
            logger.error(f"Error creating PartnerEnrichment: {e}")
            return PartnerEnrichment(
                verified_url=verified_url,
                status="incomplete"
            )