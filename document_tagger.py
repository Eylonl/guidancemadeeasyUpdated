import re
import os
from typing import Dict, Optional, Tuple
from openai import OpenAI
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def extract_text_from_file(file_data: bytes, file_type: str) -> str:
    """Extract text content from uploaded file based on file type"""
    try:
        if file_type in ['txt', 'html']:
            if isinstance(file_data, bytes):
                return file_data.decode('utf-8')
            elif isinstance(file_data, str):
                return file_data
            else:
                return str(file_data) if file_data else ""
        elif file_type == 'pdf':
            # Extract text from PDF using PyPDF2
            try:
                import PyPDF2
                import io
                
                if not isinstance(file_data, bytes):
                    return f"Invalid PDF data type: {type(file_data)}"
                
                pdf_reader = PyPDF2.PdfReader(io.BytesIO(file_data))
                text = ""
                for page in pdf_reader.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text + "\n"
                return text.strip() if text.strip() else "No text found in PDF"
            except ImportError:
                # Fallback: try pdfplumber if PyPDF2 not available
                try:
                    import pdfplumber
                    import io
                    
                    if not isinstance(file_data, bytes):
                        return f"Invalid PDF data type: {type(file_data)}"
                    
                    with pdfplumber.open(io.BytesIO(file_data)) as pdf:
                        text = ""
                        for page in pdf.pages:
                            page_text = page.extract_text()
                            if page_text:
                                text += page_text + "\n"
                    return text.strip() if text.strip() else "No text found in PDF"
                except ImportError:
                    # If neither library is available, return placeholder
                    return "PDF text extraction not available - please install PyPDF2 or pdfplumber"
        else:
            return f"Unsupported file type: {file_type}"
    except Exception as e:
        return f"Error extracting text: {str(e)}"

def extract_document_metadata(content: str, filename: str, client: OpenAI) -> Dict[str, Optional[str]]:
    """
    Use AI to extract ticker, year, quarter, and document type from document content
    Uses progressive analysis - tries 1000 chars first, then expands if needed
    """
    
    # First try regex patterns for quick extraction
    ticker_match = re.search(r'\b([A-Z]{1,5})\b(?:\s+(?:Inc|Corp|Corporation|Company|Ltd))?', content)
    year_match = re.search(r'\b(20\d{2})\b', content)
    quarter_match = re.search(r'\b(?:Q([1-4])|([1-4])Q|(?:first|second|third|fourth)\s+quarter)\b', content.lower())
    
    # Progressive content analysis - start with 1000 chars
    content_sample = content[:1000] if len(content) > 1000 else content
    
    prompt = f"""
Analyze this earnings document and extract the following metadata:

Document filename: {filename}
Document content sample:
{content_sample}

Please extract and return ONLY a JSON object with these fields:
{{
    "ticker": "stock ticker symbol (e.g., MSFT, AAPL)",
    "year": "4-digit year (e.g., 2024)",
    "quarter": "quarter in format Q1, Q2, Q3, or Q4",
    "document_type": "one of: presentation, prepared_remarks, transcript, earnings_release, or other"
}}

Rules:
- If you cannot determine a field with confidence, use null
- Ticker should be the stock symbol, not company name
- Year should be the reporting period year, not document creation year
- Quarter should be the financial quarter being reported
- Document type should reflect the content type

Return only the JSON object, no other text.
"""

    # Try AI analysis with progressive content sampling
    def try_ai_extraction(sample_content: str) -> Optional[Dict]:
        try:
            ai_prompt = f"""
Analyze this earnings document and extract the following metadata:

Document filename: {filename}
Document content sample:
{sample_content}

Please extract and return ONLY a JSON object with these fields:
{{
    "ticker": "stock ticker symbol (e.g., MSFT, AAPL)",
    "year": "4-digit year (e.g., 2024)",
    "quarter": "quarter in format Q1, Q2, Q3, or Q4",
    "document_type": "one of: presentation, prepared_remarks, transcript, earnings_release, or other"
}}

Rules:
- If you cannot determine a field with confidence, use null
- Ticker should be the stock symbol, not company name
- Year should be the reporting period year, not document creation year
- Quarter should be the financial quarter being reported
- Document type should reflect the content type

Return only the JSON object, no other text.
"""
            
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": ai_prompt}],
                temperature=0.1,
                max_tokens=200
            )
            
            result_text = response.choices[0].message.content.strip()
            
            # Try to parse JSON response
            import json
            metadata = json.loads(result_text)
            
            # Validate and clean the results
            ticker = metadata.get('ticker', '').upper() if metadata.get('ticker') else None
            year = metadata.get('year')
            quarter = metadata.get('quarter', '').upper() if metadata.get('quarter') else None
            doc_type = metadata.get('document_type', 'other')
            
            # Validate year format
            if year and not re.match(r'^20\d{2}$', str(year)):
                year = None
                
            # Validate quarter format
            if quarter and not re.match(r'^Q[1-4]$', quarter):
                quarter = None
                
            # Validate ticker (1-5 uppercase letters)
            if ticker and not re.match(r'^[A-Z]{1,5}$', ticker):
                ticker = None
                
            return {
                'ticker': ticker,
                'year': int(year) if year else None,
                'quarter': quarter,
                'document_type': doc_type
            }
            
        except Exception:
            return None
    
    # Progressive AI analysis: try 1000 chars first
    ai_result = try_ai_extraction(content_sample)
    
    # If AI extraction was successful and found most fields, return it
    if ai_result and ai_result.get('ticker') and ai_result.get('year') and ai_result.get('quarter'):
        return ai_result
    
    # If first attempt didn't find all fields and document is longer, try with more content
    if len(content) > 1000 and (not ai_result or not all([ai_result.get('ticker'), ai_result.get('year'), ai_result.get('quarter')])):
        extended_sample = content[:2500] if len(content) > 2500 else content
        extended_result = try_ai_extraction(extended_sample)
        
        # Use extended result if it found more fields
        if extended_result and sum(1 for v in [extended_result.get('ticker'), extended_result.get('year'), extended_result.get('quarter')] if v) > sum(1 for v in [ai_result.get('ticker'), ai_result.get('year'), ai_result.get('quarter')] if v):
            ai_result = extended_result
    
    # Return AI result if we got one, otherwise fall back to regex
    if ai_result:
        return ai_result
    
    # Fallback to regex patterns
    ticker = ticker_match.group(1) if ticker_match else None
    year = int(year_match.group(1)) if year_match else None
    
    if quarter_match:
        quarter_num = quarter_match.group(1) or quarter_match.group(2)
        quarter = f"Q{quarter_num}" if quarter_num else None
    else:
        quarter = None
    
    # Determine document type from filename and content
    doc_type = "other"
    filename_lower = filename.lower()
    content_lower = content.lower()
    
    if any(word in filename_lower for word in ['presentation', 'slides', 'deck']):
        doc_type = "presentation"
    elif any(word in filename_lower for word in ['prepared', 'remarks', 'script']):
        doc_type = "prepared_remarks"
    elif any(word in filename_lower for word in ['transcript', 'call']):
        doc_type = "transcript"
    elif any(word in content_lower for word in ['earnings call', 'conference call']):
        doc_type = "transcript"
    elif any(word in content_lower for word in ['earnings release', 'press release']):
        doc_type = "earnings_release"
    
    return {
        'ticker': ticker,
        'year': year,
        'quarter': quarter,
        'document_type': doc_type
    }

def validate_and_confirm_metadata(metadata: Dict, content_preview: str) -> Dict:
    """
    Validate extracted metadata and provide confidence scores
    """
    confidence = {
        'ticker': 0.0,
        'year': 0.0,
        'quarter': 0.0,
        'document_type': 0.0
    }
    
    # Calculate confidence scores based on pattern matching
    if metadata.get('ticker'):
        # Check if ticker appears multiple times in content
        ticker_count = len(re.findall(rf'\b{metadata["ticker"]}\b', content_preview, re.IGNORECASE))
        confidence['ticker'] = min(ticker_count * 0.2, 1.0)
    
    if metadata.get('year'):
        # Check if year appears in content
        year_count = len(re.findall(rf'\b{metadata["year"]}\b', content_preview))
        confidence['year'] = min(year_count * 0.3, 1.0)
    
    if metadata.get('quarter'):
        # Check if quarter appears in content
        quarter_patterns = [metadata['quarter'], metadata['quarter'].replace('Q', '')]
        quarter_found = any(pattern in content_preview for pattern in quarter_patterns)
        confidence['quarter'] = 0.8 if quarter_found else 0.3
    
    if metadata.get('document_type'):
        confidence['document_type'] = 0.7  # Base confidence for document type
    
    return {
        'metadata': metadata,
        'confidence': confidence,
        'overall_confidence': sum(confidence.values()) / len(confidence)
    }
