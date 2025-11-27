"""
Kafka producer for lead_generated topic.

This module provides the LeadGenProducer class for publishing AI-discovered
leads to the "lead_generated" Kafka topic with retry logic and fallback handling.
"""

import json
import logging
import time
from pathlib import Path
from datetime import datetime
from typing import Optional
from app.model.lead_gen_model import LeadObject
from app.util.confluent.confluent_config import producer

logger = logging.getLogger("lead_gen_pipeline")


class LeadGenProducer:
    """
    Kafka producer for publishing lead generation results.
    
    This class handles formatting LeadObject instances into Kafka messages
    and publishing them to the "lead_generated" topic with retry logic
    and fallback queue support.
    
    Attributes:
        topic: Kafka topic name ("lead_generated")
        max_retries: Maximum number of publish attempts (default: 3)
        fallback_dir: Directory for fallback queue files
    """
    
    def __init__(self, topic: str = "lead_generated", max_retries: int = 3):
        """
        Initialize the LeadGenProducer.
        
        Args:
            topic: Kafka topic name (default: "lead_generated")
            max_retries: Maximum retry attempts (default: 3)
        """
        self.topic = topic
        self.max_retries = max_retries
        self.producer = producer
        
        # Setup fallback directory
        self.fallback_dir = Path("backend/app/util/confluent/fallback_queue")
        self.fallback_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"LeadGenProducer initialized for topic: {self.topic}")
    
    def format_message(self, lead: LeadObject) -> dict:
        """
        Format LeadObject into Kafka message schema.
        
        Converts a LeadObject Pydantic model into the standardized
        Kafka message format with nested data structure.
        
        Args:
            lead: LeadObject instance to format
            
        Returns:
            Dictionary containing formatted message with event_type,
            timestamp, and nested data fields
        """
        message = {
            "event_type": lead.event_type,
            "timestamp": lead.timestamp.isoformat(),
            "data": {
                "source_agent": lead.source_agent,
                "market": lead.market,
                "city": lead.city,
                "partner_profile": {
                    "name": lead.partner_profile.name,
                    "url": str(lead.partner_profile.url),
                    "contact_person": lead.partner_profile.contact_person,
                    "contact_method": lead.partner_profile.contact_method,
                    "entity_type": lead.partner_profile.entity_type
                },
                "ai_context": {
                    "key_insight": lead.ai_context.key_insight,
                    "draft_message": lead.ai_context.draft_message
                }
            }
        }
        
        return message
    
    def _delivery_callback(self, err, msg, lead_name: str):
        """
        Callback for Kafka delivery reports.
        
        Args:
            err: Error object if delivery failed
            msg: Message object if delivery succeeded
            lead_name: Partner name for logging context
        """
        if err is not None:
            logger.error(f"Kafka delivery failed for lead '{lead_name}': {err}")
        else:
            logger.info(
                f"Lead '{lead_name}' delivered to {msg.topic()} "
                f"[partition {msg.partition()}]"
            )
    
    async def publish_lead(self, lead: LeadObject) -> bool:
        """
        Publish lead to Kafka with retry logic and fallback queue.
        
        Attempts to publish the lead to Kafka with exponential backoff
        retry logic. If all retries fail, writes the lead to a fallback
        file queue for manual recovery.
        
        Args:
            lead: LeadObject instance to publish
            
        Returns:
            True if published successfully, False if all retries failed
        """
        partner_name = lead.partner_profile.name
        message = self.format_message(lead)
        
        for attempt in range(1, self.max_retries + 1):
            try:
                logger.debug(
                    f"Publishing lead '{partner_name}' to {self.topic} "
                    f"(attempt {attempt}/{self.max_retries})"
                )
                
                # Produce message to Kafka
                self.producer.produce(
                    self.topic,
                    json.dumps(message).encode('utf-8'),
                    callback=lambda err, msg: self._delivery_callback(
                        err, msg, partner_name
                    )
                )
                
                # Trigger callbacks and wait for delivery
                self.producer.poll(1)
                
                logger.info(
                    f"Lead '{partner_name}' published successfully to {self.topic}"
                )
                return True
                
            except Exception as e:
                logger.warning(
                    f"Kafka publish attempt {attempt}/{self.max_retries} failed "
                    f"for lead '{partner_name}': {e}"
                )
                
                if attempt < self.max_retries:
                    # Exponential backoff: 1s, 2s, 4s
                    backoff_time = 2 ** (attempt - 1)
                    logger.debug(f"Retrying in {backoff_time} seconds...")
                    time.sleep(backoff_time)
                else:
                    # All retries exhausted
                    logger.error(
                        f"All {self.max_retries} publish attempts failed for "
                        f"lead '{partner_name}'. Writing to fallback queue."
                    )
                    self._write_to_fallback(lead, message)
                    return False
        
        return False
    
    def _write_to_fallback(self, lead: LeadObject, message: dict):
        """
        Write failed lead to fallback file queue.
        
        Creates a timestamped JSON file in the fallback directory
        containing the full lead data for manual recovery.
        
        Args:
            lead: LeadObject that failed to publish
            message: Formatted Kafka message
        """
        try:
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S_%f")
            partner_slug = lead.partner_profile.name.replace(" ", "_").lower()
            filename = f"lead_{timestamp}_{partner_slug}.json"
            filepath = self.fallback_dir / filename
            
            # Write full lead data to file
            with open(filepath, 'w') as f:
                json.dump(message, f, indent=2)
            
            logger.info(
                f"Lead '{lead.partner_profile.name}' written to fallback queue: "
                f"{filepath}"
            )
            
        except Exception as e:
            logger.error(
                f"Failed to write lead '{lead.partner_profile.name}' to "
                f"fallback queue: {e}. Full lead data: {message}"
            )
    
    def flush(self):
        """
        Flush any pending messages in the producer queue.
        
        Should be called before application shutdown to ensure
        all messages are delivered.
        """
        logger.debug("Flushing Kafka producer...")
        self.producer.flush()
        logger.info("Kafka producer flushed successfully")
