import asyncio
import json
import re
from typing import Dict, List, Any
from playwright.async_api import async_playwright, Page, Locator

# --- Configuration ---
# Using the same URL and timeout as the main script
BASE_URL = "https://www.saudiexchange.sa/wps/portal/saudiexchange/hidden/company-profile-main/!ut/p/z1/04_Sj9CPykssy0xPLMnMz0vMAfIjo8ziTR3NDIw8LAz83d2MXA0C3SydAl1c3Q0NvE30w1EVGAQHmAIVBPga-xgEGbgbmOlHEaPfAAdwNCCsPwqvEndzdAVYnAhWgMcNXvpR6Tn5SZDwyCgpKbBSNVA1KElMSSwvzVEFujE5P7cgMa8yuDI3KR-oyMTYyEg_OLFIvyA3NMIgMyA3XNdREQDj62qi/dz/d5/L0lHSkovd0RNQU5rQUVnQSEhLzROVkUvZW4!/"
TIMEOUT_MS = 120000

class FinancialHistoryScraper:
    def __init__(self, headless: bool = False):
        self.headless = headless

    async def scrape(self) -> Dict[str, Any]:
        """
        Scrapes Historical Financial Data strictly following User's workflow:
        1. Click 'Display Previous Periods' ONCE at the start.
        2. Iterate sub-tabs and periods and scrape valid tables.
        """
        history_data = {}
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=self.headless, args=["--disable-http2"])
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (HTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                viewport={"width": 1600, "height": 1000},
                locale="en-US"
            )
            page = await context.new_page()
            
            try:
                print(f"Navigating to {BASE_URL}...")
                await page.goto(BASE_URL, timeout=TIMEOUT_MS)
                await page.wait_for_load_state("domcontentloaded")
                
                print("Processing Financials...")
                if await self._click_tab(page, "Financials"):
                    await page.wait_for_timeout(3000)
                    await self._js_click_tab(page, "FINANCIAL INFORMATION")
                    await page.wait_for_timeout(2000)

                    # --- Step 1: Global History Activation ---
                    print("  -> Step 1: Activating History Mode (Clicking 'Display Previous Periods' ONCE)...")
                    
                    # Check if already visible (just in case)
                    if not await self._table_has_history(page):
                        await self._click_display_previous_periods(page)
                        # Wait for toggle
                        print("      -> Waiting for history headers (2021/2020)...")
                        for _ in range(15):
                            await page.wait_for_timeout(1000)
                            if await self._table_has_history(page):
                                print("      -> History headers appeared!")
                                break
                    else:
                        print("      -> History headers already visible. Skipping click.")

                    # --- Step 2: Iterate and Scrape (No more clicking) ---
                    sub_tabs = ["Balance Sheet", "Statement Of Income", "Cash Flows"]
                    periods = ["Annually", "Quarterly"]
                    
                    for tab_name in sub_tabs:
                        print(f"\n  -> Processing Sub-tab: {tab_name}...")
                        if not await self._js_click_tab(page, tab_name):
                             print(f"    -> Warning: Could not click {tab_name}")
                             continue
                        await page.wait_for_timeout(2500)

                        for period in periods:
                            print(f"    -> Processing Period: {period}...")
                            await self._js_click_tab(page, period)
                            await page.wait_for_timeout(2500)
                            
                            # Just Extract
                            # We grab the largest visible table, assuming it's the correct one
                            # OR we check strictly for history if we want to be safe, 
                            # but user said "don't click again", so we just take what we have.
                            
                            target_table = None
                            visible_tables = await self._get_visible_tables_content(page)
                            
                            # Prioritize table with history headers if multiple exist
                            for tbl in visible_tables:
                                headers = str(list(tbl[0].keys())).lower()
                                if "2021" in headers or "2020" in headers:
                                    target_table = tbl
                                    break
                            
                            # Fallback to largest table if specific history headers missing (e.g. maybe Quarterly doesn't go back to 2021?)
                            if not target_table and visible_tables:
                                print(f"      -> Note: History headers (2020/2021) not explicit. Using largest visible table.")
                                target_table = max(visible_tables, key=len)

                            if target_table:
                                key = f"{tab_name.replace(' ', '_')}_{period}"
                                history_data[key] = [target_table]
                                print(f"      -> Captured {len(target_table)} rows for {key}")
                            else:
                                print("      -> Failed to find any visible table.")

                else:
                    print("Could not find 'Financials' tab.")

            except Exception as e:
                print(f"An error occurred during scraping: {e}")
            finally:
                await browser.close()
                
        return history_data

    # --- Helper methods ---

    async def _click_display_previous_periods(self, page: Page):
        """Clicks the button/link to show previous periods."""
        # Scroll down first
        await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        await page.wait_for_timeout(500)
        
        clicked = await page.evaluate("""() => {
            const buttons = Array.from(document.querySelectorAll('a, button, div, span'));
            // Find button with exact text or close match
            const target = buttons.find(b => b.innerText && b.innerText.trim() === 'Display Previous Periods');
            if (target) {
                target.scrollIntoView();
                target.click();
                return true;
            }
            return false;
        }""")
        
        if not clicked:
             print("      -> 'Display Previous Periods' button not found via JS.")

        # Scroll back up to see table
        await page.evaluate("window.scrollTo(0, 0)")

    async def _get_visible_tables_content(self, page: Page) -> List[List[Dict[str, str]]]:
        """Helper to get content of all visible tables."""
        extracted = []
        tables = await page.locator("table").all()
        for table in tables:
            if await table.is_visible():
                data = await self._parse_html_table(table)
                if data:
                    extracted.append(data)
        return extracted

    async def _table_has_history(self, page: Page) -> bool:
        """Checks if ANY visible table has 2021 or 2020 in headers."""
        tables = await self._get_visible_tables_content(page)
        for tbl in tables:
            if not tbl: continue
            headers = " ".join(list(tbl[0].keys())).lower()
            if "2021" in headers or "2020" in headers:
                return True
        return False

    async def _get_history_table(self, page: Page) -> List[Dict[str, str]]:
        """Returns the visible table that has history headers."""
        tables = await self._get_visible_tables_content(page)
        for tbl in tables:
            if not tbl: continue
            headers = " ".join(list(tbl[0].keys())).lower()
            if "2021" in headers or "2020" in headers:
                return tbl
        return []

    async def _click_tab(self, page: Page, tab_name: str) -> bool:
        return await self._js_click_tab(page, tab_name)

    async def _js_click_tab(self, page: Page, text: str) -> bool:
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

    async def _parse_html_table(self, table_locator: Locator) -> List[Dict[str, str]]:
        try:
            rows = table_locator.locator("tr")
            row_count = await rows.count()
            if row_count == 0: return []

            headers = []
            header_row = rows.nth(0)
            th_cells = header_row.locator("th")
            th_count = await th_cells.count()
            
            if th_count > 0:
                for i in range(th_count):
                    text = await th_cells.nth(i).inner_text() 
                    headers.append((text or f"col_{i}").strip())
            else:
                td_cells = header_row.locator("td")
                for i in range(await td_cells.count()):
                     headers.append(f"col_{i}")

            data = []
            start_row = 1 if th_count > 0 else 0
            
            for i in range(start_row, row_count):
                row = rows.nth(i)
                cells = row.locator("td, th")
                cell_count = await cells.count()
                row_dict = {}
                for j in range(cell_count):
                    key = headers[j] if j < len(headers) else f"col_{j}"
                    val = await cells.nth(j).inner_text() 
                    row_dict[key] = (val or "").strip()
                if row_dict:
                    data.append(row_dict)
            return data
        except Exception:
            return []

async def main():
    scraper = FinancialHistoryScraper(headless=False)
    data = await scraper.scrape()
    output_file = "scrape_financials_history.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)
    print(f"\nHistory scraping complete. Data saved to {output_file}")

if __name__ == "__main__":
    asyncio.run(main())
