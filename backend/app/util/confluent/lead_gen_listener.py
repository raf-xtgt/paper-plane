"""
Kafka consumer for lead_generated topic.

This module implements the LeadGenListener class that consumes lead generation
events from Kafka and prepares them for dashboard notification.
"""

import json
import asyncio
import logging
from confluent_kafka import Consumer, KafkaError
from pydantic import ValidationError
from app.util.confluent.confluent_config import conf_base
from app.model.lead_gen_model import LeadObject
from app.util.api.db_config import AsyncSessionLocal
from app.service.lead_profile.lead_profile_service import LeadProfileService
from app.service.lead_profile.generated_lead_service import GeneratedLeadService
from app.model.api.ppl_lead_profile import PPLPartnerProfileCreate
from app.model.api.ppl_generated_lead import PPLGeneratedLeadCreate

# Configure logger
logger = logging.getLogger("lead_gen_listener")

# Topic name
TOPIC_LEAD_GENERATED = "lead_generated"


class LeadGenListener:
    """
    Kafka consumer for processing lead_generated events.
    
    This class listens to the "lead_generated" Kafka topic and processes
    incoming lead objects. It logs received leads and prepares data structures
    for future dashboard notification integration.
    """
    
    def __init__(self):
        """Initialize the Kafka consumer for lead_generated topic."""
        # Configure consumer with unique group ID
        consumer_config = conf_base.copy()
        consumer_config.update({
            'group.id': 'fastapi_lead_gen_consumer_group',
            'auto.offset.reset': 'earliest'
        })
        
        self.consumer = Consumer(consumer_config)
        self.consumer.subscribe([TOPIC_LEAD_GENERATED])
        self.running = False
        self.lead_profile_service = LeadProfileService()
        self.generated_lead_service = GeneratedLeadService()
        
        logger.info(f"LeadGenListener initialized for topic: {TOPIC_LEAD_GENERATED}")
    
    async def process_lead(self, lead_data: dict) -> dict:
        """
        Process incoming lead message from Kafka.
        
        This method parses the Lead Object from the Kafka message,
        logs the received lead, and prepares a data structure for
        dashboard notification (future integration point).
        
        Args:
            lead_data: Raw lead data from Kafka message
            
        Returns:
            dict: Prepared data structure for dashboard notification
        """
        try:
            # Extract relevant fields from the incoming lead_data structure
            event_type = lead_data.get("event_type")
            timestamp_str = lead_data.get("timestamp")
            nested_data = lead_data.get("data", {})
            
            # Extract partner_profile data from nested structure
            partner_profile_data = nested_data.get("partner_profile", {})
            
            # Reconstruct the LeadObject with proper PartnerProfile structure
            # We need to create the PartnerProfile object separately since it's nested in the Kafka message
            from app.model.lead_gen_model import PartnerProfile, PageKeyFact, OutreachDraft
            
            # Handle key_facts reconstruction
            key_facts = None
            if partner_profile_data.get("key_facts"):
                key_facts = []
                for fact_data in partner_profile_data["key_facts"]:
                    if isinstance(fact_data, str):
                        # If it's just a string, create a minimal PageKeyFact
                        key_facts.append(PageKeyFact(
                            page_url="",
                            markdown_content="",
                            key_facts=[fact_data]
                        ))
                    elif isinstance(fact_data, list):
                        # If it's a list of facts
                        key_facts.append(PageKeyFact(
                            page_url="",
                            markdown_content="",
                            key_facts=fact_data
                        ))
            
            # Handle outreach_draft_message reconstruction
            outreach_draft = None
            if partner_profile_data.get("outreach_draft_message"):
                outreach_draft = OutreachDraft(
                    draft_message=partner_profile_data["outreach_draft_message"]
                )
            
            # Create PartnerProfile object
            partner_profile = PartnerProfile(
                guid=partner_profile_data.get("guid"),
                org_name=partner_profile_data.get("org_name"),
                primary_contact=partner_profile_data.get("primary_contact"),
                review_score=partner_profile_data.get("review_score"),
                total_reviews=partner_profile_data.get("total_reviews"),
                website_url=partner_profile_data.get("website_url"),
                address=partner_profile_data.get("address"),
                emails=partner_profile_data.get("emails"),
                phone_numbers=partner_profile_data.get("phone_numbers"),
                internal_urls=partner_profile_data.get("internal_urls"),
                external_urls=partner_profile_data.get("external_urls"),
                entity_type=partner_profile_data.get("entity_type"),
                lead_phase=partner_profile_data.get("lead_phase"),
                key_facts=key_facts,
                outreach_draft_message=outreach_draft
            )
            
            # Create LeadObject with reconstructed PartnerProfile
            lead = LeadObject(
                event_type=event_type,
                timestamp=timestamp_str,
                source_agent=nested_data.get("source_agent"),
                market=nested_data.get("market"),
                city=nested_data.get("city"),
                partner_profile=partner_profile
            )
            
            # Log received lead with partner name and city
            logger.info(
                f"Lead received: {lead.partner_profile.org_name} in {lead.city} "
                f"(Market: {lead.market})"
            )
            
            # Log additional details at debug level
            logger.debug(
                f"Lead details - Entity: {lead.partner_profile.entity_type}, "
                f"Website: {lead.partner_profile.website_url}, "
                f"Phase: {lead.partner_profile.lead_phase}"
            )
            
            # Prepare data structure for dashboard notification
            # This is a future integration point for the dashboard UI
            dashboard_notification = {
                "notification_type": "new_lead",
                "lead_id": f"{lead.city}_{lead.partner_profile.org_name}_{lead.timestamp.isoformat()}",
                "timestamp": lead.timestamp.isoformat(),
                "summary": {
                    "partner_name": lead.partner_profile.org_name,
                    "city": lead.city,
                    "market": lead.market,
                    "entity_type": lead.partner_profile.entity_type,
                    "lead_phase": lead.partner_profile.lead_phase
                },
                "details": {
                    "website": lead.partner_profile.website_url,
                    "address": lead.partner_profile.address,
                    "primary_contact": lead.partner_profile.primary_contact,
                    "emails": lead.partner_profile.emails,
                    "phone_numbers": lead.partner_profile.phone_numbers,
                    "review_score": lead.partner_profile.review_score,
                    "total_reviews": lead.partner_profile.total_reviews,
                    "outreach_draft": lead.partner_profile.outreach_draft_message.draft_message if lead.partner_profile.outreach_draft_message else None
                },
                "actions": [
                    {"type": "edit", "label": "Edit Message"},
                    {"type": "approve", "label": "Approve & Send"}
                ]
            }
            
            logger.debug(f"Dashboard notification prepared: {dashboard_notification['lead_id']}")
            
            # Persist to database
            async with AsyncSessionLocal() as db:
                try:
                    # Map PartnerProfile from LeadObject to PPLPartnerProfileCreate
                    # Handle key_facts flattening for database storage
                    key_facts_for_db = None
                    if lead.partner_profile.key_facts:
                        key_facts_for_db = []
                        for fact in lead.partner_profile.key_facts:
                            if fact.key_facts:
                                key_facts_for_db.extend(fact.key_facts)
                    
                    partner_profile_create = PPLPartnerProfileCreate(
                        org_name=lead.partner_profile.org_name,
                        primary_contact=lead.partner_profile.primary_contact,
                        review_score=lead.partner_profile.review_score,
                        total_reviews=lead.partner_profile.total_reviews,
                        website_url=lead.partner_profile.website_url,
                        address=lead.partner_profile.address,
                        emails=lead.partner_profile.emails,
                        phone_numbers=lead.partner_profile.phone_numbers,
                        internal_urls=lead.partner_profile.internal_urls,
                        external_urls=lead.partner_profile.external_urls,
                        entity_type=lead.partner_profile.entity_type,
                        lead_phase=lead.partner_profile.lead_phase,
                        key_facts=key_facts_for_db,
                        outreach_draft_message=lead.partner_profile.outreach_draft_message.draft_message if lead.partner_profile.outreach_draft_message else None,
                        user_guid=getattr(lead, 'user_guid', None)
                    )
                    
                    db_partner_profile = await self.lead_profile_service.create_lead_profile(
                        db, partner_profile_create
                    )
                    logger.info(f"Partner profile created: {db_partner_profile.guid}")

                    # Update dashboard notification with database GUIDs
                    dashboard_notification["partner_profile_guid"] = str(db_partner_profile.guid)
                    
                except Exception as db_error:
                    logger.error(f"Database error persisting lead: {db_error}", exc_info=True)
                    # Continue processing even if DB fails
            
            return dashboard_notification
            
        except ValidationError as ve:
            logger.error(f"Pydantic validation error processing lead: {ve.errors()}", exc_info=True)
            return None
        except Exception as e:
            logger.error(f"Unexpected error processing lead: {e}", exc_info=True)
            return None
    
    async def start(self):
        """
        Start consuming messages from lead_generated topic.
        
        This method runs in a background task and continuously polls
        the Kafka topic for new lead generation events.
        """
        self.running = True
        logger.info("LeadGenListener started - listening to lead_generated topic...")
        
        try:
            while self.running:
                # Poll for messages with short timeout
                msg = self.consumer.poll(0.1)
                
                if msg is None:
                    # No message available, sleep to avoid busy waiting
                    await asyncio.sleep(1.0)
                    continue
                
                if msg.error():
                    if msg.error().code() == KafkaError._PARTITION_EOF:
                        # End of partition, not an error
                        logger.debug(f"Reached end of partition: {msg.partition()}")
                    else:
                        logger.error(f"Consumer error: {msg.error()}")
                    continue
                
                # Process message
                try:
                    lead_data = json.loads(msg.value().decode('utf-8'))
                    dashboard_data = await self.process_lead(lead_data)
                    
                    if dashboard_data:
                        # Future: Send to dashboard notification service
                        # For now, just log that it's ready
                        logger.info(
                            f"Lead ready for dashboard: {dashboard_data['summary']['partner_name']}"
                        )
                    
                except json.JSONDecodeError as e:
                    logger.error(f"Failed to decode message: {e}")
                except Exception as e:
                    logger.error(f"Error processing message: {e}", exc_info=True)
                
                # Yield control to event loop
                await asyncio.sleep(0.01)
                
        except asyncio.CancelledError:
            logger.info("LeadGenListener shutting down...")
        finally:
            self.stop()
    
    def stop(self):
        """
        Stop the consumer and close the connection.
        """
        self.running = False
        if self.consumer:
            self.consumer.close()
            logger.info("LeadGenListener stopped and consumer closed")


# Singleton instance for use in main.py
lead_gen_listener = LeadGenListener()
