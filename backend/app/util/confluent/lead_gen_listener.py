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
            # The LeadObject expects fields like 'source_agent', 'market', 'city', etc.,
            # directly, but the Kafka message nests these under a 'data' key.
            event_type = lead_data.get("event_type")
            timestamp_str = lead_data.get("timestamp")
            nested_data = lead_data.get("data", {})
            
            # Combine top-level fields with the nested 'data' fields for Pydantic parsing
            combined_data_for_pydantic = {
                "event_type": event_type,
                "timestamp": timestamp_str,
                **nested_data # Unpack the nested data
            }
            
            # Parse Lead Object using Pydantic model for validation
            lead = LeadObject(**combined_data_for_pydantic)
            
            # Log received lead with partner name and city
            logger.info(
                f"Lead received: {lead.partner_profile.name} in {lead.city} "
                f"(Market: {lead.market})"
            )
            
            # Log additional details at debug level
            logger.debug(
                f"Lead details - Contact: {lead.partner_profile.contact_person}, "
                f"Method: {lead.partner_profile.contact_method}, "
                f"Insight: {lead.ai_context.key_insight}"
            )
            
            # Prepare data structure for dashboard notification
            # This is a future integration point for the dashboard UI
            dashboard_notification = {
                "notification_type": "new_lead",
                "lead_id": f"{lead.city}_{lead.partner_profile.name}_{lead.timestamp.isoformat()}",
                "timestamp": lead.timestamp.isoformat(),
                "summary": {
                    "partner_name": lead.partner_profile.name,
                    "city": lead.city,
                    "market": lead.market,
                    "contact_person": lead.partner_profile.contact_person,
                    "entity_type": lead.partner_profile.entity_type
                },
                "details": {
                    "website": str(lead.partner_profile.url),
                    "contact_method": lead.partner_profile.contact_method,
                    "contact_channel": lead.partner_profile.contact_channel,
                    "key_insight": lead.ai_context.key_insight,
                    "draft_message": lead.ai_context.draft_message
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
                    # Create partner profile
                    partner_profile_create = PPLPartnerProfileCreate(
                        name=lead.partner_profile.name,
                        url=str(lead.partner_profile.url) if lead.partner_profile.url else None,
                        contact_person=lead.partner_profile.contact_person,
                        contact_method=lead.partner_profile.contact_method,
                        contact_channel=lead.partner_profile.contact_channel,
                        entity_type=lead.partner_profile.entity_type,
                        user_guid=lead.user_guid if hasattr(lead, 'user_guid') else None
                    )
                    
                    db_partner_profile = await self.lead_profile_service.create_lead_profile(
                        db, partner_profile_create
                    )
                    logger.info(f"Partner profile created: {db_partner_profile.guid}")
                    
                    # Create generated lead
                    generated_lead_create = PPLGeneratedLeadCreate(
                        partner_profile_guid=db_partner_profile.guid,
                        user_guid=lead.user_guid if hasattr(lead, 'user_guid') else db_partner_profile.guid,
                        market=lead.market,
                        city=lead.city,
                        source_agent=lead.source_agent,
                        key_insight=lead.ai_context.key_insight,
                        draft_message=lead.ai_context.draft_message,
                        notification_data=dashboard_notification,
                        status="pending"
                    )
                    
                    db_generated_lead = await self.generated_lead_service.create_generated_lead(
                        db, generated_lead_create
                    )
                    logger.info(f"Generated lead created: {db_generated_lead.guid}")
                    
                    # Update dashboard notification with database GUIDs
                    dashboard_notification["lead_id"] = str(db_generated_lead.guid)
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
