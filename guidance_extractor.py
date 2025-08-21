import os
import pandas as pd
import re
from openai import OpenAI
import streamlit as st
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def extract_guidance(text, ticker, client, model_name):
    """Enhanced function to extract guidance from SEC filings"""
    prompt = f"""You are a financial analyst assistant. Extract ONLY formal financial guidance, projections, and outlook statements with concrete numeric targets from this earnings release for {ticker}.

Return a structured table containing the following columns:

- metric (preserve EXACT metric names from the text, including specific business segments like "Productivity and Business Processes revenue", "More Personal Computing revenue", "Intelligent Cloud revenue", "Azure revenue", "Office 365 Commercial revenue", "Windows revenue", "Xbox revenue", etc. CRITICAL: ONLY append "constant currency" to the metric name if that specific guidance statement explicitly mentions "constant currency", "in constant currency", or similar currency qualifiers. Do NOT add "constant currency" to metrics that don't explicitly mention it in their guidance statement. Example: "Non-GAAP EPS is expected to be $1.44 to $1.48 in constant currency" should become "Non-GAAP EPS constant currency", while "Non-GAAP EPS is expected to be $1.46 to $1.50" should remain exactly "Non-GAAP EPS")
- value_or_range (e.g. $1.5B–$1.6B or $2.05 or $(0.05) to $0.10 - EXACTLY as it appears in the text)
- period (e.g. Q3 FY24, Full Year 2025)
- period_type (MUST be either "Quarter" or "Full Year" based on the period text)
- low (numeric low end of the range, or the single value if not a range)
- high (numeric high end of the range, or the single value if not a range)
- average (average of low and high, or just the value if not a range)

STRICT CRITERIA FOR VALID GUIDANCE:

1. MUST be presented in dedicated guidance sections: 'Outlook', 'Guidance', 'Financial Outlook', 'Business Outlook', or similar
2. MUST contain specific financial metrics including business segment breakdowns: Revenue (preserve segment names like "Productivity and Business Processes", "More Personal Computing", "Intelligent Cloud"), EPS, Earnings, Operating Income, Operating Margin, Net Income, Cash Flow, EBITDA, etc.
3. MUST include either:
   - Concrete numeric values, ranges, or percentages (e.g., "$1.5B", "15-20%", "$2.50-$3.00")
   - OR relative guidance statements (e.g., "above last year", "slight expansion", "higher than", "growth of", "increase from")
4. MUST specify a future time period (next quarter, fiscal year, etc.)
5. MUST be presented as formal company guidance, NOT management commentary

STRICTLY EXCLUDE:
- Any statements with "we expect", "we anticipate", "we believe", "we forecast", "we project"
- Any predictive or forward-looking language
- Management commentary or opinions about future performance
- Historical performance discussions (past quarters/years)
- Current quarter actual results
- Risk factors or cautionary statements
- General strategic initiatives without financial targets
- Vague statements like "continued growth" without specific targets

ONLY EXTRACT: Formal guidance presented in dedicated sections as official company targets or ranges WITHOUT forward-looking statements or predictive language.

If NO formal financial guidance is provided, return an empty table with just the headers.

CRITICAL GUIDANCE FOR THE NUMERIC COLUMNS (low, high, average):

- For concrete numeric guidance: provide ONLY numeric values (no $ signs, no % symbols, no "million" or "billion" text)
- Use negative numbers for negative values: -1 instead of "(1)" and -5 instead of "(5%)"
- For mixed sign ranges like "$(1) million to $1 million", make sure low is negative (-1) and high is positive (1)
- Convert all billions to millions (multiply by 1000): $1.2 billion → 1200
- For percentages, give the number with % sign: "5% to 7%" → low=5%, high=7%
- For dollar amounts, omit the $ sign: "$0.05 to $0.10" → low=0.05, high=0.10

- For qualitative/relative guidance (e.g., "above last year", "slight expansion"): 
  - Fill low, high, and average columns with the same qualitative text from value_or_range
  - Capture the full qualitative statement in the value_or_range column exactly as stated

FOR THE PERIOD TYPE COLUMN:

- Classify each period as either "Quarter" or "Full Year" based on the applicable period
- Use "Quarter" for: Q1, Q2, Q3, Q4, First Quarter, Next Quarter, Current Quarter, etc.
- Use "Full Year" for: Full Year, Fiscal Year, FY, Annual, Year Ending, etc.
- If a period just mentions a year (e.g., "2023" or "FY24") without specifying a quarter, classify it as "Full Year"
- THIS COLUMN IS REQUIRED AND MUST ONLY CONTAIN "Quarter" OR "Full Year" - NO OTHER VALUES

FORMATTING INSTRUCTIONS FOR VALUE_OR_RANGE COLUMN:

- Always preserve the original notation exactly as it appears in the document (maintain parentheses, $ signs, % symbols)
- Example: If document says "($0.05) to $0.10", use exactly "($0.05) to $0.10" in value_or_range column
- Example: If document says "(5%) to 2%", use exactly "(5%) to 2%" in value_or_range column
- For billion values, keep them as billions in this column: "$1.10 billion to $1.11 billion"

Respond in table format without commentary.\n\n{text}"""

    try:
        response = client.chat.completions.create(
            model=model_name,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
        )
        return response.choices[0].message.content
    except Exception as e:
        st.warning(f"Error extracting guidance: {str(e)}")
        return None

def find_guidance_paragraphs_transcript(text):
    """Extract paragraphs from transcript that likely contain guidance - expanded approach"""
    # More lenient guidance patterns
    guidance_patterns = [
        r'(?i)outlook',
        r'(?i)guidance',
        r'(?i)looking ahead',
        r'(?i)going forward',
        r'(?i)moving forward',
        r'(?i)we see',
        r'(?i)we anticipate',
        r'(?i)we forecast',
        r'(?i)we expect',
        r'(?i)we believe',
        r'(?i)we project',
        r'(?i)we estimate',
        r'(?i)we plan',
        r'(?i)we intend',
        r'(?i)for (?:the )?(?:fiscal|next|coming|upcoming|remainder|rest)',
        r'(?i)revenue',
        r'(?i)margin',
        r'(?i)growth',
        r'(?i)earnings',
        r'(?i)profit',
        r'(?i)cash flow',
        r'(?i)capex',
        r'(?i)investment',
        r'(?i)full year',
        r'(?i)next quarter',
        r'(?i)Q[1-4]',
        r'(?i)fiscal (?:year|quarter)',
        r'(?i)2024|2025|2026',
        r'(?i)\$[\d\.]',
        r'(?i)\d+%',
        r'(?i)range of',
        r'(?i)between.*and',
        r'(?i)approximately',
        r'(?i)about \$'
    ]
    
    # CFO-specific patterns to capture all CFO comments
    cfo_patterns = [
        r'(?i)chief financial officer',
        r'(?i)\bCFO\b',
        r'(?i)finance chief',
        r'(?i)financial officer'
    ]
    
    # Split into paragraphs
    paragraphs = re.split(r'\n\s*\n|\.\s+(?=[A-Z])', text)
    guidance_paragraphs = []
    
    for para in paragraphs:
        # Include paragraph if it matches guidance patterns OR contains CFO content
        has_guidance = any(re.search(pattern, para) for pattern in guidance_patterns)
        has_cfo_content = any(re.search(pattern, para) for pattern in cfo_patterns)
        
        if has_guidance or has_cfo_content:
            # Skip safe harbor and legal disclaimers
            if not (re.search(r'(?i)safe harbor', para) or 
                    re.search(r'(?i)forward-looking statements.*risks', para) or
                    re.search(r'(?i)disclaimer', para)):
                guidance_paragraphs.append(para.strip())
    
    # No paragraph limit - capture all relevant content
    return guidance_paragraphs

def extract_transcript_guidance(text, ticker, client, model_name):
    """Extract guidance from earnings call transcripts - token efficient"""
    # First, filter to guidance-relevant paragraphs only
    guidance_paragraphs = find_guidance_paragraphs_transcript(text)
    
    if not guidance_paragraphs:
        st.warning("No guidance-related paragraphs found in transcript")
        return None
    
    # Join filtered paragraphs - no character limits
    filtered_text = "\n\n".join(guidance_paragraphs)
    
    # Check token estimate (rough: 4 chars per token)
    estimated_tokens = len(filtered_text) // 4
    st.info(f"Sending ~{estimated_tokens:,} tokens to AI (filtered from {len(text):,} characters to {len(filtered_text):,} characters)")
    
    # No character truncation - send all relevant content
    
    prompt = f"""You are a financial analyst assistant. Extract ONLY formal financial guidance, projections, and outlook statements with concrete numeric targets from this earnings call transcript for {ticker}.

CRITICAL COMPLIANCE REQUIREMENT: Do NOT extract any forward-looking statements or predictive language. Only extract formal guidance that is presented as official company targets or ranges.

Return a structured table containing the following columns:

- metric (preserve EXACT metric names from the text, including specific business segments like "Productivity and Business Processes revenue", "More Personal Computing revenue", "Intelligent Cloud revenue", "Azure revenue", "Office 365 Commercial revenue", "Windows revenue", "Xbox revenue", etc. CRITICAL: ONLY append "constant currency" to the metric name if that specific guidance statement explicitly mentions "constant currency", "in constant currency", or similar currency qualifiers. Do NOT add "constant currency" to metrics that don't explicitly mention it in their guidance statement. Example: "Non-GAAP EPS is expected to be $1.44 to $1.48 in constant currency" should become "Non-GAAP EPS constant currency", while "Non-GAAP EPS is expected to be $1.46 to $1.50" should remain exactly "Non-GAAP EPS")
- value_or_range (e.g. $1.5B–$1.6B or $2.05 or $(0.05) to $0.10 - EXACTLY as it appears in the text)
- period (e.g. Q3 FY24, Full Year 2025)
- period_type (MUST be either "Quarter" or "Full Year" based on the period text)
- low (numeric low end of the range, or the single value if not a range)
- high (numeric high end of the range, or the single value if not a range)
- average (average of low and high, or just the value if not a range)

STRICT CRITERIA FOR VALID GUIDANCE:

1. MUST be presented as formal company guidance in prepared remarks or official Q&A responses
2. MUST contain specific financial metrics including business segment breakdowns: Revenue (preserve segment names like "Productivity and Business Processes", "More Personal Computing", "Intelligent Cloud"), EPS, Earnings, Operating Income, Operating Margin, Net Income, Cash Flow, EBITDA, etc.
3. MUST include concrete numeric values, ranges, or percentages (e.g., "$1.5B", "15-20%", "$2.50-$3.00")
4. MUST specify a future time period (next quarter, fiscal year, etc.)
5. MUST be presented as official targets or ranges, NOT management commentary

STRICTLY EXCLUDE (COMPLIANCE REQUIREMENT):
- Any statements with "we expect", "we anticipate", "we believe", "we forecast", "we project"
- Any predictive or forward-looking language
- Management commentary or opinions about future performance
- General business commentary without specific numbers
- Operational updates (customer growth, market trends, etc.)
- Vague statements like "continued growth" without specific targets
- Historical performance discussions
- Market commentary or industry trends
- General strategic initiatives without financial targets

ONLY EXTRACT: Formal guidance presented as official company targets or ranges in prepared remarks or official responses, without predictive language.

If NO formal financial guidance (without forward-looking statements) is provided, return an empty table with just the headers.

CRITICAL GUIDANCE FOR THE NUMERIC COLUMNS (low, high, average):

- For concrete numeric guidance: provide ONLY numeric values (no $ signs, no % symbols, no "million" or "billion" text)
- Use negative numbers for negative values: -1 instead of "(1)" and -5 instead of "(5%)"
- For mixed sign ranges like "$(1) million to $1 million", make sure low is negative (-1) and high is positive (1)
- Convert all billions to millions (multiply by 1000): $1.2 billion → 1200
- For percentages, give the number with % sign: "5% to 7%" → low=5%, high=7%
- For dollar amounts, omit the $ sign: "$0.05 to $0.10" → low=0.05, high=0.10

- For qualitative/relative guidance (e.g., "above last year", "slight expansion"): 
  - Fill low, high, and average columns with the same qualitative text from value_or_range
  - Capture the full qualitative statement in the value_or_range column exactly as stated

FOR THE PERIOD TYPE COLUMN:

- Classify each period as either "Quarter" or "Full Year" based on the applicable period
- Use "Quarter" for: Q1, Q2, Q3, Q4, First Quarter, Next Quarter, Current Quarter, etc.
- Use "Full Year" for: Full Year, Fiscal Year, FY, Annual, Year Ending, etc.
- If a period just mentions a year (e.g., "2023" or "FY24") without specifying a quarter, classify it as "Full Year"
- THIS COLUMN IS REQUIRED AND MUST ONLY CONTAIN "Quarter" OR "Full Year" - NO OTHER VALUES

FORMATTING INSTRUCTIONS FOR VALUE_OR_RANGE COLUMN:

- Always preserve the original notation exactly as it appears in the document (maintain parentheses, $ signs, % symbols)
- Example: If document says "($0.05) to $0.10", use exactly "($0.05) to $0.10" in value_or_range column
- Example: If document says "(5%) to 2%", use exactly "(5%) to 2%" in value_or_range column
- For billion values, keep them as billions in this column: "$1.10 billion to $1.11 billion"

Respond in table format without commentary.\n\n{filtered_text}"""

    try:
        response = client.chat.completions.create(
            model=model_name,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
        )
        return response.choices[0].message.content
    except Exception as e:
        st.warning(f"Error extracting transcript guidance: {str(e)}")
        return None

def split_gaap_non_gaap(df):
    """Split rows that contain both GAAP and non-GAAP guidance into separate rows"""
    if 'value_or_range' not in df.columns or 'metric' not in df.columns:
        return df

    rows = []
    for _, row in df.iterrows():
        val = str(row['value_or_range'])
        match = re.search(r'(\d[\d\.\s%to–-]*)\s*on a GAAP basis.*?(\d[\d\.\s%to–-]*)\s*on a non-GAAP basis', val, re.I)
        if match:
            gaap_val = match.group(1).strip() + " GAAP"
            non_gaap_val = match.group(2).strip() + " non-GAAP"
            for new_val, label in [(gaap_val, "GAAP"), (non_gaap_val, "Non-GAAP")]:
                new_row = row.copy()
                new_row["value_or_range"] = new_val
                new_row["metric"] = f"{row['metric']} ({label})"
                rows.append(new_row)
        else:
            rows.append(row)
    return pd.DataFrame(rows)

def standardize_metric_names(df):
    """Standardize and clean up metric names for consistency"""
    if 'metric' not in df.columns:
        return df
    
    # Define comprehensive standardized metric mappings
    metric_mappings = {
        # Revenue variations
        'revenue': 'Revenue',
        'revenues': 'Revenue',
        'total revenue': 'Revenue',
        'total revenues': 'Revenue',
        'net revenue': 'Revenue',
        'net revenues': 'Revenue',
        'net sales': 'Revenue',
        'total net sales': 'Revenue',
        'sales': 'Revenue',
        'total sales': 'Revenue',
        'gross sales': 'Revenue',
        'top line': 'Revenue',
        'turnover': 'Revenue',
        'income': 'Revenue',
        'total income': 'Revenue',
        'product revenue': 'Product Revenue',
        'product revenues': 'Product Revenue',
        'service revenue': 'Service Revenue',
        'service revenues': 'Service Revenue',
        'subscription revenue': 'Subscription Revenue',
        'subscription revenues': 'Subscription Revenue',
        'recurring revenue': 'Recurring Revenue',
        'license revenue': 'License Revenue',
        'software revenue': 'Software Revenue',
        'hardware revenue': 'Hardware Revenue',
        'consulting revenue': 'Consulting Revenue',
        'professional services revenue': 'Professional Services Revenue',
        'maintenance revenue': 'Maintenance Revenue',
        'support revenue': 'Support Revenue',
        'cloud revenue': 'Cloud Revenue',
        'saas revenue': 'SaaS Revenue',
        'platform revenue': 'Platform Revenue',
        'digital revenue': 'Digital Revenue',
        'online revenue': 'Online Revenue',
        'e-commerce revenue': 'E-commerce Revenue',
        'retail revenue': 'Retail Revenue',
        'wholesale revenue': 'Wholesale Revenue',
        'international revenue': 'International Revenue',
        'domestic revenue': 'Domestic Revenue',
        'organic revenue': 'Organic Revenue',
        'constant currency revenue': 'Constant Currency Revenue',
        
        # EPS variations
        'eps': 'EPS',
        'earnings per share': 'EPS',
        'diluted eps': 'EPS (Diluted)',
        'diluted earnings per share': 'EPS (Diluted)',
        'basic eps': 'EPS (Basic)',
        'basic earnings per share': 'EPS (Basic)',
        'adjusted eps': 'EPS (Adjusted)',
        'adjusted earnings per share': 'EPS (Adjusted)',
        'normalized eps': 'EPS (Normalized)',
        'core eps': 'EPS (Core)',
        'continuing operations eps': 'EPS (Continuing Operations)',
        'reported eps': 'EPS (Reported)',
        'pro forma eps': 'EPS (Pro Forma)',
        'non-gaap eps': 'EPS (Non-GAAP)',
        'non-gaap eps usd (non-gaap)': 'EPS (Non-GAAP)',
        'non-gaap eps q1 range usd (non-gaap)': 'EPS (Non-GAAP)',
        'eps (non-gaap)': 'EPS (Non-GAAP)',
        'gaap eps': 'EPS (GAAP)',
        
        # Operating metrics
        'operating income': 'Operating Income',
        'income from operations': 'Operating Income',
        'operating profit': 'Operating Income',
        'operating earnings': 'Operating Income',
        'operating results': 'Operating Income',
        'segment operating income': 'Segment Operating Income',
        'adjusted operating income': 'Operating Income (Adjusted)',
        'core operating income': 'Operating Income (Core)',
        'normalized operating income': 'Operating Income (Normalized)',
        'operating margin': 'Operating Margin',
        'operating profit margin': 'Operating Margin',
        'operating income margin': 'Operating Margin',
        'segment operating margin': 'Segment Operating Margin',
        'adjusted operating margin': 'Operating Margin (Adjusted)',
        'core operating margin': 'Operating Margin (Core)',
        
        # Net income variations
        'net income': 'Net Income',
        'net earnings': 'Net Income',
        'profit': 'Net Income',
        'net profit': 'Net Income',
        'bottom line': 'Net Income',
        'earnings': 'Net Income',
        'adjusted net income': 'Net Income (Adjusted)',
        'normalized net income': 'Net Income (Normalized)',
        'core net income': 'Net Income (Core)',
        'continuing operations net income': 'Net Income (Continuing Operations)',
        'attributable net income': 'Net Income (Attributable)',
        'net income attributable to shareholders': 'Net Income (Attributable to Shareholders)',
        
        # EBITDA variations
        'ebitda': 'EBITDA',
        'adjusted ebitda': 'EBITDA (Adjusted)',
        'normalized ebitda': 'EBITDA (Normalized)',
        'core ebitda': 'EBITDA (Core)',
        'segment ebitda': 'Segment EBITDA',
        'ebitda margin': 'EBITDA Margin',
        'adjusted ebitda margin': 'EBITDA Margin (Adjusted)',
        'ebit': 'EBIT',
        'adjusted ebit': 'EBIT (Adjusted)',
        'ebit margin': 'EBIT Margin',
        
        # Cash flow variations
        'cash flow': 'Cash Flow',
        'operating cash flow': 'Operating Cash Flow',
        'cash flow from operations': 'Operating Cash Flow',
        'cash from operations': 'Operating Cash Flow',
        'free cash flow': 'Free Cash Flow',
        'fcf': 'Free Cash Flow',
        'adjusted free cash flow': 'Free Cash Flow (Adjusted)',
        'normalized free cash flow': 'Free Cash Flow (Normalized)',
        'unlevered free cash flow': 'Unlevered Free Cash Flow',
        'levered free cash flow': 'Levered Free Cash Flow',
        'cash flow per share': 'Cash Flow Per Share',
        'free cash flow per share': 'Free Cash Flow Per Share',
        'investing cash flow': 'Investing Cash Flow',
        'financing cash flow': 'Financing Cash Flow',
        'cash flow yield': 'Cash Flow Yield',
        
        # Margin variations
        'gross margin': 'Gross Margin',
        'gross profit margin': 'Gross Margin',
        'gross profit': 'Gross Profit',
        'net margin': 'Net Margin',
        'profit margin': 'Net Margin',
        'net profit margin': 'Net Margin',
        'pretax margin': 'Pretax Margin',
        'pre-tax margin': 'Pretax Margin',
        'contribution margin': 'Contribution Margin',
        'segment margin': 'Segment Margin',
        'service margin': 'Service Margin',
        'product margin': 'Product Margin',
        'software margin': 'Software Margin',
        'hardware margin': 'Hardware Margin',
        
        # Capital and investment metrics
        'capex': 'CapEx',
        'capital expenditures': 'CapEx',
        'capital spending': 'CapEx',
        'capital investments': 'CapEx',
        'pp&e investments': 'CapEx',
        'maintenance capex': 'Maintenance CapEx',
        'growth capex': 'Growth CapEx',
        'r&d': 'R&D',
        'research and development': 'R&D',
        'r&d expenses': 'R&D',
        'research and development expenses': 'R&D',
        'sales and marketing': 'Sales & Marketing',
        'sg&a': 'SG&A',
        'selling general and administrative': 'SG&A',
        
        # Balance sheet metrics
        'total assets': 'Total Assets',
        'total liabilities': 'Total Liabilities',
        'shareholders equity': 'Shareholders Equity',
        'stockholders equity': 'Shareholders Equity',
        'book value': 'Book Value',
        'book value per share': 'Book Value Per Share',
        'tangible book value': 'Tangible Book Value',
        'working capital': 'Working Capital',
        'net working capital': 'Working Capital',
        'current assets': 'Current Assets',
        'current liabilities': 'Current Liabilities',
        'long term debt': 'Long-term Debt',
        'total debt': 'Total Debt',
        'net debt': 'Net Debt',
        'cash and equivalents': 'Cash & Equivalents',
        'cash and cash equivalents': 'Cash & Equivalents',
        'total cash': 'Cash & Equivalents',
        
        # Ratios and returns
        'roe': 'ROE',
        'return on equity': 'ROE',
        'roa': 'ROA',
        'return on assets': 'ROA',
        'roic': 'ROIC',
        'return on invested capital': 'ROIC',
        'roce': 'ROCE',
        'return on capital employed': 'ROCE',
        'debt to equity': 'Debt-to-Equity',
        'debt equity ratio': 'Debt-to-Equity',
        'current ratio': 'Current Ratio',
        'quick ratio': 'Quick Ratio',
        'asset turnover': 'Asset Turnover',
        'inventory turnover': 'Inventory Turnover',
        'receivables turnover': 'Receivables Turnover',
        
        # Growth metrics
        'revenue growth': 'Revenue Growth',
        'sales growth': 'Revenue Growth',
        'organic growth': 'Organic Growth',
        'constant currency growth': 'Constant Currency Growth',
        'same store sales': 'Same Store Sales',
        'comparable sales': 'Comparable Sales',
        'comp sales': 'Comparable Sales',
        'like for like sales': 'Like-for-Like Sales',
        'user growth': 'User Growth',
        'customer growth': 'Customer Growth',
        'subscriber growth': 'Subscriber Growth',
        
        # Per share metrics
        'book value per share': 'Book Value Per Share',
        'tangible book value per share': 'Tangible Book Value Per Share',
        'sales per share': 'Sales Per Share',
        'revenue per share': 'Revenue Per Share',
        'dividends per share': 'Dividends Per Share',
        'dividend per share': 'Dividends Per Share',
        
        # Tax metrics
        'tax rate': 'Tax Rate',
        'effective tax rate': 'Effective Tax Rate',
        'tax expense': 'Tax Expense',
        'income tax expense': 'Tax Expense',
        'provision for income taxes': 'Tax Expense',
        
        # Other financial metrics
        'backlog': 'Backlog',
        'deferred revenue': 'Deferred Revenue',
        'unearned revenue': 'Deferred Revenue',
        'contract liabilities': 'Deferred Revenue',
        'remaining performance obligations': 'Remaining Performance Obligations',
        'rpo': 'Remaining Performance Obligations',
        'annual recurring revenue': 'Annual Recurring Revenue',
        'arr': 'Annual Recurring Revenue',
        'monthly recurring revenue': 'Monthly Recurring Revenue',
        'mrr': 'Monthly Recurring Revenue',
        'total contract value': 'Total Contract Value',
        'tcv': 'Total Contract Value',
        'annual contract value': 'Annual Contract Value',
        'acv': 'Annual Contract Value',
        'customer lifetime value': 'Customer Lifetime Value',
        'clv': 'Customer Lifetime Value',
        'ltv': 'Customer Lifetime Value',
        'customer acquisition cost': 'Customer Acquisition Cost',
        'cac': 'Customer Acquisition Cost',
        'churn rate': 'Churn Rate',
        'retention rate': 'Retention Rate',
        'net retention rate': 'Net Retention Rate',
        'gross retention rate': 'Gross Retention Rate',
        'dollar based net retention': 'Dollar-Based Net Retention',
        'net dollar retention': 'Dollar-Based Net Retention',
        'ndr': 'Dollar-Based Net Retention',
        'average selling price': 'Average Selling Price',
        'asp': 'Average Selling Price',
        'average revenue per user': 'Average Revenue Per User',
        'arpu': 'Average Revenue Per User',
        'average revenue per customer': 'Average Revenue Per Customer',
        'arpc': 'Average Revenue Per Customer',
    }
    
    standardized_df = df.copy()
    
    for idx, row in df.iterrows():
        original_metric = str(row.get('metric', '')).strip()
        
        # Clean up the metric name
        cleaned_metric = original_metric.lower()
        
        # Remove common prefixes/suffixes that add noise
        cleaned_metric = re.sub(r'\b(gaap|non-gaap|adjusted|diluted|basic)\s+', '', cleaned_metric)
        cleaned_metric = re.sub(r'\s+(gaap|non-gaap|adjusted|diluted|basic)\b', '', cleaned_metric)
        
        # Remove parenthetical content that's not GAAP/Non-GAAP
        cleaned_metric = re.sub(r'\([^)]*\)', '', cleaned_metric)
        cleaned_metric = cleaned_metric.strip()
        
        # Apply standardization
        standardized_metric = metric_mappings.get(cleaned_metric, original_metric)
        
        # Preserve GAAP/Non-GAAP distinctions from original
        if 'non-gaap' in original_metric.lower():
            if '(Non-GAAP)' not in standardized_metric:
                standardized_metric += ' (Non-GAAP)'
        elif 'gaap' in original_metric.lower() and 'non-gaap' not in original_metric.lower():
            if '(GAAP)' not in standardized_metric:
                standardized_metric += ' (GAAP)'
        
        # Preserve adjusted distinction
        if 'adjusted' in original_metric.lower() and '(Adjusted)' not in standardized_metric:
            standardized_metric += ' (Adjusted)'
        
        standardized_df.at[idx, 'metric'] = standardized_metric
    
    return standardized_df

def format_guidance_values(df):
    """Replace NULL values with value_or_range text - never show NULL"""
    formatted_df = df.copy()
    for idx, row in df.iterrows():
        value_text = str(row.get('value_or_range', ''))
        
        for col in ['low', 'high', 'average']:
            if col in df.columns:
                cell_value = row.get(col)
                # Replace NULL/None values with value_or_range text
                if pd.isnull(cell_value) or str(cell_value).strip().upper() in ['N/A', 'NA', 'NULL', 'TBD', '', '-', 'NONE']:
                    formatted_df.at[idx, col] = value_text
    
    return formatted_df

def process_guidance_table(table_text, source_type="SEC"):
    """Process guidance table text into DataFrame"""
    if not table_text or "|" not in table_text:
        return None
    
    try:
        rows = [r.strip().split("|")[1:-1] for r in table_text.strip().split("\n") if "|" in r]
        if len(rows) <= 1:
            return None
            
        column_names = [c.strip().lower().replace(' ', '_') for c in rows[0]]
        df = pd.DataFrame(rows[1:], columns=column_names)
        
        # Standardize metric names first
        df = standardize_metric_names(df)
        
        # Format values
        df = format_guidance_values(df)
        
        # Check if format_guidance_values returned None
        if df is None:
            return None
        
        # Split GAAP/non-GAAP if needed
        if 'value_or_range' in df.columns:
            df = split_gaap_non_gaap(df.rename(columns={'value_or_range': 'Value or range'}))
            if 'Value or range' in df.columns:
                df.rename(columns={'Value or range': 'value_or_range'}, inplace=True)
        
        # Add source type
        df["source_type"] = source_type
        
        return df
        
    except Exception as e:
        st.warning(f"Error processing guidance table: {str(e)}")
        return None
