"""
Web Crawler helper module for Navigator Agent.

This module provides intelligent website navigation capabilities using Crawl4AI
with Playwright for dynamic content rendering and extraction.
"""

import logging
import asyncio
import os
import re
from typing import List, Optional, Tuple, Dict, Any
from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig
from crawl4ai.content_filter_strategy import PruningContentFilter

# Configure logging
logger = logging.getLogger("lead_gen_pipeline.navigator.webcrawler")


class NavigatorWebCrawler:
    """
    Crawl4AI wrapper for intelligent website navigation.
    
    Features:
    - Headless browser with JavaScript execution
    - Intelligent page navigation (Staff/Team pages)
    - Dynamic content handling (lazy loading, virtual scroll)
    - Overlay removal (pop-ups, cookie banners)
    - Content cleaning and Markdown conversion
    """
    
    def __init__(self, page_timeout: int = 60, max_retries: int = 3, max_navigation_depth: int = 1):
        """Initialize WebCrawler with configuration."""
        self.page_timeout = page_timeout
        self.max_retries = max_retries
        self.max_navigation_depth = max_navigation_depth  # Limit navigation depth to prevent infinite loops
        
        # Configuration from environment variables
        self.headless = os.getenv("CRAWL4AI_HEADLESS", "true").lower() == "true"
        self.stealth_mode = os.getenv("CRAWL4AI_STEALTH", "true").lower() == "true"
        self.user_agent_mode = os.getenv("CRAWL4AI_USER_AGENT_MODE", "random")
        
        # Keywords for finding relevant pages (prioritized by importance)
        # Based on Requirement 3.2: prioritize Staff, Team, Leadership, Board, Partners, Doctors, Faculty, About Us, Contact, Director, CEO
        self.high_priority_keywords = [
            "staff", "team", "leadership", "board", "directors", 
            "management", "faculty", "doctors", "personnel", "ceo", "director"
        ]
        
        self.medium_priority_keywords = [
            "about", "contact", "partners", "administration", 
            "founder", "executive", "principal", "about us"
        ]
        
        # User agents for retry attempts
        self.user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ]
        
        logger.debug(f"NavigatorWebCrawler initialized - headless: {self.headless}, stealth: {self.stealth_mode}")
    
    async def crawl_website(
        self, 
        website_url: str, 
        entity_name: str
    ) -> Tuple[str, str]:
        """
        Crawl website and return (markdown_content, verified_url).
        
        Features:
        - Retry logic with different user agents for bot detection
        - Network idle waiting for dynamic content
        - Intelligent navigation to Staff/Team pages
        - Overlay removal and content cleaning
        
        Args:
            website_url: URL to crawl
            entity_name: Name of entity for logging
            
        Returns:
            Tuple of (markdown_content, verified_url)
        """
        last_exception = None
        
        # Try crawling with retries and different user agents
        for attempt in range(self.max_retries):
            try:
                logger.debug(f"Crawling attempt {attempt + 1}/{self.max_retries} for {entity_name}")
                
                # Configure crawler for this attempt
                crawler = self._configure_crawler(attempt)
                
                async with crawler:
                    # Crawl the main page with network idle waiting
                    result = await crawler.arun(
                        url=website_url,
                        config=self._get_crawler_config()
                    )
                    
                    if not result.success:
                        raise Exception(f"Crawl failed: {result.error_message}")
                    
                    verified_url = result.url
                    main_content = result.markdown or ""
                    
                    # Clean and validate main content
                    if len(main_content.strip()) < 100:
                        logger.warning(f"Main page content too short for {entity_name}: {len(main_content)} chars")
                    
                    # Try to find and crawl relevant pages
                    relevant_content = await self._crawl_relevant_pages(
                        crawler, result, entity_name
                    )
                    
                    # Combine and clean content
                    combined_content = self._combine_and_clean_content(
                        main_content, relevant_content, entity_name
                    )
                    
                    logger.info(f"Successfully crawled {entity_name}: {len(combined_content)} characters")
                    return combined_content, verified_url
                    
            except Exception as e:
                last_exception = e
                logger.warning(f"Crawling attempt {attempt + 1} failed for {entity_name}: {e}")
                
                # Wait before retry (exponential backoff)
                if attempt < self.max_retries - 1:
                    wait_time = 2 ** attempt
                    logger.debug(f"Waiting {wait_time}s before retry")
                    await asyncio.sleep(wait_time)
        
        # All retries failed
        logger.error(f"All crawling attempts failed for {entity_name}: {last_exception}")
        
        # Return minimal content to allow processing to continue
        return self._create_fallback_content(website_url, entity_name), website_url
    
    def _configure_crawler(self, attempt: int = 0) -> AsyncWebCrawler:
        """
        Configure Crawl4AI with optimal settings for bot detection avoidance.
        
        Args:
            attempt: Retry attempt number for user agent rotation
            
        Returns:
            Configured AsyncWebCrawler instance
        """
        # Select user agent for this attempt
        user_agent = None
        if attempt < len(self.user_agents):
            user_agent = self.user_agents[attempt]
        
        browser_config = BrowserConfig(
            headless=self.headless,
            java_script_enabled=True,
            use_persistent_context=True,
            user_agent_mode=self.user_agent_mode if not user_agent else "custom",
            user_agent=user_agent,
            enable_stealth=self.stealth_mode,
            viewport_width=1920,
            viewport_height=1080,
            # Additional anti-detection measures
            ignore_https_errors=True,
            extra_args=[
                "--no-sandbox",
                "--disable-blink-features=AutomationControlled",
                "--disable-features=VizDisplayCompositor"
            ]
        )
        
        return AsyncWebCrawler(
            browser_config=browser_config,
            verbose=False
        )
    
    def _get_crawler_config(self) -> CrawlerRunConfig:
        """
        Get crawler run configuration with dynamic content handling.
        
        Features:
        - Network idle waiting for JavaScript content
        - Full page scanning with virtual scrolling
        - Overlay removal (pop-ups, cookie banners)
        - Content filtering and cleaning
        """
        return CrawlerRunConfig(
            # Wait for network idle to ensure dynamic content loads
            wait_until="networkidle",
            
            # Enable full page scanning for lazy-loaded content
            scan_full_page=True,
            
            # Remove overlay elements that block content
            remove_overlay_elements=True,
            
            # Exclude non-content elements
            excluded_selector=(
                "nav, footer, header, .navigation, .menu, "
                ".advertisement, .ads, .cookie-banner, .popup, "
                ".modal, .overlay, .sidebar, .breadcrumb, "
                "script, style, noscript"
            ),
            
            # Use content filter for cleaning
            content_filter=PruningContentFilter(
                threshold=0.48,  # Balance between content and noise
                threshold_type="fixed",
                min_word_threshold=10
            ),
            
            # Virtual scrolling configuration for dynamic content
            scroll_delay=2,  # Wait 2 seconds between scrolls
            max_scroll_steps=5,  # Limit scrolling to prevent infinite loops
            
            # Timeout configuration
            page_timeout=self.page_timeout * 1000,  # Convert to milliseconds
            
            # Additional options for better content extraction
            word_count_threshold=10,
            only_text=False,  # Keep some HTML structure for better parsing
            
            # CSS selector for main content (fallback)
            css_selector="main, article, .content, .main-content, #content, #main"
        )
    
    async def _crawl_relevant_pages(
        self, 
        crawler: AsyncWebCrawler, 
        main_result, 
        entity_name: str
    ) -> Optional[str]:
        """
        Find and crawl relevant pages (Staff/Team/Contact) with navigation depth limiting.
        
        Implements Requirements 3.3, 3.4, 3.5:
        - Visits highest priority page based on keyword matching
        - Limits navigation depth to prevent infinite crawling loops
        - Handles navigation failures gracefully and continues with available content
        
        Args:
            crawler: Configured AsyncWebCrawler instance
            main_result: Result from main page crawl
            entity_name: Entity name for logging
            
        Returns:
            Content from relevant pages or None
        """
        try:
            # Extract links from main page
            if not main_result.links:
                logger.debug(f"No links found on main page for {entity_name}")
                return None
            
            # Find relevant pages using intelligent keyword matching
            relevant_links = self._find_relevant_pages(main_result.links)
            
            if not relevant_links:
                logger.debug(f"No relevant pages found for {entity_name}")
                return None
            
            # Crawl relevant pages with depth limiting
            combined_content = []
            
            for i, target_url in enumerate(relevant_links):
                # Respect navigation depth limit (Requirement 3.4)
                if i >= self.max_navigation_depth:
                    logger.debug(f"Reached navigation depth limit ({self.max_navigation_depth}) for {entity_name}")
                    break
                
                try:
                    logger.debug(f"Crawling relevant page {i+1}/{len(relevant_links)} for {entity_name}: {target_url}")
                    
                    # Crawl with timeout to prevent hanging
                    result = await asyncio.wait_for(
                        crawler.arun(url=target_url, config=self._get_crawler_config()),
                        timeout=self.page_timeout
                    )
                    
                    if result.success and result.markdown:
                        content_length = len(result.markdown)
                        logger.debug(f"Successfully crawled relevant page {i+1}: {content_length} chars")
                        
                        # Only include substantial content
                        if content_length > 50:
                            combined_content.append(result.markdown)
                        else:
                            logger.debug(f"Skipping page {i+1} due to insufficient content ({content_length} chars)")
                    else:
                        # Handle navigation failures gracefully (Requirement 3.5)
                        logger.warning(f"Failed to crawl relevant page {i+1} for {entity_name}: {result.error_message if hasattr(result, 'error_message') else 'Unknown error'}")
                        
                except asyncio.TimeoutError:
                    # Handle timeout gracefully and continue with other pages
                    logger.warning(f"Timeout crawling relevant page {i+1} for {entity_name}, continuing with remaining pages")
                    continue
                    
                except Exception as e:
                    # Handle other navigation failures gracefully (Requirement 3.5)
                    logger.warning(f"Error crawling relevant page {i+1} for {entity_name}: {e}, continuing with remaining pages")
                    continue
            
            # Combine content from all successfully crawled pages
            if combined_content:
                final_content = "\n\n--- Relevant Page Content ---\n\n".join(combined_content)
                logger.info(f"Successfully crawled {len(combined_content)} relevant page(s) for {entity_name}: {len(final_content)} total chars")
                return final_content
            else:
                logger.debug(f"No usable content found from relevant pages for {entity_name}")
                return None
                
        except Exception as e:
            # Handle overall navigation failures gracefully (Requirement 3.5)
            logger.warning(f"Failed to crawl relevant pages for {entity_name}: {e}")
            return None
    
    def _find_relevant_pages(self, links: List[Dict[str, Any]]) -> List[str]:
        """
        Identify Staff/Team/Contact pages using keyword matching with priority scoring.
        
        Implements Requirement 3.1, 3.2, 3.3:
        - Identifies links containing keywords related to staff, team, leadership, or contact information
        - Prioritizes navigation based on keyword relevance
        - Returns highest priority pages for navigation
        
        Args:
            links: List of link dictionaries from Crawl4AI
            
        Returns:
            List of relevant URLs sorted by priority (highest first)
        """
        relevant_links = []
        processed_urls = set()  # Prevent duplicate URLs
        
        for link in links:
            if not isinstance(link, dict) or 'href' not in link:
                continue
                
            href = link['href']
            text = link.get('text', '').lower().strip()
            
            # Skip if we've already processed this URL
            if href in processed_urls:
                continue
            processed_urls.add(href)
            
            # Skip external links, anchors, and non-relevant protocols
            if self._should_skip_link(href):
                continue
            
            # Calculate relevance score with enhanced priority weighting
            relevance_score = self._calculate_relevance_score(href, text)
            
            if relevance_score > 0:
                relevant_links.append((href, relevance_score, text))
        
        # Sort by relevance score (highest first)
        relevant_links.sort(key=lambda x: x[1], reverse=True)
        
        # Log found relevant pages for debugging
        if relevant_links:
            logger.debug(f"Found {len(relevant_links)} relevant pages:")
            for url, score, text in relevant_links[:5]:  # Show top 5
                logger.debug(f"  - '{text}' ({url}) - Score: {score}")
        else:
            logger.debug("No relevant pages found with current keywords")
        
        # Return top pages based on navigation depth limit
        max_pages = min(len(relevant_links), self.max_navigation_depth)
        return [url for url, _, _ in relevant_links[:max_pages]]
    
    def _should_skip_link(self, href: str) -> bool:
        """
        Determine if a link should be skipped during navigation.
        
        Args:
            href: URL to evaluate
            
        Returns:
            True if link should be skipped
        """
        href_lower = href.lower()
        
        # Skip external links (different domain)
        if href.startswith('http') and not any(domain in href_lower for domain in ['localhost', '127.0.0.1']):
            # Allow external links only if they're subdomains of the current site
            # This is a simplified check - in production, you'd want more sophisticated domain matching
            pass
        
        # Skip non-web protocols
        if any(protocol in href_lower for protocol in ['mailto:', 'tel:', 'javascript:', 'ftp:', '#']):
            return True
        
        # Skip file downloads and media
        if any(ext in href_lower for ext in ['.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx', 
                                           '.jpg', '.jpeg', '.png', '.gif', '.mp4', '.mp3', '.zip']):
            return True
        
        # Skip social media and external service links
        social_domains = ['facebook.com', 'twitter.com', 'linkedin.com', 'instagram.com', 
                         'youtube.com', 'tiktok.com', 'whatsapp.com']
        if any(domain in href_lower for domain in social_domains):
            return True
        
        return False
    
    def _calculate_relevance_score(self, href: str, text: str) -> int:
        """
        Calculate relevance score for a link based on keyword matching.
        
        Implements enhanced scoring system for Requirement 3.2:
        - High priority keywords get higher weights
        - Exact matches get bonus points
        - URL path matching gets additional points
        
        Args:
            href: URL of the link
            text: Link text content
            
        Returns:
            Relevance score (higher = more relevant)
        """
        relevance_score = 0
        href_lower = href.lower()
        text_lower = text.lower()
        
        # High priority keywords (weight: 5) - Staff, Team, Leadership, Board, etc.
        for keyword in self.high_priority_keywords:
            # Exact text match gets highest score
            if keyword == text_lower:
                relevance_score += 10
            # Partial text match
            elif keyword in text_lower:
                relevance_score += 5
            # URL path match
            elif keyword in href_lower:
                relevance_score += 4
        
        # Medium priority keywords (weight: 3) - About, Contact, etc.
        for keyword in self.medium_priority_keywords:
            # Exact text match
            if keyword == text_lower:
                relevance_score += 6
            # Partial text match
            elif keyword in text_lower:
                relevance_score += 3
            # URL path match
            elif keyword in href_lower:
                relevance_score += 2
        
        # Bonus scoring for common patterns
        # Multi-word exact matches for "about us", "our team", etc.
        high_value_phrases = [
            "our team", "our staff", "meet the team", "leadership team",
            "board of directors", "management team", "faculty members",
            "our doctors", "medical staff", "contact us", "about us"
        ]
        
        for phrase in high_value_phrases:
            if phrase in text_lower:
                relevance_score += 8
        
        # Penalty for overly generic terms that might not be useful
        generic_terms = ["home", "news", "blog", "events", "gallery", "services"]
        for term in generic_terms:
            if term == text_lower:
                relevance_score -= 2
        
        return max(0, relevance_score)  # Ensure non-negative score
    
    def _combine_and_clean_content(
        self, 
        main_content: str, 
        relevant_content: Optional[str], 
        entity_name: str
    ) -> str:
        """
        Combine and clean content from multiple pages.
        
        Args:
            main_content: Content from main page
            relevant_content: Content from relevant pages (optional)
            entity_name: Entity name for logging
            
        Returns:
            Combined and cleaned content
        """
        # Start with main content
        combined_content = main_content.strip()
        
        # Add relevant content if available
        if relevant_content and relevant_content.strip():
            combined_content += f"\n\n--- Staff/Team Page Content ---\n\n{relevant_content.strip()}"
        
        # Basic content cleaning
        # Remove excessive whitespace
        import re
        combined_content = re.sub(r'\n\s*\n\s*\n', '\n\n', combined_content)
        combined_content = re.sub(r'[ \t]+', ' ', combined_content)
        
        # Remove common noise patterns
        noise_patterns = [
            r'Cookie Policy.*?Accept',
            r'This website uses cookies.*?(?:\n|$)',
            r'JavaScript is disabled.*?(?:\n|$)',
            r'Please enable JavaScript.*?(?:\n|$)'
        ]
        
        for pattern in noise_patterns:
            combined_content = re.sub(pattern, '', combined_content, flags=re.IGNORECASE | re.DOTALL)
        
        # Ensure minimum content length
        if len(combined_content.strip()) < 50:
            logger.warning(f"Very short content for {entity_name}: {len(combined_content)} chars")
            combined_content += f"\n\nEntity: {entity_name}\nNote: Limited content available from website."
        
        return combined_content.strip()
    
    def _create_fallback_content(self, website_url: str, entity_name: str) -> str:
        """
        Create fallback content when crawling fails completely.
        
        Args:
            website_url: Original website URL
            entity_name: Entity name
            
        Returns:
            Minimal fallback content
        """
        return f"""Website: {website_url}
Entity: {entity_name}

Note: Unable to crawl website content due to technical issues.
This may be due to:
- Website blocking automated access
- Network connectivity issues
- JavaScript-heavy content that failed to load
- Server-side restrictions

Please verify the website URL and try manual extraction if needed."""