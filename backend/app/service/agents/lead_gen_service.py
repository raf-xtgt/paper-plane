"""
Lead Generation Pipeline Service - ADK Sequential Agent Orchestration.

This service orchestrates the Scout, Navigator, Researcher, and Strategist agents in sequence
to discover, extract contact information, enrich, and draft outreach messages for potential channel partners.
The pipeline executes asynchronously with timeout handling and comprehensive logging.
"""

import os
import logging
import asyncio
from typing import Optional
from datetime import datetime
from app.service.agents.scout.scout_agent import ScoutAgent
from app.service.agents.navigator.navigator_agent import NavigatorAgent
from app.service.agents.researcher.researcher_agent import ResearcherAgent
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
    ScrapedBusinessData, PageKeyFact
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
        self.pipeline_timeout = int(os.getenv("LEAD_GEN_TIMEOUT", "600"))  # 5 minutes default
        
        logger.info(
            f"Pipeline initialized - timeout: {self.pipeline_timeout}s, "
            f"agents: Scout, Navigator, Researcher, Strategist"
        )

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
            scout_start = datetime.utcnow()
            #
            # # Run Scout agent (now async) - returns ScrapedBusinessData
            # scraped_data = await self.scout.discover_partners(city, market, district)
            #
            scout_duration = (datetime.utcnow() - scout_start).total_seconds()
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
            
            valid_scraped_data  = [
                # ScrapedBusinessData(
                #     guid='043cd6bc-21ca-49c7-a068-34e301119b8b',
                #     org_name='Optimum Diagnostic Imaging',
                #     primary_contact='+1 973-521-5685',
                #     review_score='৪.৪',
                #     total_reviews='৯১',
                #     website_url='https://odinj.com/',
                #     address='243 Chestnut St'
                # ),
                # ScrapedBusinessData(
                #     guid='63d07ba8-e0b7-4e03-b020-c667289480e1',
                #     org_name='Newark Imaging Open MRI',
                #     primary_contact='+1 973-589-7777',
                #     review_score='৪.৭',
                #     total_reviews='৮৭',
                #     website_url='http://www.newarkimaging.com/',
                #     address='400 Delancy St Suite 108'
                # ),
                ScrapedBusinessData(
                    guid='8f6a2fd4-0f83-4429-9f2e-4b39b72f1dc1',
                    org_name='UIC Medical Centre - Dr. Saurabh Patel',
                    primary_contact='+1 973-344-2929',
                    review_score='৪.২',
                    total_reviews='৮০',
                    website_url='https://uicmedcentre.com/',
                    address='99 Madison St'
                ),
                # ScrapedBusinessData(
                #     guid='98065337-e837-4813-af60-47229e37a8e4',
                #     org_name="Children's Specialized Hospital Center – Newark",
                #     primary_contact='+1 888-244-5373',
                #     review_score='৪.৮',
                #     total_reviews='৪৩',
                #     website_url='https://www.rwjbh.org/our-locations/pediatric-outpatient-facilities/childrens-specialized-outpatient-center-at-newar/',
                #     address='182 Lyons Ave'
                # )
            ]
            print("valid_scraped_data")
            print(valid_scraped_data)

            # Run Navigator Agent (async) - use validated scraped_data from Scout
            # partner_contacts = await self.navigator.navigate_and_extract_batch(valid_scraped_data)
            
            navigator_duration = (datetime.utcnow() - navigator_start).total_seconds()

            print("partner_contacts")
            # print(partner_contacts)

            # Step 3: Researcher Agent - Enhance Navigator enrichments with additional details
            # logger.info(f"Step 3/4: Researcher Agent - Enhancing {len(partner_contacts)} Navigator enrichments")
            # partner_profiles = self.consolidate_partner_data(partner_contacts, valid_scraped_data)
            partner_profiles: List[PartnerProfile] = [
                PartnerProfile(
                    guid='8f6a2fd4-0f83-4429-9f2e-4b39b72f1dc1',
                    org_name='UIC Medical Centre - Dr. Saurabh Patel',
                    primary_contact='+1 973-344-2929',
                    review_score='৪.২',
                    total_reviews='৮০',
                    website_url='https://uicmedcentre.com/',
                    address='99 Madison St',
                    emails=['needhelp@gmail.com', 'info@gmail.com'],
                    phone_numbers=[
                        '(173) 219-3874', '(360) 327-6556', '(175) 095-8426',
                        '(447) 917-3040', '(176) 002-6547', '(173) 479-4092',
                        '(176) 002-6464', '(593) 861-7689', '(949) 857-3652',
                        '(176) 003-1715', '(684) 312-7335', '(174) 644-9509',
                        '(175) 975-8655', '(169) 117-8163', '(174) 399-8931',
                        '(945) 771-6465', '(100) 804-3490', '(172) 771-4275',
                        '(365) 343-1696', '(172) 927-2122', '(537) 166-6455',
                        '(174) 613-0462', '(171) 381-7949', '(176) 001-7303',
                        '(171) 405-5514', '(174) 341-2984', '(813) 763-4563',
                        '(095) 443-6142', '(217) 946-5330', '(973) 344-2929',
                        '(914) 138-6395', '(896) 708-5614', '(175) 345-4859',
                        '(171) 381-7617', '(221) 603-9277', '(521) 203-4282',
                        '(174) 776-2308', '(176) 002-6557', '(809) 642-7346',
                        '(361) 817-5920', '(000) 000-0006', '(179) 277-2137',
                        '(172) 125-0674', '(173) 075-9904', '(943) 578-1033'
                    ],
                    internal_urls=[
                        'https://uicmedcentre.com/about-us/',
                        'https://uicmedcentre.com/',
                        'https://uicmedcentre.com/contact-us/'
                    ],
                    external_urls=[
                        'https://uicmedcentre.com/about-us/',
                        'https://uicmedcentre.com/',
                        'https://uicmedcentre.com/contact-us/',
                        'https://www.facebook.com/UICmedical/',
                        'https://www.instagram.com/uicmedcentre/'
                    ],
                    entity_type='Medical Facility',
                    lead_phase='new',
                    key_facts=[]
                )
            ]

            print("partner_profiles")
            print(partner_profiles)

            # Researcher Agent: extract key facts from : markdown from content in internal url + markdown from content in external url
            # Strategist Agent: generate outreach template on three channels: phone, external and internal.
            researcher_start = datetime.utcnow()

            if not partner_profiles:
                logger.warning("Navigator Agent returned no partner profiles")
                return []

            # Run Researcher in executor - pass validated Navigator enrichments for enhancement
            loop = asyncio.get_event_loop()
            # final_enrichments = await loop.run_in_executor(
            #     None,
            #     self.researcher.enrich_partners_from_navigator,
            #     partner_profiles
            # )

            final_enrichments: List[PartnerProfile] = [
                PartnerProfile(
                    guid="8f6a2fd4-0f83-4429-9f2e-4b39b72f1dc1",
                    org_name="UIC Medical Centre - Dr. Saurabh Patel",
                    primary_contact="+1 973-344-2929",
                    review_score="৪.২",
                    total_reviews="৮০",
                    website_url="https://uicmedcentre.com/",
                    address="99 Madison St",
                    emails=[
                        "needhelp@gmail.com",
                        "info@gmail.com",
                    ],
                    phone_numbers=[
                        "(173) 219-3874", "(360) 327-6556", "(175) 095-8426",
                        "(447) 917-3040", "(176) 002-6547", "(173) 479-4092",
                        "(176) 002-6464", "(593) 861-7689", "(949) 857-3652",
                        "(176) 003-1715", "(684) 312-7335", "(174) 644-9509",
                        "(175) 975-8655", "(169) 117-8163", "(174) 399-8931",
                        "(945) 771-6465", "(100) 804-3490", "(172) 771-4275",
                        "(365) 343-1696", "(172) 927-2122", "(537) 166-6455",
                        "(174) 613-0462", "(171) 381-7949", "(176) 001-7303",
                        "(171) 405-5514", "(174) 341-2984", "(813) 763-4563",
                        "(095) 443-6142", "(217) 946-5330", "(973) 344-2929",
                        "(914) 138-6395", "(896) 708-5614", "(175) 345-4859",
                        "(171) 381-7617", "(221) 603-9277", "(521) 203-4282",
                        "(174) 776-2308", "(176) 002-6557", "(809) 642-7346",
                        "(361) 817-5920", "(000) 000-0006", "(179) 277-2137",
                        "(172) 125-0674", "(173) 075-9904", "(943) 578-1033",
                    ],
                    internal_urls=[
                        "https://uicmedcentre.com/about-us/",
                        "https://uicmedcentre.com/",
                        "https://uicmedcentre.com/contact-us/",
                    ],
                    external_urls=[
                        "https://uicmedcentre.com/about-us/",
                        "https://uicmedcentre.com/",
                        "https://uicmedcentre.com/contact-us/",
                        "https://www.facebook.com/UICmedical/",
                        "https://www.instagram.com/uicmedcentre/",
                    ],
                    entity_type="Medical Facility",
                    lead_phase="new",
                    key_facts=[
                        PageKeyFact(
                            page_url="https://uicmedcentre.com/",
                            markdown_content="<<FULL MARKDOWN OMITTED FOR BREVITY>>",
                            key_facts=[
                                "Specializes in walk-in USCIS Immigration Medical Exams and DOT physicals for commercial drivers.",
                                "Has over 15 years of experience serving the community in Newark, NJ.",
                                "Focuses on providing convenient and comprehensive healthcare for families, workers, and immigrants.",
                            ],
                        ),
                        PageKeyFact(
                            page_url="https://uicmedcentre.com/about-us/",
                            markdown_content="<<FULL MARKDOWN OMITTED FOR BREVITY>>",
                            key_facts=[
                                "The Medical Director, Dr. Saurabh Patel, has 21 years of experience in medical practice.",
                                "The center specializes in sports medicine, obesity/weight management, and occupational medicine, including DOT physicals.",
                                "Dr. Patel is multilingual, speaking English, Gujarati, and Portuguese.",
                            ],
                        ),
                    ],
                    outreach_draft_message=None,
                )
            ]
            researcher_duration = (datetime.utcnow() - researcher_start).total_seconds()
            
            # Step 4: Strategist Agent - Draft messages
            logger.info(f"Step 4/4: Strategist Agent - Drafting messages for {len(final_enrichments)} partners")
            strategist_start = datetime.utcnow()
            
            # Validate final enrichments before passing to Strategist Agent
            if not final_enrichments:
                logger.warning("Researcher Agent returned no final enrichments")
                return []

            # outreach = await loop.run_in_executor(
            #     None,
            #     self.strategist.generate_outreach_draft_message,
            #     final_enrichments,
            #     market,
            #     city
            # )

            outreach: List[PartnerProfile] = [
                PartnerProfile(
                    guid="8f6a2fd4-0f83-4429-9f2e-4b39b72f1dc1",
                    org_name="UIC Medical Centre - Dr. Saurabh Patel",
                    primary_contact="+1 973-344-2929",
                    review_score="৪.২",
                    total_reviews="৮০",
                    website_url="https://uicmedcentre.com/",
                    address="99 Madison St",
                    emails=[
                        "needhelp@gmail.com",
                        "info@gmail.com",
                    ],
                    phone_numbers=[
                        "(173) 219-3874", "(360) 327-6556", "(175) 095-8426",
                        "(447) 917-3040", "(176) 002-6547", "(173) 479-4092",
                        "(176) 002-6464", "(593) 861-7689", "(949) 857-3652",
                        "(176) 003-1715", "(684) 312-7335", "(174) 644-9509",
                        "(175) 975-8655", "(169) 117-8163", "(174) 399-8931",
                        "(945) 771-6465", "(100) 804-3490", "(172) 771-4275",
                        "(365) 343-1696", "(172) 927-2122", "(537) 166-6455",
                        "(174) 613-0462", "(171) 381-7949", "(176) 001-7303",
                        "(171) 405-5514", "(174) 341-2984", "(813) 763-4563",
                        "(095) 443-6142", "(217) 946-5330", "(973) 344-2929",
                        "(914) 138-6395", "(896) 708-5614", "(175) 345-4859",
                        "(171) 381-7617", "(221) 603-9277", "(521) 203-4282",
                        "(174) 776-2308", "(176) 002-6557", "(809) 642-7346",
                        "(361) 817-5920", "(000) 000-0006", "(179) 277-2137",
                        "(172) 125-0674", "(173) 075-9904", "(943) 578-1033",
                    ],
                    internal_urls=[
                        "https://uicmedcentre.com/about-us/",
                        "https://uicmedcentre.com/",
                        "https://uicmedcentre.com/contact-us/",
                    ],
                    external_urls=[
                        "https://uicmedcentre.com/about-us/",
                        "https://uicmedcentre.com/",
                        "https://uicmedcentre.com/contact-us/",
                        "https://www.facebook.com/UICmedical/",
                        "https://www.instagram.com/uicmedcentre/",
                    ],
                    entity_type="Medical Facility",
                    lead_phase="new",
                    key_facts=[
                        PageKeyFact(
                            page_url="https://uicmedcentre.com/",
                            markdown_content="<<FULL MARKDOWN OMITTED FOR BREVITY>>",
                            key_facts=[
                                "Specializes in walk-in USCIS Immigration Medical Exams and DOT physicals for commercial drivers.",
                                "Has over 15 years of experience serving the community in Newark, NJ.",
                                "Focuses on providing convenient and comprehensive healthcare for families, workers, and immigrants.",
                            ],
                        ),
                        PageKeyFact(
                            page_url="https://uicmedcentre.com/about-us/",
                            markdown_content="<<FULL MARKDOWN OMITTED FOR BREVITY>>",
                            key_facts=[
                                "The Medical Director, Dr. Saurabh Patel, has 21 years of experience in medical practice.",
                                "The center specializes in sports medicine, obesity/weight management, and occupational medicine, including DOT physicals.",
                                "Dr. Patel is multilingual, speaking English, Gujarati, and Portuguese.",
                            ],
                        ),
                    ],
                    outreach_draft_message=OutreachDraft(draft_message="Hi Dr. Patel, your center's specialization in USCIS Immigration Medical Exams in Newark really stands out. My work involves connecting medical tourism agencies with experienced partners like yourself, and I see a strong potential for collaboration. Are you open to a brief chat to explore this further?"),
                )
            ]
            strategist_duration = (datetime.utcnow() - strategist_start).total_seconds()
            logger.info(
                f"Strategist Agent complete - generated {len(lead_objects)} drafts "
                f"in {strategist_duration:.2f}s"
            )
            
            # Log pipeline summary
            total_duration = (datetime.utcnow() - start_time).total_seconds()
            logger.info(
                f"Pipeline execution complete - "
                f"city: {city}, market: {market}, "
                f"total_duration: {total_duration:.2f}s, "
                f"leads_generated: {len(lead_objects)}, "
                f"scout: {scout_duration:.2f}s, "
                f"navigator: {navigator_duration:.2f}s, "
                f"researcher: {researcher_duration:.2f}s, "
                f"strategist: {strategist_duration:.2f}s"
            )
            
            return lead_objects
            
        except asyncio.TimeoutError:
            duration = (datetime.utcnow() - start_time).total_seconds()
            logger.error(
                f"Pipeline timeout exceeded - "
                f"city: {city}, market: {market}, "
                f"timeout: {self.pipeline_timeout}s, "
                f"duration: {duration:.2f}s, "
                f"partial_results: {len(lead_objects)} leads"
            )
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


    def consolidate_partner_data(
        self, 
        contact_list: List[PartnerContact], 
        scraped_data_list: List[ScrapedBusinessData]
    ) -> List[PartnerProfile]:
        """
        Groups contact data by lead_guid, extracts unique contact info, and categorizes URLs
        into internal and external lists for consolidation into PartnerProfile objects.
        Populates inherited ScrapedBusinessData fields based on matching GUIDs.

        Args:
            contact_list: A list of PartnerContact objects.
            scraped_data_list: A list of ScrapedBusinessData objects to inherit from.

        Returns:
            A list of PartnerProfile objects with inherited ScrapedBusinessData fields.
        """

        # 1. Create a lookup dictionary for ScrapedBusinessData by GUID
        scraped_data_lookup: Dict[str, ScrapedBusinessData] = {
            data.guid: data for data in scraped_data_list
        }

        # 2. Grouping mechanism: Use defaultdict to map lead_guid to a dictionary
        #    that holds sets for automatic deduplication.
        grouped_data: Dict[str, Dict[str, Set[str]]] = defaultdict(lambda: {
            'emails': set(),
            'phone_numbers': set(),
            'internal_urls': set(),
            'external_urls': set(),
        })

        # Define social media names for categorization
        SOCIAL_MEDIA = {'Facebook', 'Instagram', 'Twitter', 'LinkedIn'}

        # 3. Process and categorize each contact record
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

        # 4. Create the final list of PartnerProfile objects
        final_profiles: List[PartnerProfile] = []

        for lead_guid, aggregated_data in grouped_data.items():
            # Get the corresponding ScrapedBusinessData for this GUID
            scraped_data = scraped_data_lookup.get(lead_guid)
            
            if scraped_data:
                # Create PartnerProfile inheriting from ScrapedBusinessData
                profile = PartnerProfile(
                    # Inherited fields from ScrapedBusinessData
                    guid=scraped_data.guid,
                    org_name=scraped_data.org_name,
                    primary_contact=scraped_data.primary_contact,
                    review_score=scraped_data.review_score,
                    total_reviews=scraped_data.total_reviews,
                    website_url=scraped_data.website_url,
                    address=scraped_data.address,
                    # Additional PartnerProfile fields
                    emails=list(aggregated_data['emails']) or None,
                    phone_numbers=list(aggregated_data['phone_numbers']) or None,
                    internal_urls=list(aggregated_data['internal_urls']) or None,
                    external_urls=list(aggregated_data['external_urls']) or None,
                    entity_type=self._determine_entity_type(scraped_data.org_name),
                    lead_phase="new",  # Default phase for new leads
                    key_facts=[],
                    outreach_draft_message=None,
                )
            else:
                # Fallback if no matching ScrapedBusinessData found
                logger.warning(f"No ScrapedBusinessData found for GUID: {lead_guid}")
                profile = PartnerProfile(
                    guid=lead_guid,
                    org_name="Unknown Organization",
                    emails=list(aggregated_data['emails']) or None,
                    phone_numbers=list(aggregated_data['phone_numbers']) or None,
                    internal_urls=list(aggregated_data['internal_urls']) or None,
                    external_urls=list(aggregated_data['external_urls']) or None,
                    entity_type="Unknown",
                    lead_phase="new",
                    key_facts=[],
                    outreach_draft_message=None,
                )
            
            final_profiles.append(profile)

        return final_profiles

    def _determine_entity_type(self, org_name: Optional[str]) -> str:
        """
        Determine entity type based on organization name.
        
        Args:
            org_name: Organization name to analyze
            
        Returns:
            Entity type classification
        """
        if not org_name:
            return "Unknown"
            
        name_lower = org_name.lower()
        
        if any(keyword in name_lower for keyword in ["school", "college", "university", "academy"]):
            return "Educational Institution"
        elif any(keyword in name_lower for keyword in ["hospital", "clinic", "medical", "diagnostic", "health"]):
            return "Medical Facility"
        elif any(keyword in name_lower for keyword in ["coaching", "training", "institute", "center"]):
            return "Training Center"
        else:
            return "Business"