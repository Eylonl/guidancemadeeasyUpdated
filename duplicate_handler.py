import streamlit as st
import pandas as pd
from typing import List, Dict, Tuple

def detect_duplicates(df: pd.DataFrame, client=None, model_name="gpt-4o") -> List[int]:
    """
    Use ChatGPT to detect duplicate guidance entries that represent conflicting information
    Returns list of row indices that are duplicates (to be highlighted)
    """
    if df.empty or client is None:
        return []
    
    # Convert DataFrame to a readable format for ChatGPT
    df_text = df.to_string(index=True)
    
    prompt = f"""You are analyzing financial guidance data to identify true duplicates that represent conflicting information.

Here is the guidance data:
{df_text}

RULES FOR IDENTIFYING DUPLICATES:
1. Only flag entries as duplicates if they have the SAME metric, period, and represent CONFLICTING values
2. Do NOT flag entries as duplicates if they have identical values (e.g., 28.0% and 28% are the same)
3. Do NOT flag entries as duplicates if they are from the same source and date
4. Only flag when there are genuinely different guidance values for the same metric and period

Return ONLY a Python list of row indices (numbers) that should be highlighted as duplicates.
If no true duplicates exist, return an empty list: []

Example response format: [5, 12, 15] or []"""

    try:
        response = client.chat.completions.create(
            model=model_name,
            messages=[{"role": "user", "content": prompt}],
            temperature=0
        )
        
        result_text = response.choices[0].message.content.strip()
        
        # Parse the response to extract indices
        import ast
        try:
            duplicate_indices = ast.literal_eval(result_text)
            if isinstance(duplicate_indices, list):
                return duplicate_indices
        except:
            pass
            
        return []
        
    except Exception as e:
        print(f"Error in ChatGPT duplicate detection: {e}")
        return []

def highlight_duplicates(df: pd.DataFrame, duplicate_indices: List[int]) -> pd.DataFrame:
    """
    Apply yellow highlighting to duplicate rows in the DataFrame for Streamlit
    Returns styled DataFrame with duplicates highlighted
    """
    if not duplicate_indices or df.empty:
        return df
    
    def highlight_row(row):
        if row.name in duplicate_indices:
            return ['background-color: yellow'] * len(row)
        else:
            return [''] * len(row)
    
    return df.style.apply(highlight_row, axis=1)

def reset_duplicate_state():
    """Reset duplicate resolution session state"""
    if 'duplicate_selections' in st.session_state:
        del st.session_state.duplicate_selections
    if 'duplicate_resolved' in st.session_state:
        del st.session_state.duplicate_resolved
    if 'duplicate_resolution_complete' in st.session_state:
        del st.session_state.duplicate_resolution_complete
    if 'cleaned_guidance_data' in st.session_state:
        del st.session_state.cleaned_guidance_data
    if 'removed_count' in st.session_state:
        del st.session_state.removed_count
