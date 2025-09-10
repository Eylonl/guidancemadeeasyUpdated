import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import streamlit as st
import os
import re

# Force deployment refresh - all debug info consolidated into single expander

def get_ticker_from_cik(cik):
    """Get ticker symbol from CIK for display purposes"""
    try:
        headers = {'User-Agent': st.secrets.get('SEC_USER_AGENT', 'Your Name Contact@domain.com')}
        res = requests.get("https://www.sec.gov/files/company_tickers.json", headers=headers)
        res.raise_for_status()
        data = res.json()
        for entry in data.values():
            if str(entry["cik_str"]).zfill(10) == cik:
                return entry["ticker"].upper()
        return None
    except Exception:
        return None

@st.cache_data(show_spinner=False)
def lookup_cik(ticker):
    """Look up CIK from ticker symbol"""
    headers = {'User-Agent': st.secrets.get('SEC_USER_AGENT', 'Your Name Contact@domain.com')}
    res = requests.get("https://www.sec.gov/files/company_tickers.json", headers=headers)
    res.raise_for_status()
    data = res.json()
    for entry in data.values():
        if entry["ticker"].upper() == ticker:
            return str(entry["cik_str"]).zfill(10)

def get_fiscal_year_end(ticker, cik):
    """Get the fiscal year end month for a company from SEC data"""
    try:
        headers = {'User-Agent': st.secrets.get('SEC_USER_AGENT', 'Your Name Contact@domain.com')}
        url = f"https://data.sec.gov/submissions/CIK{cik}.json"
        resp = requests.get(url, headers=headers)
        resp.raise_for_status()
        data = resp.json()
        if 'fiscalYearEnd' in data:
            fiscal_year_end = data['fiscalYearEnd']
            if len(fiscal_year_end) == 4:
                month = int(fiscal_year_end[:2])
                day = int(fiscal_year_end[2:])
                month_name = datetime(2000, month, 1).strftime('%B')
                with st.expander("🔍 Debug Information", expanded=False):
                    st.success(f"Retrieved fiscal year end for {ticker}: {month_name} {day}")
                return month, day
        with st.expander("🔍 Debug Information", expanded=False):
            st.warning(f"Could not determine fiscal year end for {ticker} from SEC data. Using December 31 (calendar year).")
        return 12, 31
    except Exception as e:
        with st.expander("🔍 Debug Information", expanded=False):
            st.warning(f"Error retrieving fiscal year end: {str(e)}. Using December 31 (calendar year).")
        return 12, 31

def generate_fiscal_quarters(fiscal_year_end_month):
    """Dynamically generate fiscal quarters based on the fiscal year end month"""
    fiscal_year_start_month = (fiscal_year_end_month % 12) + 1
    quarters = {}
    current_month = fiscal_year_start_month
    for q in range(1, 5):
        start_month = current_month
        end_month = (start_month + 2) % 12
        if end_month == 0:
            end_month = 12
        quarters[q] = {'start_month': start_month, 'end_month': end_month}
        current_month = (end_month % 12) + 1
    return quarters

def get_fiscal_dates(ticker, quarter_num, year_num, fiscal_year_end_month, fiscal_year_end_day):
    """Calculate the appropriate date range for a fiscal quarter"""
    quarters = generate_fiscal_quarters(fiscal_year_end_month)
    if quarter_num < 1 or quarter_num > 4:
        st.error(f"Invalid quarter number: {quarter_num}. Must be 1-4.")
        return None
    quarter_info = quarters[quarter_num]
    start_month = quarter_info['start_month']
    end_month = quarter_info['end_month']
    spans_calendar_years = end_month < start_month
    if fiscal_year_end_month == 12:
        start_calendar_year = year_num
    else:
        fiscal_year_start_month = (fiscal_year_end_month % 12) + 1
        if start_month >= fiscal_year_start_month:
            start_calendar_year = year_num - 1
        else:
            start_calendar_year = year_num
    end_calendar_year = start_calendar_year
    if spans_calendar_years:
        end_calendar_year = start_calendar_year + 1
    start_date = datetime(start_calendar_year, start_month, 1)
    if end_month == 2:
        if (end_calendar_year % 4 == 0 and end_calendar_year % 100 != 0) or (end_calendar_year % 400 == 0):
            end_day = 29
        else:
            end_day = 28
    elif end_month in [4, 6, 9, 11]:
        end_day = 30
    else:
        end_day = 31
    end_date = datetime(end_calendar_year, end_month, end_day)
    report_start = end_date + timedelta(days=15)
    report_end = report_start + timedelta(days=45)
    quarter_period = f"Q{quarter_num} FY{year_num}"
    period_description = f"{start_date.strftime('%B %d, %Y')} to {end_date.strftime('%B %d, %Y')}"
    expected_report = f"~{report_start.strftime('%B %d, %Y')} to {report_end.strftime('%B %d, %Y')}"
    with st.expander("🔍 Debug Information", expanded=False):
        st.write(f"Fiscal year ends in {datetime(2000, fiscal_year_end_month, 1).strftime('%B')} {fiscal_year_end_day}")
        st.write(f"Quarter {quarter_num} spans: {datetime(2000, start_month, 1).strftime('%B')}-{datetime(2000, end_month, 1).strftime('%B')}")
        st.write("All quarters for this fiscal pattern:")
        for q, q_info in quarters.items():
            st.write(f"Q{q}: {datetime(2000, q_info['start_month'], 1).strftime('%B')}-{datetime(2000, q_info['end_month'], 1).strftime('%B')}")
    return {
        'quarter_period': quarter_period,
        'start_date': start_date,
        'end_date': end_date,
        'report_start': report_start,
        'report_end': report_end,
        'period_description': period_description,
        'expected_report': expected_report
    }

def get_accessions(cik, ticker, years_back=None, specific_quarter=None):
    """General function for finding filings"""
    headers = {'User-Agent': st.secrets.get('SEC_USER_AGENT', 'Your Name Contact@domain.com')}
    url = f"https://data.sec.gov/submissions/CIK{cik}.json"
    resp = requests.get(url, headers=headers)
    resp.raise_for_status()
    data = resp.json()
    filings = data["filings"]["recent"]
    accessions = []
    fiscal_year_end_month, fiscal_year_end_day = get_fiscal_year_end(ticker, cik)
    
    if years_back:
        cutoff = datetime.today() - timedelta(days=(365 * years_back) + 91.25)
        with st.expander("🔍 Debug Information", expanded=False):
            st.write(f"Looking for filings from the past {years_back} years plus 1 quarter (from {cutoff.strftime('%Y-%m-%d')} to present)")
        for form, date_str, accession in zip(filings["form"], filings["filingDate"], filings["accessionNumber"]):
            if form == "8-K":
                date = datetime.strptime(date_str, "%Y-%m-%d")
                if date >= cutoff:
                    accessions.append((accession, date_str))
    elif specific_quarter:
        match = re.search(r'(?:Q?(\d)Q?|Q(\d))(?:\s*FY\s*|\s*)?(\d{2}|\d{4})', specific_quarter.upper())
        if match:
            quarter = match.group(1) or match.group(2)
            year = match.group(3)
            if len(year) == 2:
                year = '20' + year
            quarter_num = int(quarter)
            year_num = int(year)
            fiscal_info = get_fiscal_dates(ticker, quarter_num, year_num, fiscal_year_end_month, fiscal_year_end_day)
            if not fiscal_info:
                return []
            with st.expander("🔍 Debug Information", expanded=False):
                st.write(f"Looking for {ticker} {fiscal_info['quarter_period']} filings")
                st.write(f"Fiscal quarter period: {fiscal_info['period_description']}")
                st.write(f"Expected earnings reporting window: {fiscal_info['expected_report']}")
                start_date = fiscal_info['report_start'] - timedelta(days=15)
                end_date = fiscal_info['report_end'] + timedelta(days=15)
                st.write(f"Searching for filings between: {start_date.strftime('%Y-%m-%d')} and {end_date.strftime('%Y-%m-%d')}")
            for form, date_str, accession in zip(filings["form"], filings["filingDate"], filings["accessionNumber"]):
                if form == "8-K":
                    date = datetime.strptime(date_str, "%Y-%m-%d")
                    if start_date <= date <= end_date:
                        accessions.append((accession, date_str))
                        with st.expander("🔍 Debug Information", expanded=False):
                            st.write(f"Found filing from {date_str}: {accession}")
    else:
        # Default: auto-detect most recent quarter and search for that specific quarter's earnings
        current_date = datetime.today()
        
        # Determine the most recent completed quarter based on fiscal year end
        if fiscal_year_end_month <= 3:  # Jan-Mar fiscal year end
            if current_date.month <= fiscal_year_end_month:
                # We're in the fiscal year, determine quarter
                quarter_num = ((current_date.month - fiscal_year_end_month - 1) % 12) // 3 + 1
                year_num = current_date.year
            else:
                # We're past fiscal year end, so last quarter was Q4 of previous fiscal year
                quarter_num = 4
                year_num = current_date.year
        else:  # Apr-Dec fiscal year end
            if current_date.month > fiscal_year_end_month:
                # We're past fiscal year end, so last quarter was Q4
                quarter_num = 4
                year_num = current_date.year
            else:
                # We're in the fiscal year
                months_into_fy = (current_date.month - fiscal_year_end_month - 1) % 12
                quarter_num = months_into_fy // 3 + 1
                year_num = current_date.year
        
        # Adjust for the most recent completed quarter (subtract 1 quarter)
        quarter_num -= 1
        if quarter_num <= 0:
            quarter_num = 4
            year_num -= 1
        
        with st.expander("🔍 Debug Information", expanded=False):
            st.write(f"Auto-detecting most recent quarter: Q{quarter_num} {year_num}")
        
        # Use the quarter-based search logic
        fiscal_info = get_fiscal_dates(ticker, quarter_num, year_num, fiscal_year_end_month, fiscal_year_end_day)
        if fiscal_info:
            with st.expander("🔍 Debug Information", expanded=False):
                st.write(f"Looking for {ticker} {fiscal_info['quarter_period']} filings")
                st.write(f"Expected earnings reporting window: {fiscal_info['expected_report']}")
                start_date = fiscal_info['report_start'] - timedelta(days=15)
                end_date = fiscal_info['report_end'] + timedelta(days=15)
                st.write(f"Searching for filings between: {start_date.strftime('%Y-%m-%d')} and {end_date.strftime('%Y-%m-%d')}")
            for form, date_str, accession in zip(filings["form"], filings["filingDate"], filings["accessionNumber"]):
                if form == "8-K":
                    date = datetime.strptime(date_str, "%Y-%m-%d")
                    if start_date <= date <= end_date:
                        accessions.append((accession, date_str))
                        with st.expander("🔍 Debug Information", expanded=False):
                            st.write(f"Found filing from {date_str}: {accession}")
    
    if accessions:
        with st.expander("🔍 Debug Information", expanded=False):
            st.write(f"Found {len(accessions)} relevant 8-K filings")
    else:
        available_dates = []
        for form, date_str in zip(filings["form"], filings["filingDate"]):
            if form == "8-K":
                available_dates.append(date_str)
        if available_dates:
            available_dates.sort(reverse=True)
            with st.expander("🔍 Debug Information", expanded=False):
                st.write("All available 8-K filing dates:")
                for date in available_dates[:15]:
                    st.write(f"- {date}")
                if len(available_dates) > 15:
                    st.write(f"... and {len(available_dates) - 15} more")
    return accessions

def is_earnings_release(url, headers):
    """Validate that a document is actually an earnings release"""
    try:
        # Skip iXBRL files that cause redirect issues
        if 'ixbrl' in url.lower():
            with st.expander("🔍 Debug Information", expanded=False):
                st.write(f"Skipped iXBRL file: {url}")
            return False
            
        # Get a sample of the document content with redirect handling
        res = requests.get(url, headers=headers, timeout=30, allow_redirects=False)
        
        # Handle redirects manually to avoid infinite loops
        if res.status_code in [301, 302, 303, 307, 308]:
            with st.expander("🔍 Debug Information", expanded=False):
                st.write(f"Skipped redirected URL: {url}")
            return False
            
        if res.status_code != 200:
            return False
        
        content = res.text.lower()
        
        # Check for earnings-related keywords
        earnings_keywords = [
            'earnings', 'quarterly results', 'financial results', 
            'revenue', 'net income', 'earnings per share', 'eps',
            'quarterly earnings', 'fiscal quarter', 'q1', 'q2', 'q3', 'q4',
            'first quarter', 'second quarter', 'third quarter', 'fourth quarter'
        ]
        
        # Must have at least 3 earnings keywords
        keyword_count = sum(1 for keyword in earnings_keywords if keyword in content)
        
        # Strong exclusion indicators (these are likely NOT earnings releases)
        strong_exclusions = [
            'dividend declaration only', 'stock split announcement', 
            'director appointment', 'officer appointment',
            'merger agreement', 'acquisition agreement'
        ]
        
        # Check for strong exclusions that indicate non-earnings documents
        has_strong_exclusions = any(exclusion in content for exclusion in strong_exclusions)
        
        # Additional check: if it has many earnings keywords, it's likely an earnings release
        # even if it mentions some business activities
        is_likely_earnings = keyword_count >= 5
        
        # Must have earnings keywords and either be clearly earnings-focused or not have strong exclusions
        return keyword_count >= 3 and (is_likely_earnings or not has_strong_exclusions)
        
    except Exception as e:
        with st.expander("🔍 Debug Information", expanded=False):
            st.write(f"Error validating earnings release {url}: {str(e)}")
        return False

def get_ex99_1_links(cik, accessions):
    """Enhanced function to find exhibit 99.1 files with better searching and earnings validation"""
    links = []
    headers = {'User-Agent': st.secrets.get('SEC_USER_AGENT', 'Your Name Contact@domain.com')}
    for accession, date_str in accessions:
        accession_no_dashes = accession.replace('-', '')
        base_folder = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accession_no_dashes}/"
        index_url = base_folder + f"{accession}-index.htm"
        try:
            res = requests.get(index_url, headers=headers, timeout=30)
            if res.status_code != 200:
                continue
            soup = BeautifulSoup(res.text, "html.parser")
            found_exhibit = False
            
            # First, look for explicit 99.1 exhibits
            for row in soup.find_all("tr"):
                row_text = row.get_text().lower()
                if "99.1" in row_text or "99.01" in row_text:
                    tds = row.find_all("td")
                    if len(tds) >= 3:
                        filename = tds[2].text.strip()
                        exhibit_url = base_folder + filename
                        
                        # Validate it's an earnings release
                        if is_earnings_release(exhibit_url, headers):
                            with st.expander("🔍 Debug Information", expanded=False):
                                st.write(f"✅ Validated earnings release: {exhibit_url}")
                            links.append((date_str, accession, exhibit_url))
                            found_exhibit = True
                            break
                        else:
                            with st.expander("🔍 Debug Information", expanded=False):
                                st.write(f"⏭️ Skipped non-earnings 8-K: {exhibit_url}")
            
            # If no explicit 99.1, look for other exhibit files
            if not found_exhibit:
                for row in soup.find_all("tr"):
                    tds = row.find_all("td")
                    if len(tds) >= 3:
                        filename = tds[2].text.strip()
                        if filename.endswith('.htm') and ('ex' in filename.lower() or 'exhibit' in filename.lower()):
                            exhibit_url = base_folder + filename
                            
                            # Validate it's an earnings release
                            if is_earnings_release(exhibit_url, headers):
                                with st.expander("🔍 Debug Information", expanded=False):
                                    st.write(f"✅ Validated earnings release: {exhibit_url}")
                                links.append((date_str, accession, exhibit_url))
                                found_exhibit = True
                                break
                            else:
                                with st.expander("🔍 Debug Information", expanded=False):
                                    st.write(f"⏭️ Skipped non-earnings 8-K: {exhibit_url}")
            
            # Try common patterns as fallback
            if not found_exhibit:
                date_no_dash = date_str.replace('-', '')
                common_patterns = [
                    f"ex-991x{date_no_dash}x8k.htm",
                    f"ex991x{date_no_dash}x8k.htm",
                    f"ex-99_1x{date_no_dash}x8k.htm",
                    f"ex991{date_no_dash}.htm", 
                    f"exhibit991.htm",
                    f"ex99-1.htm",
                    f"ex991.htm",
                    f"ex-99.1.htm",
                    f"exhibit99_1.htm"
                ]
                for pattern in common_patterns:
                    test_url = base_folder + pattern
                    try:
                        test_res = requests.head(test_url, headers=headers, timeout=10)
                        if test_res.status_code == 200:
                            # Validate it's an earnings release
                            if is_earnings_release(test_url, headers):
                                with st.expander("🔍 Debug Information", expanded=False):
                                    st.write(f"✅ Validated earnings release: {test_url}")
                                links.append((date_str, accession, test_url))
                                found_exhibit = True
                                break
                            else:
                                with st.expander("🔍 Debug Information", expanded=False):
                                    st.write(f"⏭️ Skipped non-earnings 8-K: {test_url}")
                    except:
                        continue
        except Exception as e:
            with st.expander("🔍 Debug Information", expanded=False):
                st.write(f"Error processing accession {accession}: {str(e)}")
            continue
    return links

def find_guidance_paragraphs(text):
    """Extract paragraphs from text that are likely to contain guidance information
    Optimized for large documents with progressive filtering"""
    
    # For very large documents (>50k chars), do initial keyword filtering
    if len(text) > 50000:
        # First pass: extract sections likely to contain guidance
        guidance_sections = []
        
        # Comprehensive section headers for guidance extraction
        section_headers = [
            'OUTLOOK', 'GUIDANCE', 'FORWARD LOOKING', 'BUSINESS OUTLOOK', 'FINANCIAL OUTLOOK',
            'LOOKING AHEAD', 'GOING FORWARD', 'FUTURE EXPECTATIONS', 'EXPECTATIONS',
            'PROJECTIONS', 'FORECASTS', 'TARGETS', 'GOALS', 'OBJECTIVES',
            'NEXT QUARTER', 'UPCOMING QUARTER', 'COMING QUARTER', 'CURRENT QUARTER',
            'NEXT YEAR', 'UPCOMING YEAR', 'COMING YEAR', 'CURRENT YEAR',
            'REVENUE OUTLOOK', 'EARNINGS OUTLOOK', 'MARGIN OUTLOOK', 'GROWTH OUTLOOK',
            'BUSINESS UPDATE', 'OPERATIONAL UPDATE', 'STRATEGIC UPDATE',
            'KEY METRICS', 'PERFORMANCE METRICS', 'FINANCIAL METRICS'
        ]
        
        # Split by section headers
        header_pattern = r'\n\s*(?:' + '|'.join(section_headers) + r')\s*\n'
        sections = re.split(header_pattern, text, flags=re.IGNORECASE)
        
        # For slide presentations, treat each slide as a potential section
        # Look for slide indicators and preserve entire slides
        slide_patterns = [
            r'\n\s*(?:Slide|Page)\s+\d+\s*\n',
            r'\n\s*\d+\s*/\s*\d+\s*\n',  # Page numbers like "5 / 20"
            r'\n\s*━+\s*\n',  # Slide separators
            r'\n\s*─+\s*\n',  # Alternative separators
            r'\n\s*═+\s*\n'   # Another separator style
        ]
        
        # Check if this looks like a slide presentation
        is_slideshow = any(re.search(pattern, text) for pattern in slide_patterns)
        
        if is_slideshow:
            # For slideshows, split by slide indicators and keep entire slides
            for pattern in slide_patterns:
                if re.search(pattern, text):
                    slides = re.split(pattern, text)
                    break
            else:
                slides = [text]  # Fallback if no clear slide pattern
            
            # Evaluate each slide for guidance content
            for slide in slides:
                if len(slide.strip()) < 100:  # Skip very short slides
                    continue
                    
                # Score slides based ONLY on guidance indicators to avoid historical performance data
                guidance_score = 0
                guidance_score += len(re.findall(r'(?i)(?:expect|anticipate|forecast|project|estimate|target|outlook|guidance|plan|intend|believe|see|view)', slide))
                
                # Lower threshold for slides since they're more concise
                if guidance_score >= 2:
                    guidance_sections.append(slide.strip())
        else:
            # For regular documents, look for paragraphs with high density of guidance keywords
            paragraphs = text.split('\n\n')
            for para in paragraphs:
                if len(para) < 50:  # Skip very short paragraphs
                    continue
                    
                # Score based ONLY on guidance indicators to avoid historical performance data
                guidance_score = 0
                guidance_score += len(re.findall(r'(?i)(?:expect|anticipate|forecast|project|estimate|target|outlook|guidance|plan|intend|believe|see|view|confident|optimistic)', para))
                
                # If paragraph has high guidance density, include it
                if guidance_score >= 3:
                    guidance_sections.append(para)
        
        # Limit to most relevant sections but allow more for slideshows
        max_sections = 15 if is_slideshow else 10
        text = '\n\n'.join(guidance_sections[:max_sections])
    
    # Split into sentences for more precise filtering
    sentences = re.split(r'(?<=[.!?])\s+', text)
    guidance_sentences = []
    
    # Look for sentences that contain both guidance indicators AND financial content
    for sentence in sentences:
            
        # Skip obvious boilerplate
        if (re.search(r'(?i)safe harbor', sentence) or
            re.search(r'(?i)forward-looking statements.*risks', sentence) or
            re.search(r'(?i)will provide.*guidance.*connection with.*earnings', sentence) or
            re.search(r'(?i)conference call.*webcast', sentence) or
            re.search(r'(?i)undertakes no duty to update', sentence) or
            re.search(r'(?i)actual results could differ materially', sentence) or
            re.search(r'(?i)based on current expectations.*subject to risks', sentence)):
            continue
            
        # Look for guidance indicators
        has_guidance_indicator = (
            re.search(r'(?i)(?:expect|anticipate|forecast|project|estimate|target)', sentence) or
            re.search(r'(?i)(?:outlook|guidance)', sentence) or
            re.search(r'(?i)for (?:the )?(?:fiscal|next|coming|upcoming) (?:quarter|year)', sentence) or
            re.search(r'(?i)(?:revenue|earnings|eps|margin|growth) (?:is|to be|will be) (?:expected|anticipated)', sentence)
        )
        
        # Look for financial content
        has_financial_content = (
            re.search(r'\$[\d,.]+(?: billion| million|B|M)?', sentence) or  # Dollar amounts
            re.search(r'\d+\.?\d*%', sentence) or  # Percentages
            re.search(r'(?i)\d+\.?\d*(?:\s*(?:billion|million|percent|%))', sentence) or  # Numbers with units
            re.search(r'(?i)(?:revenue|earnings|eps|margin|growth).*\$?\d+', sentence) or  # Financial metrics with numbers
            re.search(r'(?i)\d+.*(?:quarter|year|q[1-4]|fy\d+)', sentence)  # Numbers with time periods
        )
        
        # Only include sentences with both guidance indicators AND financial content
        if has_guidance_indicator and has_financial_content:
            guidance_sentences.append(sentence.strip())
    
    # Check if we actually found any meaningful guidance sentences
    found_paragraphs = len(guidance_sentences) > 0
    
    formatted_paragraphs = "\n\n".join(guidance_sentences)
    if found_paragraphs:
        formatted_paragraphs = (
            f"DOCUMENT TYPE: SEC 8-K Earnings Release for {{ticker}}\n\n"
            f"POTENTIAL GUIDANCE INFORMATION (extracted from full document):\n\n{formatted_paragraphs}\n\n"
            "Note: These are selected sentences that may contain forward-looking guidance."
        )
    
    return formatted_paragraphs, found_paragraphs
