import streamlit as st
import pandas as pd
from typing import List, Dict, Tuple

def detect_duplicates(df: pd.DataFrame) -> List[int]:
    """
    Detect duplicate guidance entries with same metric and period but different low/high values
    Only flags as duplicates when low/high values are DIFFERENT between SEC and transcript guidance
    Returns list of row indices that are duplicates (to be highlighted)
    """
    if df.empty:
        return []
    
    duplicate_indices = []
    
    # Group by metric and period to identify potential duplicates
    grouping_cols = ['metric', 'period']
    
    # Check if all required columns exist
    if not all(col in df.columns for col in grouping_cols):
        return []
    
    # Also need low, high, and source_type columns
    required_cols = grouping_cols + ['low', 'high', 'source_type']
    if not all(col in df.columns for col in required_cols):
        return []
    
    # Clean whitespace in grouping columns to catch duplicates with spacing differences
    df_clean = df.copy()
    for col in grouping_cols:
        if col in df_clean.columns:
            df_clean[col] = df_clean[col].astype(str).str.strip()
    
    grouped = df_clean.groupby(grouping_cols)
    
    for group_key, group_df in grouped:
        if len(group_df) > 1:
            # Check if we have both SEC and Transcript sources
            sources = group_df['source_type'].unique()
            if len(sources) > 1 and any('SEC' in str(s) for s in sources) and any('Transcript' in str(s) for s in sources):
                # Check if low/high values are different between sources
                low_values = group_df['low'].unique()
                high_values = group_df['high'].unique()
                
                # Only flag as duplicates if the low/high values are DIFFERENT
                if len(low_values) > 1 or len(high_values) > 1:
                    # Add all indices in this duplicate group to the list
                    original_indices = df.loc[group_df.index].index.tolist()
                    duplicate_indices.extend(original_indices)
    
    return duplicate_indices

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
