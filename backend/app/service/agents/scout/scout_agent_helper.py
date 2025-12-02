import asyncio
import random
import re
from playwright.async_api import async_playwright

async def extract_business_info(page):
    """
    Extracts data from the currently open details panel.
    """
    data = {
        "org_name": None,
        "primary_contact": None,
        "review_score": None,
        "total_reviews": None,
        "website_url": None
    }

    try:
        # 1. Organization Name (Usually the H1 in the side panel)
        # We wait briefly for the main header to appear
        await page.wait_for_selector("h1", timeout=5000)
        data["org_name"] = await page.locator("h1").first.inner_text()

        # 2. Review Score & Total Reviews
        # These are usually grouped near the stars.
        # We look for the span that contains the numeric rating (e.g. "4.7")
        # Google often puts the score in a div with role="img" aria-label="4.7 stars"
        # But a more robust way is looking for the text directly if the aria-label is complex
        try:
            rating_locator = page.locator('div[role="main"] span[role="img"]').first
            aria_label = await rating_locator.get_attribute("aria-label") 
            # aria_label format: "4.7 stars 87 Reviews" or similar
            if aria_label:
                # Extract score
                score_match = re.search(r"(\d\.\d)", aria_label)
                if score_match:
                    data["review_score"] = score_match.group(1)
                
                # Extract count (sometimes in the label, sometimes in a separate span)
                # Let's try to find the count in the text next to the stars usually inside parenthesis
                count_locator = page.locator('div[role="main"] button[jsaction*="reviewChart"]').first
                if await count_locator.count() > 0:
                     count_text = await count_locator.inner_text() # e.g. "(87)"
                     data["total_reviews"] = count_text.replace("(", "").replace(")", "").replace(",", "")
        except Exception:
            pass # Keep default None if scraping fails

        # 3. Website URL
        # Look for the button with 'website' in the aria-label or data-item-id="authority"
        try:
            website_btn = page.locator('a[data-item-id="authority"]').first
            if await website_btn.count() > 0:
                data["website_url"] = await website_btn.get_attribute("href")
        except Exception:
            pass

        # 4. Primary Contact (Phone)
        # Look for button with data-item-id that starts with 'phone'
        try:
            phone_btn = page.locator('button[data-item-id^="phone"]').first
            if await phone_btn.count() > 0:
                # The text is often inside a div within the button
                data["primary_contact"] = (await phone_btn.get_attribute("aria-label")).replace("Phone: ", "")
        except Exception:
            pass

    except Exception as e:
        print(f"Error extracting data: {e}")

    return data

async def scrape_google_maps(query):
    async with async_playwright() as p:
        # Launch browser (headless=False to see it working, set to True for production)
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()
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
                
                # Scrape
                business_data = await extract_business_info(page)
                
                # Log matching schema
                print(f"Scraped {i+1}: {business_data['org_name']}")
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
