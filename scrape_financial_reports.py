import asyncio
import json
from typing import Dict, List, Any
from playwright.async_api import async_playwright, Page, Locator

# --- Configuration ---
BASE_URL = "https://www.saudiexchange.sa/wps/portal/saudiexchange/hidden/company-profile-main/!ut/p/z1/04_Sj9CPykssy0xPLMnMz0vMAfIjo8ziTR3NDIw8LAz83d2MXA0C3SydAl1c3Q0NvE30w1EVGAQHmAIVBPga-xgEGbgbmOlHEaPfAAdwNCCsPwqvEndzdAVYnAhWgMcNXvpR6Tn5SZDwyCgpKbBSNVA1KElMSSwvzVEFujE5P7cgMa8yuDI3KR-oyMTYyEg_OLFIvyA3NMIgMyA3XNdREQDj62qi/dz/d5/L0lHSkovd0RNQU5rQUVnQSEhLzROVkUvZW4!/"
TIMEOUT_MS = 120000

class FinancialReportsScraper:
    def __init__(self, headless: bool = False):
        self.headless = headless

    async def scrape(self) -> Dict[str, Any]:
        """Main method to scrape only Financial Statements and Reports."""
        reports_data = {}
        
        async with async_playwright() as p:
            # Launch browser
            browser = await p.chromium.launch(headless=self.headless, args=["--disable-http2"])
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (HTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                viewport={"width": 1600, "height": 1000},
                locale="en-US"
            )
            page = await context.new_page()
            
            try:
                print(f"Navigating to {BASE_URL}...")
                
                # Retry logic for navigation
                for attempt in range(3):
                    try:
                        await page.goto(BASE_URL, timeout=TIMEOUT_MS)
                        await page.wait_for_load_state("domcontentloaded")
                        break
                    except Exception as nav_e:
                        print(f"  -> Navigation attempt {attempt+1} failed: {nav_e}")
                        if attempt == 2:
                             print("  -> Max retries reached. Returning empty data.")
                             await browser.close()
                             return reports_data
                        await asyncio.sleep(5)
                
                # Navigate to Financials Tab
                print("Processing Financials Tab...")
                if await self._click_tab(page, "Financials"):
                    await page.wait_for_timeout(2000) 
                    
                    # Target Section: FINANCIAL STATEMENTS AND REPORTS
                    print("\n--- Scraping FINANCIAL STATEMENTS AND REPORTS ---")
                    reports_data = await self._scrape_statements_and_reports(page)
                    
                else:
                    print("Could not find 'Financials' tab.")

            except Exception as e:
                print(f"An error occurred during scraping: {e}")
            finally:
                await browser.close()
                
        return reports_data

    # --- Helper methods ---

    async def _click_tab(self, page: Page, tab_name: str) -> bool:
        """Helper to find and click a tab."""
        return await self._js_click_tab(page, tab_name)

    async def _js_click_tab(self, page: Page, text: str) -> bool:
        """Robust JS click using scoring strategy."""
        return await page.evaluate(f"""(text) => {{
            const target = text.toLowerCase();
            const tags = ['li', 'a', 'button', 'div', 'span', 'h2', 'h3', 'h4', 'h5'];
            let best = null;
            let bestScore = -9999;
            
            function getScore(el) {{
               let score = 0;
               const txt = (el.innerText || '').toLowerCase().trim();
               if (!txt.includes(target)) return -10000;
               score -= txt.length; 
               const tag = el.tagName.toLowerCase();
               if (['li', 'a', 'button'].includes(tag)) score += 2000;
               else if (['div', 'span'].includes(tag)) score += 500;
               if (txt === target) score += 1000;
               if (el.offsetParent !== null) score += 100;
               return score;
            }}
            
            const all = document.querySelectorAll(tags.join(','));
            for (const el of all) {{
               if (el.offsetParent === null) continue;
               const s = getScore(el);
               if (s > bestScore) {{
                   bestScore = s;
                   best = el;
               }}
            }}
            
            if (best && bestScore > -5000) {{
                best.scrollIntoView();
                best.click();
                return true;
            }}
            return false;
        }}""", text)

    async def _scrape_statements_and_reports(self, page: Page) -> Dict[str, Any]:
        """
        Scrapes 'FINANCIAL STATEMENTS AND REPORTS'.
        """
        reports_data = {}
        
        print("\n  -> Preparing view for FINANCIAL STATEMENTS AND REPORTS...")
        
        try:
            # Try specific text
            clicked = await self._js_click_tab(page, "FINANCIAL STATEMENTS AND REPORTS")
            if not clicked:
                 clicked = await self._js_click_tab(page, "Financial Statements")
            
            if not clicked:
                print("  -> Failed to click 'FINANCIAL STATEMENTS AND REPORTS' tab.")
                return reports_data
            
            await page.wait_for_timeout(5000)

            # Locate the main table
            table_locator = page.locator(".tableStyle table")
            try:
                await table_locator.first.wait_for(state="visible", timeout=10000)
            except: pass

            if await table_locator.count() == 0:
                print("  -> Main table (.tableStyle table) not found in DOM!")
                return reports_data
            
            print("  -> Found main table. Parsing rows sequentially...")

            # Capture ALL links
            raw_data = await page.evaluate("""() => {
                const rows = Array.from(document.querySelectorAll('.tableStyle table tr'));
                const results = {};
                let currentSection = 'General Reports';
                
                rows.forEach(row => {
                    const text = row.innerText.trim();
                    
                    if (text === 'Financial Statements' || text === 'XBRL' || text === 'Board Report' || text === 'ESG Report') {
                        currentSection = text;
                        results[currentSection] = [];
                        return; 
                    }
                    
                    const th = row.querySelector('th');
                    if (th) {
                        const thText = th.innerText.trim();
                         if (['Financial Statements', 'XBRL', 'Board Report', 'ESG Report'].includes(thText)) {
                            currentSection = thText;
                            results[currentSection] = [];
                            return;
                        }
                    }
                    
                    if (!results[currentSection]) results[currentSection] = [];

                    const anchors = Array.from(row.querySelectorAll('a'));
                    anchors.forEach(a => {
                        const href = a.href;
                        if (!href || href.includes('javascript') || href === '#') return;
                        
                        let context = '';
                        const firstCell = row.querySelector('td');
                        if (firstCell) context = firstCell.innerText.trim();
                        
                        results[currentSection].push({
                            url: href,
                            context: context,
                            text: a.innerText.trim()
                        });
                    });
                });
                return results;
            }""")
            
            for section, items in raw_data.items():
                if not items: continue
                clean_items = []
                for item in items:
                    url = item['url']
                    lower_url = url.lower()
                    f_type = 'unknown'
                    if '.pdf' in lower_url: f_type = 'pdf'
                    elif '.xls' in lower_url: f_type = 'excel'
                    else: f_type = 'other'
                    
                    clean_items.append({
                        "url": url,
                        "file_type": f_type,
                        "context": item['context'],
                        "row_info": item['text']
                    })
                
                reports_data[section] = clean_items
                print(f"      -> Saved {len(clean_items)} items for {section}")

        except Exception as e:
            print(f"  -> Error processing statements section: {e}")
            
        return reports_data

async def main():
    scraper = FinancialReportsScraper(headless=False)
    data = await scraper.scrape()
    
    # Save to a dedicated JSON file for reports
    output_file = "scrape_financial_reports.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)
        
    print(f"\nReports scraping complete. Data saved to {output_file}")

if __name__ == "__main__":
    asyncio.run(main())
