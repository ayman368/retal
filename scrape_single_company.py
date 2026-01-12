import asyncio
import json
import os
from typing import Dict, List, Any
from playwright.async_api import async_playwright, Page, Locator

# --- Configuration ---
BASE_URL_TEMPLATE = "https://www.saudiexchange.sa/wps/portal/saudiexchange/hidden/company-profile-main/!ut/p/z1/04_Sj9CPykssy0xPLMnMz0vMAfIjo8ziTR3NDIw8LAz83d2MXA0C3SydAl1c3Q0NvE30I4EKzBEKDMKcTQzMDPxN3H19LAzdTU31w8syU8v1wwkpK8hOMgUA-oskdg!!/"
TIMEOUT_MS = 120000

# ⚠️ غير الرمز هنا لكل شركة
COMPANY_SYMBOL = "4325"  # غير الرقم ده لكل شركة عاوز تسحبها

class SingleCompanyScraper:
    def __init__(self, headless: bool = False):
        self.headless = headless

    async def scrape(self, symbol: str) -> Dict[str, Any]:
        """Scrapes financial data for a single company."""
        print(f"\n{'='*60}")
        print(f"Processing Company: {symbol}")
        print(f"{'='*60}")
        
        company_data = {
            "symbol": symbol,
            "financial_information": {}
        }
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=self.headless, args=["--disable-http2"])
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (HTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                viewport={"width": 1600, "height": 1000},
                locale="en-US"
            )
            page = await context.new_page()
            
            try:
                # Navigate to company page
                url = f"{BASE_URL_TEMPLATE}?companySymbol={symbol}"
                print(f"Navigating to {url}...")
                await page.goto(url, timeout=TIMEOUT_MS)
                await page.wait_for_load_state("domcontentloaded")
                await page.wait_for_timeout(3000)
                
                # Navigate to Financials Tab
                print("Processing Financials...")
                if await self._click_tab(page, "Financials"):
                    await page.wait_for_timeout(2000)
                    
                    # FINANCIAL INFORMATION
                    print("  -> Switching to 'FINANCIAL INFORMATION' tab...")
                    clicked_info = await self._js_click_tab(page, "FINANCIAL INFORMATION")
                    if clicked_info:
                        await page.wait_for_timeout(3000)
                        company_data["financial_information"] = await self._scrape_financials_simple(page)
                    else:
                        print("  -> 'FINANCIAL INFORMATION' tab not found.")
                else:
                    print("Could not find 'Financials' tab.")
                    
            except Exception as e:
                print(f"Error scraping company {symbol}: {e}")
                company_data["error"] = str(e)
            finally:
                await browser.close()
                
        return company_data

    # --- Helper methods ---

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

    async def _extract_all_tables(self, page: Page) -> List[Dict[str, Any]]:
        extracted_tables = []
        try:
            tables = await page.locator("table").all()
            for table in tables:
                is_vis = await table.is_visible()
                table_data = await self._parse_html_table(table)
                if table_data:
                    extracted_tables.append({
                        "content": table_data,
                        "visible": is_vis
                    })
        except Exception as e:
            print(f"Error extracting tables: {e}")
        return extracted_tables

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

    async def _scrape_financials_simple(self, page: Page) -> Dict[str, Any]:
        financial_data = {}
        periods = ["Annually", "Quarterly"]
        
        for period in periods:
            if page.is_closed(): break

            try:
                print(f"  -> Processing Period: {period}...")
                
                clicked = await self._js_click_tab(page, period)
                if not clicked:
                    print(f"      -> Failed to find tab for {period}")
                    continue
                
                await page.wait_for_timeout(3000)
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await page.wait_for_timeout(1000)

                tables_info = await self._extract_all_tables(page)
                
                main_table = None
                candidates = []
                
                for t_info in tables_info:
                    tbl = t_info['content']
                    if not tbl: continue
                    
                    header_row = tbl[0]
                    headers = " ".join(list(header_row.keys())).lower()
                    first_col_val = list(header_row.values())[0] if header_row else ""
                    
                    is_candidate = False
                    if "balance sheet" in headers or "balance sheet" in str(first_col_val).lower():
                         if len(tbl) > 5: is_candidate = True
                    elif "20" in headers and len(tbl) > 5:
                         content_snippet = str(tbl[:3]).lower()
                         if "assets" in content_snippet or "revenue" in content_snippet:
                             is_candidate = True
                    
                    if is_candidate:
                        candidates.append(t_info)

                visible_candidates = [c for c in candidates if c['visible']]
                
                if visible_candidates:
                    main_table = visible_candidates[0]['content']
                elif candidates:
                    main_table = candidates[0]['content']
                
                if main_table:
                    print(f"      -> Selected Table with {len(main_table)} rows.")
                    
                    for section in ["Balance Sheet", "Statement Of Income", "Cash Flows"]:
                        sliced = self._slice_mixed_table(main_table, section)
                        if sliced:
                            key = f"{period}_{section.replace(' ', '_')}"
                            financial_data[key] = [sliced]
                            print(f"         -> Extracted {section}: {len(sliced)} rows")
                else:
                    print(f"      -> Warning: No main data table found for {period}")

            except Exception as e:
                print(f"    -> Error processing {period}: {e}")

        return financial_data

    def _slice_mixed_table(self, table: List[Dict[str, str]], target_section: str) -> List[Dict[str, str]]:
        if not table: return []
        idx_income = -1
        idx_cash = -1
        
        header_key = list(table[0].keys())[0]
        for i, row in enumerate(table):
            val = row.get(header_key, "").strip()
            if "Statement Of Income" in val or "Statement of Income" in val:
                idx_income = i
            elif "Cash Flows" in val and len(val) < 40: 
                idx_cash = i
                
        if idx_income == -1 and idx_cash == -1:
             if target_section == "Balance Sheet": return table
             return []

        start_idx = 0
        end_idx = len(table)
        
        if target_section == "Balance Sheet":
            start_idx = 0
            if idx_income != -1: end_idx = idx_income
            elif idx_cash != -1: end_idx = idx_cash
            
        elif target_section == "Statement Of Income":
            if idx_income == -1: return [] 
            start_idx = idx_income + 1 
            if idx_cash != -1: end_idx = idx_cash
            
        elif target_section == "Cash Flows":
            if idx_cash == -1: return [] 
            start_idx = idx_cash + 1 
            end_idx = len(table)
            
        if start_idx >= end_idx:
            return []
            
        return table[start_idx:end_idx]

async def main():
    scraper = SingleCompanyScraper(headless=False)
    data = await scraper.scrape(COMPANY_SYMBOL)
    
    # Create companies_data folder if it doesn't exist
    os.makedirs("companies_data", exist_ok=True)
    
    # Save to individual JSON file named after the company symbol
    output_file = f"companies_data/{COMPANY_SYMBOL}.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)
    
    print(f"\n{'='*60}")
    print(f"✅ Company {COMPANY_SYMBOL} scraping complete!")
    print(f"📁 Data saved to: {output_file}")
    print(f"{'='*60}")

if __name__ == "__main__":
    asyncio.run(main())
