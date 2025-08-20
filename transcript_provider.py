import os
import sys
import streamlit as st
from dotenv import load_dotenv

# Fix Unicode encoding issue on Windows by redirecting stdout temporarily
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
                    metadata = {
                        'quarter': f"Q{quarter_int}",
                        'year': year_int,
                        'company': ticker.upper(),
                        'report_date': matching_transcript['report_date'].iloc[0]
                    }
                
                return transcript_text.strip(), None, metadata
                
            except ValueError as e:
                return None, str(e), None
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
            
            metadata = {
                'quarter': f"Q{latest_quarter}",
                'year': latest_year,
                'company': ticker.upper(),
                'report_date': latest['report_date']
            }
            
            return transcript_text.strip(), None, metadata
            
    except Exception as e:
        return None, f"Error fetching transcript with defeatbeta-api: {str(e)}", None

# Legacy function for backward compatibility - now uses defeatbeta-api only
def fetch_transcript_apininjas(ticker, year=None, quarter=None):
    """Legacy function - now uses defeatbeta-api only"""
    return fetch_transcript_defeatbeta(ticker, year, quarter)

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
            return transcript, None
        else:
            st.warning(f"No transcript found for {ticker} {quarter_str} {year_num}: {error}")
            return None, error
    else:
        # Most recent transcript (no specific quarter/year)
        transcript, error, metadata = fetch_transcript_defeatbeta(ticker, None, None)
        
        if transcript:
            st.success(f"Found most recent transcript for {ticker}")
            st.write(f"Transcript length: {len(transcript):,} characters")
            if metadata:
                st.write(f"Metadata: {metadata}")
            return transcript, None
        else:
            st.warning(f"No transcript found for {ticker}: {error}")
            return None, error
