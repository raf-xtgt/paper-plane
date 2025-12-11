"""
Web Crawler helper module for Navigator Agent.

This module provides intelligent website navigation capabilities using Crawl4AI
with Playwright for dynamic content rendering and extraction.
"""

import logging
import asyncio
import os
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
    
    def __init__(self, page_timeout: int = 60, max_retries: int = 3):
        """Initialize WebCrawler with configuration."""
        self.page_timeout = page_timeout
        self.max_retries = max_retries
        
        # Configuration from environment variables
        self.headless = os.getenv("CRAWL4AI_HEADLESS", "true").lower() == "true"
        self.stealth_mode = os.getenv("CRAWL4AI_STEALTH", "true").lower() == "true"
        self.user_agent_mode = os.getenv("CRAWL4AI_USER_AGENT_MODE", "random")
        
        # Keywords for finding relevant pages (prioritized by importance)
        self.high_priority_keywords = [
            "staff", "team", "leadership", "board", "directors", 
            "management", "faculty", "doctors", "personnel"
        ]
        
        self.medium_priority_keywords = [
            "about", "contact", "partners", "administration", 
            "ceo", "founder", "executive", "principal"
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
        Find and crawl relevant pages (Staff/Team/Contact).
        
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
                return None
            
            relevant_links = self._find_relevant_pages(main_result.links)
            
            if not relevant_links:
                logger.debug(f"No relevant pages found for {entity_name}")
                return None
            
            # Crawl the most relevant page
            target_url = relevant_links[0]
            logger.debug(f"Crawling relevant page for {entity_name}: {target_url}")
            
            result = await crawler.arun(
                url=target_url,
                config=self._get_crawler_config()
            )
            
            if result.success and result.markdown:
                logger.debug(f"Successfully crawled relevant page: {len(result.markdown)} chars")
                return result.markdown
            
        except Exception as e:
            logger.warning(f"Failed to crawl relevant pages for {entity_name}: {e}")
        
        return None
    
    def _find_relevant_pages(self, links: List[Dict[str, Any]]) -> List[str]:
        """
        Identify Staff/Team/Contact pages using keyword matching with priority scoring.
        
        Args:
            links: List of link dictionaries from Crawl4AI
            
        Returns:
            List of relevant URLs sorted by priority
        """
        relevant_links = []
        
        for link in links:
            if not isinstance(link, dict) or 'href' not in link:
                continue
                
            href = link['href']
            text = link.get('text', '').lower()
            
            # Calculate relevance score with priority weighting
            relevance_score = 0
            
            # High priority keywords (weight: 3)
            for keyword in self.high_priority_keywords:
                if keyword in text:
                    relevance_score += 3
                if keyword in href.lower():
                    relevance_score += 3
            
            # Medium priority keywords (weight: 2)
            for keyword in self.medium_priority_keywords:
                if keyword in text:
                    relevance_score += 2
                if keyword in href.lower():
                    relevance_score += 2
            
            # Bonus for exact matches
            if any(keyword == text.strip() for keyword in self.high_priority_keywords):
                relevance_score += 5
            
            if relevance_score > 0:
                relevant_links.append((href, relevance_score, text))
        
        # Sort by relevance score (highest first) and return URLs
        relevant_links.sort(key=lambda x: x[1], reverse=True)
        
        # Log found relevant pages
        if relevant_links:
            logger.debug(f"Found {len(relevant_links)} relevant pages:")
            for url, score, text in relevant_links[:3]:
                logger.debug(f"  - {text} ({url}) - Score: {score}")
        
        return [url for url, _, _ in relevant_links[:3]]  # Return top 3
    
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