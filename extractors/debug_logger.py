"""
Debug logging module for extractors
"""
import streamlit as st

def log_fiscal_info(fiscal_year_end_month, fiscal_year_end_day, quarter_num, quarters):
    """Log fiscal year information"""
    st.write(f"Fiscal year ends in {fiscal_year_end_month} {fiscal_year_end_day}")
    st.write(f"Quarter {quarter_num} spans: {quarters[quarter_num]['start_month']}-{quarters[quarter_num]['end_month']}")
    st.write("All quarters for this fiscal pattern:")
    for q, q_info in quarters.items():
        st.write(f"Q{q}: {q_info['start_month']}-{q_info['end_month']}")

def log_filing_search(ticker, fiscal_info, start_date, end_date):
    """Log filing search parameters"""
    st.write(f"Looking for {ticker} {fiscal_info['quarter_period']} filings")
    st.write(f"Fiscal quarter period: {fiscal_info['period_description']}")
    st.write(f"Expected earnings reporting window: {fiscal_info['expected_report']}")
    st.write(f"Searching for filings between: {start_date.strftime('%Y-%m-%d')} and {end_date.strftime('%Y-%m-%d')}")

def log_filing_found(date_str, accession):
    """Log when a filing is found"""
    st.write(f"Found filing from {date_str}: {accession}")

def log_filings_summary(accessions_count):
    """Log summary of filings found"""
    st.write(f"Found {accessions_count} relevant 8-K filings")

def log_years_back_search(years_back, cutoff_date):
    """Log years back search parameters"""
    st.write(f"Looking for filings from the past {years_back} years plus 1 quarter (from {cutoff_date} to present)")

def log_auto_detect_quarter(quarter_num, year_num):
    """Log auto-detected quarter"""
    st.write(f"Auto-detecting most recent quarter: Q{quarter_num} {year_num}")

def log_available_dates(available_dates):
    """Log available filing dates"""
    st.write("All available 8-K filing dates:")
    for date in available_dates[:15]:
        st.write(f"- {date}")
    if len(available_dates) > 15:
        st.write(f"... and {len(available_dates) - 15} more")

def log_skipped_file(url, reason=""):
    """Log skipped files"""
    if reason:
        st.write(f"Skipped {reason}: {url}")
    else:
        st.write(f"Skipped: {url}")

def log_validated_earnings(url):
    """Log validated earnings release"""
    st.write(f"✅ Validated earnings release: {url}")

def log_skipped_non_earnings(url):
    """Log skipped non-earnings filing"""
    st.write(f"⏭️ Skipped non-earnings 8-K: {url}")

def log_processing_error(accession, error):
    """Log processing errors"""
    st.write(f"Error processing accession {accession}: {str(error)}")

def log_validation_error(url, error):
    """Log validation errors"""
    st.write(f"Error validating earnings release {url}: {str(error)}")
