"""
Lead Generation Pipeline Service - ADK Sequential Agent Orchestration.

This service orchestrates the Scout, Navigator, Researcher, and Strategist agents in sequence
to discover, extract contact information, enrich, and draft outreach messages for potential channel partners.
The pipeline executes asynchronously with timeout handling and comprehensive logging.
"""

import os
import logging
import asyncio
from datetime import datetime
from app.service.agents.scout.scout_agent import ScoutAgent
from app.service.agents.navigator.navigator_agent import NavigatorAgent
from app.service.agents.researcher_agent import ResearcherAgent
from app.service.agents.strategist_agent import StrategistAgent
from app.util.confluent.lead_gen_producer import LeadGenProducer
from app.model.lead_gen_model import (
    LeadObject,
    PartnerProfile,
    PartnerContact,
    AIContext,
    PartnerDiscovery,
    PartnerEnrichment,
    OutreachDraft,
    ScrapedBusinessData
)
from typing import List, Dict, Set
from collections import defaultdict

# Configure logging
logger = logging.getLogger("lead_gen_pipeline")


class LeadGenPipeline:
    """
    Lead Generation Pipeline orchestrating Scout, Navigator, Researcher, and Strategist agents.
    
    This class implements the ADK sequential agent pattern, executing agents in order:
    1. Scout Agent: Discovers 3-10 potential partners
    2. Navigator Agent: Extracts decision-maker contact information from partner websites
    3. Researcher Agent: Enriches each partner with additional contact details
    4. Strategist Agent: Generates personalized outreach messages
    
    The pipeline includes timeout handling, error recovery, and comprehensive logging.
    """
    
    def __init__(self):
        """Initialize the pipeline with all four agents."""
        logger.info("Initializing Lead Generation Pipeline")
        
        # Initialize agents
        self.scout = ScoutAgent()
        self.navigator = NavigatorAgent()
        self.researcher = ResearcherAgent()
        self.strategist = StrategistAgent()
        
        # Initialize Kafka producer
        self.lead_producer = LeadGenProducer()
        
        # Load configuration
        self.pipeline_timeout = int(os.getenv("LEAD_GEN_TIMEOUT", "300"))  # 5 minutes default
        
        logger.info(
            f"Pipeline initialized - timeout: {self.pipeline_timeout}s, "
            f"agents: Scout, Navigator, Researcher, Strategist"
        )
    
    def _convert_scraped_data_to_discoveries(
        self, 
        scraped_data: List[ScrapedBusinessData]
    ) -> List[PartnerDiscovery]:
        """
        Convert ScrapedBusinessData objects to PartnerDiscovery for Strategist Agent.
        
        Args:
            scraped_data: List of ScrapedBusinessData from Scout Agent
            
        Returns:
            List of PartnerDiscovery for Strategist Agent processing
        """
        discoveries = []
        for data in scraped_data:
            # Determine entity type based on org_name or use default
            entity_type = "Business"  # Default type
            if data.org_name:
                name_lower = data.org_name.lower()
                if any(keyword in name_lower for keyword in ["school", "college", "university", "academy"]):
                    entity_type = "Educational Institution"
                elif any(keyword in name_lower for keyword in ["hospital", "clinic", "medical", "diagnostic", "health"]):
                    entity_type = "Medical Facility"
                elif any(keyword in name_lower for keyword in ["coaching", "training", "institute", "center"]):
                    entity_type = "Training Center"
            
            discoveries.append(PartnerDiscovery(
                entity_name=data.org_name or "Unknown Business",
                website_url=data.website_url,
                type=entity_type
            ))
        return discoveries
    

    def _format_lead_object(
        self,
        discovery: PartnerDiscovery,
        enrichment: PartnerEnrichment,
        draft: OutreachDraft,
        market: str,
        city: str
    ) -> LeadObject:
        """
        Format agent outputs into a LeadObject for Kafka publishing.
        
        Args:
            discovery: Partner discovery from Scout Agent
            enrichment: Partner enrichment from Researcher Agent
            draft: Outreach draft from Strategist Agent
            market: Market vertical
            city: Target city
            
        Returns:
            LeadObject ready for Kafka publishing
        """
        partner_profile = PartnerProfile(
            name=discovery.entity_name,
            url=enrichment.verified_url,
            contact_person=enrichment.decision_maker,
            contact_method=enrichment.contact_info,
            contact_channel=enrichment.contact_channel,
            entity_type=discovery.type
        )
        
        ai_context = AIContext(
            key_insight=enrichment.key_fact,
            draft_message=draft.draft_message
        )
        
        lead_object = LeadObject(
            event_type="lead_discovered",
            timestamp=datetime.utcnow(),
            source_agent="adk_v1",
            market=market,
            city=city,
            partner_profile=partner_profile,
            ai_context=ai_context
        )
        
        return lead_object
    
    async def execute(self, city: str, market: str, district:str) -> List[LeadObject]:
        """
        Execute the full pipeline synchronously and return Lead Objects.
        
        This method runs all four agents in sequence:
        1. Scout discovers partners
        2. Navigator extracts decision-maker contact information from partner websites
        3. Researcher enriches each partner with additional contact details
        4. Strategist drafts messages for each partner
        
        Args:
            city: Target city name
            market: Market vertical (Student Recruitment or Medical Tourism)
            district: Target district name
            
        Returns:
            List of LeadObject instances ready for Kafka publishing
            
        Raises:
            asyncio.TimeoutError: If pipeline exceeds timeout limit
        """
        logger.info(
            f"Starting pipeline execution - district:{district}, city: {city}, market: {market}, "
            f"timeout: {self.pipeline_timeout}s"
        )
        
        start_time = datetime.utcnow()
        lead_objects = []
        
        try:
            # Step 1: Scout Agent - Discover partners
            # logger.info("Step 1/4: Scout Agent - Discovering partners")
            # scout_start = datetime.utcnow()
            #
            # # Run Scout agent (now async) - returns ScrapedBusinessData
            # scraped_data = await self.scout.discover_partners(city, market, district)
            #
            # scout_duration = (datetime.utcnow() - scout_start).total_seconds()
            # logger.info(
            #     f"Scout Agent complete - found {len(scraped_data)} partners "
            #     f"in {scout_duration:.2f}s"
            # )
            #
            # if not scraped_data:
            #     logger.warning(
            #         f"Scout Agent returned no partners - city: {city}, market: {market}. "
            #         f"Pipeline complete with empty results."
            #     )
            #     return []

            
            # Step 2: Navigator Agent - Extract contact information from websites
            # logger.info(f"Step 2/4: Navigator Agent - Extracting contact info from {len(scraped_data)} partner websites")
            navigator_start = datetime.utcnow()
            
            # # Validate scraped data before passing to Navigator Agent
            # valid_scraped_data = [
            #     data for data in scraped_data
            #     if data.website_url and ("http" in str(data.website_url) or "https" in str(data.website_url))
            # ]
            # if len(valid_scraped_data) != len(scraped_data):
            #     logger.warning(
            #         f"Filtered out {len(scraped_data) - len(valid_scraped_data)} partners without valid website URLs"
            #     )
            #
            # if not valid_scraped_data:
            #     logger.warning("No partners with valid website URLs found after validation")
            #     return []
            
            valid_scraped_data = [
                    ScrapedBusinessData(
                        guid="25fea789-55f1-43b6-8a1a-7451ad233d28",
                        org_name="UIC Medical Centre - Dr. Saurabh Patel",
                        primary_contact="+1 973-344-2929",
                        review_score="৪.২",
                        total_reviews="৮০",
                        website_url="https://uicmedcentre.com/",
                        address="99 Madison St",
                    ),
                    ScrapedBusinessData(
                        guid="59fa8bf0-6ce5-4779-ad02-ddc387285561",
                        org_name="Newark Imaging Open MRI",
                        primary_contact="+1 973-589-7777",
                        review_score="৪.৭",
                        total_reviews="৮৭",
                        website_url="http://www.newarkimaging.com/",
                        address="400 Delancy St Suite 108",
                    )
                ]
            # print("valid_scraped_data")
            # print(valid_scraped_data)

            # Run Navigator Agent (async) - use validated scraped_data from Scout
            partner_contacts = await self.navigator.navigate_and_extract_batch(valid_scraped_data)
            
            navigator_duration = (datetime.utcnow() - navigator_start).total_seconds()

            print("partner_contacts")
            print(partner_contacts)

            # Step 3: Researcher Agent - Enhance Navigator enrichments with additional details
            logger.info(f"Step 3/4: Researcher Agent - Enhancing {len(partner_contacts)} Navigator enrichments")
            partner_profiles = self.consolidate_partner_data(partner_contacts)

        #     researcher_start = datetime.utcnow()
            
        #     # Validate Navigator enrichments before passing to Researcher Agent
        #     if not navigator_enrichments:
        #         logger.warning("Navigator Agent returned no enrichments")
        #         return []
            
        #     # Ensure all Navigator enrichments have valid URLs
        #     valid_navigator_enrichments = [
        #         e for e in navigator_enrichments 
        #         if e.verified_url and str(e.verified_url).startswith(('http://', 'https://'))
        #     ]
            
        #     if len(valid_navigator_enrichments) != len(navigator_enrichments):
        #         logger.warning(
        #             f"Filtered out {len(navigator_enrichments) - len(valid_navigator_enrichments)} "
        #             f"Navigator enrichments with invalid URLs"
        #         )
            
        #     if not valid_navigator_enrichments:
        #         logger.warning("No valid Navigator enrichments found after validation")
        #         return []
            
        #     # Run Researcher in executor - pass validated Navigator enrichments for enhancement
        #     loop = asyncio.get_event_loop()
        #     final_enrichments = await loop.run_in_executor(
        #         None,
        #         self.researcher.enrich_partners_from_navigator,
        #         valid_navigator_enrichments
        #     )
            
        #     researcher_duration = (datetime.utcnow() - researcher_start).total_seconds()
        #     complete_count = sum(1 for e in final_enrichments if e.status == "complete")
        #     logger.info(
        #         f"Researcher Agent complete - {complete_count}/{len(final_enrichments)} complete "
        #         f"in {researcher_duration:.2f}s"
        #     )
            
        #     # Step 4: Strategist Agent - Draft messages
        #     logger.info(f"Step 4/4: Strategist Agent - Drafting messages for {len(final_enrichments)} partners")
        #     strategist_start = datetime.utcnow()
            
        #     # Validate final enrichments before passing to Strategist Agent
        #     if not final_enrichments:
        #         logger.warning("Researcher Agent returned no final enrichments")
        #         return []
            
        #     # Convert valid scraped data back to discoveries for Strategist Agent
        #     discoveries = self._convert_scraped_data_to_discoveries(valid_scraped_data)
            
        #     # Ensure discoveries and enrichments lists are aligned
        #     min_length = min(len(discoveries), len(final_enrichments))
        #     if len(discoveries) != len(final_enrichments):
        #         logger.warning(
        #             f"Mismatched list lengths: {len(discoveries)} discoveries vs {len(final_enrichments)} enrichments. "
        #             f"Processing first {min_length} items."
        #         )
            
        #     # Process each partner through Strategist
        #     for i in range(min_length):
        #         discovery = discoveries[i]
        #         enrichment = final_enrichments[i]
        #         try:
        #             # Validate individual partner data before processing
        #             if not discovery.entity_name or not enrichment.verified_url:
        #                 logger.warning(
        #                     f"Skipping partner with incomplete data - "
        #                     f"entity_name: {discovery.entity_name}, url: {enrichment.verified_url}"
        #                 )
        #                 continue
                    
        #             # Run Strategist in executor
        #             draft = await loop.run_in_executor(
        #                 None,
        #                 self.strategist.draft_message,
        #                 discovery,
        #                 enrichment,
        #                 market,
        #                 city
        #             )
                    
        #             # Validate draft before creating lead object
        #             if not draft or not draft.draft_message:
        #                 logger.warning(f"Strategist returned empty draft for {discovery.entity_name}")
        #                 continue
                    
        #             # Format into LeadObject
        #             lead_object = self._format_lead_object(
        #                 discovery,
        #                 enrichment,
        #                 draft,
        #                 market,
        #                 city
        #             )
                    
        #             lead_objects.append(lead_object)
                    
        #             logger.debug(
        #                 f"Lead object created for {discovery.entity_name} - "
        #                 f"status: {enrichment.status}"
        #             )
                    
        #         except Exception as e:
        #             logger.error(
        #                 f"Failed to process partner {discovery.entity_name} - "
        #                 f"Error: {str(e)} - Skipping this partner",
        #                 exc_info=True
        #             )
        #             continue
            
        #     strategist_duration = (datetime.utcnow() - strategist_start).total_seconds()
        #     logger.info(
        #         f"Strategist Agent complete - generated {len(lead_objects)} drafts "
        #         f"in {strategist_duration:.2f}s"
        #     )
            
        #     # Log pipeline summary
        #     total_duration = (datetime.utcnow() - start_time).total_seconds()
        #     logger.info(
        #         f"Pipeline execution complete - "
        #         f"city: {city}, market: {market}, "
        #         f"total_duration: {total_duration:.2f}s, "
        #         f"leads_generated: {len(lead_objects)}, "
        #         f"scout: {scout_duration:.2f}s, "
        #         f"navigator: {navigator_duration:.2f}s, "
        #         f"researcher: {researcher_duration:.2f}s, "
        #         f"strategist: {strategist_duration:.2f}s"
        #     )
            
        #     return lead_objects
            
        # except asyncio.TimeoutError:
        #     duration = (datetime.utcnow() - start_time).total_seconds()
        #     logger.error(
        #         f"Pipeline timeout exceeded - "
        #         f"city: {city}, market: {market}, "
        #         f"timeout: {self.pipeline_timeout}s, "
        #         f"duration: {duration:.2f}s, "
        #         f"partial_results: {len(lead_objects)} leads"
        #     )
            # Return partial results if any
            return lead_objects
            
        except Exception as e:
            duration = (datetime.utcnow() - start_time).total_seconds()
            logger.error(
                f"Pipeline execution failed - "
                f"city: {city}, market: {market}, "
                f"duration: {duration:.2f}s, "
                f"error: {str(e)}",
                exc_info=True
            )
            # Return partial results if any
            return lead_objects
    
    async def run_async(self, job_id: str, city: str, market: str, district:str):
        """
        Background task wrapper for async pipeline execution.
        
        This method wraps the execute() method with timeout handling and
        triggers Kafka publishing upon completion. It's designed to be
        called as a background task from the FastAPI endpoint.
        
        Args:
            job_id: Unique job identifier for tracking
            city: Target city name
            market: Market vertical
        """
        logger.info(
            f"Background pipeline started - "
            f"job_id: {job_id}, city: {city}, market: {market}"
        )
        
        start_time = datetime.utcnow()
        
        try:
            # Execute pipeline with timeout
            lead_objects = await asyncio.wait_for(
                self.execute(city, market, district),
                timeout=self.pipeline_timeout
            )
            
            duration = (datetime.utcnow() - start_time).total_seconds()
            
            if not lead_objects:
                logger.warning(
                    f"Pipeline completed with no leads - "
                    f"job_id: {job_id}, city: {city}, market: {market}, "
                    f"duration: {duration:.2f}s"
                )
                return
            
            logger.info(
                f"Pipeline completed successfully - "
                f"job_id: {job_id}, city: {city}, market: {market}, "
                f"leads: {len(lead_objects)}, duration: {duration:.2f}s"
            )
            
            # Publish leads to Kafka
            logger.info(
                f"Publishing {len(lead_objects)} leads to Kafka - "
                f"job_id: {job_id}, topic: lead_generated"
            )
            
            publish_start = datetime.utcnow()
            success_count = 0
            failure_count = 0
            
            for lead in lead_objects:
                try:
                    published = await self.lead_producer.publish_lead(lead)
                    if published:
                        success_count += 1
                    else:
                        failure_count += 1
                except Exception as e:
                    logger.error(
                        f"Failed to publish lead '{lead.partner_profile.name}' - "
                        f"job_id: {job_id}, error: {str(e)}",
                        exc_info=True
                    )
                    failure_count += 1
            
            # Flush producer to ensure all messages are sent
            self.lead_producer.flush()
            
            publish_duration = (datetime.utcnow() - publish_start).total_seconds()
            
            logger.info(
                f"Kafka publishing complete - "
                f"job_id: {job_id}, "
                f"total: {len(lead_objects)}, "
                f"success: {success_count}, "
                f"failed: {failure_count}, "
                f"duration: {publish_duration:.2f}s"
            )
            
        except asyncio.TimeoutError:
            duration = (datetime.utcnow() - start_time).total_seconds()
            logger.error(
                f"Pipeline timeout in background task - "
                f"job_id: {job_id}, city: {city}, market: {market}, "
                f"timeout: {self.pipeline_timeout}s, duration: {duration:.2f}s"
            )
            
        except Exception as e:
            duration = (datetime.utcnow() - start_time).total_seconds()
            logger.error(
                f"Pipeline failed in background task - "
                f"job_id: {job_id}, city: {city}, market: {market}, "
                f"duration: {duration:.2f}s, error: {str(e)}",
                exc_info=True
            )


    def consolidate_partner_data(self, contact_list: List[PartnerContact]) -> List[PartnerProfile]:
        """
        Groups contact data by lead_guid, extracts unique contact info, and categorizes URLs
        into internal and external lists for consolidation into PartnerProfile objects.

        Args:
            contact_list: A list of PartnerContact objects.

        Returns:
            A list of partially filled PartnerProfile objects, one for each unique lead_guid.
        """

        # 1. Grouping mechanism: Use defaultdict to map lead_guid to a dictionary
        #    that holds sets for automatic deduplication.
        grouped_data: Dict[str, Dict[str, Set[str]]] = defaultdict(lambda: {
            'emails': set(),
            'phone_numbers': set(),
            'internal_urls': set(),
            'external_urls': set(),
        })

        # Define social media names for categorization
        SOCIAL_MEDIA = {'Facebook', 'Instagram', 'Twitter', 'LinkedIn'}

        # 2. Process and categorize each contact record
        for contact in contact_list:
            guid = contact.lead_guid
            data_sets = grouped_data[guid] # Get the sets for this lead_guid

            # Categorize contact_info
            if contact.name == 'Phone':
                data_sets['phone_numbers'].add(contact.contact_info)
            elif contact.name == 'Email':
                data_sets['emails'].add(contact.contact_info)

            # Categorize URL
            if contact.name in SOCIAL_MEDIA:
                # External URL (Social Media)
                data_sets['external_urls'].add(contact.url)
                # You might also want to add the social media contact_info (URL) here
                data_sets['external_urls'].add(contact.contact_info)
            else:
                # Internal URL (or non-social media external link)
                data_sets['internal_urls'].add(contact.url)

        # 3. Create the final list of PartnerProfile objects
        final_profiles: List[PartnerProfile] = []

        for lead_guid, aggregated_data in grouped_data.items():
            # Note: We are creating a partial PartnerProfile here.
            # Required fields like 'org_name' and 'entity_type' are left as placeholder
            # strings since the input data doesn't provide them.

            profile = PartnerProfile(
                guid=lead_guid,
                emails=list(aggregated_data['emails']) or None,
                phone_numbers=list(aggregated_data['phone_numbers']) or None,
                internal_urls=list(aggregated_data['internal_urls']) or None,
                external_urls=list(aggregated_data['external_urls']) or None,
                # Placeholder values for required fields not in input list
                org_name="UIC Medical Centre (Placeholder)",
                entity_type="Medical/Clinic (Placeholder)"
            )
            final_profiles.append(profile)

        return final_profiles