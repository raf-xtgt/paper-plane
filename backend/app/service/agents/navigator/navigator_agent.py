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
from app.model.lead_gen_model import ScrapedBusinessData, PartnerEnrichment, PartnerContactDetails
from app.service.agents.navigator.navigator_content_extractor import NavigatorContentExtractor
from app.service.agents.navigator.navigator_llm_processor import LLMProcessor
from app.service.agents.navigator.navigator_crawler import NavigatorCrawler
import re
from pydantic import ValidationError
from app.model.lead_gen_model import PartnerContact

# Configure logging
logger = logging.getLogger("lead_gen_pipeline.navigator")

# Configure Gemini API
genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))


class NavigatorAgent:
    """
    Navigator Agent for intelligent web crawling and contact extraction.
    
    Uses Playwright to render dynamic content and extract
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
        self.content_extractor = NavigatorContentExtractor(self.model)
        self.llm_processor = LLMProcessor(model_name=self.model_name)
        self.data_validator = DataValidator()
        self.crawler = NavigatorCrawler()
        logger.info(f"Navigator Agent initialized with model: {self.model_name}")
    
    async def navigate_and_extract_batch(
        self, 
        scraped_data: List[ScrapedBusinessData]
    ) -> List[PartnerContact]:
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
        logger.info(f"Starting V2 batch processing of {len(valid_data)} partners with valid URLs")
        
        if not valid_data:
            logger.warning("No partners with valid website URLs found")
            return []
        
        # Create semaphore to limit concurrent processing
        semaphore = asyncio.Semaphore(self.concurrent_limit)
        
        async def process_with_semaphore(data: ScrapedBusinessData, index: int) -> List[PartnerContact]:
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
                    return [PartnerContact(
                            name="NA",
                            contact_info="NA",
                            url="NA"
                        )]

        # Process all partners concurrently with limit
        tasks = [
            process_with_semaphore(data, i) 
            for i, data in enumerate(valid_data)
        ]
        
        # Execute all tasks and collect results
        results = await asyncio.gather(*tasks, return_exceptions=True)
        # Flatten the list of lists into a single list of PartnerContact
        flat_results = [item for sublist in results if isinstance(sublist, set) for item in sublist]
        return flat_results
    
    async def navigate_and_extract(
        self, 
        website_url: str, 
        entity_name: str
    ) -> List[PartnerContact]:
        """
        Process single partner with V2 crawling and extraction.
        
        V2 Flow:
        1. Use web_crawler_v2.crawl_and_extract_contacts() for systematic contact extraction
        2. Process markdown with llm_processor.structure_contact_data() 
        3. Create PartnerEnrichment with all_contacts field from structured data
        
        Args:
            website_url: Website URL to crawl
            entity_name: Name of the entity/organization
            
        Returns:
            PartnerEnrichment object with V2 extracted data
        """
        start_time = asyncio.get_event_loop().time()
        logger.info(f"V2 processing {entity_name} at {website_url}")
        
        try:
            structured_contacts = await self.crawler.start(website_url)
            duration = asyncio.get_event_loop().time() - start_time
            logger.info(
                f"V2 processing completed for {entity_name} in {duration:.2f}s - "
                f"Total Contacts: {len(structured_contacts)}"
            )
            return structured_contacts

        except asyncio.TimeoutError:
            logger.error(f"V2 timeout processing {entity_name} after {self.timeout}s")
            return [PartnerContact(
                name="NA",
                contact_info="NA",
                url="NA"
            )]
        except Exception as e:
            logger.error(f"V2 error processing {entity_name}: {e}")
            return [PartnerContact(
                name="NA",
                contact_info="NA",
                url="NA"
            )]
    
    def _create_v2_partner_enrichment(
        self, 
        structured_contacts: List[Dict[str, Any]], 
        website_url: str, 
        entity_name: str
    ) -> PartnerEnrichment:
        """
        Create PartnerEnrichment with V2 comprehensive contact data.
        
        Args:
            structured_contacts: List of structured contact dictionaries
            website_url: Website URL
            entity_name: Entity name for logging
            
        Returns:
            PartnerEnrichment with all_contacts field populated
        """
        try:
            # Convert structured contacts to PartnerContactDetails objects
            all_contacts = []
            for contact_data in structured_contacts:
                try:
                    contact = PartnerContactDetails(**contact_data)
                    all_contacts.append(contact)
                except ValidationError as e:
                    logger.warning(f"Invalid contact data for {entity_name}: {e}")
                    continue
            
            # Determine primary contact for backward compatibility
            primary_decision_maker = None
            primary_contact_info = None
            primary_contact_channel = None
            
            if all_contacts:
                # Prioritize email contacts, then phone, then others
                email_contacts = [c for c in all_contacts if c.contact_channel == "Email"]
                phone_contacts = [c for c in all_contacts if c.contact_channel == "PhoneNo"]
                
                if email_contacts:
                    primary = email_contacts[0]
                elif phone_contacts:
                    primary = phone_contacts[0]
                else:
                    primary = all_contacts[0]
                
                primary_decision_maker = primary.decision_maker
                primary_contact_info = primary.contact_info
                primary_contact_channel = primary.contact_channel
            
            # Determine status based on contact availability
            status = "complete" if all_contacts else "incomplete"
            
            # Create PartnerEnrichment with V2 data
            enrichment = PartnerEnrichment(
                decision_maker=primary_decision_maker,
                contact_info=primary_contact_info,
                contact_channel=primary_contact_channel,
                key_fact=None,  # V2 doesn't extract key facts
                verified_url=website_url,
                status=status,
                all_contacts=all_contacts
            )
            
            logger.debug(f"Created V2 PartnerEnrichment for {entity_name}: {len(all_contacts)} contacts, status: {status}")
            return enrichment
            
        except Exception as e:
            logger.error(f"Error creating V2 PartnerEnrichment for {entity_name}: {e}")
            return PartnerEnrichment(
                verified_url=website_url,
                status="incomplete",
                all_contacts=[]
            )


class DataValidator:
    """
    Validation and normalization of extracted data.
    
    Implements Requirements 7.1, 7.2, 7.3, 7.4, 7.5:
    - Email format validation using regex patterns
    - Phone number normalization for consistent formatting
    - Contact channel classification and determination
    - PartnerEnrichment validation with Pydantic model validation
    - Status determination logic (complete vs incomplete)
    - Data normalization and cleanup for extracted information
    """
    
    def __init__(self):
        """Initialize DataValidator with validation patterns and configurations."""
        # Email validation pattern (Requirement 7.1)
        self.email_pattern = re.compile(
            r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        )
        
        # Phone number patterns for validation
        self.phone_patterns = [
            re.compile(r'^\+?[1-9]\d{1,14}$'),  # International format
            re.compile(r'^\d{10}$'),  # US 10-digit format
            re.compile(r'^\d{3}-\d{3}-\d{4}$'),  # US format with dashes
            re.compile(r'^\(\d{3}\)\s?\d{3}-\d{4}$'),  # US format with parentheses
        ]
        
        # Valid contact channels for validation
        self.valid_contact_channels = [
            "WhatsApp", "Email", "Messenger", "Instagram", "PhoneNo", "Other"
        ]
        
        # Generic email prefixes to avoid (prefer personal emails)
        self.generic_email_prefixes = [
            "info", "contact", "admin", "support", "noreply", "no-reply",
            "webmaster", "hello", "mail", "sales", "service", "help"
        ]
        
        logger.debug("DataValidator initialized with validation patterns")
    
    def validate_email(self, email: str) -> bool:
        """
        Validate email format using regex patterns.
        
        Implements Requirement 7.1: Email address validation using proper email format validation.
        
        Args:
            email: Email address to validate
            
        Returns:
            True if email format is valid, False otherwise
        """
        if not email or not isinstance(email, str):
            return False
        
        email = email.strip().lower()
        
        # Check basic format
        if not self.email_pattern.match(email):
            return False
        
        # Additional validation checks
        if email.count('@') != 1:
            return False
        
        local_part, domain_part = email.split('@')
        
        # Validate local part
        if not local_part or len(local_part) > 64:
            return False
        
        # Validate domain part
        if not domain_part or len(domain_part) > 255:
            return False
        
        # Check for valid domain structure
        if not re.match(r'^[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', domain_part):
            return False
        
        return True
    
    def normalize_phone(self, phone: str) -> str:
        """
        Normalize phone number format for consistent formatting.
        
        Implements Requirement 7.2: Phone number normalization to consistent format.
        
        Args:
            phone: Phone number to normalize
            
        Returns:
            Normalized phone number string
        """
        if not phone or not isinstance(phone, str):
            return phone
        
        # Remove all non-digit characters except +
        normalized = re.sub(r'[^\d+]', '', phone.strip())
        
        # Handle different phone number formats
        if normalized.startswith('+'):
            # International format - keep as is if valid
            if len(normalized) >= 8 and len(normalized) <= 16:
                return normalized
        elif len(normalized) == 10:
            # US 10-digit format - add +1 prefix
            return f"+1{normalized}"
        elif len(normalized) == 11 and normalized.startswith('1'):
            # US 11-digit format starting with 1 - add + prefix
            return f"+{normalized}"
        elif len(normalized) >= 7:
            # Other formats - keep as is if reasonable length
            return normalized
        
        # Return original if normalization doesn't produce valid result
        return phone
    
    def determine_contact_channel(self, contact_info: str) -> str:
        """
        Classify contact information into appropriate channel type.
        
        Implements Requirement 7.5: Contact channel classification for contact type classification.
        
        Args:
            contact_info: Contact information string to classify
            
        Returns:
            Contact channel type: WhatsApp|Email|Messenger|Instagram|PhoneNo|Other
        """
        if not contact_info or not isinstance(contact_info, str):
            return "Other"
        
        contact_lower = contact_info.lower().strip()
        
        # Email detection (highest priority for @ symbol)
        if '@' in contact_info and self.validate_email(contact_info):
            return "Email"
        
        # WhatsApp detection
        whatsapp_indicators = [
            'whatsapp', 'wa.me', 'wa.link', 'whatsapp:', 'whatsapp number',
            'whatsapp contact', 'wa:', 'whatsapp chat'
        ]
        if any(indicator in contact_lower for indicator in whatsapp_indicators):
            return "WhatsApp"
        
        # Instagram detection
        instagram_indicators = [
            'instagram', 'insta', '@', 'ig:', 'instagram.com',
            'instagram handle', 'instagram account'
        ]
        if any(indicator in contact_lower for indicator in instagram_indicators):
            # Additional check to avoid false positives with email addresses
            if '@' not in contact_info or 'instagram' in contact_lower:
                return "Instagram"
        
        # Messenger detection
        messenger_indicators = [
            'messenger', 'fb', 'facebook', 'm.me', 'facebook messenger',
            'fb messenger', 'facebook.com'
        ]
        if any(indicator in contact_lower for indicator in messenger_indicators):
            return "Messenger"
        
        # Phone number detection (check for digit patterns)
        if re.search(r'[\d+\-\(\)\s]{7,}', contact_info):
            # Additional validation to ensure it's actually a phone number
            digits_only = re.sub(r'[^\d]', '', contact_info)
            if len(digits_only) >= 7:
                return "PhoneNo"
        
        # Default to Other if no specific pattern matches
        return "Other"
    
    def validate_partner_enrichment(
        self, 
        data: Dict[str, Any], 
        verified_url: str
    ) -> PartnerEnrichment:
        """
        Create and validate PartnerEnrichment object with comprehensive validation.
        
        Implements Requirements 7.3, 7.4, 7.5:
        - Pydantic model validation for PartnerEnrichment
        - Status determination logic (complete vs incomplete)
        - Data normalization and cleanup for extracted information
        
        Args:
            data: Dictionary with extracted contact information
            verified_url: Verified website URL
            
        Returns:
            Validated PartnerEnrichment object
        """
        try:
            # Extract and validate individual fields
            decision_maker = self._validate_and_clean_decision_maker(data.get("decision_maker"))
            contact_info = self._validate_and_clean_contact_info(data.get("contact_info"))
            key_fact = self._validate_and_clean_key_fact(data.get("key_fact"))
            
            # Normalize contact info if it's a phone number
            if contact_info:
                # Determine contact channel first
                contact_channel = data.get("contact_channel")
                if not contact_channel or contact_channel not in self.valid_contact_channels:
                    contact_channel = self.determine_contact_channel(contact_info)
                
                # Normalize phone numbers
                if contact_channel == "PhoneNo":
                    contact_info = self.normalize_phone(contact_info)
                
                # Validate email addresses
                elif contact_channel == "Email":
                    if not self.validate_email(contact_info):
                        logger.warning(f"Invalid email format detected: {contact_info}")
                        contact_info = None
                        contact_channel = None
            else:
                contact_channel = None
            
            # Determine completion status (Requirement 7.3, 7.4)
            status = self._determine_completion_status(decision_maker, contact_info)
            
            # Create PartnerEnrichment object with Pydantic validation
            enrichment = PartnerEnrichment(
                decision_maker=decision_maker,
                contact_info=contact_info,
                contact_channel=contact_channel,
                key_fact=key_fact,
                verified_url=verified_url,
                status=status
            )
            
            logger.debug(f"PartnerEnrichment validation successful - Status: {status}")
            return enrichment
            
        except ValidationError as e:
            logger.error(f"Pydantic validation error creating PartnerEnrichment: {e}")
            # Return minimal valid object with incomplete status
            return PartnerEnrichment(
                verified_url=verified_url,
                status="incomplete"
            )
        except Exception as e:
            logger.error(f"Unexpected error creating PartnerEnrichment: {e}")
            return PartnerEnrichment(
                verified_url=verified_url,
                status="incomplete"
            )
    
    def _validate_and_clean_decision_maker(self, decision_maker: Any) -> Optional[str]:
        """
        Validate and clean decision maker information.
        
        Args:
            decision_maker: Raw decision maker data
            
        Returns:
            Cleaned decision maker string or None
        """
        if not decision_maker or not isinstance(decision_maker, str):
            return None
        
        cleaned = decision_maker.strip()
        
        # Check for null-like values
        null_values = ["null", "none", "n/a", "na", "not available", "not found", ""]
        if cleaned.lower() in null_values:
            return None
        
        # Ensure reasonable length (not too short or too long)
        if len(cleaned) < 2 or len(cleaned) > 200:
            return None
        
        # Basic format validation - should contain letters
        if not re.search(r'[a-zA-Z]', cleaned):
            return None
        
        return cleaned
    
    def _validate_and_clean_contact_info(self, contact_info: Any) -> Optional[str]:
        """
        Validate and clean contact information.
        
        Args:
            contact_info: Raw contact information data
            
        Returns:
            Cleaned contact info string or None
        """
        if not contact_info or not isinstance(contact_info, str):
            return None
        
        cleaned = contact_info.strip()
        
        # Check for null-like values
        null_values = ["null", "none", "n/a", "na", "not available", "not found", ""]
        if cleaned.lower() in null_values:
            return None
        
        # Ensure reasonable length
        if len(cleaned) < 3 or len(cleaned) > 100:
            return None
        
        # Check if it's a generic email (prefer personal emails)
        if '@' in cleaned:
            local_part = cleaned.split('@')[0].lower()
            if local_part in self.generic_email_prefixes:
                logger.debug(f"Skipping generic email: {cleaned}")
                return None
        
        return cleaned
    
    def _validate_and_clean_key_fact(self, key_fact: Any) -> Optional[str]:
        """
        Validate and clean key fact information.
        
        Args:
            key_fact: Raw key fact data
            
        Returns:
            Cleaned key fact string or None
        """
        if not key_fact or not isinstance(key_fact, str):
            return None
        
        cleaned = key_fact.strip()
        
        # Check for null-like values
        null_values = ["null", "none", "n/a", "na", "not available", "not found", ""]
        if cleaned.lower() in null_values:
            return None
        
        # Ensure reasonable length (key facts should be meaningful)
        if len(cleaned) < 10 or len(cleaned) > 500:
            return None
        
        # Should contain some meaningful content (letters and possibly numbers)
        if not re.search(r'[a-zA-Z]', cleaned):
            return None
        
        return cleaned
    
    def _determine_completion_status(
        self, 
        decision_maker: Optional[str], 
        contact_info: Optional[str]
    ) -> str:
        """
        Determine completion status based on available information.
        
        Implements Requirements 7.3, 7.4:
        - "complete": Both decision_maker and contact_info successfully extracted
        - "incomplete": Missing either decision_maker or contact_info (or both)
        
        Args:
            decision_maker: Validated decision maker information
            contact_info: Validated contact information
            
        Returns:
            Status string: "complete" or "incomplete"
        """
        # Complete status requires both decision maker and contact info
        if decision_maker and contact_info:
            return "complete"
        else:
            return "incomplete"