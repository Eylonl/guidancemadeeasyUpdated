import streamlit as st
import pandas as pd
from typing import List, Dict, Tuple

def detect_duplicates(df: pd.DataFrame) -> List[int]:
    """
    Detect duplicate guidance entries with same metric, period, and filing_date but different low/high values
    Returns list of row indices that are duplicates (to be highlighted)
    """
    if df.empty:
        return []
    
    duplicate_indices = []
    
    # Group by metric, period, and filing_date to properly identify duplicates
    grouping_cols = ['metric', 'period', 'filing_date']
    
    # Check if all required columns exist
    if not all(col in df.columns for col in grouping_cols):
        return []
    
    # Clean whitespace in grouping columns to catch duplicates with spacing differences
    df_clean = df.copy()
    for col in grouping_cols:
        if col in df_clean.columns:
            df_clean[col] = df_clean[col].astype(str).str.strip()
    
    grouped = df_clean.groupby(grouping_cols)
    
    for group_key, group_df in grouped:
        if len(group_df) > 1:
            # Check if low/high values are actually different
            low_values = group_df['low'].unique()
            high_values = group_df['high'].unique()
            
            # Only flag as duplicates if values are truly different
            # Remove NaN values for comparison
            low_values_clean = [v for v in low_values if pd.notna(v)]
            high_values_clean = [v for v in high_values if pd.notna(v)]
            
            if len(low_values_clean) > 1 or len(high_values_clean) > 1:
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
