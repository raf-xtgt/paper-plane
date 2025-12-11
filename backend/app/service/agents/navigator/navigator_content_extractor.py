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
        try:
            prompt = self._construct_extraction_prompt(
                entity_name, verified_url, markdown_content
            )
            
            response = await asyncio.get_event_loop().run_in_executor(
                None, self.model.generate_content, prompt
            )
            
            # Parse JSON response
            response_text = response.text.strip()
            
            # Try to extract JSON from response
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if json_match:
                json_str = json_match.group()
                extracted_data = json.loads(json_str)
            else:
                # Fallback: try to parse entire response as JSON
                extracted_data = json.loads(response_text)
            
            # Validate and normalize extracted data
            return self._validate_extraction(extracted_data)
            
        except json.JSONDecodeError as e:
            logger.warning(f"JSON parsing failed for {entity_name}: {e}")
            return self._fallback_extraction(markdown_content)
        except Exception as e:
            logger.error(f"LLM extraction failed for {entity_name}: {e}")
            return {"status": "incomplete"}
    
    def _construct_extraction_prompt(
        self, 
        entity_name: str, 
        verified_url: str, 
        content: str
    ) -> str:
        """Build structured prompt for LLM extraction."""
        # Truncate content if too long
        max_content_length = 8000
        if len(content) > max_content_length:
            content = content[:max_content_length] + "... [truncated]"
        
        return f"""
Extract decision-maker contact information from this website content for {entity_name}.

Website: {verified_url}
Content:
{content}

Extract the following information and return as JSON:
{{
    "decision_maker": "Name and title of decision-maker (CEO, Director, Principal, etc.)",
    "contact_info": "Direct contact information (email, phone, WhatsApp number)",
    "contact_channel": "One of: WhatsApp, Email, Messenger, Instagram, PhoneNo, Other",
    "key_fact": "One specific key fact about the organization for personalization",
    "status": "complete or incomplete"
}}

Rules:
1. Focus on decision-makers: CEO, Director, Principal, Head, Manager, Owner
2. Prefer direct contact info over general contact forms
3. For contact_channel: classify the contact_info type
4. For key_fact: find something specific and interesting (awards, specialties, history)
5. Set status to "complete" only if you find both decision_maker AND contact_info
6. Return valid JSON only, no additional text

JSON Response:
"""
    
    def _validate_extraction(self, extracted_data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate and normalize extracted contact information."""
        # Ensure required fields exist
        validated = {
            "decision_maker": extracted_data.get("decision_maker"),
            "contact_info": extracted_data.get("contact_info"),
            "contact_channel": extracted_data.get("contact_channel"),
            "key_fact": extracted_data.get("key_fact"),
            "status": extracted_data.get("status", "incomplete")
        }
        
        # Validate status logic
        if validated["decision_maker"] and validated["contact_info"]:
            validated["status"] = "complete"
        else:
            validated["status"] = "incomplete"
        
        return validated
    
    def _fallback_extraction(self, content: str) -> Dict[str, Any]:
        """Fallback regex-based extraction for emails and phone numbers."""
        # Simple regex patterns for fallback
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        phone_pattern = r'[\+]?[1-9]?[0-9]{7,15}'
        
        emails = re.findall(email_pattern, content)
        phones = re.findall(phone_pattern, content)
        
        contact_info = None
        contact_channel = None
        
        if emails:
            contact_info = emails[0]
            contact_channel = "Email"
        elif phones:
            contact_info = phones[0]
            contact_channel = "PhoneNo"
        
        return {
            "decision_maker": None,
            "contact_info": contact_info,
            "contact_channel": contact_channel,
            "key_fact": None,
            "status": "incomplete"
        }