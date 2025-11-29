"""
Researcher Agent for partner enrichment through web scraping.

This agent visits partner websites discovered by Scout Agent, navigates to
relevant pages (Contact, Staff, About Us, Leadership), and extracts decision-maker
information, contact details, and key facts for personalization.
"""

import os
import logging
import requests
from typing import Optional, List
from bs4 import BeautifulSoup
import google.generativeai as genai
from app.model.lead_gen_model import PartnerDiscovery, PartnerEnrichment
import json
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
    
    def _get_system_prompt(self) -> str:
        """
        Generate system prompt for extracting partner information.
        
        Returns:
            System prompt string for the agent
        """
        return """You are an Intelligence Researcher AI agent. Your task is to extract specific information from website content.

        Extract the following information:
        1. Decision-maker name: Look for titles like Principal, Head Doctor, Director, CEO, Founder, Head of School, Medical Director
        2. Contact information: Email address, phone number, or WhatsApp number (prefer direct contact, not general info@)
        3. Key fact: One interesting fact for personalization such as:
           - Recent awards or recognitions
           - New branches or expansion
           - Institutional motto or mission
           - Years of establishment
           - Notable achievements or milestones
           - Unique programs or services

        Return ONLY a JSON object with this exact structure:
        {
            "decision_maker": "Name of decision maker or null",
            "contact_info": "Email/phone/WhatsApp or null",
            "key_fact": "One interesting fact or null"
        }

        Rules:
        - Return null for fields you cannot find
        - Be precise - only extract information you are confident about
        - For decision_maker, include their title (e.g., "Dr. John Smith, Medical Director")
        - For contact_info, prefer direct contact over general info
        - For key_fact, choose the most relevant for business outreach
        - Return ONLY the JSON object, no additional text"""
    
    def _fetch_page_content(self, url: str) -> Optional[str]:
        """
        Fetch HTML content from a URL with timeout.
        
        Args:
            url: Website URL to fetch
            
        Returns:
            HTML content as string, or None on failure
        """
        try:
            logger.debug(f"Fetching URL: {url}")
            response = requests.get(
                url, 
                headers=self.headers, 
                timeout=self.timeout,
                allow_redirects=True
            )
            response.raise_for_status()
            
            logger.debug(f"Successfully fetched {len(response.content)} bytes from {url}")
            return response.text
            
        except requests.Timeout:
            logger.warning(f"Timeout fetching URL: {url} (timeout: {self.timeout}s)")
            return None
        except requests.RequestException as e:
            logger.warning(f"Failed to fetch URL: {url}, error: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error fetching URL: {url}, error: {str(e)}", exc_info=True)
            return None
    
    def _find_relevant_pages(self, base_url: str, html_content: str) -> List[str]:
        """
        Find links to Contact, Staff, About Us, and Leadership pages.
        
        Args:
            base_url: Base website URL
            html_content: HTML content of the main page
            
        Returns:
            List of relevant page URLs to scrape
        """
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            relevant_urls = [base_url]  # Always include main page
            
            # Keywords to look for in links
            keywords = [
                'contact', 'about', 'staff', 'team', 'leadership', 
                'faculty', 'doctors', 'management', 'about-us', 
                'our-team', 'meet-the-team', 'administration'
            ]
            
            # Find all links
            links = soup.find_all('a', href=True)
            
            for link in links:
                href = link['href']
                link_text = link.get_text().lower().strip()
                
                # Check if link text or href contains relevant keywords
                if any(keyword in link_text or keyword in href.lower() for keyword in keywords):
                    # Convert relative URLs to absolute
                    if href.startswith('/'):
                        full_url = base_url.rstrip('/') + href
                    elif href.startswith('http'):
                        full_url = href
                    else:
                        full_url = base_url.rstrip('/') + '/' + href
                    
                    if full_url not in relevant_urls:
                        relevant_urls.append(full_url)
                        logger.debug(f"Found relevant page: {full_url}")
            
            logger.info(f"Found {len(relevant_urls)} relevant pages for {base_url}")
            return relevant_urls[:5]  # Limit to 5 pages to stay within timeout
            
        except Exception as e:
            logger.warning(f"Failed to parse links from {base_url}, error: {str(e)}")
            return [base_url]
    
    def _extract_text_content(self, html_content: str) -> str:
        """
        Extract clean text content from HTML.
        
        Args:
            html_content: Raw HTML content
            
        Returns:
            Cleaned text content
        """
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Remove script and style elements
            for script in soup(["script", "style", "nav", "footer", "header"]):
                script.decompose()
            
            # Get text
            text = soup.get_text(separator='\n')
            
            # Clean up whitespace
            lines = (line.strip() for line in text.splitlines())
            chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
            text = '\n'.join(chunk for chunk in chunks if chunk)
            
            return text
            
        except Exception as e:
            logger.warning(f"Failed to extract text content, error: {str(e)}")
            return ""
    
    def _extract_info_with_llm(self, text_content: str, entity_name: str) -> dict:
        """
        Use Gemini to extract structured information from text content.
        
        Args:
            text_content: Cleaned text content from website
            entity_name: Name of the partner entity
            
        Returns:
            Dictionary with decision_maker, contact_info, and key_fact
        """
        try:
            system_prompt = self._get_system_prompt()
            
            # Truncate content if too long (keep first 4000 chars)
            if len(text_content) > 4000:
                text_content = text_content[:4000] + "\n... [content truncated]"
            
            user_prompt = f"""Entity Name: {entity_name}

Website Content:
{text_content}

Extract the decision-maker name, contact information, and one key fact from the above content."""
            
            logger.debug(f"Sending {len(text_content)} chars to Gemini for extraction")
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
            
            extracted_data = json.loads(response_text)
            
            logger.debug(f"Successfully extracted data: {extracted_data}")
            return extracted_data
            
        except json.JSONDecodeError as e:
            logger.error(
                f"Failed to parse LLM JSON response for {entity_name}, error: {str(e)}",
                exc_info=True
            )
            logger.debug(f"Raw LLM response: {response.text if 'response' in locals() else 'N/A'}")
            return {"decision_maker": None, "contact_info": None, "key_fact": None}
        except Exception as e:
            logger.error(
                f"LLM extraction failed for {entity_name}, error: {str(e)}",
                exc_info=True
            )
            return {"decision_maker": None, "contact_info": None, "key_fact": None}
    
    def enrich_partner(self, partner: PartnerDiscovery) -> PartnerEnrichment:
        """
        Enrich a single partner with contact details and key facts.
        
        Args:
            partner: PartnerDiscovery object from Scout Agent
            
        Returns:
            PartnerEnrichment object with status (complete/incomplete)
        """
        logger.info(f"Starting enrichment for: {partner.entity_name} ({partner.website_url})")
        
        try:
            # Fetch main page content
            main_content = self._fetch_page_content(str(partner.website_url))
            
            if not main_content:
                logger.warning(
                    f"Failed to fetch main page for {partner.entity_name} - "
                    f"URL: {partner.website_url} - Marking as incomplete for manual review"
                )
                return PartnerEnrichment(
                    decision_maker=None,
                    contact_info=None,
                    key_fact=None,
                    verified_url=partner.website_url,
                    status="incomplete"
                )
            
            # Find relevant pages
            relevant_pages = self._find_relevant_pages(str(partner.website_url), main_content)
            
            # Collect text content from all relevant pages
            all_text_content = []
            
            for page_url in relevant_pages:
                if page_url == str(partner.website_url):
                    # Already have main page content
                    text = self._extract_text_content(main_content)
                else:
                    # Fetch additional page
                    page_content = self._fetch_page_content(page_url)
                    if page_content:
                        text = self._extract_text_content(page_content)
                    else:
                        continue
                
                if text:
                    all_text_content.append(text)
            
            if not all_text_content:
                logger.warning(
                    f"No text content extracted for {partner.entity_name} - "
                    f"URL: {partner.website_url} - Marking as incomplete for manual review"
                )
                return PartnerEnrichment(
                    decision_maker=None,
                    contact_info=None,
                    key_fact=None,
                    verified_url=partner.website_url,
                    status="incomplete"
                )
            
            # Combine all text content
            combined_text = "\n\n=== PAGE BREAK ===\n\n".join(all_text_content)
            
            # Extract information using LLM
            extracted_info = self._extract_info_with_llm(combined_text, partner.entity_name)
            
            # Determine status
            has_decision_maker = extracted_info.get("decision_maker") is not None
            has_contact = extracted_info.get("contact_info") is not None
            
            status = "complete" if (has_decision_maker and has_contact) else "incomplete"
            
            enrichment = PartnerEnrichment(
                decision_maker=extracted_info.get("decision_maker"),
                contact_info=extracted_info.get("contact_info"),
                key_fact=extracted_info.get("key_fact"),
                verified_url=partner.website_url,
                status=status
            )
            
            if status == "incomplete":
                logger.warning(
                    f"Enrichment incomplete for {partner.entity_name} - "
                    f"URL: {partner.website_url} - "
                    f"decision_maker: {bool(enrichment.decision_maker)}, "
                    f"contact_info: {bool(enrichment.contact_info)}, "
                    f"key_fact: {bool(enrichment.key_fact)} - "
                    f"Requires manual review"
                )
            else:
                logger.info(
                    f"Enrichment {status} for {partner.entity_name} - "
                    f"decision_maker: {bool(enrichment.decision_maker)}, "
                    f"contact_info: {bool(enrichment.contact_info)}, "
                    f"key_fact: {bool(enrichment.key_fact)}"
                )
            
            return enrichment
            
        except Exception as e:
            logger.error(
                f"Partner enrichment failed for {partner.entity_name} - "
                f"URL: {partner.website_url} - "
                f"Error: {str(e)} - "
                f"Marking as incomplete for manual review",
                exc_info=True
            )
            return PartnerEnrichment(
                decision_maker=None,
                contact_info=None,
                key_fact=None,
                verified_url=partner.website_url,
                status="incomplete"
            )
    
    def enrich_partners(self, partners: List[PartnerDiscovery]) -> List[PartnerEnrichment]:
        """
        Enrich multiple partners with contact details and key facts.
        
        Skips failed websites and continues processing remaining partners.
        All failures are logged for manual review.
        
        Args:
            partners: List of PartnerDiscovery objects from Scout Agent
            
        Returns:
            List of PartnerEnrichment objects
        """
        logger.info(f"Starting enrichment for {len(partners)} partners")
        
        enriched_partners = []
        failed_urls = []
        
        for partner in partners:
            try:
                enrichment = self.enrich_partner(partner)
                enriched_partners.append(enrichment)
                
                # Track failed URLs for summary logging
                if enrichment.status == "incomplete":
                    failed_urls.append(str(partner.website_url))
                    
            except Exception as e:
                # Catch any unexpected errors and continue to next partner
                logger.error(
                    f"Unexpected error enriching {partner.entity_name} - "
                    f"URL: {partner.website_url} - "
                    f"Error: {str(e)} - "
                    f"Skipping and continuing to next partner",
                    exc_info=True
                )
                failed_urls.append(str(partner.website_url))
                
                # Still add incomplete enrichment to results
                enriched_partners.append(PartnerEnrichment(
                    decision_maker=None,
                    contact_info=None,
                    key_fact=None,
                    verified_url=partner.website_url,
                    status="incomplete"
                ))
        
        # Log summary
        complete_count = sum(1 for p in enriched_partners if p.status == "complete")
        incomplete_count = len(enriched_partners) - complete_count
        
        logger.info(
            f"Enrichment complete: {complete_count} complete, {incomplete_count} incomplete "
            f"out of {len(partners)} total partners"
        )
        
        # Log failed URLs for manual review
        if failed_urls:
            logger.warning(
                f"Failed URLs requiring manual review ({len(failed_urls)}): "
                f"{', '.join(failed_urls)}"
            )
        
        return enriched_partners
