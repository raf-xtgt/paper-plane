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
        Execute LLM extraction with comprehensive error handling and retry logic.
        
        Args:
            prompt: Extraction prompt for the LLM
            entity_name: Entity name for logging
            max_retries: Maximum number of retry attempts
            
        Returns:
            Dictionary with extracted data
            
        Raises:
            Exception: If all retry attempts fail
        """
        last_exception = None
        
        for attempt in range(max_retries):
            try:
                logger.debug(f"LLM extraction attempt {attempt + 1}/{max_retries} for {entity_name}")
                
                # Execute LLM request in executor to avoid blocking
                response = await asyncio.get_event_loop().run_in_executor(
                    None, self._safe_llm_request, prompt
                )
                
                # Validate response object
                if not response or not hasattr(response, 'text'):
                    raise ValueError("Invalid response object from LLM")
                
                # Parse and validate JSON response
                parsed_data = self._parse_llm_response(response.text, entity_name)
                
                # Additional validation of parsed data structure
                validated_response = self._validate_llm_response_structure(parsed_data, entity_name)
                
                logger.debug(f"LLM extraction successful for {entity_name} on attempt {attempt + 1}")
                return validated_response
                
            except json.JSONDecodeError as e:
                last_exception = e
                logger.warning(
                    f"JSON parsing failed for {entity_name} (attempt {attempt + 1}/{max_retries}): {e}"
                )
                if attempt == max_retries - 1:
                    logger.error(f"All JSON parsing attempts failed for {entity_name}")
                    break
                
                # Exponential backoff for JSON parsing errors
                delay = min(2 ** attempt, 16)  # Cap at 16 seconds
                await asyncio.sleep(delay)
                
            except (ValueError, AttributeError) as e:
                last_exception = e
                logger.warning(
                    f"Response validation failed for {entity_name} (attempt {attempt + 1}/{max_retries}): {e}"
                )
                if attempt == max_retries - 1:
                    break
                
                # Shorter delay for validation errors
                await asyncio.sleep(1 + attempt)
                
            except Exception as e:
                last_exception = e
                error_type = type(e).__name__
                logger.warning(
                    f"LLM request failed for {entity_name} (attempt {attempt + 1}/{max_retries}) - {error_type}: {e}"
                )
                
                if attempt == max_retries - 1:
                    logger.error(f"All LLM extraction attempts failed for {entity_name}")
                    break
                
                # Enhanced exponential backoff with jitter for rate limiting
                base_delay = 2 ** attempt
                jitter = 0.1 * attempt * (1 + (attempt % 2))  # Variable jitter
                delay = min(base_delay + jitter, 30)  # Cap at 30 seconds
                
                logger.debug(f"Retrying {entity_name} after {delay:.1f}s delay")
                await asyncio.sleep(delay)
        
        # If we get here, all attempts failed
        error_msg = f"All {max_retries} extraction attempts failed for {entity_name}"
        if last_exception:
            error_msg += f". Last error: {type(last_exception).__name__}: {last_exception}"
        
        raise Exception(error_msg)
    
    def _safe_llm_request(self, prompt: str):
        """
        Safely execute LLM request with additional error handling.
        
        Args:
            prompt: Extraction prompt for the LLM
            
        Returns:
            LLM response object
            
        Raises:
            Exception: If LLM request fails
        """
        try:
            # Add timeout and safety checks
            if not prompt or len(prompt.strip()) == 0:
                raise ValueError("Empty or invalid prompt provided")
            
            # Execute the LLM request
            response = self.model.generate_content(prompt)
            
            # Validate response
            if not response:
                raise ValueError("No response received from LLM")
            
            if not hasattr(response, 'text'):
                raise ValueError("Response object missing text attribute")
            
            if not response.text:
                raise ValueError("Empty text response from LLM")
            
            return response
            
        except Exception as e:
            logger.error(f"LLM request execution failed: {type(e).__name__}: {e}")
            raise
    
    def _validate_llm_response_structure(self, parsed_data: Dict[str, Any], entity_name: str) -> Dict[str, Any]:
        """
        Validate the structure and content of parsed LLM response.
        
        Args:
            parsed_data: Parsed JSON data from LLM
            entity_name: Entity name for logging
            
        Returns:
            Validated response data
            
        Raises:
            ValueError: If response structure is invalid
        """
        if not isinstance(parsed_data, dict):
            raise ValueError(f"LLM response is not a dictionary: {type(parsed_data)}")
        
        # Check for required fields (even if they might be null)
        required_fields = ["decision_maker", "contact_info", "contact_channel", "key_fact", "status"]
        missing_fields = [field for field in required_fields if field not in parsed_data]
        
        if missing_fields:
            logger.warning(f"LLM response missing fields for {entity_name}: {missing_fields}")
            # Add missing fields with null values
            for field in missing_fields:
                parsed_data[field] = None
        
        # Validate status field
        valid_statuses = ["complete", "incomplete"]
        if parsed_data.get("status") not in valid_statuses:
            logger.warning(f"Invalid status '{parsed_data.get('status')}' for {entity_name}, defaulting to 'incomplete'")
            parsed_data["status"] = "incomplete"
        
        # Validate contact_channel if present
        if parsed_data.get("contact_channel"):
            valid_channels = ["WhatsApp", "Email", "Messenger", "Instagram", "PhoneNo", "Other"]
            if parsed_data["contact_channel"] not in valid_channels:
                logger.warning(f"Invalid contact_channel '{parsed_data['contact_channel']}' for {entity_name}")
                parsed_data["contact_channel"] = None
        
        logger.debug(f"LLM response structure validated for {entity_name}")
        return parsed_data
    
    def _parse_llm_response(self, response_text: str, entity_name: str) -> Dict[str, Any]:
        """
        Parse LLM response with comprehensive fallback mechanisms.
        
        Args:
            response_text: Raw response text from LLM
            entity_name: Entity name for logging
            
        Returns:
            Dictionary with parsed data
            
        Raises:
            json.JSONDecodeError: If all parsing strategies fail
        """
        if not response_text or not response_text.strip():
            raise json.JSONDecodeError("Empty response from LLM", "", 0)
        
        response_text = response_text.strip()
        logger.debug(f"Parsing LLM response for {entity_name} (length: {len(response_text)})")
        
        # Enhanced JSON extraction strategies with better error handling
        extraction_strategies = [
            ("Direct JSON parsing", self._parse_direct_json),
            ("JSON block extraction", self._parse_json_block),
            ("Code block extraction", self._parse_code_block_json),
            ("Nested JSON extraction", self._parse_nested_json),
            ("Cleaned JSON extraction", self._parse_cleaned_json),
            ("Regex-based extraction", self._parse_regex_json),
            ("Fallback structure creation", self._create_fallback_json_structure)
        ]
        
        parsing_errors = []
        
        for strategy_name, strategy_func in extraction_strategies:
            try:
                logger.debug(f"Trying {strategy_name} for {entity_name}")
                extracted_data = strategy_func(response_text, entity_name)
                
                if isinstance(extracted_data, dict) and extracted_data:
                    logger.debug(f"Successfully parsed JSON using {strategy_name} for {entity_name}")
                    return extracted_data
                    
            except Exception as e:
                error_msg = f"{strategy_name}: {type(e).__name__}: {e}"
                parsing_errors.append(error_msg)
                logger.debug(f"Strategy {strategy_name} failed for {entity_name}: {e}")
                continue
        
        # If all strategies fail, log detailed error information
        logger.error(f"All JSON parsing strategies failed for {entity_name}")
        logger.error(f"Response preview: {response_text[:300]}...")
        logger.error(f"Parsing errors: {'; '.join(parsing_errors)}")
        
        raise json.JSONDecodeError(
            f"Could not extract valid JSON from response using any strategy. Errors: {'; '.join(parsing_errors)}", 
            response_text, 
            0
        )
    
    def _parse_direct_json(self, text: str, entity_name: str) -> Dict[str, Any]:
        """Parse text directly as JSON."""
        return json.loads(text)
    
    def _parse_json_block(self, text: str, entity_name: str) -> Dict[str, Any]:
        """Extract JSON block from text using regex."""
        match = re.search(r'\{.*\}', text, re.DOTALL)
        if not match:
            raise ValueError("No JSON block found")
        return json.loads(match.group())
    
    def _parse_code_block_json(self, text: str, entity_name: str) -> Dict[str, Any]:
        """Extract JSON from code blocks (```json ... ```)."""
        patterns = [
            r'```json\s*(\{.*?\})\s*```',
            r'```\s*(\{.*?\})\s*```',
            r'`(\{.*?\})`'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
            if match:
                return json.loads(match.group(1))
        
        raise ValueError("No JSON found in code blocks")
    
    def _parse_nested_json(self, text: str, entity_name: str) -> Dict[str, Any]:
        """Extract nested JSON objects."""
        # Find balanced braces
        brace_count = 0
        start_idx = -1
        
        for i, char in enumerate(text):
            if char == '{':
                if brace_count == 0:
                    start_idx = i
                brace_count += 1
            elif char == '}':
                brace_count -= 1
                if brace_count == 0 and start_idx != -1:
                    json_str = text[start_idx:i+1]
                    try:
                        return json.loads(json_str)
                    except json.JSONDecodeError:
                        continue
        
        raise ValueError("No valid nested JSON found")
    
    def _parse_cleaned_json(self, text: str, entity_name: str) -> Dict[str, Any]:
        """Parse JSON after cleaning common formatting issues."""
        # Remove common prefixes and suffixes
        cleaned = text
        
        # Remove common response prefixes
        prefixes_to_remove = [
            r'^.*?(?=\{)',  # Everything before first {
            r'^[^{]*',      # Non-brace characters at start
        ]
        
        for prefix in prefixes_to_remove:
            cleaned = re.sub(prefix, '', cleaned, flags=re.DOTALL)
        
        # Remove common suffixes
        suffixes_to_remove = [
            r'\}.*$',  # Everything after last }
        ]
        
        for suffix in suffixes_to_remove:
            cleaned = re.sub(suffix, '}', cleaned, flags=re.DOTALL)
        
        # Fix common JSON formatting issues
        cleaned = re.sub(r',\s*}', '}', cleaned)  # Remove trailing commas
        cleaned = re.sub(r',\s*]', ']', cleaned)  # Remove trailing commas in arrays
        
        return json.loads(cleaned)
    
    def _parse_regex_json(self, text: str, entity_name: str) -> Dict[str, Any]:
        """Extract JSON using comprehensive regex patterns."""
        # Try to extract key-value pairs manually
        json_obj = {}
        
        # Extract decision_maker
        dm_patterns = [
            r'"decision_maker"\s*:\s*"([^"]*)"',
            r"'decision_maker'\s*:\s*'([^']*)'",
            r'decision_maker["\']?\s*:\s*["\']([^"\']*)["\']'
        ]
        
        for pattern in dm_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                json_obj["decision_maker"] = match.group(1)
                break
        
        # Extract contact_info
        ci_patterns = [
            r'"contact_info"\s*:\s*"([^"]*)"',
            r"'contact_info'\s*:\s*'([^']*)'",
            r'contact_info["\']?\s*:\s*["\']([^"\']*)["\']'
        ]
        
        for pattern in ci_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                json_obj["contact_info"] = match.group(1)
                break
        
        # Extract other fields similarly
        field_patterns = {
            "contact_channel": [
                r'"contact_channel"\s*:\s*"([^"]*)"',
                r"'contact_channel'\s*:\s*'([^']*)'",
            ],
            "key_fact": [
                r'"key_fact"\s*:\s*"([^"]*)"',
                r"'key_fact'\s*:\s*'([^']*)'",
            ],
            "status": [
                r'"status"\s*:\s*"([^"]*)"',
                r"'status'\s*:\s*'([^']*)'",
            ]
        }
        
        for field, patterns in field_patterns.items():
            for pattern in patterns:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    json_obj[field] = match.group(1)
                    break
        
        if not json_obj:
            raise ValueError("No extractable JSON fields found")
        
        return json_obj
    
    def _create_fallback_json_structure(self, text: str, entity_name: str) -> Dict[str, Any]:
        """Create a basic JSON structure as last resort."""
        logger.warning(f"Creating fallback JSON structure for {entity_name}")
        
        # Try to extract any email or phone from the text
        email_match = re.search(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', text)
        phone_match = re.search(r'[\+]?[1-9][\d\s\-\(\)]{7,15}', text)
        
        contact_info = None
        contact_channel = None
        
        if email_match:
            contact_info = email_match.group()
            contact_channel = "Email"
        elif phone_match:
            contact_info = phone_match.group()
            contact_channel = "PhoneNo"
        
        return {
            "decision_maker": None,
            "contact_info": contact_info,
            "contact_channel": contact_channel,
            "key_fact": None,
            "status": "incomplete"
        }
    
    def _construct_extraction_prompt(
        self, 
        entity_name: str, 
        verified_url: str, 
        content: str
    ) -> str:
        """
        Build structured prompt for LLM extraction with entity context.
        
        Args:
            entity_name: Name of the entity
            verified_url: Verified website URL
            content: Website content in markdown format
            
        Returns:
            Structured prompt for contact information extraction
        """
        # Analyze entity context for better prompt customization
        entity_context = self._analyze_entity_context(entity_name, verified_url)
        
        # Prepare content with intelligent truncation
        processed_content = self._prepare_content_for_extraction(content)
        
        # Build the structured prompt with entity-specific context
        prompt = self._build_extraction_prompt_template(
            entity_name, 
            verified_url, 
            processed_content, 
            entity_context
        )
        
        return prompt
    
    def _analyze_entity_context(self, entity_name: str, verified_url: str) -> Dict[str, Any]:
        """
        Analyze entity context to customize extraction approach.
        
        Args:
            entity_name: Name of the entity
            verified_url: Verified website URL
            
        Returns:
            Dictionary with entity context information
        """
        context = {
            "entity_type": "Unknown",
            "likely_decision_makers": ["CEO", "Director", "Manager"],
            "sector_keywords": [],
            "extraction_focus": "general"
        }
        
        entity_lower = entity_name.lower() if entity_name else ""
        url_lower = verified_url.lower() if verified_url else ""
        
        # Determine entity type and customize extraction approach
        if any(keyword in entity_lower for keyword in ["school", "college", "university", "academy", "institute"]):
            context.update({
                "entity_type": "Educational Institution",
                "likely_decision_makers": ["Principal", "Director", "Head", "Dean", "President"],
                "sector_keywords": ["education", "academic", "student", "curriculum"],
                "extraction_focus": "educational"
            })
        elif any(keyword in entity_lower for keyword in ["hospital", "clinic", "medical", "health", "diagnostic"]):
            context.update({
                "entity_type": "Healthcare Organization",
                "likely_decision_makers": ["Medical Director", "Chief Medical Officer", "Administrator", "Director"],
                "sector_keywords": ["medical", "healthcare", "patient", "treatment"],
                "extraction_focus": "healthcare"
            })
        elif any(keyword in entity_lower for keyword in ["company", "corp", "ltd", "inc", "business"]):
            context.update({
                "entity_type": "Business Organization",
                "likely_decision_makers": ["CEO", "Managing Director", "President", "General Manager"],
                "sector_keywords": ["business", "corporate", "services", "solutions"],
                "extraction_focus": "corporate"
            })
        elif any(keyword in entity_lower for keyword in ["center", "centre", "facility", "lab", "laboratory"]):
            context.update({
                "entity_type": "Service Center",
                "likely_decision_makers": ["Director", "Manager", "Head", "Coordinator"],
                "sector_keywords": ["services", "facility", "center", "operations"],
                "extraction_focus": "service"
            })
        
        return context
    
    def _prepare_content_for_extraction(self, content: str) -> str:
        """
        Prepare and optimize content for extraction with intelligent truncation.
        
        Args:
            content: Raw website content
            
        Returns:
            Processed content optimized for extraction
        """
        if not content:
            return ""
        
        # Remove excessive whitespace and normalize
        content = re.sub(r'\n\s*\n', '\n\n', content.strip())
        
        # Define content sections to prioritize
        priority_sections = [
            r'(?i)(about\s+us?|who\s+we\s+are|our\s+team|leadership|management|staff|faculty)',
            r'(?i)(contact\s+us?|get\s+in\s+touch|reach\s+us|contact\s+info|contact\s+details)',
            r'(?i)(principal|director|ceo|head|manager|administrator|founder|owner)',
            r'(?i)(phone|email|whatsapp|call|write|message)'
        ]
        
        # Extract priority content sections
        priority_content = []
        for pattern in priority_sections:
            matches = re.finditer(pattern, content, re.IGNORECASE | re.MULTILINE)
            for match in matches:
                start = max(0, match.start() - 200)
                end = min(len(content), match.end() + 200)
                section = content[start:end].strip()
                if section and section not in priority_content:
                    priority_content.append(section)
        
        # Combine priority content with beginning and end of full content
        max_content_length = 8000
        
        if len(content) <= max_content_length:
            return content
        
        # If content is too long, use intelligent truncation
        priority_text = '\n\n'.join(priority_content)
        remaining_length = max_content_length - len(priority_text) - 100  # Buffer for separators
        
        if remaining_length > 1000:
            # Add beginning and end of content
            begin_length = remaining_length // 2
            end_length = remaining_length - begin_length
            
            beginning = content[:begin_length]
            ending = content[-end_length:]
            
            processed_content = f"{beginning}\n\n--- PRIORITY SECTIONS ---\n{priority_text}\n\n--- END CONTENT ---\n{ending}"
        else:
            # Use only priority content if space is limited
            processed_content = priority_text[:max_content_length]
        
        return processed_content
    
    def _build_extraction_prompt_template(
        self, 
        entity_name: str, 
        verified_url: str, 
        content: str, 
        entity_context: Dict[str, Any]
    ) -> str:
        """
        Build the final extraction prompt with entity-specific customization.
        
        Args:
            entity_name: Name of the entity
            verified_url: Verified website URL
            content: Processed content
            entity_context: Entity context information
            
        Returns:
            Complete structured prompt for extraction
        """
        # Customize decision-maker priorities based on entity type
        decision_maker_priorities = self._get_decision_maker_priorities(entity_context)
        
        # Get sector-specific extraction guidelines
        sector_guidelines = self._get_sector_specific_guidelines(entity_context)
        
        # Build the comprehensive prompt
        prompt = f"""You are an expert at extracting decision-maker contact information from {entity_context['entity_type'].lower()} websites.

EXTRACTION TARGET: {entity_name}
ENTITY TYPE: {entity_context['entity_type']}
WEBSITE: {verified_url}

WEBSITE CONTENT:
{content}

EXTRACTION SCHEMA:
Return ONLY a valid JSON object matching this exact structure:
{{
    "decision_maker": "Full name and title of the primary decision-maker",
    "contact_info": "Direct contact information (email, phone, WhatsApp)",
    "contact_channel": "Exact channel type: WhatsApp|Email|Messenger|Instagram|PhoneNo|Other",
    "key_fact": "One specific, interesting fact about the organization",
    "status": "complete|incomplete"
}}

DECISION-MAKER PRIORITIES FOR {entity_context['entity_type'].upper()}:
{decision_maker_priorities}

CONTACT INFORMATION EXTRACTION RULES:
1. PRIORITY ORDER: Direct emails > Named phone numbers > WhatsApp > Social media
2. AVOID: Generic emails (info@, contact@, admin@, support@)
3. PREFER: Personal emails with names, direct phone lines with extensions
4. VALIDATE: Email format (contains @ and valid domain), phone format (7+ digits)

CONTACT CHANNEL CLASSIFICATION:
- "Email": Valid email addresses (name@domain.com format)
- "WhatsApp": WhatsApp numbers, wa.me links, or explicit WhatsApp mentions
- "PhoneNo": Phone numbers without WhatsApp indication
- "Instagram": Instagram handles (@username) or instagram.com links
- "Messenger": Facebook Messenger or m.me links
- "Other": Any other contact method not fitting above categories

KEY FACT EXTRACTION FOR {entity_context['entity_type'].upper()}:
{sector_guidelines}

STATUS DETERMINATION LOGIC:
- "complete": BOTH decision_maker AND contact_info successfully extracted
- "incomplete": Missing EITHER decision_maker OR contact_info (or both)

CRITICAL OUTPUT REQUIREMENTS:
1. Return ONLY valid JSON - no explanations, no markdown formatting, no additional text
2. Use null for missing fields, never use empty strings or "N/A"
3. Ensure contact_channel exactly matches the contact_info type
4. Include full names with titles (e.g., "Dr. Sarah Johnson, Principal")
5. Verify all extracted information is factually present in the content

EXTRACTION FOCUS: Focus on {entity_context['extraction_focus']} sector patterns and terminology.

JSON Response:"""
        
        return prompt
    
    def _get_decision_maker_priorities(self, entity_context: Dict[str, Any]) -> str:
        """Get formatted decision-maker priorities based on entity type."""
        priorities = entity_context.get('likely_decision_makers', ['CEO', 'Director', 'Manager'])
        
        formatted_priorities = []
        for i, title in enumerate(priorities, 1):
            formatted_priorities.append(f"{i}. {title}")
        
        return '\n'.join(formatted_priorities)
    
    def _get_sector_specific_guidelines(self, entity_context: Dict[str, Any]) -> str:
        """Get sector-specific guidelines for key fact extraction."""
        entity_type = entity_context.get('entity_type', 'Unknown')
        
        guidelines = {
            'Educational Institution': """- Academic achievements, accreditations, or certifications
- Years of operation and establishment history
- Student enrollment numbers or graduation rates
- Specialized programs, courses, or departments
- Awards, rankings, or recognition received
- Campus facilities or infrastructure highlights""",
            
            'Healthcare Organization': """- Medical specializations and services offered
- Years of operation and establishment date
- Certifications, accreditations, or quality awards
- Advanced equipment or technology available
- Patient capacity or service statistics
- Notable medical achievements or recognition""",
            
            'Business Organization': """- Years in business and company history
- Industry specializations or unique services
- Business certifications or quality standards
- Client base size or market presence
- Awards, recognition, or achievements
- Branch locations or expansion details""",
            
            'Service Center': """- Types of services offered and specializations
- Years of operation and establishment
- Certifications or quality standards
- Service capacity or operational scale
- Technology or equipment capabilities
- Recognition or awards received"""
        }
        
        return guidelines.get(entity_type, """- Years of operation or establishment date
- Specializations or unique services offered
- Awards, certifications, or recognition received
- Notable achievements or milestones
- Operational scale or capacity details
- Branch locations or expansion information""")
    
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
        Create comprehensive fallback result when LLM extraction fails completely.
        
        Args:
            content: Website content for regex-based extraction
            
        Returns:
            Fallback extraction result with best-effort extraction
        """
        logger.info("Attempting comprehensive fallback regex-based extraction")
        
        fallback_result = {
            "decision_maker": None,
            "contact_info": None,
            "contact_channel": None,
            "key_fact": None,
            "status": "incomplete"
        }
        
        try:
            # Extract decision makers using pattern matching
            decision_maker = self._extract_decision_maker_fallback(content)
            if decision_maker:
                fallback_result["decision_maker"] = decision_maker
            
            # Extract contact information
            contact_info, contact_channel = self._extract_contact_info_fallback(content)
            if contact_info:
                fallback_result["contact_info"] = contact_info
                fallback_result["contact_channel"] = contact_channel
            
            # Extract key facts
            key_fact = self._extract_key_fact_fallback(content)
            if key_fact:
                fallback_result["key_fact"] = key_fact
            
            # Update status if we found both decision maker and contact info
            if fallback_result["decision_maker"] and fallback_result["contact_info"]:
                fallback_result["status"] = "complete"
            
            logger.info(f"Fallback extraction completed - Status: {fallback_result['status']}")
            
        except Exception as e:
            logger.error(f"Fallback extraction failed: {e}")
        
        return fallback_result
    
    def _extract_decision_maker_fallback(self, content: str) -> Optional[str]:
        """Extract decision maker information using regex patterns."""
        # Decision maker title patterns
        title_patterns = [
            r'(?i)(principal|director|ceo|president|head|manager|administrator|founder|owner)\s*[:\-]?\s*([A-Za-z\s\.]+)',
            r'(?i)([A-Za-z\s\.]+),?\s*(principal|director|ceo|president|head|manager|administrator)',
            r'(?i)(dr\.?|mr\.?|ms\.?|mrs\.?)\s+([A-Za-z\s]+),?\s*(principal|director|ceo|president|head|manager)',
        ]
        
        for pattern in title_patterns:
            matches = re.findall(pattern, content)
            for match in matches:
                if isinstance(match, tuple) and len(match) >= 2:
                    # Clean and format the match
                    if match[0].lower() in ['principal', 'director', 'ceo', 'president', 'head', 'manager', 'administrator', 'founder', 'owner']:
                        name = match[1].strip()
                        title = match[0].strip()
                    else:
                        name = match[0].strip() if match[0] else match[1].strip()
                        title = match[2].strip() if len(match) > 2 else match[1].strip()
                    
                    if name and len(name) > 2:
                        return f"{name}, {title.title()}"
        
        return None
    
    def _extract_contact_info_fallback(self, content: str) -> tuple[Optional[str], Optional[str]]:
        """Extract contact information with channel classification."""
        # Enhanced email patterns
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        
        # Enhanced phone patterns
        phone_patterns = [
            r'[\+]?[1-9][\d\s\-\(\)]{7,15}',
            r'\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b',
            r'\b\(\d{3}\)\s?\d{3}[-.\s]?\d{4}\b'
        ]
        
        # WhatsApp patterns
        whatsapp_patterns = [
            r'(?i)whatsapp[:\s]*[\+]?[\d\s\-\(\)]{7,15}',
            r'(?i)wa\.me/[\d]+',
            r'(?i)whatsapp[:\s]*[\+]?[\d\s\-\(\)]{7,15}'
        ]
        
        # Find all contact information
        emails = re.findall(email_pattern, content, re.IGNORECASE)
        phones = []
        whatsapp_numbers = []
        
        for pattern in phone_patterns:
            phones.extend(re.findall(pattern, content))
        
        for pattern in whatsapp_patterns:
            whatsapp_numbers.extend(re.findall(pattern, content))
        
        # Filter out generic emails
        filtered_emails = [
            email for email in emails 
            if not any(generic in email.lower() for generic in [
                'info@', 'contact@', 'admin@', 'support@', 'noreply@', 
                'no-reply@', 'webmaster@', 'hello@', 'mail@', 'sales@'
            ])
        ]
        
        # Priority order: Personal emails > WhatsApp > Phones > Generic emails
        if filtered_emails:
            return filtered_emails[0], "Email"
        elif whatsapp_numbers:
            return whatsapp_numbers[0], "WhatsApp"
        elif phones:
            # Clean up phone number
            phone = re.sub(r'[^\d+]', '', phones[0])
            if len(phone) >= 7:
                return phone, "PhoneNo"
        elif emails:
            return emails[0], "Email"
        
        return None, None
    
    def _extract_key_fact_fallback(self, content: str) -> Optional[str]:
        """Extract key facts using pattern matching."""
        # Key fact patterns
        fact_patterns = [
            r'(?i)(established|founded|since)\s+(\d{4})',
            r'(?i)(\d+)\s+years?\s+(of\s+)?(experience|operation)',
            r'(?i)(award|recognition|certified|accredited)[^.]{0,100}',
            r'(?i)(specializ|focus)[^.]{0,100}',
            r'(?i)(\d+)\s+(students?|branches?|locations?|centers?)'
        ]
        
        for pattern in fact_patterns:
            matches = re.findall(pattern, content)
            if matches:
                match = matches[0]
                if isinstance(match, tuple):
                    fact = ' '.join(str(m) for m in match if m).strip()
                else:
                    fact = str(match).strip()
                
                if len(fact) > 10:  # Ensure meaningful length
                    return fact[:200]  # Limit length
        
        return None