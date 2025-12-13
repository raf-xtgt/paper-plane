"""
Navigator Web Crawler V2 - Simplified systematic contact extraction.

This module implements a streamlined approach to web crawling that focuses on
comprehensive contact information extraction without complex relevance filtering.
The crawler systematically scans base pages and key navigation pages to extract
all available contact information.
"""

import logging
import asyncio
import os
import re
from typing import List, Optional, Dict, Any, Tuple
from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig
from urllib.parse import urljoin, urlparse

# Configure logging
logger = logging.getLogger("lead_gen_pipeline.navigator.webcrawler_v2")

# Ensure logger is properly configured
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)


class NavigatorWebCrawlerV2:
    """
    Simplified web crawler focused on systematic contact extraction.
    
    This V2 implementation follows a streamlined approach:
    1. Scan entire base page for links and contact information
    2. Identify key navigation pages (About, Contact, Team, etc.)
    3. Systematically crawl each navigation page
    4. Extract ALL contact information without relevance filtering
    5. Generate structured markdown following specified schema
    
    Features:
    - Comprehensive contact extraction (emails, phones, social media)
    - Systematic navigation page discovery
    - No complex dynamic content handling
    - All contact information treated as relevant
    """
    
    def __init__(self, page_timeout: int = 60):
        """
        Initialize NavigatorWebCrawlerV2 with simplified configuration.
        
        Implements Requirements 1.1, 7.1:
        - Initialize basic Crawl4AI AsyncWebCrawler with minimal settings
        - Set up page timeout and retry configuration
        - Create logging setup for systematic contact extraction
        
        Args:
            page_timeout: Timeout for page loading in seconds (default: 60)
        """
        # Basic configuration parameters
        self.page_timeout = page_timeout
        self.max_retries = 3  # Fixed retry count for simplicity
        
        # Minimal Crawl4AI configuration from environment
        self.headless = os.getenv("CRAWL4AI_HEADLESS", "true").lower() == "true"
        self.javascript_enabled = os.getenv("CRAWL4AI_JAVASCRIPT", "true").lower() == "true"
        
        # Target navigation pages for systematic discovery
        self.target_navigation_keywords = [
            "about", "about us", "contact", "contact us", 
            "events", "team", "staff", "leadership"
        ]
        
        # Initialize contact extractor component
        self.contact_extractor = ContactExtractor()
        
        # Setup systematic contact extraction logging
        logger.info(
            f"NavigatorWebCrawlerV2 initialized with simplified configuration - "
            f"timeout: {self.page_timeout}s, retries: {self.max_retries}, "
            f"headless: {self.headless}, javascript: {self.javascript_enabled}"
        )
        logger.debug(f"Target navigation keywords: {self.target_navigation_keywords}")
    
    async def crawl_and_extract_contacts(
        self, 
        website_url: str, 
        entity_name: str
    ) -> str:
        """
        Main crawling method that implements the systematic V2 approach.
        
        Process:
        1. Scan base page for links and contact information
        2. Discover navigation pages in header/footer
        3. Crawl each navigation page systematically
        4. Generate combined markdown with all contact information
        
        Args:
            website_url: Base website URL to crawl
            entity_name: Name of entity for logging
            
        Returns:
            Combined markdown with all extracted contact information
        """
        logger.info(f"Starting V2 systematic crawl for {entity_name} at {website_url}")
        
        try:
            # Step 1: Scan base page
            base_page_data = await self._scan_base_page(website_url)
            
            if not base_page_data:
                logger.warning(f"Failed to scan base page for {entity_name}")
                return self._create_fallback_markdown(website_url, entity_name)
            
            # Step 2: Find navigation pages
            navigation_pages = self._find_navigation_pages(base_page_data["links"])
            logger.info(f"Found {len(navigation_pages)} navigation pages for {entity_name}")
            
            # Step 3: Crawl navigation pages
            all_contacts = base_page_data["contact_info"].copy()
            
            for nav_url in navigation_pages:
                nav_data = await self._crawl_navigation_page(nav_url)
                if nav_data and nav_data["contact_info"]:
                    all_contacts.extend(nav_data["contact_info"])
                    logger.debug(f"Extracted {len(nav_data['contact_info'])} contacts from {nav_url}")
            
            # Step 4: Generate structured markdown
            final_markdown = self._generate_contact_markdown(all_contacts, entity_name, website_url)
            
            logger.info(f"V2 crawl completed for {entity_name}: {len(all_contacts)} total contacts extracted")
            return final_markdown
            
        except Exception as e:
            logger.error(f"V2 crawl failed for {entity_name}: {e}")
            return self._create_fallback_markdown(website_url, entity_name)
    
    async def _scan_base_page(self, url: str) -> Optional[Dict[str, Any]]:
        """
        Scan entire base page for links and contact information.
        
        Args:
            url: Base page URL to scan
            
        Returns:
            Dictionary with links, contact_info, and content_markdown
        """
        logger.debug(f"Scanning base page: {url}")
        
        try:
            # Configure crawler for base page
            crawler = await self._create_crawler()
            if not crawler:
                return None
            
            # Crawl base page
            result = await crawler.arun(
                url=url,
                config=self._get_crawler_config()
            )
            
            if not result or not result.success:
                logger.warning(f"Base page crawl failed: {getattr(result, 'error_message', 'Unknown error')}")
                return None
            
            # Extract links
            links = self._extract_links(result)
            
            # Extract contact information
            contact_info = self._extract_contact_information(result.markdown or "")
            
            logger.debug(f"Base page scan complete: {len(links)} links, {len(contact_info)} contacts")
            
            return {
                "links": links,
                "contact_info": contact_info,
                "content_markdown": result.markdown or ""
            }
            
        except Exception as e:
            logger.error(f"Error scanning base page {url}: {e}")
            return None
    
    def _find_navigation_pages(self, links: List[str]) -> List[str]:
        """
        Find About/Contact/Team pages in navigation.
        
        Search order: Header navigation first, then footer if needed.
        Target pages: "About", "About Us", "Contact", "Contact Us", "Events", "Team"
        
        Args:
            links: List of all links found on base page
            
        Returns:
            List of navigation page URLs to crawl
        """
        navigation_pages = []
        processed_urls = set()
        
        logger.debug(f"Searching for navigation pages in {len(links)} links")
        
        for link in links:
            if link in processed_urls:
                continue
            processed_urls.add(link)
            
            # Skip external links and non-web protocols
            if self._should_skip_link(link):
                continue
            
            # Check if link matches target navigation pages
            link_lower = link.lower()
            for target_page in self.target_pages:
                if target_page.replace(" ", "") in link_lower or target_page.replace(" ", "-") in link_lower:
                    navigation_pages.append(link)
                    logger.debug(f"Found navigation page: {link} (matches '{target_page}')")
                    break
        
        # Remove duplicates while preserving order
        unique_pages = []
        seen = set()
        for page in navigation_pages:
            if page not in seen:
                unique_pages.append(page)
                seen.add(page)
        
        logger.info(f"Identified {len(unique_pages)} navigation pages to crawl")
        return unique_pages
    
    async def _crawl_navigation_page(self, url: str) -> Optional[Dict[str, Any]]:
        """
        Crawl individual navigation page and extract contact info.
        
        Args:
            url: Navigation page URL to crawl
            
        Returns:
            Dictionary with contact_info and content_markdown
        """
        logger.debug(f"Crawling navigation page: {url}")
        
        try:
            # Configure crawler for navigation page
            crawler = await self._create_crawler()
            if not crawler:
                return None
            
            # Crawl navigation page with timeout
            result = await asyncio.wait_for(
                crawler.arun(url=url, config=self._get_crawler_config()),
                timeout=self.page_timeout
            )
            
            if not result or not result.success:
                logger.warning(f"Navigation page crawl failed for {url}: {getattr(result, 'error_message', 'Unknown error')}")
                return None
            
            # Extract contact information
            contact_info = self._extract_contact_information(result.markdown or "")
            
            logger.debug(f"Navigation page crawl complete for {url}: {len(contact_info)} contacts")
            
            return {
                "contact_info": contact_info,
                "content_markdown": result.markdown or ""
            }
            
        except asyncio.TimeoutError:
            logger.warning(f"Timeout crawling navigation page: {url}")
            return None
        except Exception as e:
            logger.error(f"Error crawling navigation page {url}: {e}")
            return None
    
    def _extract_contact_information(self, content: str) -> List[Dict[str, Any]]:
        """
        Extract all contact information from page content.
        
        Extracts:
        - Email addresses (including mailto links)
        - Phone numbers (including tel links)  
        - Social media handles (Facebook, LinkedIn, WhatsApp, Instagram)
        - Names associated with contact information
        
        Args:
            content: Page content to extract contacts from
            
        Returns:
            List of contact dictionaries with name, contact, and type
        """
        if not content:
            return []
        
        contacts = []
        
        # Extract emails
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        emails = re.findall(email_pattern, content)
        
        for email in emails:
            # Try to find associated name
            name = self._find_associated_name(content, email)
            contacts.append({
                "decision_maker": name,
                "contact_info": email,
                "contact_channel": "Email"
            })
        
        # Extract phone numbers
        phone_pattern = r'(\+?1?[-.\s]?)?\(?[0-9]{3}\)?[-.\s]?[0-9]{3}[-.\s]?[0-9]{4}'
        phones = re.findall(phone_pattern, content)
        
        for phone_match in phones:
            phone = ''.join(phone_match) if isinstance(phone_match, tuple) else phone_match
            phone = phone.strip()
            if len(phone) >= 10:  # Valid phone number length
                # Try to find associated name
                name = self._find_associated_name(content, phone)
                contacts.append({
                    "decision_maker": name,
                    "contact_info": phone,
                    "contact_channel": "PhoneNo"
                })
        
        # Extract social media handles
        social_patterns = {
            "facebook.com": "Messenger",
            "linkedin.com": "Others",
            "instagram.com": "Instagram",
            "whatsapp.com": "WhatsApp",
            "wa.me": "WhatsApp"
        }
        
        for domain, channel in social_patterns.items():
            pattern = rf'https?://(?:www\.)?{re.escape(domain)}/[^\s<>"\']*'
            matches = re.findall(pattern, content, re.IGNORECASE)
            
            for match in matches:
                # Try to find associated name
                name = self._find_associated_name(content, match)
                contacts.append({
                    "decision_maker": name,
                    "contact_info": match,
                    "contact_channel": channel
                })
        
        logger.debug(f"Extracted {len(contacts)} contact items from content")
        return contacts
    
    def _find_associated_name(self, content: str, contact_info: str) -> Optional[str]:
        """
        Find names associated with contact information using proximity analysis.
        
        Args:
            content: Full page content
            contact_info: Contact information to find name for
            
        Returns:
            Associated name if found, None otherwise
        """
        # Simple proximity-based name extraction
        # Look for names within 100 characters before the contact info
        
        contact_pos = content.find(contact_info)
        if contact_pos == -1:
            return None
        
        # Extract text before contact info
        start_pos = max(0, contact_pos - 100)
        context = content[start_pos:contact_pos]
        
        # Look for name patterns (First Last)
        name_pattern = r'\b([A-Z][a-z]+\s+[A-Z][a-z]+)\b'
        names = re.findall(name_pattern, context)
        
        if names:
            # Return the last (closest) name found
            return names[-1]
        
        return None
    
    def _generate_contact_markdown(
        self, 
        all_contacts: List[Dict[str, Any]], 
        entity_name: str, 
        website_url: str
    ) -> str:
        """
        Generate structured markdown following the specified schema.
        
        Schema:
        decision_maker("Name tied to a phone or email or social media handle")
        contact_info: ("Contact information - WhatsApp number, email, etc.")
        contact_channel: ("WhatsApp", "Email", "Messenger", "Instagram", "PhoneNo", "Others")
        
        Args:
            all_contacts: List of all extracted contact information
            entity_name: Name of the entity
            website_url: Website URL
            
        Returns:
            Structured markdown with all contact information
        """
        markdown_sections = []
        
        # Add header
        markdown_sections.append(f"# Contact Information for {entity_name}")
        markdown_sections.append(f"Website: {website_url}")
        markdown_sections.append("")
        
        if not all_contacts:
            markdown_sections.append("No contact information found.")
            return "\n".join(markdown_sections)
        
        # Group contacts by type for better organization
        contacts_by_type = {}
        for contact in all_contacts:
            channel = contact.get("contact_channel", "Others")
            if channel not in contacts_by_type:
                contacts_by_type[channel] = []
            contacts_by_type[channel].append(contact)
        
        # Add contact sections
        for channel, contacts in contacts_by_type.items():
            markdown_sections.append(f"## {channel} Contacts")
            
            for contact in contacts:
                decision_maker = contact.get("decision_maker") or "Unknown"
                contact_info = contact.get("contact_info", "")
                
                markdown_sections.append(f"- **Decision Maker:** {decision_maker}")
                markdown_sections.append(f"  - **Contact Info:** {contact_info}")
                markdown_sections.append(f"  - **Contact Channel:** {channel}")
                markdown_sections.append("")
        
        return "\n".join(markdown_sections)
    
    async def _create_crawler(self) -> Optional[AsyncWebCrawler]:
        """
        Create and configure AsyncWebCrawler with simplified settings.
        
        Returns:
            Configured AsyncWebCrawler instance or None if creation fails
        """
        try:
            # Simplified browser configuration
            config = BrowserConfig(
                headless=self.headless,
                java_script_enabled=self.javascript_enabled,
                viewport_width=1920,
                viewport_height=1080,
                ignore_https_errors=True
            )
            
            # Create crawler with basic configuration
            crawler = AsyncWebCrawler(
                browser_config=config,
                verbose=False
            )
            
            logger.debug("Successfully created AsyncWebCrawler")
            return crawler
            
        except Exception as e:
            logger.error(f"Failed to create crawler: {e}")
            return None
    
    def _get_crawler_config(self) -> CrawlerRunConfig:
        """
        Get simplified crawler run configuration for V2.
        
        Returns:
            Basic CrawlerRunConfig optimized for contact extraction
        """
        return CrawlerRunConfig(
            # Basic settings for reliable crawling
            wait_until="networkidle",
            page_timeout=self.page_timeout * 1000,  # Convert to milliseconds
            
            # Remove overlay elements that block content
            remove_overlay_elements=True,
            
            # Exclude non-content elements
            excluded_selector=(
                "nav.advertisement, .ads, .cookie-banner, .popup, "
                ".modal, .overlay, script, style, noscript"
            ),
            
            # Keep HTML structure for link extraction
            only_text=False,
            word_count_threshold=5
        )
    
    def _extract_links(self, result) -> List[str]:
        """
        Extract all internal links from crawl result.
        
        Args:
            result: Crawl4AI result object
            
        Returns:
            List of internal links found on the page
        """
        links = []
        
        if not result or not hasattr(result, 'links') or not result.links:
            logger.debug("No links found in crawl result")
            return links
        
        base_domain = urlparse(result.url).netloc
        
        for link_data in result.links:
            if isinstance(link_data, dict) and 'href' in link_data:
                href = link_data['href']
            else:
                href = str(link_data)
            
            # Convert relative URLs to absolute
            if href.startswith('/'):
                href = urljoin(result.url, href)
            
            # Only include internal links
            if urlparse(href).netloc == base_domain or not urlparse(href).netloc:
                links.append(href)
        
        logger.debug(f"Extracted {len(links)} internal links")
        return links
    
    def _should_skip_link(self, link: str) -> bool:
        """
        Determine if a link should be skipped during navigation page discovery.
        
        Args:
            link: URL to evaluate
            
        Returns:
            True if link should be skipped, False otherwise
        """
        if not link:
            return True
        
        link_lower = link.lower()
        
        # Skip non-web protocols
        if any(protocol in link_lower for protocol in ['mailto:', 'tel:', 'javascript:', 'ftp:']):
            return True
        
        # Skip file downloads
        if any(ext in link_lower for ext in ['.pdf', '.doc', '.docx', '.xls', '.xlsx', '.zip']):
            return True
        
        # Skip external domains (basic check)
        if link.startswith('http') and any(domain in link_lower for domain in ['facebook.com', 'twitter.com', 'linkedin.com', 'instagram.com']):
            return True
        
        return False
    
    def _create_fallback_markdown(self, website_url: str, entity_name: str) -> str:
        """
        Create fallback markdown when crawling fails completely.
        
        Args:
            website_url: Website URL that failed
            entity_name: Entity name
            
        Returns:
            Basic markdown indicating crawl failure
        """
        return f"""# Contact Information for {entity_name}
Website: {website_url}

**Note:** Unable to extract contact information due to crawling failure.
Please verify the website URL and try again.
"""


class ContactExtractor:
    """
    Specialized component for extracting contact information from web content.
    
    This class provides comprehensive contact extraction capabilities including:
    - Email addresses with mailto link support
    - Phone numbers with tel link support  
    - Social media handles from supported platforms
    - Name association using proximity analysis
    """
    
    def __init__(self):
        """Initialize ContactExtractor with regex patterns and configurations."""
        # Email extraction patterns
        self.email_pattern = re.compile(
            r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
            re.IGNORECASE
        )
        
        # Phone number patterns (various formats)
        self.phone_patterns = [
            re.compile(r'\+?1?[-.\s]?\(?[0-9]{3}\)?[-.\s]?[0-9]{3}[-.\s]?[0-9]{4}'),  # US format
            re.compile(r'\+[1-9]\d{1,14}'),  # International format
            re.compile(r'\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b'),  # Basic format
        ]
        
        # Social media domain patterns
        self.social_patterns = {
            "facebook.com": "Messenger",
            "fb.com": "Messenger", 
            "linkedin.com": "Others",
            "instagram.com": "Instagram",
            "whatsapp.com": "WhatsApp",
            "wa.me": "WhatsApp",
            "t.me": "Others"  # Telegram
        }
        
        # Name patterns for association
        self.name_pattern = re.compile(r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\b')
        
        logger.debug("ContactExtractor initialized with extraction patterns")
    
    def extract_emails(self, content: str) -> List[Dict[str, Any]]:
        """
        Extract all email addresses and associated names.
        
        Args:
            content: Web content to extract emails from
            
        Returns:
            List of email contact dictionaries
        """
        contacts = []
        
        if not content:
            return contacts
        
        # Find all email addresses
        emails = self.email_pattern.findall(content)
        
        # Remove duplicates while preserving order
        unique_emails = []
        seen = set()
        for email in emails:
            email_lower = email.lower()
            if email_lower not in seen:
                unique_emails.append(email)
                seen.add(email_lower)
        
        # Extract contacts with name association
        for email in unique_emails:
            name = self._find_name_near_contact(content, email)
            contacts.append({
                "decision_maker": name,
                "contact_info": email,
                "contact_channel": "Email"
            })
        
        logger.debug(f"Extracted {len(contacts)} email contacts")
        return contacts
    
    def extract_phone_numbers(self, content: str) -> List[Dict[str, Any]]:
        """
        Extract all phone numbers and associated names.
        
        Args:
            content: Web content to extract phone numbers from
            
        Returns:
            List of phone contact dictionaries
        """
        contacts = []
        
        if not content:
            return contacts
        
        # Find phone numbers using multiple patterns
        phones = set()
        for pattern in self.phone_patterns:
            matches = pattern.findall(content)
            for match in matches:
                # Clean and normalize phone number
                if isinstance(match, tuple):
                    phone = ''.join(match)
                else:
                    phone = match
                
                # Remove extra whitespace and validate length
                phone = re.sub(r'\s+', ' ', phone.strip())
                digits_only = re.sub(r'[^\d]', '', phone)
                
                if len(digits_only) >= 10:  # Valid phone number
                    phones.add(phone)
        
        # Extract contacts with name association
        for phone in phones:
            name = self._find_name_near_contact(content, phone)
            contacts.append({
                "decision_maker": name,
                "contact_info": phone,
                "contact_channel": "PhoneNo"
            })
        
        logger.debug(f"Extracted {len(contacts)} phone contacts")
        return contacts
    
    def extract_social_media(self, content: str) -> List[Dict[str, Any]]:
        """
        Extract social media handles from supported platforms.
        
        Args:
            content: Web content to extract social media from
            
        Returns:
            List of social media contact dictionaries
        """
        contacts = []
        
        if not content:
            return contacts
        
        # Extract social media URLs
        for domain, channel in self.social_patterns.items():
            # Pattern to match URLs for this domain
            pattern = rf'https?://(?:www\.)?{re.escape(domain)}/[^\s<>"\']*'
            matches = re.findall(pattern, content, re.IGNORECASE)
            
            for match in matches:
                # Clean URL
                url = match.strip()
                if url.endswith(('.', ',', ')', ']')):
                    url = url[:-1]
                
                # Find associated name
                name = self._find_name_near_contact(content, url)
                contacts.append({
                    "decision_maker": name,
                    "contact_info": url,
                    "contact_channel": channel
                })
        
        logger.debug(f"Extracted {len(contacts)} social media contacts")
        return contacts
    
    def associate_names_with_contacts(
        self, 
        content: str, 
        contacts: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Find names associated with contact information using enhanced proximity analysis.
        
        Args:
            content: Full web content
            contacts: List of contact dictionaries to enhance
            
        Returns:
            Enhanced contact list with improved name associations
        """
        enhanced_contacts = []
        
        for contact in contacts:
            contact_info = contact.get("contact_info", "")
            
            # Try to find a better name association if none exists
            if not contact.get("decision_maker"):
                name = self._find_name_near_contact(content, contact_info, extended_search=True)
                contact["decision_maker"] = name
            
            enhanced_contacts.append(contact)
        
        return enhanced_contacts
    
    def _find_name_near_contact(
        self, 
        content: str, 
        contact_info: str, 
        extended_search: bool = False
    ) -> Optional[str]:
        """
        Find names associated with contact information using proximity analysis.
        
        Args:
            content: Full page content
            contact_info: Contact information to find name for
            extended_search: Whether to use extended search radius
            
        Returns:
            Associated name if found, None otherwise
        """
        if not content or not contact_info:
            return None
        
        # Find position of contact info in content
        contact_pos = content.find(contact_info)
        if contact_pos == -1:
            return None
        
        # Define search radius
        search_radius = 200 if extended_search else 100
        
        # Extract context around contact info
        start_pos = max(0, contact_pos - search_radius)
        end_pos = min(len(content), contact_pos + len(contact_info) + search_radius)
        context = content[start_pos:end_pos]
        
        # Find names in context
        names = self.name_pattern.findall(context)
        
        if not names:
            return None
        
        # Score names by proximity to contact info
        scored_names = []
        for name in names:
            name_pos = context.find(name)
            if name_pos != -1:
                # Calculate distance from contact info
                contact_pos_in_context = contact_pos - start_pos
                distance = abs(name_pos - contact_pos_in_context)
                scored_names.append((name, distance))
        
        if scored_names:
            # Return the closest name
            scored_names.sort(key=lambda x: x[1])
            return scored_names[0][0]
        
        return None


class MarkdownGenerator:
    """
    Component for generating structured markdown from extracted contact information.
    
    This class formats contact information according to the V2 schema specification
    and provides consistent markdown output for LLM processing.
    """
    
    def __init__(self):
        """Initialize MarkdownGenerator."""
        logger.debug("MarkdownGenerator initialized")
    
    def generate_structured_markdown(
        self, 
        contacts: List[Dict[str, Any]], 
        entity_name: str, 
        website_url: str
    ) -> str:
        """
        Generate structured markdown following V2 schema specification.
        
        Schema format:
        decision_maker("Name tied to a phone or email or social media handle")
        contact_info: ("Contact information - WhatsApp number, email, etc.")
        contact_channel: ("WhatsApp", "Email", "Messenger", "Instagram", "PhoneNo", "Others")
        
        Args:
            contacts: List of extracted contact information
            entity_name: Name of the entity
            website_url: Website URL
            
        Returns:
            Structured markdown for LLM processing
        """
        sections = []
        
        # Header section
        sections.append(f"# Contact Extraction Results for {entity_name}")
        sections.append(f"**Website:** {website_url}")
        sections.append(f"**Total Contacts Found:** {len(contacts)}")
        sections.append("")
        
        if not contacts:
            sections.append("No contact information was found on this website.")
            return "\n".join(sections)
        
        # Contact details section
        sections.append("## Extracted Contact Information")
        sections.append("")
        
        for i, contact in enumerate(contacts, 1):
            decision_maker = contact.get("decision_maker") or "Not specified"
            contact_info = contact.get("contact_info", "")
            contact_channel = contact.get("contact_channel", "Others")
            
            sections.append(f"### Contact {i}")
            sections.append(f"- **Decision Maker:** {decision_maker}")
            sections.append(f"- **Contact Info:** {contact_info}")
            sections.append(f"- **Contact Channel:** {contact_channel}")
            sections.append("")
        
        # Summary section
        channel_cou