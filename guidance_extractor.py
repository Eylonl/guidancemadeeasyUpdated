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

- metric (STANDARDIZE metric names to clean, consistent formats while preserving business segments and GAAP/Non-GAAP distinctions. Examples: "FY '26 subscription revenue" becomes "Subscription Revenue", "Q1 FY '26 non-GAAP EPS" becomes "EPS (Non-GAAP)", "Productivity and Business Processes revenue" stays "Productivity and Business Processes Revenue", "Azure revenue" stays "Azure Revenue". Remove time period prefixes (FY '26, Q1, etc.) but keep segment names and accounting standards. Add (GAAP) or (Non-GAAP) suffixes where applicable. Use proper capitalization.)
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

MANDATORY: If the value_or_range column contains a % symbol, you MUST include the % symbol in low, high, and average columns.

- For percentage guidance: ALWAYS include % symbol in all numeric columns
  Example: "25.0%" → low=25.0%, high=25.0%, average=25.0%
  Example: "5% to 7%" → low=5%, high=7%, average=6%
- For dollar amounts: provide numeric values without $ signs, convert billions to millions
  Example: "$7.7 billion" → low=7700, high=7700, average=7700
  Example: "$0.05 to $0.10" → low=0.05, high=0.10, average=0.075
- Use negative numbers for negative values: -1 instead of "(1)" and -5% instead of "(5%)"
- For mixed sign ranges like "$(1) million to $1 million", make sure low is negative (-1) and high is positive (1)

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

- metric (STANDARDIZE metric names to clean, consistent formats while preserving business segments and GAAP/Non-GAAP distinctions. Examples: "FY '26 subscription revenue" becomes "Subscription Revenue", "Q1 FY '26 non-GAAP EPS" becomes "EPS (Non-GAAP)", "Productivity and Business Processes revenue" stays "Productivity and Business Processes Revenue", "Azure revenue" stays "Azure Revenue". Remove time period prefixes (FY '26, Q1, etc.) but keep segment names and accounting standards. Add (GAAP) or (Non-GAAP) suffixes where applicable. Use proper capitalization.)
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

MANDATORY: If the value_or_range column contains a % symbol, you MUST include the % symbol in low, high, and average columns.

- For percentage guidance: ALWAYS include % symbol in all numeric columns
  Example: "25.0%" → low=25.0%, high=25.0%, average=25.0%
  Example: "5% to 7%" → low=5%, high=7%, average=6%
- For dollar amounts: provide numeric values without $ signs, convert billions to millions
  Example: "$7.7 billion" → low=7700, high=7700, average=7700
  Example: "$0.05 to $0.10" → low=0.05, high=0.10, average=0.075
- Use negative numbers for negative values: -1 instead of "(1)" and -5% instead of "(5%)"
- For mixed sign ranges like "$(1) million to $1 million", make sure low is negative (-1) and high is positive (1)

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

def standardize_metric_names(df, client=None, model_name="gpt-4o-mini"):
    """Use ChatGPT to apply regex-based metric standardization"""
    if 'metric' not in df.columns or df.empty:
        return df
    
    # Get unique metrics to standardize
    unique_metrics = df['metric'].unique().tolist()
    
    if not unique_metrics:
        return df
    
    # Create prompt with regex patterns for ChatGPT to apply
    metrics_text = "\n".join([f"- {metric}" for metric in unique_metrics])
    
    prompt = f"""Apply the following standardization rules to these metric names:

METRICS TO STANDARDIZE:
{metrics_text}

STANDARDIZATION RULES TO APPLY:

1. Remove time period prefixes using these patterns:
   - Remove: FY '26, Q1 FY '26, Q2 FY '25, etc. (pattern: \\b(fy|q[1-4])\\s*[\\'\']?\\d{{2,4}}\\s*)
   - Remove: full year 2024, quarter 2025, fiscal year 2026, etc. (pattern: \\b(full\\s+year|quarter|fiscal\\s+year)\\s*\\d{{2,4}}\\s*)

2. Remove common prefixes/suffixes that add noise:
   - Remove: gaap, non-gaap, adjusted, diluted, basic when they appear as prefixes/suffixes
   - Pattern: \\b(gaap|non-gaap|adjusted|diluted|basic)\\s+ and \\s+(gaap|non-gaap|adjusted|diluted|basic)\\b

3. Remove parenthetical content that's not GAAP/Non-GAAP:
   - Pattern: \\([^)]*\\) but preserve (GAAP), (Non-GAAP), (Adjusted)

4. Apply these standardized mappings where applicable:
   - revenue/revenues/total revenue → Revenue
   - eps/earnings per share → EPS  
   - net income/net earnings → Net Income
   - ebitda → EBITDA
   - cash flow → Cash Flow
   - operating cash flow → Operating Cash Flow
   - free cash flow → Free Cash Flow
   - gross margin → Gross Margin
   - capex/capital expenditures → CapEx
   - subscription revenue → Subscription Revenue
   - product revenue → Product Revenue
   - service revenue → Service Revenue

5. Preserve GAAP/Non-GAAP distinctions:
   - If original contains "non-gaap" OR "adjusted", add "(Non-GAAP)" suffix (treat adjusted and non-GAAP as the same)
   - If original contains "gaap" but not "non-gaap" and not "adjusted", add "(GAAP)" suffix
   - NEVER use both (Non-GAAP) and (Adjusted) - they are the same thing

6. Use proper capitalization and preserve business segment names exactly.

Return ONLY a simple mapping in this format:
Original Metric → Standardized Metric
Original Metric → Standardized Metric
...

Do not include any other text or explanations."""

    try:
        import streamlit as st
        
        # Use provided client or fall back to creating one
        if client is None:
            from openai import OpenAI
            client = OpenAI(api_key=st.secrets.get("OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY"))
        
        response = client.chat.completions.create(
            model=model_name,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
        )
        
        standardization_text = response.choices[0].message.content
        
        # Parse the response to create mapping
        standardization_map = {}
        for line in standardization_text.strip().split('\n'):
            if '→' in line:
                parts = line.split('→')
                if len(parts) == 2:
                    original = parts[0].strip()
                    standardized = parts[1].strip()
                    standardization_map[original] = standardized
        
        # Apply the standardization
        standardized_df = df.copy()
        for idx, row in df.iterrows():
            original_metric = str(row.get('metric', '')).strip()
            if original_metric in standardization_map:
                standardized_df.at[idx, 'metric'] = standardization_map[original_metric]
        
        return standardized_df
        
    except Exception as e:
        st.warning(f"Error in ChatGPT metric standardization: {str(e)}")
        return df

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

def process_guidance_table(table_text, source_type="SEC", client=None, model_name="gpt-4o-mini"):
    """Process guidance table text into DataFrame"""
    if not table_text or "|" not in table_text:
        return None
    
    try:
        rows = [r.strip().split("|")[1:-1] for r in table_text.strip().split("\n") if "|" in r]
        if len(rows) <= 1:
            return None
            
        column_names = [c.strip().lower().replace(' ', '_') for c in rows[0]]
        df = pd.DataFrame(rows[1:], columns=column_names)
        
        # Standardize metric names first - pass client and model_name
        df = standardize_metric_names(df, client, model_name)
        
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
