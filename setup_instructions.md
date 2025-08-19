# Enhanced SEC 8-K & Transcript Guidance Extractor

## Setup Instructions

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure Environment Variables
Edit the `.env` file and add your API keys:

```
# OpenAI Configuration
OPENAI_API_KEY=your_actual_openai_api_key_here

# APINinjas Configuration  
APININJAS_API_KEY=your_actual_apininjas_api_key_here
APININJAS_TRANSCRIPTS_ENDPOINT=https://api.api-ninjas.com/v1/earningstranscript

# SEC Configuration
SEC_USER_AGENT=EarningsExtractor/1.0 (+contact: your_email@domain.com)
```

### 3. Run the Application
```bash
streamlit run streamlit_app_enhanced.py
```

## Features

### ✅ From Original Code (Preserved)
- **Accurate SEC EDGAR extraction** with proper fiscal year calculations
- **Excel output** with formatted guidance data
- **Robust CIK/ticker lookup** and validation
- **Enhanced exhibit 99.1 finding** with multiple fallback patterns
- **Smart guidance paragraph detection** 
- **GAAP/non-GAAP splitting** functionality

### ✅ From New Code (Added)
- **Environment variable support** (.env file instead of UI input)
- **APINinjas transcript integration** for earnings call data
- **Modular architecture** with separate components
- **Enhanced error handling** and user feedback

### 🚀 New Enhancements
- **Dual-source guidance extraction** (SEC + Transcripts)
- **Source attribution** in results
- **Combined Excel output** with both SEC and transcript guidance
- **Modern UI** with progress indicators and better organization
- **Flexible model selection** including GPT-4o Mini for cost efficiency

## File Structure
- `streamlit_app_enhanced.py` - Main application
- `edgar_enhanced.py` - SEC EDGAR logic (from original)
- `transcript_provider.py` - APINinjas integration
- `guidance_extractor.py` - AI guidance extraction
- `requirements.txt` - Dependencies
- `.env` - Environment variables (configure with your keys)

## Usage
1. Enter a ticker symbol or CIK
2. Select data sources (SEC 8-K filings and/or transcripts)
3. Choose time period (years back or specific quarter)
4. Click "Extract Guidance"
5. Download results as Excel file
