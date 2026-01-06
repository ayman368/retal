// State
let currentPeriod = 'Annually';
let currentStatement = 'Balance_Sheet';

// Init
document.addEventListener('DOMContentLoaded', () => {
    if (typeof companyData === 'undefined') {
        alert("Error: Data not loaded. Ensure company_data.js is linked.");
        return;
    }

    initDashboard(companyData);
});

function initDashboard(data) {
    renderHeader(data);
    renderStats(data.stats_overview);
    renderTradeUpdates(data.trade_updates);
    renderAnnouncements(data.announcements);
    renderCorporateActions(data.corporate_actions);
    renderDividends(data.detailed_sections['Dividends']);
    renderFinancials();
    renderShareholders(data.detailed_sections['Shareholding']);
    renderProfile(data.detailed_sections['Company Profile']);
    renderSubsidiaries(data.tables['main_page']);
    renderPeers(data.detailed_sections['Peer Comparison']);
    setupNavigation();
}

function renderTradeUpdates(tradeData) {
    const container = document.getElementById('tradeUpdatesContainer');
    const grid = document.getElementById('tradeUpdatesGrid');

    if (!tradeData || Object.keys(tradeData).length === 0) {
        container.style.display = 'none';
        return;
    }

    container.style.display = 'block';
    grid.innerHTML = '';

    // Order: Last Trade, Best Bid, Best Offer, 52 Week, Performance
    const order = ["Last Trade", "Best Bid", "Best Offer", "52 Week High", "PERFORMANCE"];

    order.forEach(key => {
        const rawVal = tradeData[key];
        if (!rawVal) return;

        const card = document.createElement('div');
        card.className = 'stat-card';
        card.style.display = 'flex';
        card.style.flexDirection = 'column';
        card.style.gap = '10px';

        // Header
        const header = document.createElement('div');
        header.className = 'stat-label';
        header.style.borderBottom = '1px solid var(--border-color)';
        header.style.paddingBottom = '5px';
        header.style.marginBottom = '5px';
        header.textContent = key === "52 Week High" ? "52 WEEK" : key.toUpperCase();
        card.appendChild(header);

        // Content Grid
        const content = document.createElement('div');
        content.style.display = 'grid';
        content.style.fontSize = '0.9rem';

        // Parsing Logic
        if (key === "Last Trade") {
            // Pattern: "Last Trade Price 11.38 % Change 0.98 Volume Traded 292"
            content.style.gridTemplateColumns = '1fr 1fr 1fr';
            content.style.gap = '10px';

            const price = extractVal(rawVal, /Price\s*([\d\.,]+)/);
            const change = extractVal(rawVal, /Change\s*([+-\d\.,]+)/);
            const volume = extractVal(rawVal, /Volume Traded\s*([\d,]+)/);

            content.innerHTML = `
                <div><div style="font-size:0.75rem; color:var(--text-muted)">Price</div><div style="font-weight:bold">${price}</div></div>
                <div><div style="font-size:0.75rem; color:var(--text-muted)">% Change</div><div style="font-weight:bold; color:${getColor(change)}">${change}</div></div>
                <div><div style="font-size:0.75rem; color:var(--text-muted)">Volume</div><div style="font-weight:bold">${volume}</div></div>
            `;
        } else if (key.includes("Bid") || key.includes("Offer")) {
            // Pattern: "Best Bid Price 11.38 Volume 547"
            content.style.gridTemplateColumns = '1fr 1fr';

            const price = extractVal(rawVal, /Price\s*(MO|[\d\.,]+)/); // Handle "MO" (Market Order)
            const volume = extractVal(rawVal, /Volume\s*([\d,]+)/);

            content.innerHTML = `
                <div><div style="font-size:0.75rem; color:var(--text-muted)">Price</div><div style="font-weight:bold">${price}</div></div>
                <div><div style="font-size:0.75rem; color:var(--text-muted)">Volume</div><div style="font-weight:bold">${volume}</div></div>
            `;
        } else if (key === "52 Week High") {
            // Pattern: "52 WEEK High 18.24 2025/04/03 Low 10.88 2025/09/08 Change** -28.07"
            content.style.gridTemplateColumns = '1fr 1fr 1fr';
            content.style.gap = '5px';

            const high = extractVal(rawVal, /High\s*([\d\.,]+)/);
            const highDate = extractVal(rawVal, /High\s*[\d\.,]+\s*(\d{4}\/\d{2}\/\d{2})/);
            const low = extractVal(rawVal, /Low\s*([\d\.,]+)/);
            const lowDate = extractVal(rawVal, /Low\s*[\d\.,]+\s*(\d{4}\/\d{2}\/\d{2})/);
            const change = extractVal(rawVal, /Change\*\*\s*([+-\d\.,]+)/);

            content.innerHTML = `
                <div>
                    <div style="font-size:0.75rem; color:var(--text-muted)">High</div>
                    <div style="font-weight:bold">${high}</div>
                    <div style="font-size:0.65rem; color:var(--text-muted)">${highDate}</div>
                </div>
                <div>
                    <div style="font-size:0.75rem; color:var(--text-muted)">Low</div>
                    <div style="font-weight:bold">${low}</div>
                    <div style="font-size:0.65rem; color:var(--text-muted)">${lowDate}</div>
                </div>
                <div>
                    <div style="font-size:0.75rem; color:var(--text-muted)">Change**</div>
                    <div style="font-weight:bold; color:${getColor(change)}">${change}</div>
                </div>
            `;
        } else if (key === "PERFORMANCE") {
            // Pattern: "PERFORMANCE Start of Year Year ago 3 Years ago 11.8 15.82 9.82"
            // The text extraction might mash it all together: "PERFORMANCE Start of Year 11.8 Year ago 15.82 ..." or headings then values
            // Let's iterate trying to find numbers associated with labels

            content.style.gridTemplateColumns = '1fr 1fr 1fr';
            content.style.gap = '5px';

            // Expected extracted text: "PERFORMANCE Start of Year 11.8 Year ago 15.82 3 Years ago 9.82"
            // Or: "Start of Year Year ago 3 Years ago 11.8 15.82 9.82"
            // We'll try regex to find the number following the label

            const startYear = extractVal(rawVal, /Start of Year\s*([\d\.,-]+)/) || extractVal(rawVal, /Year\s*([\d\.,-]+)/);
            const yearAgo = extractVal(rawVal, /Year ago\s*([\d\.,-]+)/);
            const threeYears = extractVal(rawVal, /3 Years ago\s*([\d\.,-]+)/);

            content.innerHTML = `
                <div>
                    <div style="font-size:0.75rem; color:var(--text-muted)">Start of Year</div>
                    <div style="font-weight:bold">${startYear}</div>
                </div>
                <div>
                    <div style="font-size:0.75rem; color:var(--text-muted)">Year ago</div>
                    <div style="font-weight:bold">${yearAgo}</div>
                </div>
                <div>
                    <div style="font-size:0.75rem; color:var(--text-muted)">3 Years ago</div>
                    <div style="font-weight:bold">${threeYears}</div>
                </div>
            `;
        }

        card.appendChild(content);
        grid.appendChild(card);
    });
}

function extractVal(str, regex) {
    const match = str.match(regex);
    return match ? match[1] : '-';
}

function getColor(val) {
    if (!val || val === '-') return 'inherit';
    if (val.includes('-')) return 'var(--danger)';
    return 'var(--success)';
}

function renderAnnouncements(announcements) {
    const container = document.getElementById('announcementsList');
    container.innerHTML = '';

    if (!announcements || announcements.length === 0) {
        container.innerHTML = '<div style="padding:1rem; color:var(--text-muted)">No recent announcements.</div>';
        return;
    }

    announcements.forEach(item => {
        const el = document.createElement('div');
        el.className = 'announcement-card';

        // Inline styles for base look (could be moved to CSS)
        el.style.background = 'rgba(255,255,255,0.03)';
        el.style.borderLeft = '3px solid var(--accent)';
        el.style.borderRadius = '0 6px 6px 0';
        el.style.padding = '12px 16px';
        el.style.marginBottom = '12px';
        el.style.transition = 'all 0.2s ease';
        el.style.cursor = 'default';

        // Simple hover effect logic
        el.onmouseenter = () => {
            el.style.background = 'rgba(34, 211, 238, 0.08)';
            el.style.transform = 'translateX(4px)';
        };
        el.onmouseleave = () => {
            el.style.background = 'rgba(255,255,255,0.03)';
            el.style.transform = 'translateX(0)';
        };

        el.innerHTML = `
            <div style="font-size:0.95rem; font-weight:500; margin-bottom:8px; color:var(--text-light); line-height:1.4;">
                ${item.title}
            </div>
            <div style="font-size:0.8rem; color:var(--text-secondary); display:flex; align-items:center; gap:12px;">
                <span style="display:flex; align-items:center; gap:5px;">
                    <!-- Calendar Icon -->
                    <svg width="14" height="14" fill="none" stroke="currentColor" viewBox="0 0 24 24" style="opacity:0.8">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z"></path>
                    </svg>
                    ${item.date}
                </span>
                ${item.symbol_info ? `
                    <span style="
                        background: rgba(34, 211, 238, 0.1); 
                        color: var(--accent); 
                        padding: 2px 8px; 
                        border-radius: 4px; 
                        font-family: monospace; 
                        font-weight: 600;
                        font-size: 0.75rem;
                        border: 1px solid rgba(34, 211, 238, 0.2);
                    ">
                        ${item.symbol_info}
                    </span>` : ''}
            </div>
        `;
        container.appendChild(el);
    });
}

function renderCorporateActions(actions) {
    const container = document.getElementById('corporateActionsList');
    container.innerHTML = '';

    // Combine upcoming and past for now, or just show them with headers
    // Let's show upcoming first if any

    const hasUpcoming = actions?.upcoming?.length > 0;
    const hasPast = actions?.past?.length > 0;

    if (!hasUpcoming && !hasPast) {
        container.innerHTML = '<div style="padding:1rem; color:var(--text-muted)">No corporate actions found.</div>';
        return;
    }

    if (hasUpcoming) {
        const header = document.createElement('h4');
        header.textContent = "Upcoming Events";
        header.style.color = 'var(--accent-color)';
        header.style.marginTop = '0';
        container.appendChild(header);

        actions.upcoming.forEach(act => createActionItem(act, container));
    }

    if (hasPast) {
        const header = document.createElement('h4');
        header.textContent = "Past Events";
        header.style.color = 'var(--text-secondary)';
        header.style.marginTop = hasUpcoming ? '1.5rem' : '0';
        container.appendChild(header);

        actions.past.forEach(act => createActionItem(act, container));
    }
}

function createActionItem(action, container) {
    const el = document.createElement('div');
    el.className = 'action-card';

    // Consistent styling with announcements
    el.style.background = 'rgba(255,255,255,0.03)';
    el.style.borderLeft = '3px solid var(--accent)';
    el.style.borderRadius = '0 6px 6px 0';
    el.style.padding = '12px 16px';
    el.style.marginBottom = '12px';
    el.style.transition = 'all 0.2s ease';

    el.onmouseenter = () => {
        el.style.background = 'rgba(34, 211, 238, 0.08)';
        el.style.transform = 'translateX(4px)';
    };
    el.onmouseleave = () => {
        el.style.background = 'rgba(255,255,255,0.03)';
        el.style.transform = 'translateX(0)';
    };

    el.innerHTML = `
        <div style="font-weight:600; font-size:0.9rem; margin-bottom:4px; color:var(--text-light)">${action.company_name}</div>
        <div style="font-size:0.85rem; color:var(--text-secondary); margin-bottom:6px; line-height:1.4;">${action.details}</div>
        ${action.value ? `<div style="font-size:0.85rem; color:var(--success); font-weight:bold; display:flex; align-items:center; gap:6px;">
            <svg width="12" height="12" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6"></path></svg>
            ${action.value.replace('^', '')}
        </div>` : ''}
    `;
    container.appendChild(el);
}

function renderHeader(data) {
    document.getElementById('companyName').textContent = data.header_info.company_name || "Unknown Company";
    document.getElementById('companySymbol').textContent = data.company_symbol || "----";

    const today = new Date();
    document.getElementById('lastUpdate').textContent = today.toLocaleTimeString();
}

function renderHeader(data) {
    document.getElementById('companyName').textContent = data.header_info.company_name || "Unknown Company";
    document.getElementById('companySymbol').textContent = data.company_symbol || "----";

    let price = data.header_info.price;
    let change = data.header_info.change;

    // Fallback: Check first table of main_page if price is missing
    if ((!price || price === "--") && data.tables && data.tables.main_page) {
        const firstList = data.tables.main_page[0];
        if (Array.isArray(firstList) && firstList.length > 0) {
            const row = firstList[0];
            if (row['Price']) price = row['Price'];
            if (row['Change %']) change = row['Change %'];
            else if (row['Change']) change = row['Change'];
        }
    }

    price = price || "--";
    change = change || "";

    // Calculate absolute change if we only have percentage
    // Expect format like "-3.43%"
    let changeVal = "";
    if (change.includes('%') && price !== "--" && !change.includes('(')) {
        try {
            const priceNum = parseFloat(price.replace(/,/g, ''));
            const changePct = parseFloat(change.replace('%', ''));
            if (!isNaN(priceNum) && !isNaN(changePct)) {
                // Current = Old * (1 + pct/100)
                // Old = Current / (1 + pct/100)
                const oldPrice = priceNum / (1 + (changePct / 100));
                const diff = priceNum - oldPrice;
                changeVal = diff.toFixed(2);
                if (diff > 0) changeVal = "+" + changeVal;
            }
        } catch (e) {
            console.error(e);
        }
    }

    document.getElementById('currentPrice').textContent = price;

    const changeEl = document.getElementById('priceChange');

    // Format: "Val (Pct)" or just "Pct" if failed
    if (changeVal) {
        changeEl.textContent = `${changeVal} (${change})`;
    } else {
        changeEl.textContent = change;
    }

    if (change.includes('-')) {
        changeEl.className = 'change-tag change-negative';
    } else if (change.includes('+') || (parseFloat(change) > 0)) {
        changeEl.className = 'change-tag change-positive';
    } else {
        changeEl.className = 'change-tag';
    }
}

function renderStats(stats) {
    const grid = document.getElementById('statsGrid');
    grid.innerHTML = '';

    const keys = Object.keys(stats);
    keys.forEach(key => {
        const val = stats[key];
        const card = document.createElement('div');
        card.className = 'stat-card';
        card.innerHTML = `
            <div class="stat-label">${key}</div>
            <div class="stat-value">${val}</div>
        `;
        grid.appendChild(card);
    });
}

function renderDividends(dividendsData) {
    const tbody = document.querySelector('#dividendsTable tbody');
    tbody.innerHTML = '';

    if (!dividendsData || dividendsData.length < 2) return;

    let rows = [];
    if (Array.isArray(dividendsData)) {
        for (let item of dividendsData) {
            if (Array.isArray(item) && item.length > 0 && item[0]['Announced Date']) {
                rows = item;
                break;
            }
        }
    }

    rows.forEach(row => {
        const tr = document.createElement('tr');
        tr.innerHTML = `
            <td>${row['Announced Date'] || '-'}</td>
            <td>${row['Eligibility Date'] || '-'}</td>
            <td>${row['Distribution Date'] || '-'}</td>
            <td>${row['Distribution Way'] || '-'}</td>
            <td style="font-weight:bold; color:var(--success)">${row['Dividend Amount']?.replace('^', '') || '-'}</td>
        `;
        tbody.appendChild(tr);
    });
}

function renderShareholders(shareholdingData) {
    const tbody = document.querySelector('#shareholdersTable tbody');
    tbody.innerHTML = '';

    const header = document.querySelector('#shareholders h3');
    if (header) header.innerHTML = 'Shareholders';

    if (!shareholdingData) return;

    let rows = [];
    if (Array.isArray(shareholdingData)) {
        for (let item of shareholdingData) {
            if (Array.isArray(item) && item.length > 0 && item[0]['Shareholders']) {
                rows = item;
                break;
            }
        }
    }

    rows.forEach(row => {
        const tr = document.createElement('tr');
        tr.innerHTML = `
            <td>${row['Trading Date'] || '-'}</td>
            <td style="font-weight:500">${row['Shareholders']}</td>
            <td>${row['Designation'] || '-'}</td>
            <td>${row['Total Shares Held Prev Trading Day'] || '-'}</td>
            <td>${row['Total Shares Held Trading Day'] || '-'}</td>
            <td>${row['Total Shares Change'] || '0'}</td>
        `;
        tbody.appendChild(tr);
    });
}

function renderProfile(profileData) {
    if (!profileData) return;

    const container = document.getElementById('profileTextContainer');
    container.innerHTML = '';
    if (profileData.text_sections) {
        for (const [title, text] of Object.entries(profileData.text_sections)) {
            if (title === 'Company Bylaws') continue;
            const section = document.createElement('div');
            section.innerHTML = `<h4>${title}</h4><p>${text}</p>`;
            container.appendChild(section);
        }
    }

    const equityList = document.getElementById('equityList');
    equityList.innerHTML = '';
    if (profileData.equity_profile) {
        for (const [key, val] of Object.entries(profileData.equity_profile)) {
            const item = document.createElement('div');
            item.className = 'equity-item';
            item.innerHTML = `<span>${key}</span><strong>${val}</strong>`;
            equityList.appendChild(item);
        }
    }
}

function renderSubsidiaries(mainTables) {
    const tbody = document.querySelector('#subsidiariesTable tbody');
    tbody.innerHTML = '';

    if (!mainTables) return;

    let subTable = null;
    for (let table of mainTables) {
        if (table.length > 0 && table[0]['Name Of Subsidiary']) {
            subTable = table;
            break;
        }
    }

    if (subTable) {
        subTable.forEach(row => {
            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td style="font-weight:500">${row['Name Of Subsidiary']}</td>
                <td>${row['Percentage Of Property'] || '-'}</td>
                <td>${row['Main Business'] || '-'}</td>
                <td>${row['Location Of Operation'] || '-'}</td>
            `;
            tbody.appendChild(tr);
        });
    } else {
        tbody.innerHTML = '<tr><td colspan="4">No subsidiary data found.</td></tr>';
    }
}

function renderPeers(peersData) {
    const table = document.getElementById('peersTable');
    table.innerHTML = '';

    if (!peersData) {
        table.innerHTML = '<tbody><tr><td>No peer data available.</td></tr></tbody>';
        return;
    }

    // We need to find the specific table that contains the peer metrics (Price, Market Cap, P/E)
    // The data might look like: [{ "Company Name": "Price \t 11.67" }, ...]
    let targetTable = null;

    // Look through all available tables
    // The structure is usually [ [table1], [table2] ]
    if (Array.isArray(peersData)) {
        for (let list of peersData) {
            if (Array.isArray(list) && list.length > 0) {
                // Check first row to see if it looks like the peer stats
                const firstRow = list[0];
                const key = Object.keys(firstRow)[0];
                const val = Object.values(firstRow)[0];

                // Indicators: Key matches company name OR value contains "Price" or "Ratio"
                // The scraped data often has the company name as key
                if (val && typeof val === 'string' && (val.includes('Price') || val.includes('Market Cap') || val.includes('Ratio'))) {
                    targetTable = list;
                    break;
                }
            }
        }
    }

    // If not found, try to just take the longest table or a specific index
    if (!targetTable && Array.isArray(peersData) && peersData.length > 0) {
        // Fallback: search deep
        peersData.forEach(list => {
            if (Array.isArray(list) && list.length > (targetTable?.length || 0)) targetTable = list;
        });
    }

    if (!targetTable || targetTable.length === 0) {
        table.innerHTML = '<tbody><tr><td>No comparable peer data found.</td></tr></tbody>';
        return;
    }

    // Build the UI
    // Since the format is Key: "Messy String", we need to parse it.
    // E.g. { "Retal": "Price \t 11.67" } -> Metric: Price, Value: 11.67

    const companyName = Object.keys(targetTable[0])[0];

    // Header
    const thead = document.createElement('thead');
    thead.innerHTML = `
        <tr>
            <th>Metric</th>
            <th>${companyName}</th>
        </tr>
    `;
    table.appendChild(thead);

    const tbody = document.createElement('tbody');

    targetTable.forEach(row => {
        const messyString = row[companyName];
        if (!messyString) return;

        // Clean up: "Price \t 11.67" -> ["Price", "11.67"]
        // Replace newlines and tabs with single space, then split by multiple spaces
        // Actually, often it's "Label ... Value". Better to use Regex.

        // Regex to match: Text at start ... number at end
        // Or just split by whitespace and take first and last parts?
        // Let's rely on the structure: Label is usually text, Value is number at end.

        let label = "Unknown";
        let value = "-";

        // Normalize space
        const clean = messyString.replace(/[\t\n\r]+/g, ' ').trim();

        // Try to capture the number at the end
        const match = clean.match(/^(.*?)(\d[\d,.]*)$/);

        if (match) {
            label = match[1].trim();
            value = match[2].trim();
        } else {
            // Fallback: split by space, assume last is value if it looks like number
            const parts = clean.split(/\s+/);
            const last = parts[parts.length - 1];
            if (/[\d,.]+/.test(last)) {
                value = last;
                label = parts.slice(0, -1).join(' ');
            } else {
                label = clean;
                value = ""; // Just text
            }
        }

        // Skip empty or purely decorative rows
        if (!label && !value) return;

        const tr = document.createElement('tr');
        tr.innerHTML = `
            <td style="font-weight:500">${label}</td>
            <td style="font-weight:bold">${value}</td>
        `;
        tbody.appendChild(tr);
    });

    table.appendChild(tbody);
}

// --- Financials Logic ---

function setFinancialPeriod(period) {
    currentPeriod = period;
    updateActiveButtons('.toggle-btn', period);
    renderFinancials();
}

function setFinancialStatement(stmt) {
    currentStatement = stmt;
    const btns = document.querySelectorAll('.tab-btn');
    btns.forEach(btn => {
        if (btn.getAttribute('onclick').includes(stmt)) btn.classList.add('active');
        else btn.classList.remove('active');
    });
    renderFinancials();
}

function updateActiveButtons(selector, textMatch) {
    const btns = document.querySelectorAll(selector);
    btns.forEach(btn => {
        if (btn.textContent.includes(textMatch)) btn.classList.add('active');
        else btn.classList.remove('active');
    });
}

function renderFinancials() {
    const container = document.getElementById('financialsTable').parentElement;
    container.innerHTML = '<table class="financial-table" id="financialsTable"></table>';
    const table = document.getElementById('financialsTable');

    const finData = companyData.detailed_sections['Financials'];
    if (!finData) {
        container.innerHTML = '<div style="padding:2rem">No financial data available.</div>';
        return;
    }

    // Use simplified key from optimized scraper: just "Annually" or "Quarterly"
    const key = currentPeriod;
    let dataList = finData[key];

    // Fallback: IF old data still exists (Annually_Balance_Sheet), try that
    if (!dataList) {
        dataList = finData[`${currentPeriod}_Balance_Sheet`];
    }

    if (!dataList || dataList.length === 0) {
        container.innerHTML = `<div style="padding:2rem">No data available.</div>`;
        return;
    }

    // Find the largest table (index 2 is usually the main financial table)
    let mainTable = null;
    for (let tableArray of dataList) {
        if (Array.isArray(tableArray) && tableArray.length > 15) {
            mainTable = tableArray;
            break;
        }
    }

    if (!mainTable || mainTable.length === 0) {
        container.innerHTML = '<div style="padding:2rem">No table data found.</div>';
        return;
    }

    // Extract the section we need
    const sectionData = extractFinancialSection(mainTable, currentStatement);

    if (!sectionData || sectionData.length === 0) {
        container.innerHTML = '<div style="padding:2rem">No data found for this statement.</div>';
        return;
    }

    // Build custom header based on statement type
    const statementLabels = {
        'Balance_Sheet': 'Item',
        'Statement_of_Income': 'Item',
        'Cash_Flows': 'Item'
    };

    const firstColumnLabel = statementLabels[currentStatement];
    const dateColumns = Object.keys(sectionData[0]).filter(k => k !== Object.keys(sectionData[0])[0] && !k.startsWith('col_'));

    // Header
    const thead = document.createElement('thead');
    const trHead = document.createElement('tr');

    const th1 = document.createElement('th');
    th1.textContent = firstColumnLabel;
    trHead.appendChild(th1);

    dateColumns.forEach(col => {
        const th = document.createElement('th');
        th.textContent = col;
        trHead.appendChild(th);
    });

    thead.appendChild(trHead);
    table.appendChild(thead);

    // Body
    const tbody = document.createElement('tbody');
    const firstKey = Object.keys(sectionData[0])[0];

    sectionData.forEach(row => {
        const tr = document.createElement('tr');

        // First column (item name)
        const td1 = document.createElement('td');
        td1.textContent = row[firstKey] || '-';
        td1.style.fontWeight = '500';
        tr.appendChild(td1);

        // Date columns
        dateColumns.forEach(col => {
            const td = document.createElement('td');
            td.textContent = row[col] || '-';
            tr.appendChild(td);
        });

        tbody.appendChild(tr);
    });

    // Append Metadata Rows (All Figures In / Last Update)
    // These are usually at the bottom of the mainTable
    if (mainTable && mainTable.length > 0) {
        const metadataRows = mainTable.filter(row => {
            const rowValues = Object.values(row).join(' ');
            return rowValues.includes('All Figures in') || rowValues.includes('Last Update Date');
        });

        metadataRows.forEach(row => {
            const tr = document.createElement('tr');
            tr.style.backgroundColor = 'var(--bg-card)'; // lighter bg
            tr.style.color = 'var(--text-muted)';
            tr.style.fontStyle = 'italic';

            // First column (Label)
            const td1 = document.createElement('td');
            td1.textContent = row[firstKey] || Object.values(row)[0];
            tr.appendChild(td1);

            // Date columns
            dateColumns.forEach(col => {
                const td = document.createElement('td');
                td.textContent = row[col] || '';
                tr.appendChild(td);
            });

            tbody.appendChild(tr);
        });
    }

    table.appendChild(tbody);
}

function extractFinancialSection(fullTable, statementType) {
    const sectionMarkers = {
        'Balance_Sheet': { start: null, end: 'Statement of Income' },
        'Statement_of_Income': { start: 'Statement of Income', end: 'Cash Flows' },
        'Cash_Flows': { start: 'Cash Flows', end: 'All Figures' }
    };

    const marker = sectionMarkers[statementType];
    const firstColumnKey = Object.keys(fullTable[0])[0];

    let startIndex = 0;
    let endIndex = fullTable.length;

    // Find start
    if (marker.start) {
        for (let i = 0; i < fullTable.length; i++) {
            if (fullTable[i][firstColumnKey] === marker.start) {
                startIndex = i + 1; // Skip the header row
                break;
            }
        }
    }

    // Find end
    if (marker.end) {
        for (let i = startIndex; i < fullTable.length; i++) {
            const val = fullTable[i][firstColumnKey];
            if (val === marker.end || (val && val.includes(marker.end))) {
                endIndex = i;
                break;
            }
        }
    }

    return fullTable.slice(startIndex, endIndex);
}

// --- Navigation ---
function setupNavigation() {
    const items = document.querySelectorAll('.nav-links li');
    items.forEach(item => {
        item.addEventListener('click', () => {
            items.forEach(i => i.classList.remove('active'));
            item.classList.add('active');
            document.querySelectorAll('.view-section').forEach(v => v.classList.remove('active'));
            const tabId = item.getAttribute('data-tab');
            document.getElementById(tabId).classList.add('active');
        });
    });
}
