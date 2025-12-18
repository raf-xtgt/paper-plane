"""
Strategist Agent for generating personalized outreach messages.

This agent takes enriched partner data from the Researcher Agent and generates
personalized WhatsApp messages that include the decision-maker's name, reference
key facts, and maintain a professional yet casual tone.
"""

import os
import logging
import json
from typing import Optional, List
import google.generativeai as genai
from app.model.lead_gen_model import PartnerDiscovery, PartnerEnrichment, OutreachDraft, PartnerProfile, PageKeyFact

# Configure logging
logger = logging.getLogger("lead_gen_pipeline.strategist")

# Configure Gemini API
genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))


class StrategistAgent:
    """
    Strategist Agent for generating personalized outreach messages.
    
    Uses Gemini Pro model to create contextual WhatsApp messages that
    include decision-maker names, reference key facts, and end with
    low-friction questions.
    """
    
    def __init__(self):
        """Initialize Strategist Agent with Gemini Pro model."""
        self.model_name = os.getenv("ADK_MODEL_PRO", "gemini-2.0-pro-exp")
        self.temperature = 0.7
        
        # Initialize Gemini model
        self.model = genai.GenerativeModel(
            model_name=self.model_name,
            generation_config={
                "temperature": self.temperature,
                "top_p": 0.95,
                "top_k": 40,
                "max_output_tokens": 512,
            }
        )
        
        logger.info(f"Strategist Agent initialized with model: {self.model_name}")
    
    def _get_system_prompt(self, market: str) -> str:
        """
        Generate system prompt for message drafting.
        
        Args:
            market: Market vertical (Student Recruitment or Medical Tourism)
            
        Returns:
            System prompt string for the agent
        """
        return f"""You are a Senior Sales Strategist named "Allen" working in the {market} industry. 
            Your task is to write a personalized WhatsApp message to a potential channel partner.
            
            Your message must:
            1. Address the decision-maker by name (use their name naturally in the greeting)
            2. Reference the key fact discovered about their organization (show you've done research)
            3. Be exactly 3 sentences or less
            4. Maintain a professional yet casual tone appropriate for WhatsApp
            5. End with a low-friction question like "Open to a quick chat?" or similar
            6. Be concise and respectful of their time
            7. Clearly indicate you work with {market} agencies
            
            Tone guidelines:
            - Professional but warm and approachable
            - Confident without being pushy
            - Show genuine interest in partnership
            - Use conversational language (contractions are fine)
            - Avoid overly formal business jargon
            
            Return ONLY a JSON object with this exact structure:
            {{
                "draft_message": "Your message here"
            }}
            
            The message should be ready to send via WhatsApp without any modifications.
            """
    
    def _get_fallback_template(
        self, 
        decision_maker: str | None, 
        market: str, 
        city: str,
        entity_name: str
    ) -> str:
        """
        Generate fallback template message when LLM fails.
        
        Args:
            decision_maker: Name of decision-maker (if available)
            market: Market vertical
            city: Target city
            entity_name: Partner organization name
            
        Returns:
            Fallback message string
        """
        # Extract first name from decision-maker if available
        if decision_maker:
            # Handle formats like "Dr. John Smith" or "John Smith, Principal"
            name_part = decision_maker.split(',')[0].strip()
            # Get last word as name (handles titles like Dr., Mr., etc.)
            name = name_part.split()[-1]
        else:
            name = "there"
        
        return (
            f"Hi {name}, I work with {market} agencies in {city}. "
            f"Would love to explore a partnership. Open to a quick chat?"
        )
    
    def generate_outreach_draft_message(self,
        partner_profiles: List[PartnerProfile],
        market: str,
        city: str,
    ) -> List[PartnerProfile]:
        """
        Generate personalized outreach message for a partner.
        
        Args:
            partner_discovery: Partner discovery data from Scout Agent
            partner_enrichment: Enriched partner data from Researcher Agent
            market: Market vertical
            city: Target city
            
        Returns:
            OutreachDraft object with draft_message field
        """

        for profile in partner_profiles:
            outreach_msg = self.process_partner_profile_for_outreach(profile, market, city)
            profile.outreach_draft_message = outreach_msg
        return partner_profiles

    def _concatenate_key_facts(self, pages: List[PageKeyFact]) -> str:
        """
        Concatenates key facts from a list of PageKeyFact objects into a single string.
        Each key fact is separated by a line break tag (<br/>).

        Args:
            pages: List of PageKeyFact instances

        Returns:
            A single string containing all key facts separated by <br/>
        """
        all_key_facts: List[str] = []

        for page in pages:
            all_key_facts.extend(page.key_facts)

        return "\n".join(all_key_facts)

    def process_partner_profile_for_outreach(self, profile:PartnerProfile, market:str, city:str) -> OutreachDraft:

        entity_name = profile.org_name
        key_facts = self._concatenate_key_facts(profile.key_facts)
        
        logger.info(
            f"Drafting message for: {entity_name} - "
        )
        draft_message = ""
        try:
            system_prompt = self._get_system_prompt(market)
            
            # Build context for LLM
            context_parts = [
                f"Partner Organization: {entity_name}",
                f"Market: {market}",
                f"City: {city}"
            ]
            
            if key_facts:
                context_parts.append(f"Key Facts: {key_facts}")
            else:
                context_parts.append("Key Fact: Not available (focus on partnership opportunity)")
            
            context = "\n".join(context_parts)
            
            user_prompt = f"""Write a personalized WhatsApp message for this potential partner:

            {context}

            Remember: 3 sentences max, include decision-maker's name, reference the key fact if available, end with a question."""
            
            logger.debug(f"Sending context to Gemini for message generation: {entity_name}")
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
            
            message_data = json.loads(response_text)
            draft_message = message_data.get("draft_message", "").strip()
            
            if not draft_message:
                raise ValueError("Empty draft_message in LLM response")
            
            logger.info(
                f"Successfully generated message for {entity_name} - "
                f"length: {len(draft_message)} chars"
            )

        except Exception as e:
            logger.error(
                f"Message generation failed for {entity_name} - "
                f"Error: {str(e)} - "
                f"Using fallback template",
                exc_info=True
            )

        return OutreachDraft(draft_message=draft_message)
