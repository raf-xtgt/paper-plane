"""
Navigator LLM Processor for contact information extraction and structuring.

This module contains the LLM processing components for the Navigator Agent,
including the PartnerContactDetails schema and LLMProcessor class for
Gemini Flash integration.
"""

import os
import logging
import asyncio
import json
from typing import List, Optional, Dict, Any
import google.generativeai as genai
from pydantic import BaseModel, Field, ValidationError
import re

# Configure logging
logger = logging.getLogger("lead_gen_pipeline.navigator")

# Configure Gemini API
genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))


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
    contact_channel: Optional[str] = Field(None, description="Contact channel type")


class LLMProcessor:
    """
    Gemini Flash integration for structuring extracted contact information.
    
    Implements Requirements 5.1, 5.2, 5.3, 5.4, 5.5:
    - Initialize Gemini Flash model with consistent temperature settings
    - Process markdown content and return structured contact data
    - Handle LLM parsing errors gracefully and return partial results
    - Build structured extraction prompts for contact extraction
    - Parse LLM JSON response and validate against PartnerContactDetails schema
    """
    
    def __init__(self, model_name: str = "gemini-2.0-flash-exp"):
        """
        Initialize LLMProcessor with Gemini Flash model setup.
        
        Implements Requirement 5.1: Initialize Gemini Flash model with consistent 
        temperature settings for reliable extraction.
        
        Args:
            model_name: Gemini model name to use for processing
        """
        self.model_name = model_name
        self.temperature = float(os.getenv("NAVIGATOR_V2_TEMPERATURE", "0.1"))
        self.max_tokens = int(os.getenv("NAVIGATOR_V2_MAX_TOKENS", "2048"))
        self.max_retries = 3
        self.retry_delay = 1.0
        
        # Initialize Gemini Flash with consistent settings for reliable extraction
        self.model = genai.GenerativeModel(
            model_name=self.model_name,
            generation_config={
                "temperature": self.temperature,
                "top_p": 0.95,
                "top_k": 40,
                "max_output_tokens": self.max_tokens,
                "response_mime_type": "application/json"
            }
        )
        
        logger.info(f"LLMProcessor initialized with model: {self.model_name}, temperature: {self.temperature}")
    
    async def structure_contact_data(
        self, 
        markdown_content: str, 
        entity_name: str
    ) -> List[Dict[str, Any]]:
        """
        Process markdown content and return structured contact data.
        
        Implements Requirements 5.2, 5.3, 5.4:
        - Create structure_contact_data method to process markdown content with LLM
        - Build structured extraction prompt that maps markdown sections to PartnerContactDetails schema
        - Parse LLM JSON response and validate against PartnerContactDetails data class
        - Handle LLM parsing errors gracefully and return partial results when possible
        
        Args:
            markdown_content: Combined markdown with all extracted contact information
            entity_name: Name of the entity/organization
            
        Returns:
            List of dictionaries matching PartnerContactDetails schema
        """
        if not markdown_content or not markdown_content.strip():
            logger.warning(f"Empty markdown content for {entity_name}")
            return []
        
        # Build structured extraction prompt
        prompt = self._build_extraction_prompt(entity_name, markdown_content)
        
        # Process with retry logic for rate limiting and API errors
        for attempt in range(self.max_retries):
            try:
                logger.debug(f"LLM processing attempt {attempt + 1} for {entity_name}")
                
                # Generate response using Gemini Flash
                response = await asyncio.get_event_loop().run_in_executor(
                    None, self.model.generate_content, prompt
                )
                
                if not response or not response.text:
                    logger.warning(f"Empty response from LLM for {entity_name}")
                    continue
                
                # Parse LLM JSON response and validate
                structured_data = self._parse_llm_response(response.text, entity_name)
                
                if structured_data:
                    logger.info(f"Successfully structured {len(structured_data)} contacts for {entity_name}")
                    return structured_data
                else:
                    logger.warning(f"No valid contacts extracted from LLM response for {entity_name}")
                
            except Exception as e:
                logger.error(f"LLM processing error for {entity_name} (attempt {attempt + 1}): {e}")
                
                # Wait before retry (exponential backoff with jitter)
                if attempt < self.max_retries - 1:
                    delay = self.retry_delay * (2 ** attempt) + (0.1 * attempt)
                    await asyncio.sleep(delay)
        
        # Return empty list if all attempts failed
        logger.error(f"Failed to process contact data for {entity_name} after {self.max_retries} attempts")
        return []
    
    def _build_extraction_prompt(self, entity_name: str, content: str) -> str:
        """
        Build structured prompt for contact information extraction.
        
        Implements Requirement 5.2: Build structured extraction prompt that maps 
        markdown sections to PartnerContactDetails schema.
        
        Args:
            entity_name: Name of the entity/organization
            content: Markdown content to process
            
        Returns:
            Structured prompt string for LLM processing
        """
        prompt = f"""
You are extracting contact information from a business website for {entity_name}.

Below is markdown content containing contact information. Extract ALL contact details and structure them according to the schema.

For each contact found, create an entry with:
- decision_maker: Name of person (if associated with contact)
- contact_info: The actual contact (email, phone, social handle)
- contact_channel: One of ["WhatsApp", "Email", "Messenger", "Instagram", "PhoneNo", "Others"]

IMPORTANT: 
- Extract ALL contact information found, do not filter for relevance
- If no name is associated, set decision_maker to null
- Classify contact_channel based on the type of contact information
- Return valid JSON array format

Content:
{content}

Return a JSON array of contact objects following this exact schema:
[
  {{
    "decision_maker": "John Smith" or null,
    "contact_info": "john@example.com",
    "contact_channel": "Email"
  }}
]
"""
        return prompt.strip()
    
    def _parse_llm_response(self, response: str, entity_name: str) -> List[Dict[str, Any]]:
        """
        Parse LLM JSON response and validate against PartnerContactDetails schema.
        
        Implements Requirements 5.3, 5.4:
        - Create _parse_llm_response method to handle JSON parsing and validation
        - Add fallback mechanisms for malformed JSON responses
        - Ensure consistent mapping to PartnerContactDetails schema
        
        Args:
            response: Raw LLM response text
            entity_name: Entity name for logging context
            
        Returns:
            List of validated contact dictionaries
        """
        if not response or not response.strip():
            logger.warning(f"Empty LLM response for {entity_name}")
            return []
        
        try:
            # Clean response text (remove markdown formatting if present)
            cleaned_response = response.strip()
            if cleaned_response.startswith('```json'):
                cleaned_response = cleaned_response[7:]
            if cleaned_response.endswith('```'):
                cleaned_response = cleaned_response[:-3]
            cleaned_response = cleaned_response.strip()
            
            # Parse JSON response
            parsed_data = json.loads(cleaned_response)
            
            # Ensure it's a list
            if not isinstance(parsed_data, list):
                logger.warning(f"LLM response is not a list for {entity_name}: {type(parsed_data)}")
                return []
            
            # Validate each contact entry
            validated_contacts = []
            for i, contact_data in enumerate(parsed_data):
                try:
                    # Validate against PartnerContactDetails schema
                    contact = PartnerContactDetails(**contact_data)
                    
                    # Additional validation - ensure we have meaningful contact info
                    if contact.contact_info and contact.contact_info.strip():
                        # Normalize contact channel if needed
                        if not contact.contact_channel:
                            contact.contact_channel = self._determine_contact_channel(contact.contact_info)
                        
                        validated_contacts.append(contact.dict())
                        logger.debug(f"Validated contact {i+1} for {entity_name}: {contact.contact_channel}")
                    else:
                        logger.debug(f"Skipping empty contact {i+1} for {entity_name}")
                        
                except ValidationError as e:
                    logger.warning(f"Contact validation error for {entity_name} contact {i+1}: {e}")
                    continue
                except Exception as e:
                    logger.error(f"Unexpected error validating contact {i+1} for {entity_name}: {e}")
                    continue
            
            return validated_contacts
            
        except json.JSONDecodeError as e:
            logger.error(f"JSON parsing error for {entity_name}: {e}")
            # Attempt fallback regex-based extraction
            return self._fallback_contact_extraction(response, entity_name)
        except Exception as e:
            logger.error(f"Unexpected error parsing LLM response for {entity_name}: {e}")
            return []
    
    def _determine_contact_channel(self, contact_info: str) -> str:
        """
        Determine contact channel based on contact information format.
        
        Args:
            contact_info: Contact information string
            
        Returns:
            Contact channel type
        """
        if not contact_info:
            return "Others"
        
        contact_lower = contact_info.lower().strip()
        
        # Email detection
        if '@' in contact_info and '.' in contact_info:
            return "Email"
        
        # WhatsApp detection
        whatsapp_indicators = ['whatsapp', 'wa.me', 'wa.link', 'whatsapp:']
        if any(indicator in contact_lower for indicator in whatsapp_indicators):
            return "WhatsApp"
        
        # Instagram detection
        if 'instagram' in contact_lower or contact_info.startswith('@'):
            return "Instagram"
        
        # Messenger/Facebook detection
        messenger_indicators = ['messenger', 'fb', 'facebook', 'm.me']
        if any(indicator in contact_lower for indicator in messenger_indicators):
            return "Messenger"
        
        # Phone number detection
        if re.search(r'[\d+\-\(\)\s]{7,}', contact_info):
            digits_only = re.sub(r'[^\d]', '', contact_info)
            if len(digits_only) >= 7:
                return "PhoneNo"
        
        return "Others"
    
    def _fallback_contact_extraction(self, response: str, entity_name: str) -> List[Dict[str, Any]]:
        """
        Fallback regex-based contact extraction when JSON parsing fails.
        
        Implements Requirement 5.4: Add fallback mechanisms for malformed JSON responses.
        
        Args:
            response: Raw LLM response text
            entity_name: Entity name for logging context
            
        Returns:
            List of contact dictionaries from regex extraction
        """
        logger.info(f"Attempting fallback contact extraction for {entity_name}")
        
        fallback_contacts = []
        
        # Email extraction
        email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
        emails = re.findall(email_pattern, response)
        
        for email in emails:
            fallback_contacts.append({
                "decision_maker": None,
                "contact_info": email,
                "contact_channel": "Email"
            })
        
        # Phone number extraction
        phone_pattern = r'[\+]?[1-9]?[\d\s\-\(\)]{7,15}'
        phones = re.findall(phone_pattern, response)
        
        for phone in phones:
            cleaned_phone = re.sub(r'[^\d+]', '', phone)
            if len(cleaned_phone) >= 7:
                fallback_contacts.append({
                    "decision_maker": None,
                    "contact_info": phone.strip(),
                    "contact_channel": "PhoneNo"
                })
        
        logger.info(f"Fallback extraction found {len(fallback_contacts)} contacts for {entity_name}")
        return fallback_contacts