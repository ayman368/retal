# Saudi Exchange Financial Scraper Dashboard

A comprehensive tool for scraping financial data (Balance Sheets, Income Statements, Cash Flows) from the Saudi Exchange and displaying them in a modern, interactive dashboard.

## 🚀 Features

- **Automated Scraping**: Python scripts using Playwright to extract full financial history.
- **Support for Multi-Company**: Scrapes data for multiple company symbols (Retal, etc.).
- **Interactive Dashboard**: Modern UI with a search bar, dark mode, and annual/quarterly comparisons.
- **Dynamic Table Layout**: View historical financial data in a structured, easy-to-read table format.

## 🛠️ Technology Stack

- **Python**: Playwright for web scraping and automation.
- **HTML/CSS/JS**: Vanilla frontend for the dashboard (Zakhm UI style).
- **JSON**: Data storage for company-specific financial records.

## 📦 Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/your-username/saudi-exchange-scraper.git
   cd saudi-exchange-scraper
   ```

2. **Install dependencies:**
   ```bash
   pip install playwright
   playwright install chromium
   ```

## 🖥️ Usage

### 1. Scraping Data
To scrape a single company:
```bash
python scrape_single_company.py
```
To scrape all predefined companies:
```bash
python scrape_multi_companies.py
```

### 2. Running the Dashboard
Since the dashboard loads JSON files dynamically, you need a local server to avoid CORS issues:
```bash
python start_server.py
```
Then open your browser at:
`http://localhost:8000/companies_viewer.html`

## 📁 Project Structure

- `scrape_multi_companies.py`: Main scraper for the company list.
- `companies_data/`: Directory containing all scraped JSON files.
- `companies_viewer.html`: The main dashboard UI.
- `start_server.py`: Local server utility.
- `style.css`: Shared styling for the dashboard.

---
*Developed for financial analysis and academic research.*
