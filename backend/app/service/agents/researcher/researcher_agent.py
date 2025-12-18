"""
Researcher Agent for partner enrichment through web scraping.

This agent visits partner websites discovered by Scout Agent, navigates to
relevant pages (Contact, Staff, About Us, Leadership), and extracts decision-maker
information, contact details, and key facts for personalization.
"""

import os
import logging
import asyncio
import json
from app.service.agents.researcher.all_markdowns import sample_markdown_data
from typing import List
import google.generativeai as genai
from app.model.lead_gen_model import PartnerDiscovery, PartnerEnrichment, PartnerProfile, PageMarkdown, \
    PageKeyFact, ScrapedBusinessData
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
        self.model_name = os.getenv("ADK_MODEL_PRO", "gemini-2.0-flash")
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

    
    def enrich_partners_from_navigator(self, partner_profiles: List[PartnerProfile]) -> List[PartnerProfile]:
        """
        Enrich partner profiles by crawling their internal and external URLs.
        
        Args:
            partner_profiles: List of PartnerProfile objects from Navigator Agent
            
        Returns:
            List of PartnerEnrichment objects with extracted data
        """
        logger.info(f"Starting enrichment for {len(partner_profiles)} partner profiles")

        for profile in partner_profiles:
            try:
                logger.info(f"Processing partner: {profile.org_name} (GUID: {profile.guid})")
                url = profile.website_url

                # Crawl all URLs and collect markdown content
                all_page_markdowns = []
                # try:
                #     logger.debug(f"Crawling URL: {url}")
                #
                #     # Run crawler asynchronously
                #     loop = asyncio.new_event_loop()
                #     asyncio.set_event_loop(loop)
                #
                #     try:
                #         crawler = ResearcherCrawler(max_pages=5)  # Limit pages per URL
                #         page_markdowns = loop.run_until_complete(crawler.start(url))
                #         all_page_markdowns.extend(page_markdowns)
                #         logger.debug(f"Crawled {len(page_markdowns)} pages from {url}")
                #
                #     finally:
                #         loop.close()
                #
                # except Exception as e:
                #     logger.error(f"Failed to crawl URL {url} for {profile.org_name}: {e}")
                #     continue

                # all_page_markdowns = sample_markdown_data
                logger.info(f"Collected {len(all_page_markdowns)} total pages for {profile.org_name}")
                
                # Process the markdown content to extract enrichment data
                all_page_markdowns=sample_markdown_data
                partner_key_facts = self._extract_key_facts_from_markdown(profile, all_page_markdowns)
                profile.key_facts=partner_key_facts
                profile.outreach_draft_message=None
            except Exception as e:
                logger.error(f"Failed to process partner {profile.org_name}: {e}", exc_info=True)

        logger.info(f"Enrichment complete. Processed {len(partner_profiles)} partners")
        return partner_profiles
    
    def _extract_key_facts_from_markdown(self, profile: ScrapedBusinessData, page_markdowns: List[PageMarkdown]) -> List[PageKeyFact]:
        """
        Process crawled markdown content to extract enrichment data and key facts.
        
        Args:
            profile: Original ScrapedBusinessData profile
            page_markdowns: List of PageMarkdown objects from crawling
            
        Returns:
            PartnerEnrichment object with extracted data
        """
        try:
            # Process each page to extract key facts
            page_key_facts = []
            
            for page_markdown in page_markdowns:
                try:
                    logger.debug(f"Processing page: {page_markdown.page_url}")
                    
                    # Skip if content is too short
                    if len(page_markdown.markdown_content.strip()) < 100:
                        logger.debug(f"Skipping page with insufficient content: {page_markdown.page_url}")
                        continue
                    
                    # Extract key facts from this page using LLM
                    key_facts = self._extract_key_facts_from_page(page_markdown, profile.org_name)
                    
                    if key_facts:
                        page_key_fact = PageKeyFact(
                            page_url=page_markdown.page_url,
                            markdown_content=page_markdown.markdown_content,
                            key_facts=key_facts
                        )
                        page_key_facts.append(page_key_fact)
                        logger.debug(f"Extracted {len(key_facts)} key facts from {page_markdown.page_url}")
                    
                except Exception as e:
                    logger.error(f"Error processing page {page_markdown.page_url}: {e}")
                    continue

            logger.info(f"Successfully processed {profile.org_name} - url: {profile.website_url}, key_facts: {len(page_key_facts)}")
            return page_key_facts
            
        except Exception as e:
            logger.error(f"Error processing markdown content for {profile.org_name}: {e}")
            return self._create_fallback_enrichment(profile)
    
    def _extract_key_facts_from_page(self, page_markdown: PageMarkdown, org_name: str) -> List[str]:
        """
        Extract 1-3 key facts from a single page using LLM.
        
        Args:
            page_markdown: PageMarkdown object with content
            org_name: Organization name for context
            
        Returns:
            List of 1-3 key facts extracted from the page
        """
        try:
            # Limit content to avoid token limits
            content = page_markdown.markdown_content[:4000]
            
            prompt = f"""
            Analyze the following webpage content for the organization "{org_name}" and extract 1-3 key facts that would be useful for business outreach and personalization.

            Focus on:
            - Awards, achievements, or recognition
            - Specialties, services, or unique offerings
            - Leadership information or key personnel
            - Company milestones, history, or notable projects
            - Location details, branches, or service areas
            - Mission, values, or company culture highlights

            Page URL: {page_markdown.page_url}
            Content:
            {content}

            Respond with a JSON array of 1-3 key facts (strings only):
            """

            output_format = """\n
            ```
            {
                "key_facts":["Fact 1", "Fact 2", "Fact 3"]
            }
            ```
            """
            
            response = self.model.generate_content(prompt+output_format)
            
            if response and response.text:
                try:
                    # Extract JSON from the response text
                    response_text = response.text.strip().replace("```json", "").replace("```", "")
                    # Parse JSON and extract key_facts
                    parsed_data = json.loads(response_text)
                    key_facts = parsed_data.get("key_facts", [])
                    
                    if isinstance(key_facts, list):
                        logger.debug(f"Extracted {len(key_facts)} key facts from {page_markdown.page_url}")
                        return key_facts
                    else:
                        logger.warning(f"key_facts is not a list for {page_markdown.page_url}")
                        return []
                        
                except json.JSONDecodeError as e:
                    logger.error(f"Failed to parse key facts JSON from {page_markdown.page_url}: {e}")
                    logger.debug(f"Raw response: {response.text}")
                    return []
            
        except Exception as e:
            logger.error(f"Error extracting key facts from {page_markdown.page_url}: {e}")
        
        return []
    
    def _extract_enrichment_data(self, combined_content: str, org_name: str, all_key_facts: List[str]) -> dict:
        """
        Extract comprehensive enrichment data from combined content.
        
        Args:
            combined_content: Combined markdown content from all pages
            org_name: Organization name
            all_key_facts: All extracted key facts from individual pages
            
        Returns:
            Dictionary with enrichment data
        """
        try:
            # Select the most relevant key fact
            best_key_fact = all_key_facts[0] if all_key_facts else None
            
            prompt = f"""
            Analyze the following website content for the organization "{org_name}" and extract:

            1. Decision maker name (CEO, Director, Principal, Manager, etc.)
            2. Best contact information (email or phone number)
            3. Preferred contact channel (WhatsApp, Email, Messenger, Instagram, PhoneNo, Others)
            4. Select the most relevant key fact from the provided list for personalization

            Available Key Facts:
            {json.dumps(all_key_facts) if all_key_facts else "None available"}

            Website Content (first 6000 chars):
            {combined_content[:6000]}

            Respond in this exact JSON format:
            {{
                "decision_maker": "Name or null",
                "contact_info": "email@example.com or phone number or null",
                "contact_channel": "WhatsApp|Email|Messenger|Instagram|PhoneNo|Others or null",
                "key_fact": "Most relevant key fact from the list or null"
            }}
            """
            
            response = self.model.generate_content(prompt)
            
            if response and response.text:
                try:
                    # Extract JSON from markdown code blocks if present
                    response_text = response.text.strip()
                    
                    # Check if response is wrapped in markdown code blocks
                    if "```json" in response_text and "```" in response_text:
                        # Extract content between ```json and ```
                        start_marker = "```json"
                        end_marker = "```"
                        start_idx = response_text.find(start_marker) + len(start_marker)
                        end_idx = response_text.find(end_marker, start_idx)
                        
                        if start_idx > len(start_marker) - 1 and end_idx > start_idx:
                            json_content = response_text[start_idx:end_idx].strip()
                        else:
                            json_content = response_text
                    else:
                        json_content = response_text
                    
                    enrichment_data = json.loads(json_content)
                    logger.debug(f"Successfully extracted enrichment data for {org_name}")
                    return enrichment_data
                    
                except json.JSONDecodeError as e:
                    logger.error(f"Failed to parse enrichment JSON for {org_name}: {e}")
                    logger.debug(f"Raw response: {response.text}")
                    
        except Exception as e:
            logger.error(f"Error extracting enrichment data for {org_name}: {e}")
        
        # Return fallback data
        return {
            "decision_maker": None,
            "contact_info": None,
            "contact_channel": None,
            "key_fact": best_key_fact
        }
    
    def _create_fallback_enrichment(self, profile: ScrapedBusinessData) -> PartnerEnrichment:
        """
        Create a fallback enrichment when processing fails.
        
        Args:
            profile: Original ScrapedBusinessData profile
            
        Returns:
            PartnerEnrichment with basic information
        """
        return PartnerEnrichment(
            decision_maker=None,
            contact_info=profile.primary_contact,
            contact_channel="PhoneNo" if profile.primary_contact else None,
            key_fact=f"Organization type: {profile.org_name}" if profile.org_name else None,
            verified_url=profile.website_url if profile.website_url else "https://example.com",
            status="incomplete",
            all_contacts=None
        )



