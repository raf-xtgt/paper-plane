"""
Scout Agent for partner discovery using DuckDuckGo search.

This agent searches for potential channel partners based on market vertical
and city, returning 3-10 structured partner discoveries with entity names,
website URLs, and entity types.
"""

import os
import logging
import asyncio
from typing import List
import google.generativeai as genai
from app.model.lead_gen_model import PartnerDiscovery, ScrapedBusinessData
from app.service.agents.scout.scout_agent_helper import scrape_google_maps
import json

# Configure logging
logger = logging.getLogger("lead_gen_pipeline.scout")

# Configure Gemini API
genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))


class ScoutAgent:
    """
    Scout Agent for discovering potential channel partners.
    
    Uses DuckDuckGo search to find partners based on market vertical
    and city, then uses Gemini to extract structured data from results.
    """
    
    def __init__(self):
        """Initialize Scout Agent with Gemini Flash model."""
        self.model_name = os.getenv("ADK_MODEL_FLASH", "gemini-2.0-flash-exp")
        self.temperature = 0.3
        self.max_partners = int(os.getenv("MAX_PARTNERS_PER_RUN", "10"))
        
        # Initialize Gemini model
        self.model = genai.GenerativeModel(
            model_name=self.model_name,
            generation_config={
                "temperature": self.temperature,
                "top_p": 0.95,
                "top_k": 40,
                "max_output_tokens": 2048,
            }
        )
        
        logger.info(f"Scout Agent initialized with model: {self.model_name}")
    
    def _get_system_prompt(self, market: str, city: str, district: str) -> str:
        """
        Generate system prompt based on market vertical.
        
        Args:
            market: Market vertical (Student Recruitment or Medical Tourism)
            city: Target city name
            district: Target district name
            
        Returns:
            System prompt string for the agent
        """
        base_prompt = f"""You are a Digital Scout AI agent. Your goal is to find "Channel Partners" in {city} who hold influence over our target audience."""
        
        if market == "Student Recruitment":
            base_prompt += """For "Student Recruitment" market, look for:
            - International High Schools (IB/IGCSE curriculum)
            - IELTS/TOEFL Coaching Centers
            - A-Level Tuition Centers
            - International education consultancies
            - Study abroad counseling centers

            """
        elif market == "Medical Tourism":
            base_prompt += """For "Medical Tourism" market, look for:
            - Diagnostic Centers (MRI/CT scan labs)
            - Specialist Clinics (Orthopedic, Cardiac, Dental)
            - Expat Community Centers
            - Medical referral agencies
            - Health tourism facilitators

            """
        
        base_prompt += """Your task:
        1. Analyze the Google Maps business data provided
        2. Extract entity name, website URL, and entity type from the scraped data
        3. Return ONLY valid results with accessible websites
        4. Format as JSON array with structure: [{"entity_name": str, "website_url": str, "type": str}]
        5. Limit results to 3-10 partners
        6. Prioritize established organizations with clear online presence

        Return ONLY the JSON array, no additional text or explanation."""
                
        return base_prompt
    
    def _generate_search_queries(self, city: str, market: str, district: str) -> List[str]:
        """
        Generate search queries based on city and market.
        
        Args:
            city: Target city name
            market: Market vertical
            district: Target district name
            
        Returns:
            List of search query strings
        """
        queries = []
        
        if market == "Student Recruitment":
            queries = [
                f"international high schools {city}, {district}",
                f"IELTS TOEFL coaching centers {city}, {district}",
                f"A-Level tuition centers {city}, {district}",
                f"study abroad consultants {city}, {district}",
            ]
        elif market == "Medical Tourism":
            queries = [
                f"diagnostic centers {city}, {district}",
                f"specialist clinics {city}, {district}",
                # f"medical tourism {city}, {district}",
                # f"expat health services {city}, {district}",
            ]
        
        return queries
    
    async def _scrape_google_maps(self, query: str, max_results: int = 10) -> List[dict]:
        """
        Perform Google Maps scraping and return business data.
        
        Args:
            query: Search query string
            max_results: Maximum number of results to return
            
        Returns:
            List of scraped business data dictionaries
        """
        try:
            logger.debug(f"Scraping Google Maps: {query}")
            
            # Use the helper function to scrape Google Maps
            results = await scrape_google_maps(query, headless=True, limit=max_results)
            
            logger.debug(f"Found {len(results)} results for query: {query}")
            return results
            
        except Exception as e:
            logger.error(
                f"Google Maps scraping failed - query: '{query}', error: {str(e)}",
                exc_info=True
            )
            return []
    
    def _extract_partners_with_llm(
        self, 
        scraped_data: List, 
        city: str, 
        market: str,
        district: str
    ) -> List[PartnerDiscovery]:
        """
        Use Gemini to extract structured partner data from Google Maps scraped data.
        
        Args:
            scraped_data: Raw scraped business data from Google Maps
            city: Target city name
            market: Market vertical
            district: Target district name
            
        Returns:
            List of PartnerDiscovery objects
        """
        if not scraped_data:
            logger.warning(f"No scraped data to process - city: {city}, market: {market}")
            return []
        
        try:
            # Format scraped data for LLM
            formatted_results = "\n\n".join([
                f"Business Name: {data.org_name or 'N/A'}\n"
                f"Website URL: {data.website_url or 'N/A'}\n"
                f"Address: {data.address or 'N/A'}\n"
                f"Phone: {data.primary_contact or 'N/A'}\n"
                f"Review Score: {data.review_score or 'N/A'}\n"
                f"Total Reviews: {data.total_reviews or 'N/A'}"
                for data in scraped_data[:20]  # Limit to top 20 results
            ])
            
            system_prompt = self._get_system_prompt(market, city, district)
            
            user_prompt = f"""Here are the Google Maps business data for {market} partners in {city}:

            {formatted_results}

            Extract 3-10 potential partners and return as JSON array."""
            
            # Generate response
            logger.debug(f"Sending {len(scraped_data)} scraped businesses to Gemini for extraction")
            response = self.model.generate_content([system_prompt, user_prompt])
            
            # Parse JSON response
            response_text = response.text.strip()
            
            # Remove markdown code blocks if present
            if response_text.startswith("```json"):
                response_text = response_text[7:]
            if response_text.startswith("```"):
                response_text = response_text[3:]
            if response_text.endswith("```"):
                response_text = response_text[:-3]
            
            response_text = response_text.strip()
            
            partners_data = json.loads(response_text)
            
            # Convert to PartnerDiscovery objects
            partners = []
            for data in partners_data[:self.max_partners]:
                try:
                    partner = PartnerDiscovery(
                        entity_name=data["entity_name"],
                        website_url=data["website_url"],
                        type=data["type"]
                    )
                    partners.append(partner)
                except Exception as e:
                    logger.warning(
                        f"Failed to parse partner data - city: {city}, market: {market}, "
                        f"data: {data}, error: {str(e)}"
                    )
                    continue
            
            logger.info(f"Extracted {len(partners)} partners from scraped data")
            return partners
            
        except json.JSONDecodeError as e:
            logger.error(
                f"Failed to parse LLM JSON response - city: {city}, market: {market}, "
                f"error: {str(e)}",
                exc_info=True
            )
            logger.debug(f"Raw LLM response: {response.text if 'response' in locals() else 'N/A'}")
            return []
        except Exception as e:
            logger.error(
                f"LLM extraction failed - city: {city}, market: {market}, error: {str(e)}",
                exc_info=True
            )
            return []
    
    async def discover_partners(self, city: str, market: str, district: str) -> List[ScrapedBusinessData]:
        """
        Main method to discover partners for a given city and market using Google Maps scraping.
        
        Args:
            city: Target city name
            market: Market vertical (Student Recruitment or Medical Tourism)
            district: Target district name
            
        Returns:
            List of 3-10 ScrapedBusinessData objects, or empty list on failure
        """
        logger.info(f"Starting partner discovery: city={city}, market={market}, district={district}")
        
        try:
            # Generate search queries
            queries = self._generate_search_queries(city, market, district)
            logger.info(f"Generated {len(queries)} search queries: {queries}")
            
            # Collect scraped data from all queries
            all_scraped_data = []
            for query in queries:
                logger.info(f"search query: {query} ")
                scraped_data = await self._scrape_google_maps(query, max_results=2)
                all_scraped_data.extend(scraped_data)
            
            if not all_scraped_data:
                logger.warning(
                    f"No scraped data found - city: {city}, market: {market}, district: {district}, "
                    f"queries: {queries}"
                )
                return []
            
            logger.info(f"Collected {len(all_scraped_data)} total scraped businesses")
        
            return all_scraped_data
            
        except Exception as e:
            logger.error(
                f"Partner discovery failed - city: {city}, market: {market}, district: {district}, "
                f"error: {str(e)}",
                exc_info=True
            )
            return []
