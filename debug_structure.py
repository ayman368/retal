from playwright.async_api import async_playwright
import asyncio

async def run():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        # Navigate to the page
        await page.goto("https://www.saudiexchange.sa/wps/portal/saudiexhcnage/hidden/company-profile-main/!ut/p/z1/04_Sj9CPykssy0xPLMnMz0vMAfIjo8ziTR3NDIw8LAz83d2MXA0C3SydAl1c3Q0NvE30I4EKzBEKDMKcTQzMDPxN3H19LAzdTU31w8syU8v1wwkpK8hOMgUA-oskdg!!/?companySymbol=4322", timeout=60000)
        
        # Wait for meaningful content
        await page.wait_for_selector(".stats_overview", timeout=30000)
        await page.wait_for_timeout(3000)

        target_headers = ["Last Trade", "Best Bid"]
        
        print("--- Debugging Selectors ---")
        for header in target_headers:
            print(f"\nScanning for: {header}")
            # Try specific exact match
            els = await page.get_by_text(header, exact=True).all()
            print(f"Found {len(els)} exact matches.")
            
            for i, el in enumerate(els):
                if await el.is_visible():
                    print(f"  Match {i} (Visible):")
                    # Get parent HTML to see context
                    parent = el.locator("xpath=..")
                    html = await parent.inner_html()
                    text = await parent.text_content()
                    print(f"    Parent HTML snippet: {html[:200]}...")
                    print(f"    Parent Text: {text.strip()}")
                else:
                    print(f"  Match {i} (Hidden)")
        
        await browser.close()

if __name__ == "__main__":
    asyncio.run(run())
