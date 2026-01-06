import json

def check_duplicates():
    try:
        with open('company_data_clean.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        financials = data.get('detailed_sections', {}).get('Financials', {})
        
        print("--- Analyzing Financials Section ---")
        keys = list(financials.keys())
        print(f"Keys found: {keys}")
        
        # Compare content of Annually keys
        ann_keys = [k for k in keys if k.startswith('Annually')]
        if len(ann_keys) > 1:
            base_key = ann_keys[0]
            base_content = json.dumps(financials[base_key], sort_keys=True)
            
            for k in ann_keys[1:]:
                content = json.dumps(financials[k], sort_keys=True)
                if content == base_content:
                    print(f"MATCH: '{k}' is IDENTICAL to '{base_key}'")
                else:
                    print(f"DIFF: '{k}' is DIFFERENT from '{base_key}'")
                    
        # Compare content of Quarterly keys
        qt_keys = [k for k in keys if k.startswith('Quarterly')]
        if len(qt_keys) > 1:
            base_key = qt_keys[0]
            base_content = json.dumps(financials[base_key], sort_keys=True)
            
            for k in qt_keys[1:]:
                content = json.dumps(financials[k], sort_keys=True)
                if content == base_content:
                    print(f"MATCH: '{k}' is IDENTICAL to '{base_key}'")
                else:
                    print(f"DIFF: '{k}' is DIFFERENT from '{base_key}'")

        # Check main_page tables for duplicates
        print("\n--- Analyzing Main Page Tables ---")
        main_tables = data.get('tables', {}).get('main_page', [])
        print(f"Total main tables: {len(main_tables)}")
        
        seen_tables = []
        duplicates = 0
        for i, tbl in enumerate(main_tables):
            tbl_str = json.dumps(tbl, sort_keys=True)
            if tbl_str in seen_tables:
                duplicates += 1
            else:
                seen_tables.append(tbl_str)
        
        print(f"Duplicate tables found in main_page: {duplicates}")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    check_duplicates()
