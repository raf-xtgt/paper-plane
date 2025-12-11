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
from crawl4ai.async_crawler_strategy import AsyncPlaywrightCrawlerStrategy
from crawl4ai.content_filter_strategy import PruningContentFilter

# Configure logging
logger = logging.getLogger("lead_gen_pipeline.navigator.webcrawler")

# Ensure logger is properly configured
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)


class NavigatorWebCrawler:
    """
    Crawl4AI wrapper for intelligent website navigation with enhanced dynamic content handling.
    
    Features:
    - Headless browser with JavaScript execution
    - Intelligent page navigation (Staff/Team pages)
    - Enhanced dynamic content handling (lazy loading, virtual scroll, SPAs)
    - Adaptive crawling strategies based on content patterns
    - Progressive content loading for complex websites
    - Overlay removal (pop-ups, cookie banners)
    - Content cleaning and Markdown conversion
    
    Dynamic Content Capabilities (Requirements 2.3, 2.5):
    - Single-page application (SPA) detection and handling
    - Virtual scrolling and lazy loading support
    - Adaptive scrolling strategies based on content characteristics
    - Progressive content loading with validation
    - Enhanced timeout handling for dynamic content
    """
    
    def __init__(
        self, 
        page_timeout: int = 60, 
        max_retries: int = 3, 
        max_navigation_depth: int = 1,
        enable_dynamic_content: bool = True,
        adaptive_scrolling: bool = True
    ):
        """
        Initialize WebCrawler with enhanced dynamic content handling configuration.
        
        Args:
            page_timeout: Timeout for page loading in seconds
            max_retries: Maximum retry attempts for failed crawls
            max_navigation_depth: Maximum depth for page navigation
            enable_dynamic_content: Enable enhanced dynamic content handling
            adaptive_scrolling: Enable adaptive scrolling strategies
        """
        self.page_timeout = page_timeout
        self.max_retries = max_retries
        self.max_navigation_depth = max_navigation_depth  # Limit navigation depth to prevent infinite loops
        self.enable_dynamic_content = enable_dynamic_content
        self.adaptive_scrolling = adaptive_scrolling
        
        # Configuration from environment variables
        self.headless = os.getenv("CRAWL4AI_HEADLESS", "true").lower() == "true"
        self.stealth_mode = os.getenv("CRAWL4AI_STEALTH", "true").lower() == "true"
        self.user_agent_mode = os.getenv("CRAWL4AI_USER_AGENT_MODE", "random")
        
        # Dynamic content handling settings
        self.dynamic_content_timeout = int(os.getenv("CRAWL4AI_DYNAMIC_TIMEOUT", "90"))
        self.max_scroll_attempts = int(os.getenv("CRAWL4AI_MAX_SCROLL", "15"))
        self.scroll_delay_base = int(os.getenv("CRAWL4AI_SCROLL_DELAY", "3"))
        
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
        
        logger.debug(
            f"NavigatorWebCrawler initialized - headless: {self.headless}, stealth: {self.stealth_mode}, "
            f"dynamic_content: {self.enable_dynamic_content}, adaptive_scrolling: {self.adaptive_scrolling}"
        )
    
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
        # Validate inputs
        if not website_url or not entity_name:
            error_msg = f"Invalid inputs: website_url='{website_url}', entity_name='{entity_name}'"
            logger.error(error_msg)
            return self._create_fallback_content(website_url or "unknown", entity_name or "unknown"), website_url or "unknown"
        
        logger.debug(f"Starting crawl for {entity_name} at {website_url}")
        last_exception = None
        
        # Try crawling with retries and different user agents
        for attempt in range(self.max_retries):
            try:
                logger.debug(f"Crawling attempt {attempt + 1}/{self.max_retries} for {entity_name}")
                
                # Configure crawler for this attempt
                crawler = self._configure_crawler(attempt)
                
                if crawler is None:
                    raise Exception("Failed to configure crawler")
                
                # Try to use the crawler with proper error handling
                try:
                    # Initial crawl with basic dynamic content handling
                    result = await crawler.arun(
                        url=website_url,
                        config=self._get_crawler_config()
                    )
                    
                    if not result or not result.success:
                        error_msg = getattr(result, 'error_message', 'Unknown crawl error') if result else 'No result returned'
                        raise Exception(f"Crawl failed: {error_msg}")
                    
                    verified_url = result.url
                    main_content = result.markdown or ""
                    
                    # Detect dynamic content patterns for adaptive strategy
                    content_patterns = self._detect_dynamic_content_patterns(main_content, website_url)
                    
                    # If content is insufficient or dynamic patterns detected, use adaptive handling
                    needs_enhancement = (
                        len(main_content.strip()) < 100 or 
                        content_patterns["is_spa"] or 
                        content_patterns["has_lazy_loading"] or
                        content_patterns["content_density"] == "minimal"
                    )
                    
                    if needs_enhancement:
                        logger.debug(f"Using adaptive dynamic content handling for {entity_name}: {content_patterns}")
                        
                        enhanced_result = await self._apply_adaptive_crawling_strategy(
                            crawler, website_url, entity_name, content_patterns
                        )
                        
                        if enhanced_result and enhanced_result.success and enhanced_result.markdown:
                            # Use enhanced result if it's significantly better
                            if len(enhanced_result.markdown) > len(main_content) * 1.1:  # 10% improvement
                                main_content = enhanced_result.markdown
                                verified_url = enhanced_result.url
                                logger.debug(f"Adaptive dynamic content extraction successful: {len(main_content)} chars")
                            else:
                                logger.debug(f"Adaptive handling didn't improve content significantly")
                        else:
                            logger.warning(f"Adaptive dynamic content handling failed for {entity_name}")
                    
                    # Final content validation
                    if len(main_content.strip()) < 100:
                        logger.warning(f"Main page content still insufficient for {entity_name}: {len(main_content)} chars")
                    
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
                    
                except Exception as crawl_error:
                    # Re-raise the crawl error to be handled by the outer exception handler
                    raise crawl_error
                    
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
    
    def _configure_crawler(self, attempt: int = 0) -> Optional[AsyncWebCrawler]:
        """
        Configure Crawl4AI with optimal settings for bot detection avoidance.
        
        Args:
            attempt: Retry attempt number for user agent rotation
            
        Returns:
            Configured AsyncWebCrawler instance or None if configuration fails
        """
        try:
            logger.debug(f"Configuring crawler for attempt {attempt + 1}")
            
            # Create crawler with minimal configuration first
            try:
                crawler = AsyncWebCrawler(verbose=False)
                logger.debug("Successfully created basic AsyncWebCrawler")
                return crawler
            except Exception as basic_error:
                logger.warning(f"Basic crawler creation failed: {basic_error}, trying with browser config")
            
            # If basic creation fails, try with browser configuration
            # Select user agent for this attempt
            user_agent = None
            if attempt < len(self.user_agents):
                user_agent = self.user_agents[attempt]
            
            # Simplified browser configuration to avoid potential issues
            config = BrowserConfig(
                headless=self.headless,
                java_script_enabled=True,
                user_agent=user_agent,
                viewport_width=1920,
                viewport_height=1080,
                ignore_https_errors=True
            )
            
            # Create crawler with browser configuration
            crawler = AsyncWebCrawler(
                browser_config=config,
                verbose=False
            )
            
            if crawler is None:
                logger.error("Failed to create AsyncWebCrawler instance")
                return None
                
            logger.debug("Successfully created configured AsyncWebCrawler")
            return crawler
            
        except Exception as e:
            logger.error(f"Failed to configure crawler: {e}")
            return None
    
    def _get_crawler_config(self, enhanced_dynamic_handling: bool = False) -> CrawlerRunConfig:
        """
        Get crawler run configuration with enhanced dynamic content handling.
        
        Implements Requirements 2.3, 2.5:
        - Network idle waiting for JavaScript content
        - Full page scanning with virtual scrolling for lazy-loaded content
        - Enhanced handling for single-page applications
        - Overlay removal (pop-ups, cookie banners)
        - Content filtering and cleaning
        
        Args:
            enhanced_dynamic_handling: Enable enhanced settings for complex SPAs
            
        Returns:
            Configured CrawlerRunConfig for dynamic content handling
        """
        # Base configuration for all pages
        config = CrawlerRunConfig(
            # Wait for network idle to ensure dynamic content loads (Requirement 2.2)
            wait_until="networkidle",
            
            # Enable full page scanning for lazy-loaded content (Requirement 2.3)
            scan_full_page=True,
            
            # Remove overlay elements that block content
            remove_overlay_elements=True,
            
            # Exclude non-content elements but preserve structure for dynamic content
            excluded_selector=(
                "nav, footer, header, .navigation, .menu, "
                ".advertisement, .ads, .cookie-banner, .popup, "
                ".modal, .overlay, .sidebar, .breadcrumb, "
                "script, style, noscript, .social-media, .share-buttons"
            ),

            
            # Enhanced virtual scrolling configuration for dynamic content (Requirement 2.3)
            scroll_delay=3,  # Increased delay for dynamic content loading
            max_scroll_steps=8,  # More steps for comprehensive content capture
            
            # Timeout configuration with buffer for dynamic content
            page_timeout=self.page_timeout * 1000,  # Convert to milliseconds
            
            # Additional options for better dynamic content extraction
            word_count_threshold=8,  # Lower threshold for dynamic fragments
            only_text=False,  # Keep HTML structure for dynamic content parsing
            
            # Enhanced CSS selector for dynamic content
            css_selector="main, article, .content, .main-content, #content, #main, .app, #app, .page-content, .container"
        )
        
        # Enhanced settings for complex single-page applications
        if enhanced_dynamic_handling:
            config.scroll_delay = 4  # Even longer delay for complex SPAs
            config.max_scroll_steps = 12  # More comprehensive scrolling
            config.page_timeout = (self.page_timeout + 30) * 1000  # Extended timeout
            
            # Additional selectors for SPA frameworks
            config.css_selector += ", .vue-app, .react-app, .angular-app, [data-reactroot], #root"
        
        return config
    
    async def _handle_dynamic_content(
        self, 
        crawler: AsyncWebCrawler, 
        url: str, 
        entity_name: str,
        is_spa_detected: bool = False
    ) -> Optional[any]:
        """
        Handle dynamic content with enhanced strategies for SPAs and lazy loading.
        
        Implements Requirements 2.3, 2.5:
        - Detects and handles single-page applications
        - Implements progressive content loading strategies
        - Handles virtual scrolling and lazy loading scenarios
        
        Args:
            crawler: Configured AsyncWebCrawler instance
            url: URL to crawl with dynamic content handling
            entity_name: Entity name for logging
            is_spa_detected: Whether SPA behavior was detected
            
        Returns:
            Crawl result with enhanced dynamic content or None
        """
        try:
            # Check if crawler is valid
            if crawler is None:
                logger.warning(f"Crawler is None, cannot handle dynamic content for {entity_name}")
                return None
            
            # Use enhanced configuration for detected SPAs
            config = self._get_crawler_config(enhanced_dynamic_handling=is_spa_detected)
            
            logger.debug(f"Handling dynamic content for {entity_name} (SPA: {is_spa_detected})")
            
            # First attempt with standard dynamic handling
            result = await crawler.arun(url=url, config=config)
            
            if result.success and result.markdown:
                content_length = len(result.markdown)
                logger.debug(f"Dynamic content extraction successful: {content_length} chars")
                
                # Check if we got substantial content
                if content_length > 200:
                    return result
                else:
                    logger.debug(f"Insufficient content from dynamic handling, trying enhanced mode")
            
            # If content is insufficient and we haven't tried enhanced mode, try it
            if not is_spa_detected:
                logger.debug(f"Retrying with enhanced SPA handling for {entity_name}")
                enhanced_config = self._get_crawler_config(enhanced_dynamic_handling=True)
                
                # Add additional wait time for complex dynamic content
                await asyncio.sleep(2)
                
                enhanced_result = await crawler.arun(url=url, config=enhanced_config)
                
                if enhanced_result.success and enhanced_result.markdown:
                    enhanced_length = len(enhanced_result.markdown)
                    logger.debug(f"Enhanced dynamic content extraction: {enhanced_length} chars")
                    
                    # Use enhanced result if it's significantly better
                    if enhanced_length > content_length * 1.2:  # 20% improvement threshold
                        return enhanced_result
            
            # Return the best result we got
            return result if result.success else None
            
        except Exception as e:
            logger.warning(f"Dynamic content handling failed for {entity_name}: {e}")
            return None
    
    def _detect_spa_indicators(self, content: str, url: str) -> bool:
        """
        Detect if a website is likely a single-page application.
        
        Args:
            content: Initial page content
            url: Website URL
            
        Returns:
            True if SPA indicators are detected
        """
        if not content:
            return False
        
        content_lower = content.lower()
        
        # Common SPA framework indicators
        spa_indicators = [
            'react', 'vue', 'angular', 'ember', 'backbone',
            'data-reactroot', 'ng-app', 'vue-app', 'ember-app',
            'single page application', 'spa', 'client-side routing',
            'virtual dom', 'component-based', 'progressive web app'
        ]
        
        # Check for SPA indicators in content
        indicator_count = sum(1 for indicator in spa_indicators if indicator in content_lower)
        
        # Check URL patterns that suggest SPA routing
        spa_url_patterns = ['#/', '#!/', '/app/', '/dashboard/']
        url_indicators = sum(1 for pattern in spa_url_patterns if pattern in url.lower())
        
        # Detect if content is very minimal (common in SPAs before JS loads)
        is_minimal_content = len(content.strip()) < 500
        
        # SPA detected if multiple indicators present
        spa_detected = (indicator_count >= 2) or (url_indicators >= 1) or (indicator_count >= 1 and is_minimal_content)
        
        if spa_detected:
            logger.debug(f"SPA detected - indicators: {indicator_count}, URL patterns: {url_indicators}, minimal: {is_minimal_content}")
        
        return spa_detected
    
    async def _handle_lazy_loading_content(
        self, 
        crawler: AsyncWebCrawler, 
        url: str, 
        entity_name: str
    ) -> Optional[any]:
        """
        Handle websites with extensive lazy loading using progressive scrolling.
        
        Implements enhanced virtual scrolling for Requirement 2.3:
        - Progressive content loading with validation
        - Adaptive scrolling based on content growth
        - Optimized for lazy-loaded staff/team sections
        
        Args:
            crawler: Configured AsyncWebCrawler instance
            url: URL to crawl with lazy loading handling
            entity_name: Entity name for logging
            
        Returns:
            Crawl result with comprehensive lazy-loaded content
        """
        try:
            # Check if crawler is valid
            if crawler is None:
                logger.warning(f"Crawler is None, cannot handle lazy loading content for {entity_name}")
                return None
            
            logger.debug(f"Handling lazy loading content for {entity_name}")
            
            # Configure for aggressive lazy loading handling
            lazy_config = CrawlerRunConfig(
                wait_until="networkidle",
                scan_full_page=True,
                remove_overlay_elements=True,
                
                # Aggressive scrolling for lazy content
                scroll_delay=5,  # Longer delay for lazy loading
                max_scroll_steps=15,  # More steps for comprehensive loading
                
                # Extended timeout for lazy loading
                page_timeout=(self.page_timeout + 45) * 1000,
                
                # Preserve more content during lazy loading
                content_filter=PruningContentFilter(
                    threshold=0.35,  # Lower threshold to capture lazy-loaded fragments
                    threshold_type="fixed",
                    min_word_threshold=5
                ),
                
                # Enhanced selectors for lazy-loaded content
                css_selector=(
                    "main, article, .content, .main-content, #content, #main, "
                    ".team, .staff, .people, .members, .leadership, .board, "
                    ".lazy-load, .infinite-scroll, .load-more, .dynamic-content"
                ),
                
                excluded_selector=(
                    "nav, footer, header, .navigation, .menu, "
                    ".advertisement, .ads, .cookie-banner, .popup, "
                    ".modal, .overlay, .sidebar, .breadcrumb, "
                    "script, style, noscript"
                ),
                
                word_count_threshold=5,
                only_text=False
            )
            
            # Execute with lazy loading configuration
            result = await crawler.arun(url=url, config=lazy_config)
            
            if result.success and result.markdown:
                content_length = len(result.markdown)
                logger.debug(f"Lazy loading content extraction: {content_length} chars")
                
                # Validate that we captured meaningful content
                if content_length > 300:
                    return result
                else:
                    logger.debug(f"Lazy loading extraction yielded insufficient content: {content_length} chars")
            
            return result if result.success else None
            
        except Exception as e:
            logger.warning(f"Lazy loading content handling failed for {entity_name}: {e}")
            return None
    
    def _optimize_scroll_strategy(self, content_length: int, is_spa: bool) -> dict:
        """
        Optimize scrolling strategy based on content characteristics.
        
        Args:
            content_length: Length of initially loaded content
            is_spa: Whether the site is detected as SPA
            
        Returns:
            Dictionary with optimized scroll parameters
        """
        # Base strategy
        strategy = {
            "scroll_delay": 3,
            "max_scroll_steps": 8,
            "timeout_buffer": 30
        }
        
        # Adjust for content characteristics
        if content_length < 200:
            # Very minimal content - likely heavy lazy loading
            strategy["scroll_delay"] = 5
            strategy["max_scroll_steps"] = 12
            strategy["timeout_buffer"] = 45
        elif content_length < 500:
            # Some content but likely more to load
            strategy["scroll_delay"] = 4
            strategy["max_scroll_steps"] = 10
            strategy["timeout_buffer"] = 35
        
        # Additional adjustments for SPAs
        if is_spa:
            strategy["scroll_delay"] += 1
            strategy["max_scroll_steps"] += 3
            strategy["timeout_buffer"] += 15
        
        return strategy
    
    def _detect_dynamic_content_patterns(self, content: str, url: str) -> dict:
        """
        Detect various dynamic content patterns to optimize crawling strategy.
        
        Args:
            content: Initial page content
            url: Website URL
            
        Returns:
            Dictionary with detected patterns and recommended strategies
        """
        patterns = {
            "has_lazy_loading": False,
            "has_infinite_scroll": False,
            "has_load_more": False,
            "has_virtual_scroll": False,
            "is_spa": False,
            "content_density": "normal"
        }
        
        if not content:
            patterns["content_density"] = "minimal"
            return patterns
        
        content_lower = content.lower()
        
        # Detect lazy loading indicators
        lazy_indicators = [
            "lazy", "load-more", "show-more", "view-more", 
            "infinite-scroll", "scroll-load", "on-demand"
        ]
        patterns["has_lazy_loading"] = any(indicator in content_lower for indicator in lazy_indicators)
        
        # Detect infinite scroll
        infinite_indicators = ["infinite", "endless", "continuous", "auto-load"]
        patterns["has_infinite_scroll"] = any(indicator in content_lower for indicator in infinite_indicators)
        
        # Detect load more buttons
        load_more_indicators = ["load more", "show more", "view all", "see all", "expand"]
        patterns["has_load_more"] = any(indicator in content_lower for indicator in load_more_indicators)
        
        # Detect virtual scrolling
        virtual_indicators = ["virtual-scroll", "virtualized", "windowing"]
        patterns["has_virtual_scroll"] = any(indicator in content_lower for indicator in virtual_indicators)
        
        # Detect SPA
        patterns["is_spa"] = self._detect_spa_indicators(content, url)
        
        # Determine content density
        content_length = len(content.strip())
        if content_length < 200:
            patterns["content_density"] = "minimal"
        elif content_length < 1000:
            patterns["content_density"] = "light"
        elif content_length > 5000:
            patterns["content_density"] = "heavy"
        else:
            patterns["content_density"] = "normal"
        
        return patterns
    
    async def _apply_adaptive_crawling_strategy(
        self, 
        crawler: AsyncWebCrawler, 
        url: str, 
        entity_name: str, 
        patterns: dict
    ) -> Optional[any]:
        """
        Apply adaptive crawling strategy based on detected content patterns.
        
        Implements comprehensive dynamic content handling for Requirements 2.3, 2.5:
        - Adapts strategy based on detected patterns
        - Optimizes for different types of dynamic content
        - Provides fallback mechanisms for complex scenarios
        
        Args:
            crawler: Configured AsyncWebCrawler instance
            url: URL to crawl
            entity_name: Entity name for logging
            patterns: Detected content patterns
            
        Returns:
            Optimized crawl result
        """
        try:
            # Check if crawler is valid
            if crawler is None:
                logger.warning(f"Crawler is None, cannot apply adaptive strategy for {entity_name}")
                return None
            
            logger.debug(f"Applying adaptive strategy for {entity_name}: {patterns}")
            
            # Choose strategy based on detected patterns
            if patterns["has_lazy_loading"] or patterns["has_infinite_scroll"]:
                # Use lazy loading specialized handling
                result = await self._handle_lazy_loading_content(crawler, url, entity_name)
                if result and result.success:
                    return result
            
            if patterns["is_spa"] or patterns["content_density"] == "minimal":
                # Use enhanced SPA handling
                result = await self._handle_dynamic_content(crawler, url, entity_name, is_spa_detected=True)
                if result and result.success:
                    return result
            
            # Fallback to standard enhanced handling
            result = await self._handle_dynamic_content(crawler, url, entity_name, is_spa_detected=False)
            return result
            
        except Exception as e:
            logger.warning(f"Adaptive crawling strategy failed for {entity_name}: {e}")
            return None
    
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
            # Check if crawler is valid
            if crawler is None:
                logger.warning(f"Crawler is None, cannot crawl relevant pages for {entity_name}")
                return None
            
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
                    
                    # First attempt with standard dynamic content handling
                    result = await asyncio.wait_for(
                        crawler.arun(url=target_url, config=self._get_crawler_config()),
                        timeout=self.page_timeout
                    )
                    
                    # If content is insufficient, try enhanced dynamic handling
                    if result.success and result.markdown and len(result.markdown.strip()) < 100:
                        logger.debug(f"Trying enhanced dynamic handling for relevant page {i+1}")
                        
                        enhanced_result = await asyncio.wait_for(
                            self._handle_dynamic_content(crawler, target_url, entity_name, is_spa_detected=True),
                            timeout=self.page_timeout + 30
                        )
                        
                        if enhanced_result and enhanced_result.success and enhanced_result.markdown:
                            if len(enhanced_result.markdown) > len(result.markdown):
                                result = enhanced_result
                                logger.debug(f"Enhanced dynamic handling improved content for page {i+1}")
                    
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