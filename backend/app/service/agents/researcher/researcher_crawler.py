import asyncio
import json
import logging
from typing import List, Dict, Set
from urllib.parse import urljoin, urlparse
from playwright.async_api import async_playwright, Page

logger = logging.getLogger("researcher_crawler")


class ResearcherCrawler:
    """
    Dynamic web crawler that extracts information from non-static websites.
    Uses headless browsing to navigate through websites, execute JavaScript, 
    and render the full DOM before extracting content as markdown.
    """
    
    def __init__(self, max_pages: int = 50):
        self.visited_urls: Set[str] = set()
        self.pages_data: List[Dict[str, str]] = []
        self.pages_queue: List[str] = []
        self.max_pages = max_pages
        self.base_domain = None

    async def start(self, website_url: str) -> List[Dict[str, str]]:
        """
        Start crawling from the given website URL.
        
        Args:
            website_url: The base URL to start crawling from
            
        Returns:
            List of dictionaries containing page_url and markdown_content
        """
        self.base_domain = urlparse(website_url).netloc
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            
            # Set user agent to avoid bot detection
            await page.set_extra_http_headers({
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            })

            # Initial crawl of the base page
            await self.crawl_page(page, website_url)

            # Process subpages recursively
            while self.pages_queue and len(self.visited_urls) < self.max_pages:
                next_url = self.pages_queue.pop(0)
                if next_url not in self.visited_urls:
                    await self.crawl_page(page, next_url)

            await browser.close()
            
        logger.info(f"Crawling completed. Processed {len(self.visited_urls)} pages.")
        return self.pages_data

    async def crawl_page(self, page: Page, url: str):
        """
        Crawl a single page and extract its content as markdown.
        
        Args:
            page: Playwright page instance
            url: URL to crawl
        """
        if url in self.visited_urls:
            return

        # Check if URL belongs to the same domain
        if not self._is_same_domain(url):
            return

        logger.info(f"Crawling: {url}")
        self.visited_urls.add(url)

        try:
            # Navigate to the page and wait for it to load
            await page.goto(url, wait_until="networkidle", timeout=30000)
            
            # Handle dynamic content
            await self._handle_dynamic_content(page)

            # Extract page content as markdown
            markdown_content = await self._extract_markdown_content(page)
            
            # Store the page data
            page_data = {
                "page_url": url,
                "markdown_content": markdown_content
            }
            self.pages_data.append(page_data)

            # Find and queue new pages to crawl
            new_pages = await self._find_internal_links(page)
            for new_url in new_pages:
                if new_url not in self.visited_urls and new_url not in self.pages_queue:
                    self.pages_queue.append(new_url)

        except Exception as e:
            logger.error(f"Error crawling {url}: {e}")

    async def _handle_dynamic_content(self, page: Page):
        """
        Handle dynamic content including infinite scroll, lazy loading, and pagination.
        """
        try:
            # Wait for any initial JavaScript to execute
            await page.wait_for_timeout(2000)
            
            # Handle infinite scroll / lazy loading
            previous_height = await page.evaluate("document.body.scrollHeight")
            scroll_attempts = 0
            max_scroll_attempts = 10
            
            while scroll_attempts < max_scroll_attempts:
                # Scroll to bottom
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await page.wait_for_timeout(1500)  # Wait for content to load
                
                # Check if new content loaded
                new_height = await page.evaluate("document.body.scrollHeight")
                if new_height == previous_height:
                    break
                    
                previous_height = new_height
                scroll_attempts += 1

            # Look for "Load More" or pagination buttons
            load_more_selectors = [
                'button:has-text("Load More")',
                'button:has-text("Show More")',
                'a:has-text("Next")',
                '.load-more',
                '.show-more',
                '.pagination a:last-child'
            ]
            
            for selector in load_more_selectors:
                try:
                    element = await page.query_selector(selector)
                    if element and await element.is_visible():
                        await element.click()
                        await page.wait_for_timeout(2000)
                        break
                except:
                    continue

        except Exception as e:
            logger.warning(f"Error handling dynamic content: {e}")

    async def _extract_markdown_content(self, page: Page) -> str:
        """
        Extract the page content and convert it to markdown format.
        
        Returns:
            Markdown formatted content of the page
        """
        try:
            # Get the page title
            title = await page.title()
            
            # Extract main content areas
            content_selectors = [
                'main',
                'article', 
                '.content',
                '.main-content',
                '#content',
                'body'
            ]
            
            markdown_content = f"# {title}\n\n"
            
            # Try to find the main content area
            main_content = None
            for selector in content_selectors:
                element = await page.query_selector(selector)
                if element:
                    main_content = element
                    break
            
            if not main_content:
                main_content = await page.query_selector('body')
            
            # Extract text content and structure
            if main_content:
                # Get headings and paragraphs
                headings = await main_content.query_selector_all('h1, h2, h3, h4, h5, h6')
                paragraphs = await main_content.query_selector_all('p')
                lists = await main_content.query_selector_all('ul, ol')
                
                # Process headings
                for heading in headings:
                    tag_name = await heading.evaluate('el => el.tagName.toLowerCase()')
                    text = await heading.inner_text()
                    if text.strip():
                        level = int(tag_name[1])  # h1 -> 1, h2 -> 2, etc.
                        markdown_content += f"{'#' * level} {text.strip()}\n\n"
                
                # Process paragraphs
                for paragraph in paragraphs:
                    text = await paragraph.inner_text()
                    if text.strip():
                        markdown_content += f"{text.strip()}\n\n"
                
                # Process lists
                for list_element in lists:
                    list_items = await list_element.query_selector_all('li')
                    tag_name = await list_element.evaluate('el => el.tagName.toLowerCase()')
                    
                    for i, item in enumerate(list_items):
                        text = await item.inner_text()
                        if text.strip():
                            if tag_name == 'ul':
                                markdown_content += f"- {text.strip()}\n"
                            else:  # ol
                                markdown_content += f"{i+1}. {text.strip()}\n"
                    
                    markdown_content += "\n"
                
                # If no structured content found, get all text
                if len(markdown_content.strip()) <= len(title) + 10:
                    all_text = await main_content.inner_text()
                    markdown_content += all_text
            
            return markdown_content.strip()
            
        except Exception as e:
            logger.error(f"Error extracting markdown content: {e}")
            # Fallback to basic text extraction
            try:
                return await page.inner_text('body')
            except:
                return ""

    async def _find_internal_links(self, page: Page) -> List[str]:
        """
        Find all internal links on the current page.
        
        Returns:
            List of internal URLs found on the page
        """
        internal_links = []
        
        try:
            # Get all links on the page
            links = await page.query_selector_all('a[href]')
            
            for link in links:
                href = await link.get_attribute('href')
                if href:
                    # Convert relative URLs to absolute
                    absolute_url = urljoin(page.url, href)
                    
                    # Check if it's an internal link
                    if self._is_same_domain(absolute_url) and self._is_valid_url(absolute_url):
                        internal_links.append(absolute_url)
            
            # Remove duplicates while preserving order
            seen = set()
            unique_links = []
            for link in internal_links:
                if link not in seen:
                    seen.add(link)
                    unique_links.append(link)
            
            return unique_links
            
        except Exception as e:
            logger.error(f"Error finding internal links: {e}")
            return []

    def _is_same_domain(self, url: str) -> bool:
        """
        Check if the URL belongs to the same domain as the base URL.
        
        Args:
            url: URL to check
            
        Returns:
            True if same domain, False otherwise
        """
        try:
            parsed_url = urlparse(url)
            return parsed_url.netloc == self.base_domain or parsed_url.netloc == f"www.{self.base_domain}" or parsed_url.netloc == self.base_domain.replace("www.", "")
        except:
            return False

    def _is_valid_url(self, url: str) -> bool:
        """
        Check if the URL is valid for crawling (not a file download, mailto, etc.).
        
        Args:
            url: URL to validate
            
        Returns:
            True if valid for crawling, False otherwise
        """
        try:
            parsed_url = urlparse(url)
            
            # Skip non-http protocols
            if parsed_url.scheme not in ['http', 'https']:
                return False
            
            # Skip file downloads
            file_extensions = ['.pdf', '.doc', '.docx', '.xls', '.xlsx', '.zip', '.rar', '.exe', '.dmg']
            if any(url.lower().endswith(ext) for ext in file_extensions):
                return False
            
            # Skip fragments (same page anchors)
            if parsed_url.fragment and not parsed_url.path:
                return False
                
            return True
            
        except:
            return False

    def save_results_to_file(self, filename: str = "crawled_pages.json"):
        """
        Save the crawled results to a JSON file.
        
        Args:
            filename: Name of the output file
        """
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(self.pages_data, f, indent=2, ensure_ascii=False)
            logger.info(f"Results saved to {filename}")
        except Exception as e:
            logger.error(f"Error saving results to file: {e}")


# Example usage
if __name__ == "__main__":
    async def main():
        crawler = ResearcherCrawler(max_pages=10)
        results = await crawler.start("https://example.com")
        
        print(f"Crawled {len(results)} pages:")
        for result in results:
            print(f"- {result['page_url']}")
            print(f"  Content length: {len(result['markdown_content'])} characters")
        
        # Save results to file
        crawler.save_results_to_file()

    # Run the crawler
    asyncio.run(main())