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

Create a `.env` file with the following variables:

```env
OPENAI_API_KEY=your_openai_api_key_here
SUPABASE_URL=your_supabase_url_here
SUPABASE_KEY=your_supabase_key_here
```

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
