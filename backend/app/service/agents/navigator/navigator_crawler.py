import asyncio
import json
import re
from typing import List, Dict, Set
from playwright.async_api import async_playwright, Page
from app.model.lead_gen_model import PartnerContact


class NavigatorCrawler:
    def __init__(self):
        self.visited_urls: Set[str] = set()
        self.contacts: List[Dict[str, str]] = []
        self.subpages_queue: List[str] = []

    async def start(self, lead_guid:str, url: str, primary_contact:str):
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()

            # Initial crawl
            await self.crawl(page, url, lead_guid, primary_contact)

            # Process subpages recursively
            while self.subpages_queue:
                next_url = self.subpages_queue.pop(0)
                if next_url not in self.visited_urls:
                    await self.crawl(page, next_url, lead_guid, primary_contact)

            await browser.close()
            # self.save_results()
            return self._map_contacts_to_dto()


    async def crawl(self, page: Page, url: str, lead_guid:str, primary_contact:str):
        if url in self.visited_urls:
            return

        print(f"Crawling: {url}")
        self.visited_urls.add(url)

        try:
            await page.goto(url, wait_until="networkidle", timeout=90000)
            await self._handle_dynamic_content(page)

            page_contacts = await self._extract_contacts(page)
            for contact in page_contacts:
                contact['url'] = url
                contact['lead_guid'] = lead_guid
                contact['primary_contact'] = primary_contact
            self.contacts.extend(page_contacts)

            new_subpages = await self._find_subpages(page)
            for subpage in new_subpages:
                if subpage['url'] not in self.visited_urls:
                    self.subpages_queue.append(subpage['url'])

        except Exception as e:
            print(f"Error crawling {url}: {e}")

    async def _handle_dynamic_content(self, page: Page):
        # Handle infinite scroll / lazy loading
        previous_height = await page.evaluate("document.body.scrollHeight")
        while True:
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await page.wait_for_timeout(1000)  # Wait for content to load
            new_height = await page.evaluate("document.body.scrollHeight")
            if new_height == previous_height:
                break
            previous_height = new_height

    async def _extract_contacts(self, page: Page) -> List[Dict[str, str]]:
        content = await page.content()
        found_contacts = []

        # Regex Contact Extraction (simplified for example)
        # Emails
        emails = set(re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', content))
        for email in emails:
            found_contacts.append({"name": "Email", "contact_info": email})

        # Phone Numbers (US format)
        # Pattern matches various US phone number formats:
        # (123) 456-7890, 123-456-7890, 123.456.7890, 123 456 7890, +1-123-456-7890, etc.
        phone_pattern = r'(?:\+?1[-.\s]?)?\(?([0-9]{3})\)?[-.\s]?([0-9]{3})[-.\s]?([0-9]{4})\b'
        phone_matches = re.findall(phone_pattern, content)
        phones = set()
        for match in phone_matches:
            # Reconstruct phone number in standard format
            formatted_phone = f"({match[0]}) {match[1]}-{match[2]}"
            phones.add(formatted_phone)
        
        for phone in phones:
            found_contacts.append({"name": "Phone", "contact_info": phone})

        # Social Media (Basic check)
        socials = ["facebook.com", "twitter.com", "linkedin.com", "instagram.com"]
        links = await page.query_selector_all("a")
        for link in links:
            href = await link.get_attribute("href")
            if href:
                for social in socials:
                    if social in href:
                        found_contacts.append({"name": social.split('.')[0].capitalize(), "contact_info": href})

        return found_contacts

    async def _find_subpages(self, page: Page) -> List[Dict[str, str]]:
        subpages = []
        keywords = ["about", "contact", "events", "team"]

        links = await page.query_selector_all("a")
        for link in links:
            text = await link.inner_text()
            href = await link.get_attribute("href")

            if text and href:
                for keyword in keywords:
                    if keyword.lower() in text.lower():
                        # Normalize URL
                        if not href.startswith("http"):
                            # Handle relative URLs - highly simplified, assumes base is main domain
                            # For robustness, we should use urllib.parse.urljoin
                            from urllib.parse import urljoin
                            base_url = page.url
                            href = urljoin(base_url, href)

                        subpages.append({"name": text.strip(), "url": href})
                        break
        return subpages

    def save_results(self):
        output = {"contacts": self.contacts}
        with open("contacts.json", "w") as f:
            json.dump(output, f, indent=4)
        print("Results saved to contacts.json")

    def _map_contacts_to_dto(self):
        contact_dtos = {PartnerContact(**contact) for contact in self.contacts}
        print(f"Mapped {len(contact_dtos)} contacts to DTOs")
        print(contact_dtos)
        return contact_dtos


# if __name__ == "__main__":
#     crawler = NavigatorCrawler()
#     # Example usage - would normally take from args
#     import sys
#
#     if len(sys.argv) > 1:
#         asyncio.run(crawler.start(sys.argv[1]))
#     else:
#         print("Please provide a URL")
