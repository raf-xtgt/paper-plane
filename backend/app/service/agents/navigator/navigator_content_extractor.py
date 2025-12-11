"""
Content Extractor helper module for Navigator Agent.

This module provides LLM-based information extraction from website content
using Gemini Flash for structured contact data extraction.
"""

import logging
import asyncio
import json
import re
from typing import Dict, Any, Optional
import time

# Configure logging
logger = logging.getLogger("lead_gen_pipeline.navigator.extractor")


class NavigatorContentExtractor:
    """
    LLM-based information extraction from website content.
    """
    
    def __init__(self, model):
        """Initialize ContentExtractor with Gemini model."""
        self.model = model
        logger.debug("NavigatorContentExtractor initialized")
    
    async def extract_contact_info(
        self, 
        markdown_content: str, 
        entity_name: str, 
        verified_url: str
    ) -> Dict[str, Any]:
        """
        Extract structured contact information using Gemini Flash.
        
        Args:
            markdown_content: Website content in markdown format
            entity_name: Name of the entity
            verified_url: Verified website URL
            
        Returns:
            Dictionary with extracted contact information
        """
        start_time = time.time()
        logger.debug(f"Starting contact extraction for {entity_name}")
        
        try:
            # Construct extraction prompt
            prompt = self._construct_extraction_prompt(
                entity_name, verified_url, markdown_content
            )
            
            # Execute LLM request with retry logic
            extracted_data = await self._execute_llm_extraction(prompt, entity_name)
            
            # Validate and normalize extracted data
            validated_data = self._validate_extraction(extracted_data)
            
            duration = time.time() - start_time
            logger.info(
                f"Contact extraction completed for {entity_name} in {duration:.2f}s - "
                f"Status: {validated_data.get('status', 'unknown')}"
            )
            
            return validated_data
            
        except Exception as e:
            duration = time.time() - start_time
            logger.error(f"Contact extraction failed for {entity_name} after {duration:.2f}s: {e}")
            return self._create_fallback_result(markdown_content)
    
    async def _execute_llm_extraction(
        self, 
        prompt: str, 
        entity_name: str, 
        max_retries: int = 3
    ) -> Dict[str, Any]:
        """
        Execute LLM extraction with exponential backoff retry logic.
        
        Args:
            prompt: Extraction prompt for the LLM
            entity_name: Entity name for logging
            max_retries: Maximum number of retry attempts
            
        Returns:
            Dictionary with extracted data
            
        Raises:
            Exception: If all retry attempts fail
        """
        for attempt in range(max_retries):
            try:
                # Execute LLM request in executor to avoid blocking
                response = await asyncio.get_event_loop().run_in_executor(
                    None, self.model.generate_content, prompt
                )
                
                # Parse and validate JSON response
                return self._parse_llm_response(response.text, entity_name)
                
            except json.JSONDecodeError as e:
                logger.warning(f"JSON parsing failed for {entity_name} (attempt {attempt + 1}): {e}")
                if attempt == max_retries - 1:
                    raise
                await asyncio.sleep(2 ** attempt)  # Exponential backoff
                
            except Exception as e:
                logger.warning(f"LLM request failed for {entity_name} (attempt {attempt + 1}): {e}")
                if attempt == max_retries - 1:
                    raise
                
                # Exponential backoff with jitter for rate limiting
                delay = (2 ** attempt) + (0.1 * attempt)
                await asyncio.sleep(delay)
        
        raise Exception(f"All {max_retries} extraction attempts failed for {entity_name}")
    
    def _parse_llm_response(self, response_text: str, entity_name: str) -> Dict[str, Any]:
        """
        Parse LLM response and extract JSON data.
        
        Args:
            response_text: Raw response text from LLM
            entity_name: Entity name for logging
            
        Returns:
            Dictionary with parsed data
            
        Raises:
            json.JSONDecodeError: If JSON parsing fails
        """
        if not response_text or not response_text.strip():
            raise json.JSONDecodeError("Empty response from LLM", "", 0)
        
        response_text = response_text.strip()
        
        # Try multiple JSON extraction strategies
        extraction_strategies = [
            # Strategy 1: Parse entire response as JSON
            lambda text: json.loads(text),
            
            # Strategy 2: Extract JSON block from response
            lambda text: json.loads(re.search(r'\{.*\}', text, re.DOTALL).group()),
            
            # Strategy 3: Extract JSON between code blocks
            lambda text: json.loads(re.search(r'```json\s*(\{.*?\})\s*```', text, re.DOTALL).group(1)),
            
            # Strategy 4: Extract first complete JSON object
            lambda text: json.loads(re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', text).group())
        ]
        
        for i, strategy in enumerate(extraction_strategies):
            try:
                extracted_data = strategy(response_text)
                if isinstance(extracted_data, dict):
                    logger.debug(f"JSON extracted using strategy {i + 1} for {entity_name}")
                    return extracted_data
            except (json.JSONDecodeError, AttributeError, TypeError):
                continue
        
        # If all strategies fail, log the response and raise error
        logger.error(f"Failed to parse JSON from LLM response for {entity_name}. Response: {response_text[:200]}...")
        raise json.JSONDecodeError(f"Could not extract valid JSON from response", response_text, 0)
    
    def _construct_extraction_prompt(
        self, 
        entity_name: str, 
        verified_url: str, 
        content: str
    ) -> str:
        """
        Build structured prompt for LLM extraction.
        
        Args:
            entity_name: Name of the entity
            verified_url: Verified website URL
            content: Website content in markdown format
            
        Returns:
            Structured prompt for contact information extraction
        """
        # Truncate content if too long to fit within token limits
        max_content_length = 8000
        if len(content) > max_content_length:
            # Try to keep the most relevant parts (beginning and end)
            half_length = max_content_length // 2
            content = content[:half_length] + "\n\n... [content truncated] ...\n\n" + content[-half_length:]
        
        return f"""You are an expert at extracting decision-maker contact information from business websites.

TASK: Extract contact details for decision-makers at {entity_name}

WEBSITE: {verified_url}

CONTENT:
{content}

EXTRACTION REQUIREMENTS:
Extract the following information and return ONLY a valid JSON object:

{{
    "decision_maker": "Full name and title of the primary decision-maker",
    "contact_info": "Direct contact information (email, phone, WhatsApp)",
    "contact_channel": "Exact channel type from: WhatsApp, Email, Messenger, Instagram, PhoneNo, Other",
    "key_fact": "One specific, interesting fact about the organization",
    "status": "complete or incomplete"
}}

DECISION-MAKER PRIORITIES (in order):
1. CEO, President, Managing Director
2. Principal, Director, Head
3. Manager, Coordinator, Administrator
4. Owner, Founder

CONTACT INFO PRIORITIES (in order):
1. Direct email addresses of decision-makers
2. Direct phone numbers with names
3. WhatsApp numbers
4. Social media handles with verification

CONTACT CHANNEL CLASSIFICATION:
- "Email": Valid email addresses (contains @ and domain)
- "WhatsApp": WhatsApp numbers, wa.me links, or WhatsApp mentions
- "PhoneNo": Phone numbers without WhatsApp indication
- "Instagram": Instagram handles or links
- "Messenger": Facebook Messenger or FB links
- "Other": Any other contact method

KEY FACT GUIDELINES:
- Awards, certifications, or recognition received
- Years of operation or establishment date
- Specializations or unique services
- Notable achievements or milestones
- Branch locations or expansion details

STATUS DETERMINATION:
- "complete": Both decision_maker AND contact_info are found
- "incomplete": Missing either decision_maker OR contact_info

CRITICAL RULES:
1. Return ONLY valid JSON - no explanations, no markdown, no additional text
2. Use null for missing fields, not empty strings
3. Ensure contact_channel matches the contact_info type exactly
4. Be specific with names and titles (e.g., "Dr. John Smith, Principal" not just "Principal")
5. Verify email formats and phone number validity

JSON Response:"""
    
    def _validate_extraction(self, extracted_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate and normalize extracted contact information.
        
        Args:
            extracted_data: Raw extracted data from LLM
            
        Returns:
            Validated and normalized data dictionary
        """
        # Initialize validated structure with defaults
        validated = {
            "decision_maker": None,
            "contact_info": None,
            "contact_channel": None,
            "key_fact": None,
            "status": "incomplete"
        }
        
        # Validate and clean decision_maker
        decision_maker = extracted_data.get("decision_maker")
        if decision_maker and isinstance(decision_maker, str):
            decision_maker = decision_maker.strip()
            if decision_maker and decision_maker.lower() not in ["null", "none", "n/a", ""]:
                validated["decision_maker"] = decision_maker
        
        # Validate and clean contact_info
        contact_info = extracted_data.get("contact_info")
        if contact_info and isinstance(contact_info, str):
            contact_info = contact_info.strip()
            if contact_info and contact_info.lower() not in ["null", "none", "n/a", ""]:
                validated["contact_info"] = contact_info
        
        # Validate contact_channel
        contact_channel = extracted_data.get("contact_channel")
        valid_channels = ["WhatsApp", "Email", "Messenger", "Instagram", "PhoneNo", "Other"]
        if contact_channel in valid_channels:
            validated["contact_channel"] = contact_channel
        elif validated["contact_info"]:
            # Auto-determine channel if not provided or invalid
            validated["contact_channel"] = self._determine_contact_channel(validated["contact_info"])
        
        # Validate and clean key_fact
        key_fact = extracted_data.get("key_fact")
        if key_fact and isinstance(key_fact, str):
            key_fact = key_fact.strip()
            if key_fact and key_fact.lower() not in ["null", "none", "n/a", ""]:
                validated["key_fact"] = key_fact
        
        # Determine final status based on completeness
        if validated["decision_maker"] and validated["contact_info"]:
            validated["status"] = "complete"
        else:
            validated["status"] = "incomplete"
        
        return validated
    
    def _determine_contact_channel(self, contact_info: str) -> str:
        """
        Determine contact channel based on contact information format.
        
        Args:
            contact_info: Contact information string
            
        Returns:
            Contact channel classification
        """
        if not contact_info:
            return "Other"
        
        contact_lower = contact_info.lower()
        
        # Email detection
        if '@' in contact_info and re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', contact_info.strip()):
            return "Email"
        
        # WhatsApp detection
        if any(keyword in contact_lower for keyword in ['whatsapp', 'wa.me', 'wa.link', 'whatsapp:']):
            return "WhatsApp"
        
        # Social media detection
        if any(keyword in contact_lower for keyword in ['instagram', 'insta', '@', 'ig:']):
            return "Instagram"
        
        if any(keyword in contact_lower for keyword in ['messenger', 'fb', 'facebook', 'm.me']):
            return "Messenger"
        
        # Phone number detection
        if re.search(r'[\d+\-\(\)\s]{7,}', contact_info):
            return "PhoneNo"
        
        return "Other"
    
    def _create_fallback_result(self, content: str) -> Dict[str, Any]:
        """
        Create fallback result when LLM extraction fails completely.
        
        Args:
            content: Website content for regex-based extraction
            
        Returns:
            Fallback extraction result with incomplete status
        """
        logger.info("Attempting fallback regex-based extraction")
        
        # Enhanced regex patterns for better extraction
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        phone_pattern = r'[\+]?[1-9][\d\s\-\(\)]{7,15}'
        
        # Find all emails and phones
        emails = re.findall(email_pattern, content, re.IGNORECASE)
        phones = re.findall(phone_pattern, content)
        
        # Filter out common non-personal emails
        filtered_emails = [
            email for email in emails 
            if not any(generic in email.lower() for generic in [
                'info@', 'contact@', 'admin@', 'support@', 'noreply@', 
                'no-reply@', 'webmaster@', 'hello@', 'mail@'
            ])
        ]
        
        # Use filtered emails first, then any email, then phones
        contact_info = None
        contact_channel = None
        
        if filtered_emails:
            contact_info = filtered_emails[0]
            contact_channel = "Email"
        elif emails:
            contact_info = emails[0]
            contact_channel = "Email"
        elif phones:
            # Clean up phone number
            phone = re.sub(r'[^\d+]', '', phones[0])
            if len(phone) >= 7:  # Minimum valid phone length
                contact_info = phone
                contact_channel = "PhoneNo"
        
        return {
            "decision_maker": None,
            "contact_info": contact_info,
            "contact_channel": contact_channel,
            "key_fact": None,
            "status": "incomplete"
        }