import asyncio
import re
import json
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from playwright.async_api import async_playwright, Page, Locator

# --- Configuration ---
BASE_URL = "https://www.saudiexchange.sa/wps/portal/saudiexchange/hidden/company-profile-main/!ut/p/z1/04_Sj9CPykssy0xPLMnMz0vMAfIjo8ziTR3NDIw8LAz83d2MXA0C3SydAl1c3Q0NvE30I4EKzBEKDMKcTQzMDPxN3H19LAzdTU31w8syU8v1wwkpK8hOMgUA-oskdg!!/?companySymbol={symbol}"
DEFAULT_SYMBOL = "4322"
TIMEOUT_MS = 60000

@dataclass
class ScrapedData:
    """Data structure to hold all scraped information."""
    company_symbol: str
    header_info: Dict[str, str] = field(default_factory=dict)
    stats_overview: Dict[str, str] = field(default_factory=dict)
    trade_updates: Dict[str, str] = field(default_factory=dict)
    announcements: List[Dict[str, str]] = field(default_factory=list)
    corporate_actions: Dict[str, List[Dict[str, str]]] = field(default_factory=lambda: {"upcoming": [], "past": []})
    tables: Dict[str, List[Dict[str, Any]]] = field(default_factory=dict)
    detailed_sections: Dict[str, Any] = field(default_factory=dict)

class SaudiExchangeScraper:
    def __init__(self, headless: bool = False):
        self.headless = headless

    async def scrape(self, symbol: str = DEFAULT_SYMBOL) -> ScrapedData:
        """Main method to perform the scraping."""
        data = ScrapedData(company_symbol=symbol)
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=self.headless)
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (HTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                viewport={"width": 1600, "height": 1000},
                locale="en-US"
            )
            page = await context.new_page()
            
            try:
                url = BASE_URL.format(symbol=symbol)
                print(f"Navigating to {url}...")
                await page.goto(url, timeout=TIMEOUT_MS)
                await page.wait_for_load_state("networkidle")
                
                # 1. Extract Header Info
                print("Extracting header info...")
                data.header_info = await self._extract_header_info(page)
                
                # 2. Extract Stats Overview
                print("Extracting Stats Overview...")
                data.stats_overview = await self._extract_stats_overview(page)

                # 3. Extract Trade Updates (New)
                print("Extracting Trade Updates...")
                data.trade_updates = await self._extract_trade_updates(page)
                
                # 4. Extract Tables from the Main Page
                print("Extracting main page tables...")
                data.tables["main_page"] = await self._extract_all_tables(page)
                
                # 5. Navigate Tabs
                print("Processing tabs...")
                
                # 5a. Standard Tabs
                tabs_data = await self._process_tabs(page)
                data.detailed_sections.update(tabs_data)

                # 5b. Announcements & Corporate Actions (New Tab)
                print("Processing Announcements & Corporate Actions...")
                ann_data = await self._scrape_announcements_and_actions(page)
                data.announcements = ann_data["announcements"]
                data.corporate_actions = ann_data["corporate_actions"]
                
            except Exception as e:
                print(f"An error occurred during scraping: {e}")
            finally:
                await browser.close()
                
        return data
    def _clean_text(self, text: str) -> str:
        """Cleans whitespace and newlines from text."""
        if not text:
            return ""
        return re.sub(r'\s+', ' ', text).strip()

    async def _extract_trade_updates(self, page: Page) -> Dict[str, str]:
        """Scrapes 'Last Trade', 'Best Bid', 'Best Offer', '52 Week High', and 'Performance'."""
        updates = {}
        # Use a list of (key_name, selector_text, exact_match)
        targets = [
            ("Last Trade", "Last Trade", True),
            ("Best Bid", "Best Bid", True),
            ("Best Offer", "Best Offer", True),
            ("52 Week High", "52 WEEK", True), # Try strict 52 WEEK first
            ("PERFORMANCE", "PERFORMANCE", True)
        ]
        
        try:
            for key, search_text, is_exact in targets:
                # Find all occurrences
                locs = page.get_by_text(search_text, exact=is_exact)
                count = await locs.count()
                
                found_valid = False
                for i in range(count):
                    el = locs.nth(i)
                    if await el.is_visible():
                        # specific check for 52 week to avoid footer
                        # footnotes usually have smaller text or different structure, but easier to check content
                        container = el.locator("xpath=..")
                        raw_text = await container.text_content()
                        
                        # Data validation
                        if "*" in raw_text and "Average Trade Size" in raw_text:
                            continue # Skip footnote
                            
                        # If we are here, it's likely valid
                        await el.scroll_into_view_if_needed()
                        
                        # Cleaning: sometimes we need to go up one more level if the text is just the header
                        cleaned = self._clean_text(raw_text)
                        if len(cleaned) < len(search_text) * 1.5:
                             container = container.locator("xpath=..")
                             raw_text = await container.text_content()
                             cleaned = self._clean_text(raw_text)
                        
                        updates[key] = cleaned
                        found_valid = True
                        break # Stop checking other matches for this key
                
                if not found_valid:
                    # Fallback for 52 Week if "52 WEEK" exact failed, try "52 Week High"
                    if key == "52 Week High" and is_exact:
                         # Try loose match but validate
                         loose_locs = page.get_by_text("52 Week High", exact=False)
                         if await loose_locs.count() > 0:
                             first = loose_locs.first
                             if await first.is_visible():
                                 container = first.locator("xpath=..")
                                 raw = await container.text_content()
                                 if "*" not in raw:
                                     updates[key] = self._clean_text(raw)

        except Exception as e:
            print(f"Error extracting trade updates: {e}")
            
        return updates




    async def _scrape_announcements_and_actions(self, page: Page) -> Dict[str, Any]:
        """Handles the 'Announcements & Corporate Actions' tab including scrolling loop."""
        result = {
            "announcements": [],
            "corporate_actions": {"upcoming": [], "past": []}
        }
        
        tab_name = "Announcements & Corporate Actions"
        if not await self._click_tab(page, tab_name):
            print(f"  -> Could not navigate to {tab_name}")
            return result
        
        # --- Part A: Announcements (Scrolling) ---
        print("  -> Helper: Executing scrolling loop for Announcements...")
        try:
            # Selector for the scrolling container
            scroll_container = page.locator(".announcement_Box")
            
            # If specific container doesn't exist/visible, fall back to window scroll
            container_exists = await scroll_container.count() > 0 and await scroll_container.first.is_visible()
            
            for i in range(5):
                if container_exists:
                    # Scroll container to bottom
                    # Need to use evaluate because playwright's scroll_into_view might not trigger infinite scroll triggers on the container itself
                    await scroll_container.first.evaluate("el => el.scrollTop = el.scrollHeight")
                else:
                    await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                
                await page.wait_for_timeout(1000) # 1 sec delay
            
            # Extraction
            # Selector: .announcement_Box .scrollbar ul li
            items = page.locator(".announcement_Box .scrollbar ul li")
            count = await items.count()
            print(f"  -> Found {count} announcements after scrolling.")
            
            for i in range(count):
                li = items.nth(i)
                title = await li.locator("h2").text_content()
                price = await li.locator(".price_date .price").text_content()
                date = await li.locator(".price_date .date").text_content()
                
                result["announcements"].append({
                    "title": (title or "").strip(),
                    "symbol_info": (price or "").strip(),
                    "date": (date or "").strip()
                })
                
        except Exception as e:
            print(f"  -> Error scraping announcements: {e}")

        # --- Part B: Corporate Actions ---
        print("  -> Helper: Extracting Corporate Actions...")
        try:
            # Upcoming
            upcoming_items = page.locator("#upComingCorporateAction li, #upComingCorporateActionsEvent li")
            uc_count = await upcoming_items.count()
            for i in range(uc_count):
                li = upcoming_items.nth(i)
                result["corporate_actions"]["upcoming"].append({
                    "company_name": (await li.locator(".name").text_content() or "").strip(),
                    "details": (await li.locator(".devident-date").text_content() or "").strip(),
                    "value": (await li.locator(".share").text_content() or "").strip()
                })
            
            # Past
            past_items = page.locator("#pastCorporateAction li, #pastCorporateActionsEvent li")
            pc_count = await past_items.count()
            for i in range(pc_count):
                li = past_items.nth(i)
                result["corporate_actions"]["past"].append({
                    "company_name": (await li.locator(".name").text_content() or "").strip(),
                    "details": (await li.locator(".devident-date").text_content() or "").strip(),
                    "value": (await li.locator(".share").text_content() or "").strip()
                })
                
        except Exception as e:
            print(f"  -> Error scraping corporate actions: {e}")

        return result

    async def _extract_header_info(self, page: Page) -> Dict[str, str]:
        """Extracts the top header information like current price and change."""
        info = {}
        try:
            # 1. Company Name
            title_el = page.locator("h1, .company-name, .pagetitle").first
            if await title_el.is_visible():
                info["company_name"] = (await title_el.text_content() or "").strip()

            # 2. detailed Price & Change from Stats Overview area (Preferred)
            # visual: Price and Change are often above the stats grid
            # Strategy: Look for the container that has the specific Change format "val (pct%)" or similar
            
            # Try to find the detailed change text container directly
            # The pattern is usually like "-0.40 (-3.43%)" or just "-0.40" then "(-3.43%)"
            
            # Common container classes in this sector
            candidates = [
                ".market-status", 
                ".company-header", 
                ".stock-info",
                ".main-market-info"
            ]
            
            found_detailed = False
            
            for selector in candidates:
                section = page.locator(selector).first
                if await section.is_visible():
                    # Attempt to find Price
                    # Usually the largest number or class .last / .price / .current
                    price_el = section.locator(".last, .price, .current-price, strong").first
                    if await price_el.is_visible():
                        price_text = (await price_el.text_content() or "").strip()
                        if re.search(r'\d+\.\d+', price_text):
                            info["price"] = price_text
                    
                    # Attempt to find Change
                    # Look for something with % and +/- or brackets
                    change_el = section.locator(".change, .diff, .variance").first
                    if await change_el.is_visible():
                        change_text = (await change_el.text_content() or "").strip()
                        info["change"] = change_text
                        found_detailed = True
                        break
            
            # Fallback / Refinement: Look specifically near "Stats Overview" if global header failed or gave simple data
            if not found_detailed or not info.get("price"):
                # Find the Stats Overview header
                stats_header = page.get_by_text("Stats Overview", exact=False)
                if await stats_header.count() > 0:
                    # Look at siblings or parent's siblings (often the price is right next to it)
                    # We can search the whole container of the component
                    container = stats_header.locator("xpath=./ancestor::div[contains(@class, 'row') or contains(@class, 'container') or contains(@class, 'card')][1]")
                    
                    if await container.count() > 0:
                        text = await container.text_content()
                        # Clean up text (remove multiple spaces)
                        text = re.sub(r'\s+', ' ', text).strip()
                        
                        # Strategy: Find the change pattern first [-0.40 (-3.43%)]
                        # Then look at the number immediately preceding it.
                        
                        # Regex for change: (val) (pct%)
                        # checks for space between val and pct or not
                        change_pattern = re.search(r'([+-]?\d{1,4}\.\d{2})\s*\(([+-]?\d{1,4}\.\d{2}%)\)', text)
                        
                        if change_pattern:
                            info["change"] = f"{change_pattern.group(1)} ({change_pattern.group(2)})"
                            
                            # Now find the price BEFORE this match
                            # Get the text before the match
                            start_index = change_pattern.start()
                            text_before = text[:start_index].strip()
                            
                            # Find the last number in "text_before"
                            # This number is likely the price
                            price_candidates = re.findall(r'(\d{1,5}\.\d{2})', text_before)
                            if price_candidates:
                                info["price"] = price_candidates[-1]
                        else:
                            # Fallback if specific format not found, try simple extraction guided by reasonable range validation later
                            # But avoid grabbing the first random number like 156.21
                            pass

        except Exception as e:
            print(f"Warning: Could not extract header info: {e}")
            
        return info


    async def _extract_stats_overview(self, page: Page) -> Dict[str, str]:
        """Extracts key-value pairs from the 'Stats Overview' section."""
        stats = {}
        try:
            section = page.locator(".stats_overview").first
            
            # Ensure section is visible and in view (triggers lazy loads)
            if await section.count() > 0:
                await section.scroll_into_view_if_needed()
                await page.wait_for_timeout(500)

            # Polling loop: Wait for "Open" to be a number (not "-" or empty)
            # Try up to 10 times with 1.5s delay (15s total)
            max_retries = 10
            for attempt in range(max_retries):
                stats = {} # Reset storage
                
                if await section.count() > 0:
                    items = section.locator("li")
                    count = await items.count()
                    for i in range(count):
                        item = items.nth(i)
                        # The label is usually in a span, value in a strong or .value class
                        label_el = item.locator("span").first
                        value_el = item.locator("strong, .value").first
                        
                        if await label_el.is_visible():
                            raw_label = (await label_el.text_content() or "").strip()
                            # Clean label: remove *, (^), and trim
                            label = raw_label.replace("*", "").replace("(^)", "").strip()
                            value = "-"
                            if await value_el.is_visible():
                                value = (await value_el.text_content() or "").strip()
                            
                            if label:
                                stats[label] = value
                
                # Check quality of data
                open_val = stats.get("Open", "-")
                
                # We expect "Open" to be something like "11.63" (digits)
                # Regex check: looks for at least one digit
                if re.search(r'\d', open_val):
                    print(f"  -> Stats successfully loaded (Open: {open_val})")
                    break 
                
                if attempt < max_retries - 1:
                    print(f"  -> Stats data pending (Open: '{open_val}'), waiting... ({attempt+1}/{max_retries})")
                    await page.wait_for_timeout(1500)

        except Exception as e:
            print(f"Error extracting stats overview: {e}")
        return stats

    async def _extract_all_tables(self, page: Page) -> List[Dict[str, Any]]:
        """Finds all visible <table> elements and parses them."""
        extracted_tables = []
        try:
            tables = page.locator("table")
            count = await tables.count()
            for i in range(count):
                table = tables.nth(i)
                if await table.is_visible():
                    table_data = await self._parse_html_table(table)
                    if table_data:
                        extracted_tables.append(table_data)
        except Exception as e:
            print(f"Error extracting tables: {e}")
        return extracted_tables

    async def _parse_html_table(self, table_locator: Locator) -> List[Dict[str, str]]:
        """Helper to parse a single HTML table into a list of dictionaries."""
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
                    text = await th_cells.nth(i).text_content()
                    headers.append((text or f"col_{i}").strip())
            else:
                td_cells = header_row.locator("td")
                for i in range(await td_cells.count()):
                     headers.append(f"col_{i}")

            data = []
            start_row = 1 if th_count > 0 else 0
            for i in range(start_row, row_count):
                cells = rows.nth(i).locator("td, th")
                cell_count = await cells.count()
                row_dict = {}
                for j in range(cell_count):
                    key = headers[j] if j < len(headers) else f"col_{j}"
                    val = await cells.nth(j).text_content()
                    row_dict[key] = (val or "").strip()
                if row_dict:
                    data.append(row_dict)
            return data
        except Exception:
            return []

    async def _process_tabs(self, page: Page) -> Dict[str, Any]:
        """Iterates through tabs including the complex Financials and Company Profile tabs."""
        tabs_data = {}
        # Standard tabs
        simple_tabs = ["Dividends", "Shareholding", "Peer Comparison"]
        
        for tab_name in simple_tabs:
            print(f"Processing tab: {tab_name}...")
            if await self._click_tab(page, tab_name):
                tabs_data[tab_name] = await self._extract_all_tables(page)
        
        # Company Profile (Separated for specialized scraping)
        print("Processing Company Profile...")
        if await self._click_tab(page, "Company Profile"):
            tabs_data["Company Profile"] = await self._scrape_company_profile_deep(page)

        # Financials specifically (Deep Scraping)
        print("Processing Financials (Deep Scrape)...")
        if await self._click_tab(page, "Financials"):
            await page.wait_for_timeout(2000) # Ensure initial load
            try:
                tabs_data["Financials"] = await self._scrape_financials_deep(page)
            except Exception as e:
                print(f"Error scraping financials deep: {e}")
                # Fallback to just grabbing what's there
                tabs_data["Financials_Fallback"] = await self._extract_all_tables(page)
            
        return tabs_data

    async def _scrape_company_profile_deep(self, page: Page) -> Dict[str, Any]:
        """Scrapes text sections (Overview, History) and stats (Equity Profile) from Company Profile."""
        profile_data = {
            "tables": await self._extract_all_tables(page),
            "text_sections": {},
            "equity_profile": {}
        }
        
        try:
            # 1. Scrape Text Sections (Overview, History, etc.)
            target_headers = ["Company overview", "Company History", "Company Bylaws"]
            
            # Simple text parsing using locators for robustness
            for header in target_headers:
                # Find the element and get the text of the following paragraph
                xpath = f"//p[contains(., '{header}')]/following-sibling::p[1] | //strong[contains(., '{header}')]/../following-sibling::p[1]"
                content_loc = page.locator(xpath).first
                if await content_loc.is_visible():
                    text = await content_loc.text_content()
                    profile_data["text_sections"][header] = (text or "").strip()

            # 2. Scrape Equity Profile
            # Specifically target the list that comes *after* the "Equity Profile" header
            # This avoids grabbing the stats overview bar at the top of the page
            # XPath finds "Equity Profile" text -> finds the first following <ul> -> finds its <li> children
            equity_items_xpath = "//*[contains(text(), 'Equity Profile')]/following::ul[1]//li"
            
            items = page.locator(f"xpath={equity_items_xpath}")
            count = await items.count()
            
            if count > 0:
                print(f"  -> Found {count} items in Equity Profile section.")
                for i in range(count):
                    item = items.nth(i)
                    if await item.is_visible():
                        label_el = item.locator("span").first
                        value_el = item.locator("strong").first
                        
                        if await label_el.is_visible() and await value_el.is_visible():
                            label = (await label_el.text_content() or "").strip()
                            value = (await value_el.text_content() or "").strip()
                            if label and value:
                                profile_data["equity_profile"][label] = value
            else:
                print("  -> No items found for Equity Profile (check selector).")
        
        except Exception as e:
            print(f"Error scraping company profile deep: {e}")
            
        return profile_data

    async def _click_tab(self, page: Page, tab_name: str) -> bool:
        """Helper to find and click a tab."""
        try:
            # Locate by text, ensuring visibility
            locator = page.get_by_text(tab_name, exact=True)
            count = await locator.count()
            target = None
            
            for i in range(count):
                el = locator.nth(i)
                if await el.is_visible():
                    target = el
                    break
            
            if target:
                await target.scroll_into_view_if_needed()
                try:
                    await target.click(timeout=3000)
                except:
                    await target.evaluate("el => el.click()")
                await page.wait_for_timeout(3000) # Wait for content
                return True
            else:
                print(f"  -> Tab '{tab_name}' not found.")
        except Exception as e:
            print(f"  -> Error clicking {tab_name}: {e}")
        return False

    async def _scrape_financials_deep(self, page: Page) -> Dict[str, Any]:
        """
        Iterates through Annually/Quarterly and gets the full table for each.
        Optimized to avoid duplicates since all statements are in one huge table.
        """
        financial_data = {}
        
        periods = ["Annually", "Quarterly"]
        # We only need to ensure the main view is loaded.
        # Usually checking "Balance Sheet" or just the period is enough.
        
        for period in periods:
            print(f"  -> Switching period to: {period}")
            
            # 1. Click Period Toggle
            period_clicked = False
            try:
                # Try text match
                period_locator = page.get_by_text(period, exact=False)
                if await period_locator.count() > 0:
                    for i in range(await period_locator.count()):
                        elem = period_locator.nth(i)
                        if await elem.is_visible():
                            await elem.click(timeout=3000)
                            period_clicked = True
                            await page.wait_for_timeout(2000)
                            # print(f"    -> Clicked {period}")
                            break
            except: pass
            
            if not period_clicked:
                # Try specific xpath strategy
                try:
                    xpath = f"//a[contains(text(), '{period}')] | //button[contains(text(), '{period}')]"
                    elem = page.locator(f"xpath={xpath}")
                    if await elem.count() > 0 and await elem.first.is_visible():
                         await elem.first.click(timeout=3000)
                         await page.wait_for_timeout(2000)
                except: pass

            # 1.5 Expand Data (Display Previous Periods)
            # The user wants to click "Display Previous Periods" to load ~4 more years of data.


            # 2. Extract Table (Initial / Short)
            print(f"    -> Extracting initial table for {period}...")
            tables_short = await self._extract_all_tables(page)
            if tables_short:
                financial_data[f"{period}_Short"] = tables_short

            # 3. Expand Data (Display Previous Periods)
            try:
                expand_btn = page.get_by_text("Display Previous Periods", exact=False)
                if await expand_btn.count() > 0:
                    first_btn = expand_btn.first
                    if await first_btn.is_visible():
                        print(f"    -> Found 'Display Previous Periods' for {period}, clicking...")
                        await first_btn.click()
                        await page.wait_for_timeout(4000)
            except Exception as e:
                print(f"    -> Info: Could not expand previous periods: {e}")

            # 4. Extract Tables (Expanded - Iterating through Statement Types)
            print(f"    -> Extracting expanded tables for {period} (Iterating sub-tabs)...")
            
            # Note exact capitalization from screenshots
            statement_types = ["Balance Sheet", "Statement Of Income", "Cash Flows"]
            found_any_expanded = False
            
            for stmt in statement_types:
                try:
                    # Strategy 1: strict/lenient text match
                    # We try to find the tab. The user noted "Statement Of Income" (capital O) might be key.
                    clicked = False
                    
                    # Try specific text variations
                    # (Sometimes specific capitalization matters or trailing spaces)
                    candidates = page.get_by_text(stmt, exact=False)
                    if await candidates.count() > 0:
                        for i in range(await candidates.count()):
                            el = candidates.nth(i)
                            if await el.is_visible():
                                try:
                                    await el.click(timeout=1500)
                                    clicked = True
                                    break
                                except: pass
                    
                    # Strategy 2: If simple text failed, try broad XPath
                    if not clicked:
                        xpath = f"//*[contains(text(), '{stmt}')] | //*[contains(text(), '{stmt.upper()}')]"
                        x_candidates = page.locator(f"xpath={xpath}")
                        for i in range(await x_candidates.count()):
                             el = x_candidates.nth(i)
                             if await el.is_visible():
                                 try:
                                     await el.click(timeout=1500)
                                     clicked = True
                                     break
                                 except: pass

                    if clicked:
                         await page.wait_for_timeout(3000) # Wait for table load
                         print(f"      -> Clicked '{stmt}', scraping...")
                         tables_stmt = await self._extract_all_tables(page)
                         
                         if tables_stmt:
                             # Use a clean key
                             clean_key = f"{period}_{stmt.replace(' ', '_')}"
                             financial_data[clean_key] = tables_stmt
                             found_any_expanded = True
                             print(f"      -> Saved {len(tables_stmt)} tables to {clean_key}")
                    else:
                        print(f"      -> Warning: Could not find clickable tab for {stmt}")
                except Exception as e:
                    print(f"      -> Error scraping {stmt}: {e}")

            if not found_any_expanded:
                 print(f"      -> Fallback: No statement tabs found, scraping current view as generic '{period}'...")
                 tables_full = await self._extract_all_tables(page)
                 if tables_full:
                    financial_data[period] = tables_full
        
        return financial_data

async def main():
    scraper = SaudiExchangeScraper(headless=False)
    data = await scraper.scrape()
    
    output_file = "company_data_clean.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(data.__dict__, f, ensure_ascii=False, indent=4)
        
    js_output_file = "company_data.js"
    with open(js_output_file, "w", encoding="utf-8") as f:
        json_str = json.dumps(data.__dict__, ensure_ascii=False, indent=4)
        f.write(f"const companyData = {json_str};")
    
    print(f"\nScanning complete. Data saved to {output_file} and {js_output_file}")
    print(f"Stats Overview found: {len(data.stats_overview)} key-values")
    # Quick summary of financials and profile
    if "Financials" in data.detailed_sections:
         print(f"Financials keys found: {list(data.detailed_sections['Financials'].keys())}")
    if "Company Profile" in data.detailed_sections:
         print(f"Profile keys found: {list(data.detailed_sections['Company Profile'].keys())}")

if __name__ == "__main__":
    asyncio.run(main())
