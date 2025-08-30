import streamlit as st
import sys
import io
import requests
import re
from datetime import datetime

# Null writer to suppress stdout during imports
class NullWriter:
    def write(self, txt): pass
    def flush(self): pass

# Temporarily suppress stdout to avoid Unicode issues during import
original_stdout = sys.stdout
try:
    sys.stdout = NullWriter()
    from defeatbeta_api.data.ticker import Ticker
    from defeatbeta_api.client.duckdb_conf import Configuration
finally:
    sys.stdout = original_stdout

def fetch_transcript_apininjas(ticker, year=None, quarter=None):
    """Fetch earnings transcript using APINinjas API as fallback"""
    try:
        # Get API key from Streamlit secrets
        api_key = st.secrets.get("APININJAS_API_KEY")
        if not api_key:
            return None, "APINinjas API key not found in secrets", None
        
        # Format the query
        if year and quarter:
            # Convert quarter format
            quarter_num = quarter.replace("Q", "") if quarter.startswith("Q") else quarter
            query = f"{ticker} Q{quarter_num} {year} earnings call transcript"
        else:
            query = f"{ticker} earnings call transcript"
        
        # APINinjas API endpoint
        url = "https://api.api-ninjas.com/v1/earningstranscript"
        headers = {
            'X-Api-Key': api_key
        }
        params = {
            'ticker': ticker.upper()
        }
        
        response = requests.get(url, headers=headers, params=params, timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            if data and 'transcript' in data:
                transcript_text = data['transcript']
                
                # Extract actual quarter/year from transcript content if possible
                actual_quarter = quarter
                actual_year = year
                
                # Try to extract actual reporting period and earnings date from transcript
                earnings_date = None
                if transcript_text:
                    # Look for fiscal year patterns in the transcript
                    fy_match = re.search(r'fiscal (\d{4})', transcript_text.lower())
                    quarter_match = re.search(r'(first|second|third|fourth|q[1-4])\s+quarter', transcript_text.lower())
                    
                    # Try to extract earnings call date from transcript
                    # Common patterns for earnings call dates
                    date_patterns = [
                        r'(\w+\s+\d{1,2},\s+\d{4})',  # "January 25, 2024"
                        r'(\d{1,2}/\d{1,2}/\d{4})',   # "1/25/2024"
                        r'(\d{4}-\d{2}-\d{2})',       # "2024-01-25"
                        r'((?:january|february|march|april|may|june|july|august|september|october|november|december)\s+\d{1,2},?\s+\d{4})'  # case insensitive month names
                    ]
                    
                    # Look for date patterns in the first 1000 characters (header area)
                    header_text = transcript_text[:1000].lower()
                    for pattern in date_patterns:
                        date_match = re.search(pattern, header_text, re.IGNORECASE)
                        if date_match:
                            try:
                                date_str = date_match.group(1)
                                # Try to parse the date
                                if '/' in date_str:
                                    earnings_date = datetime.strptime(date_str, '%m/%d/%Y').strftime('%Y-%m-%d')
                                elif '-' in date_str:
                                    earnings_date = date_str
                                else:
                                    # Handle month name formats
                                    earnings_date = datetime.strptime(date_str, '%B %d, %Y').strftime('%Y-%m-%d')
                                break
                            except:
                                continue
                    
                    if fy_match:
                        extracted_year = int(fy_match.group(1))
                        # If extracted year is in the future, it's likely wrong
                        current_year = datetime.now().year
                        if extracted_year > current_year + 1:
                            actual_year = current_year
                        else:
                            actual_year = extracted_year
                    
                    if quarter_match:
                        quarter_text = quarter_match.group(1).lower()
                        if quarter_text in ['first', 'q1']:
                            actual_quarter = 'Q1'
                        elif quarter_text in ['second', 'q2']:
                            actual_quarter = 'Q2'
                        elif quarter_text in ['third', 'q3']:
                            actual_quarter = 'Q3'
                        elif quarter_text in ['fourth', 'q4']:
                            actual_quarter = 'Q4'
                
                # Validate the year - don't allow future years beyond next year
                current_year = datetime.now().year
                if actual_year and actual_year > current_year + 1:
                    actual_year = current_year
                
                # Create metadata with validated data
                metadata = {
                    'quarter': actual_quarter or 'Latest',
                    'year': actual_year or current_year,
                    'company': ticker.upper(),
                    'source': 'APINinjas',
                    'earnings_date': earnings_date
                }
                
                return transcript_text, None, metadata
            else:
                return None, f"No transcript data returned from APINinjas for {ticker}", None
        else:
            return None, f"APINinjas API error: {response.status_code}", None
            
    except Exception as e:
        return None, f"APINinjas error: {str(e)}", None

# No longer using .env file - using Streamlit secrets instead

def fetch_transcript_defeatbeta(ticker, year=None, quarter=None):
    """Fetch earnings transcript using defeatbeta-api only"""
    try:
        # Initialize the ticker (will work in Linux cloud environment)
        db_ticker = Ticker(ticker)
        
        # Get transcripts object
        transcripts = db_ticker.earning_call_transcripts()
        
        if year and quarter:
            # Convert quarter format from "Q1" to "1" if provided
            quarter_num = quarter.replace("Q", "") if quarter.startswith("Q") else quarter
            try:
                quarter_int = int(quarter_num)
                year_int = int(year)
            except ValueError:
                return None, f"Invalid quarter/year format: {quarter}/{year}", None
            
            # Get specific transcript
            try:
                transcript_df = transcripts.get_transcript(year_int, quarter_int)
                
                # Convert structured data to text format
                transcript_text = ""
                for _, row in transcript_df.iterrows():
                    speaker = row.get('speaker', 'Unknown')
                    content = row.get('content', '')
                    transcript_text += f"{speaker}: {content}\n\n"
                
                # Get metadata from transcripts list
                transcripts_list = transcripts.get_transcripts_list()
                matching_transcript = transcripts_list[
                    (transcripts_list['fiscal_year'] == year_int) & 
                    (transcripts_list['fiscal_quarter'] == quarter_int)
                ]
                
                metadata = {}
                if not matching_transcript.empty:
                    report_date = matching_transcript['report_date'].iloc[0]
                    # Ensure the date is in string format for consistency
                    if hasattr(report_date, 'strftime'):
                        earnings_date_str = report_date.strftime('%Y-%m-%d')
                    else:
                        earnings_date_str = str(report_date)
                    
                    metadata = {
                        'quarter': f"Q{quarter_int}",
                        'year': year_int,
                        'company': ticker.upper(),
                        'report_date': report_date,
                        'earnings_date': earnings_date_str
                    }
                
                return transcript_text.strip(), None, metadata
                
            except ValueError as e:
                # Try APINinjas as fallback
                st.write("DefeatBeta API failed, trying APINinjas fallback...")
                return fetch_transcript_apininjas(ticker, year, quarter)
        else:
            # Get most recent transcript
            transcripts_list = transcripts.get_transcripts_list()
            if transcripts_list.empty:
                return None, f"No transcripts found for {ticker}", None
            
            # Get the most recent transcript (last row)
            latest = transcripts_list.iloc[-1]
            latest_year = latest['fiscal_year']
            latest_quarter = latest['fiscal_quarter']
            
            transcript_df = transcripts.get_transcript(latest_year, latest_quarter)
            
            # Convert structured data to text format
            transcript_text = ""
            for _, row in transcript_df.iterrows():
                speaker = row.get('speaker', 'Unknown')
                content = row.get('content', '')
                transcript_text += f"{speaker}: {content}\n\n"
            
            report_date = latest['report_date']
            # Ensure the date is in string format for consistency
            if hasattr(report_date, 'strftime'):
                earnings_date_str = report_date.strftime('%Y-%m-%d')
            else:
                earnings_date_str = str(report_date)
            
            metadata = {
                'quarter': f"Q{latest_quarter}",
                'year': latest_year,
                'company': ticker.upper(),
                'report_date': report_date,
                'earnings_date': earnings_date_str
            }
            
            return transcript_text.strip(), None, metadata
            
    except Exception as e:
        # Try APINinjas as fallback when DefeatBeta fails completely
        st.write("DefeatBeta API unavailable, trying APINinjas fallback...")
        return fetch_transcript_apininjas(ticker, year, quarter)

# This function is now defined above as the actual APINinjas implementation

def get_transcript_for_quarter(ticker, quarter_num, year_num):
    """Get transcript for a specific quarter and year"""
    if quarter_num and year_num:
        quarter_str = f"Q{quarter_num}"
        transcript, error, metadata = fetch_transcript_defeatbeta(ticker, year_num, quarter_str)
        
        if transcript:
            st.success(f"Found transcript for {ticker} {quarter_str} {year_num}")
            st.write(f"Transcript length: {len(transcript):,} characters")
            if metadata:
                st.write(f"Metadata: {metadata}")
            return transcript, None, metadata
        else:
            st.warning(f"No transcript found for {ticker} {quarter_str} {year_num}: {error}")
            return None, error, None
    else:
        # Most recent transcript (no specific quarter/year)
        transcript, error, metadata = fetch_transcript_defeatbeta(ticker, None, None)
        
        if transcript:
            st.success(f"Found most recent transcript for {ticker}")
            st.write(f"Transcript length: {len(transcript):,} characters")
            if metadata:
                st.write(f"Metadata: {metadata}")
            return transcript, None, metadata
        else:
            st.warning(f"No transcript found for {ticker}: {error}")
            return None, error, None
