"""
Researcher Agent for partner enrichment through web scraping.

This agent visits partner websites discovered by Scout Agent, navigates to
relevant pages (Contact, Staff, About Us, Leadership), and extracts decision-maker
information, contact details, and key facts for personalization.
"""

import os
import logging
import asyncio
from typing import List
import google.generativeai as genai
from app.model.lead_gen_model import PartnerDiscovery, PartnerEnrichment, PartnerProfile, PageMarkdown, \
    ScrapedBusinessData
from app.service.agents.researcher.researcher_crawler import ResearcherCrawler

# Configure logging
logger = logging.getLogger("lead_gen_pipeline.researcher")

# Configure Gemini API
genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))


class ResearcherAgent:
    """
    Researcher Agent for enriching partner data through web scraping.
    
    Visits partner websites, navigates to relevant pages, and extracts
    decision-maker names, contact information, and key facts using
    BeautifulSoup and Gemini LLM.
    """
    
    def __init__(self):
        """Initialize Researcher Agent with Gemini Flash model."""
        self.model_name = os.getenv("ADK_MODEL_FLASH", "gemini-2.0-flash-exp")
        self.temperature = 0.2
        self.timeout = int(os.getenv("RESEARCHER_TIMEOUT", "30"))
        
        # Initialize Gemini model
        self.model = genai.GenerativeModel(
            model_name=self.model_name,
            generation_config={
                "temperature": self.temperature,
                "top_p": 0.95,
                "top_k": 40,
                "max_output_tokens": 1024,
            }
        )
        
        # Request headers to mimic browser
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        logger.info(f"Researcher Agent initialized with model: {self.model_name}, timeout: {self.timeout}s")

    
    def enrich_partners_from_navigator(self, partner_profiles: List[ScrapedBusinessData]) -> List[PartnerEnrichment]:
        """
        Enrich partner profiles by crawling their internal and external URLs.
        
        Args:
            partner_profiles: List of PartnerProfile objects from Navigator Agent
            
        Returns:
            List of PartnerEnrichment objects with extracted data
        """
        logger.info(f"Starting enrichment for {len(partner_profiles)} partner profiles")
        
        enrichments = []
        
        for profile in partner_profiles:
            try:
                logger.info(f"Processing partner: {profile.org_name} (GUID: {profile.guid})")
                url = profile.website_url

                # Crawl all URLs and collect markdown content
                all_page_markdowns = []
                try:
                    logger.debug(f"Crawling URL: {url}")

                    # Run crawler asynchronously
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)

                    try:
                        crawler = ResearcherCrawler(max_pages=5)  # Limit pages per URL
                        page_markdowns = loop.run_until_complete(crawler.start(url))
                        all_page_markdowns.extend(page_markdowns)
                        logger.debug(f"Crawled {len(page_markdowns)} pages from {url}")

                    finally:
                        loop.close()

                except Exception as e:
                    logger.error(f"Failed to crawl URL {url} for {profile.org_name}: {e}")
                    continue
                
                logger.info(f"Collected {len(all_page_markdowns)} total pages for {profile.org_name}")
                
                # Process the markdown content to extract enrichment data
                enrichment = self._process_markdown_content(profile, all_page_markdowns)
                enrichments.append(enrichment)
                
            except Exception as e:
                logger.error(f"Failed to process partner {profile.org_name}: {e}", exc_info=True)
                # Create incomplete enrichment as fallback
                enrichment = PartnerEnrichment(
                    decision_maker=None,
                    contact_info=None,
                    contact_channel=None,
                    key_fact=f"Error processing: {str(e)[:100]}",
                    verified_url=profile.internal_urls[0] if profile.internal_urls else "https://example.com",
                    status="incomplete",
                    all_contacts=None
                )
                enrichments.append(enrichment)
        
        logger.info(f"Enrichment complete. Processed {len(enrichments)} partners")
        return enrichments
    
    def _process_markdown_content(self, profile: PartnerProfile, page_markdowns: List[PageMarkdown]) -> PartnerEnrichment:
        """
        Process crawled markdown content to extract enrichment data.
        
        Args:
            profile: Original PartnerProfile
            page_markdowns: List of PageMarkdown objects from crawling
            
        Returns:
            PartnerEnrichment object with extracted data
        """
        try:
            # Combine all markdown content for analysis
            combined_content = ""
            for page in page_markdowns:
                combined_content += f"\n\n--- Page: {page.page_url} ---\n"
                combined_content += page.markdown_content
            
            if not combined_content.strip():
                logger.warning(f"No content extracted for {profile.org_name}")
                return PartnerEnrichment(
                    decision_maker=None,
                    contact_info=None,
                    contact_channel=None,
                    key_fact=None,
                    verified_url=profile.internal_urls[0] if profile.internal_urls else "https://example.com",
                    status="incomplete",
                    all_contacts=None
                )
            
            # Use Gemini to extract structured data from markdown content
            prompt = f"""
            Analyze the following website content for the organization "{profile.org_name}" and extract:

            1. Decision maker name (CEO, Director, Principal, Manager, etc.)
            2. Best contact information (email or phone number)
            3. Preferred contact channel (WhatsApp, Email, Messenger, Instagram, PhoneNo, Others)
            4. One key fact for personalization (awards, achievements, specialties, branches, motto, etc.)

            Website Content:
            {combined_content[:8000]}  # Limit content to avoid token limits

            Respond in this exact JSON format:
            {{
                "decision_maker": "Name or null",
                "contact_info": "email@example.com or phone number or null",
                "contact_channel": "WhatsApp|Email|Messenger|Instagram|PhoneNo|Others or null",
                "key_fact": "One interesting fact or null"
            }}
            """
            
            try:
                response = self.model.generate_content(prompt)
                
                if response and response.text:
                    # Parse the JSON response
                    import json
                    extracted_data = json.loads(response.text.strip())
                    
                    # Determine status based on extracted data
                    status = "complete" if (
                        extracted_data.get("decision_maker") and 
                        extracted_data.get("contact_info")
                    ) else "incomplete"
                    
                    # Get verified URL (prefer internal URLs)
                    verified_url = (
                        profile.internal_urls[0] if profile.internal_urls 
                        else profile.external_urls[0] if profile.external_urls 
                        else "https://example.com"
                    )
                    
                    enrichment = PartnerEnrichment(
                        decision_maker=extracted_data.get("decision_maker"),
                        contact_info=extracted_data.get("contact_info"),
                        contact_channel=extracted_data.get("contact_channel"),
                        key_fact=extracted_data.get("key_fact"),
                        verified_url=verified_url,
                        status=status,
                        all_contacts=None  # Could be populated with detailed contact extraction
                    )
                    
                    logger.info(f"Successfully enriched {profile.org_name} - status: {status}")
                    return enrichment
                    
                else:
                    logger.warning(f"Empty response from Gemini for {profile.org_name}")
                    
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse Gemini response for {profile.org_name}: {e}")
            except Exception as e:
                logger.error(f"Gemini API error for {profile.org_name}: {e}")
            
        except Exception as e:
            logger.error(f"Error processing markdown content for {profile.org_name}: {e}")
        
        # Fallback enrichment
        verified_url = (
            profile.internal_urls[0] if profile.internal_urls 
            else profile.external_urls[0] if profile.external_urls 
            else "https://example.com"
        )
        
        return PartnerEnrichment(
            decision_maker=None,
            contact_info=profile.primary_contact,  # Use existing contact if available
            contact_channel="PhoneNo" if profile.primary_contact else None,
            key_fact=f"Organization type: {profile.entity_type}",
            verified_url=verified_url,
            status="incomplete",
            all_contacts=None
        )



