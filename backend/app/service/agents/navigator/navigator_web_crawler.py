"""
Web Crawler helper module for Navigator Agent.

This module provides intelligent website navigation capabilities using Crawl4AI
with Playwright for dynamic content rendering and extraction.
"""

import logging
from typing import List, Optional, Tuple, Dict, Any
from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig
from crawl4ai.content_filter_strategy import PruningContentFilter

# Configure logging
logger = logging.getLogger("lead_gen_pipeline.navigator.webcrawler")


class NavigatorWebCrawler:
    """
    Crawl4AI wrapper for intelligent website navigation.
    """
    
    def __init__(self, page_timeout: int = 60, max_retries: int = 3):
        """Initialize WebCrawler with configuration."""
        self.page_timeout = page_timeout
        self.max_retries = max_retries
        
        # Keywords for finding relevant pages
        self.relevant_keywords = [
            "staff", "team", "leadership", "board", "partners", 
            "doctors", "faculty", "about", "contact", "director", 
            "ceo", "management", "administration", "personnel"
        ]
        
        logger.debug("NavigatorWebCrawler initialized")
    
    async def crawl_website(
        self, 
        website_url: str, 
        entity_name: str
    ) -> Tuple[str, str]:
        """
        Crawl website and return (markdown_content, verified_url).
        
        Args:
            website_url: URL to crawl
            entity_name: Name of entity for logging
            
        Returns:
            Tuple of (markdown_content, verified_url)
        """
        crawler = self._configure_crawler()
        
        try:
            async with crawler:
                # First, crawl the main page
                result = await crawler.arun(
                    url=website_url,
                    config=self._get_crawler_config()
                )
                
                if not result.success:
                    raise Exception(f"Failed to crawl {website_url}: {result.error_message}")
                
                verified_url = result.url
                main_content = result.markdown or ""
                
                # Try to find and crawl relevant pages
                relevant_content = await self._crawl_relevant_pages(
                    crawler, result, entity_name
                )
                
                # Combine content
                combined_content = main_content
                if relevant_content:
                    combined_content += f"\n\n--- Additional Page Content ---\n\n{relevant_content}"
                
                logger.debug(f"Crawled {entity_name}: {len(combined_content)} characters")
                return combined_content, verified_url
                
        except Exception as e:
            logger.error(f"Crawling failed for {entity_name}: {e}")
            # Return minimal content to allow processing to continue
            return f"Website: {website_url}\nEntity: {entity_name}", website_url
    
    def _configure_crawler(self) -> AsyncWebCrawler:
        """Configure Crawl4AI with optimal settings."""
        browser_config = BrowserConfig(
            headless=True,
            java_script_enabled=True,
            use_persistent_context=True,
            user_agent_mode="random",
            enable_stealth=True,
            viewport_width=1920,
            viewport_height=1080
        )
        
        return AsyncWebCrawler(
            browser_config=browser_config,
            verbose=False
        )
    
    def _get_crawler_config(self) -> CrawlerRunConfig:
        """Get crawler run configuration."""
        return CrawlerRunConfig(
            wait_until="networkidle",
            scan_full_page=True,
            remove_overlay_elements=True,
            excluded_selector="nav, footer, .advertisement, .cookie-banner, .popup",
            content_filter=PruningContentFilter(),
            scroll_delay=2,
            max_scroll_steps=5,
            page_timeout=self.page_timeout * 1000  # Convert to milliseconds
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
        Identify Staff/Team/Contact pages using keyword matching.
        
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
            
            # Check if link text contains relevant keywords
            relevance_score = 0
            for keyword in self.relevant_keywords:
                if keyword in text:
                    relevance_score += 1
                if keyword in href.lower():
                    relevance_score += 1
            
            if relevance_score > 0:
                relevant_links.append((href, relevance_score))
        
        # Sort by relevance score (highest first) and return URLs
        relevant_links.sort(key=lambda x: x[1], reverse=True)
        return [url for url, _ in relevant_links[:3]]  # Return top 3