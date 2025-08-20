# Enhanced Financial Analysis App

A powerful Streamlit application for financial analysis with earnings transcript processing, document analysis, and AI-powered insights.

## Features

- **Earnings Transcript Analysis**: Fetch and analyze earnings call transcripts using defeatbeta-api
- **Document Processing**: Upload and analyze financial documents (PDF, TXT)
- **AI-Powered Insights**: Generate summaries and extract key information using OpenAI
- **Data Storage**: Persistent storage with Supabase integration
- **Interactive UI**: Clean, modern Streamlit interface

## Technology Stack

- **Frontend**: Streamlit
- **Data Source**: defeatbeta-api (Hugging Face datasets)
- **AI**: OpenAI GPT models
- **Database**: Supabase
- **Deployment**: Streamlit Community Cloud

## Environment Variables

Add these to your Streamlit Cloud secrets or local `.env` file:

```
OPENAI_API_KEY=your_openai_api_key_here
APP_PASSWORD=your_secure_password_here
SUPABASE_URL=your_supabase_url_here
SUPABASE_SERVICE_ROLE_KEY=your_supabase_service_role_key_here
SUPABASE_BUCKET=documents
SEC_USER_AGENT=EarningsExtractor/1.0 (+contact: your_email@domain.com)
```

### API Key Security

The app now includes password protection for the hosted OpenAI API key:

- **Option 1**: Enter the app password to use the hosted OpenAI key
- **Option 2**: Check "Use my own OpenAI API key" and enter your own key

This prevents unauthorized usage of your OpenAI credits while still allowing legitimate users access.

## Local Development

1. Clone the repository
2. Install dependencies: `pip install -r requirements.txt`
3. Set up environment variables in `.env` file
4. Run the app: `streamlit run streamlit_app_enhanced.py`

## Cloud Deployment

This app is deployed on Streamlit Community Cloud and automatically syncs with GitHub commits.

### Deployment URL
[Your app will be available here after deployment]

## Usage

1. **Transcript Analysis**: Enter a stock ticker to fetch earnings transcripts
2. **Document Upload**: Upload financial documents for analysis
3. **AI Analysis**: Get AI-powered insights and summaries
4. **Data Export**: Download results in various formats

## Requirements

- Python 3.8+
- OpenAI API key
- Supabase account (for data storage)

## License

MIT License
