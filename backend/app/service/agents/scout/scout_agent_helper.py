import asyncio
import random
import re
from playwright.async_api import async_playwright
from app.model.lead_gen_model import ScrapedBusinessData

async def extract_business_info(page, index=0):
    """
    Extracts data from the currently open business card in the side panel.
    Uses the new scraping strategy based on Google Maps HTML structure.
    
    Args:
        page: Playwright page object
        index: Index of the business card to extract (0-based)
    """

    data = ScrapedBusinessData()

    try:
        # Wait for the business card to load
        await page.wait_for_selector('div[role="article"]', timeout=5000)
        
        # Get the business card at the specified index
        business_card = page.locator('div[role="article"]').nth(index)
        
        # 1. Organization Name - Extract from aria-label attribute
        try:
            aria_label = await business_card.get_attribute("aria-label")
            if aria_label:
                data.org_name = aria_label.strip()
        except Exception as e:
            print(f"Error extracting org_name: {e}")

        # 2. Review Score - Extract from span.MW4etd
        try:
            score_locator = business_card.locator('span.MW4etd[aria-hidden="true"]').first
            if await score_locator.count() > 0:
                data.review_score = (await score_locator.inner_text()).strip()
        except Exception as e:
            print(f"Error extracting review_score: {e}")

        # 3. Total Reviews - Extract from span.UY7F9
        try:
            reviews_locator = business_card.locator('span.UY7F9[aria-hidden="true"]').first
            if await reviews_locator.count() > 0:
                reviews_text = await reviews_locator.inner_text()
                # Remove parentheses and commas
                data.total_reviews = reviews_text.strip().replace('(', '').replace(')', '').replace(',', '')
        except Exception as e:
            print(f"Error extracting total_reviews: {e}")

        # 4. Address - Look for pattern: <span aria-hidden="true">·</span> <span>address</span>
        try:
            # Find all spans with aria-hidden="true" containing "·"
            separator_spans = business_card.locator('span[aria-hidden="true"]')
            separator_count = await separator_spans.count()
            
            for i in range(separator_count):
                span_text = await separator_spans.nth(i).inner_text()
                if span_text.strip() == "·":
                    # Get the next sibling span
                    parent = separator_spans.nth(i).locator('..')
                    next_spans = await parent.locator('span').all()
                    
                    # Check spans after the separator
                    for span in next_spans:
                        span_content = await span.inner_text()
                        # Check if it looks like an address (contains numbers and street keywords)
                        if re.search(r'\d+\s+\w+\s+(Street|St|Avenue|Ave|Road|Rd|Boulevard|Blvd|Drive|Dr|Suite|Ste|#)', span_content, re.IGNORECASE):
                            data.address = span_content.strip()
                            break
                    
                    if data.address:
                        break
        except Exception as e:
            print(f"Error extracting address: {e}")

        # 5. Website URL - Extract from a.lcr4fd.S9kvJb href attribute
        try:
            website_link = business_card.locator('a.lcr4fd.S9kvJb').first
            if await website_link.count() > 0:
                href = await website_link.get_attribute("href")
                data.website_url = href
        except Exception as e:
            print(f"Error extracting website_url: {e}")

        # 6. Primary Contact (Phone) - Look for phone number in span.UsdlK
        try:
            phone_locator = business_card.locator('span.UsdlK').first
            if await phone_locator.count() > 0:
                phone_text = await phone_locator.inner_text()
                data.primary_contact = phone_text.strip()
        except Exception as e:
            print(f"Error extracting phone: {e}")

    except Exception as e:
        print(f"Error extracting business data: {e}")

    return data

async def scrape_google_maps(query, headless=True):
    """
    Scrapes Google Maps for business information.
    
    Args:
        query: Search query string
        headless: Run browser in headless mode (True for production/cloud, False for debugging)
    """
    async with async_playwright() as p:
        # Launch browser in headless mode for cloud deployment
        # Additional args for running in containerized environments (Docker, Cloud Run, etc.)
        browser = await p.chromium.launch(
            headless=headless,
            args=[
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-dev-shm-usage',
                '--disable-gpu',
                '--no-first-run',
                '--no-zygote',
                '--single-process',
                '--disable-blink-features=AutomationControlled'
            ]
        )
        
        # Create context with realistic user agent to avoid detection
        context = await browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            viewport={'width': 1920, 'height': 1080}
        )
        page = await context.new_page()

        # Navigate to Google Maps
        print(f"Searching for: {query}")
        await page.goto("https://www.google.com/maps")
        
        # Handle "Before you continue" cookie consent if it appears
        try:
            await page.get_by_role("button", name="Accept all").click(timeout=3000)
        except:
            pass # Cookie banner might not appear

        # Input query
        search_input = page.locator("input#searchboxinput")
        await search_input.fill(query)
        await search_input.press("Enter")

        # Wait for results to load in the sidebar (feed)
        # The list items usually have a class like 'hfpxzc' (the link overlay)
        await page.wait_for_selector('a[href*="/maps/place/"]', timeout=10000)

        # Get the list of results
        # Note: We need to handle scrolling if we wanted > 10, but for 10 usually they load or 
        # we might need one small scroll.
        
        # We select the "link" elements that overlay the cards
        # using the class 'hfpxzc' is a common trick for Maps, or matching by href structure
        listings_locator = page.locator('a[href*="/maps/place/"]')
        
        # Ensure we have at least some results
        count = await listings_locator.count()
        print(f"Found {count} initial listings (scrolling might be needed for more)")

        results = []
        
        # Limit to 10
        limit = 2
        processed = 0

        # We iterate by index. Note: DOM might update, so we re-query or be careful.
        # Safest way in Playwright for master-detail:
        for i in range(count):
            if processed >= limit:
                break
            
            # Re-locate the element to avoid stale handles
            listing = listings_locator.nth(i)
            
            try:
                # Click the listing to open details
                await listing.click()
                
                # Wait for the Details Panel to load (look for h1)
                await page.wait_for_selector('h1', timeout=5000)
                
                # Scrape - pass the index to extract the correct business card
                business_data = await extract_business_info(page, index=i)
                
                # Log matching schema
                print(f"Scraped {i+1}: {business_data.org_name}")
                results.append(business_data)
                
                processed += 1
                
                # Throttling as requested
                sleep_time = random.uniform(10, 30)
                print(f"Waiting {sleep_time:.2f} seconds...")
                await asyncio.sleep(sleep_time)

            except Exception as e:
                print(f"Failed to process listing {i}: {e}")

        await browser.close()
        return results

# Example Usage
if __name__ == "__main__":
    # Query 1
    async def main():
        data_newark = await scrape_google_maps("diagnostic centers newark, new jersey")
        print("\n--- FINAL OUTPUT (Newark) ---")
        print(data_newark)

        # Query 2 (You can uncomment to run)
        # data_dhaka = await scrape_google_maps("study abroad consultants gulhsan, dhaka")
        # print(data_dhaka)
    asyncio.run(main())
