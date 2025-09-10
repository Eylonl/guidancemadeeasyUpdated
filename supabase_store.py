import hashlib
import os
from typing import Optional, List, Dict, Any
from supabase import create_client, Client
from dotenv import load_dotenv
import pathlib

def get_supabase_config():
    """Get Supabase configuration from Streamlit secrets"""
    import streamlit as st
    
    return {
        "url": st.secrets.get("SUPABASE_URL", ""),
        "key": st.secrets.get("SUPABASE_SERVICE_ROLE_KEY", ""),
        "bucket": st.secrets.get("SUPABASE_BUCKET", "documents")
    }

def get_client() -> Client:
    config = get_supabase_config()
    if not config["url"] or not config["key"]:
        raise RuntimeError("Missing SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY")
    return create_client(config["url"], config["key"])

def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()

def storage_path(kind: str, ticker: str, year: int, quarter: str, filename: str) -> str:
    # For uploads, use timestamp + filename to ensure uniqueness
    if kind == "uploads":
        import time
        timestamp = int(time.time() * 1000)  # milliseconds for uniqueness
        file_extension = filename.split('.')[-1].lower() if '.' in filename else 'txt'
        # Use original filename with timestamp prefix to maintain readability
        base_name = filename.rsplit('.', 1)[0] if '.' in filename else filename
        unique_filename = f"{timestamp}_{base_name}.{file_extension}"
        return f"{kind}/{ticker.upper()}/{year}-{quarter}/{unique_filename}"
    else:
        # For other kinds, use original filename
        return f"{kind}/{ticker.upper()}/{year}-{quarter}/{filename}"

def upload_bytes(path: str, data: bytes, content_type: str = "application/octet-stream") -> str:
    sb = get_client()
    config = get_supabase_config()
    
    # Validate input data type
    if not isinstance(data, bytes):
        raise RuntimeError(f"Expected bytes for upload data, got {type(data)}: {data}")
    
    # Use the bucket creation helper
    bucket_name = config["bucket"]
    if ensure_bucket_exists(bucket_name):
        try:
            # Use simple Supabase upload method (no upsert)
            result = sb.storage.from_(bucket_name).upload(path, data)
            return path
        except Exception as e:
            raise RuntimeError(f"Failed to upload to bucket '{bucket_name}': {str(e)}")
    
    # If primary bucket creation failed, try fallbacks
    fallback_buckets = ["documents", "files", "storage", "uploads"]
    for fallback_bucket in fallback_buckets:
        if ensure_bucket_exists(fallback_bucket):
            try:
                # Use simple Supabase upload method for fallback (no upsert)
                result = sb.storage.from_(fallback_bucket).upload(path, data)
                config["bucket"] = fallback_bucket
                return path
            except Exception:
                continue
    
    raise RuntimeError(f"Could not create or upload to any bucket. Tried: {[bucket_name] + fallback_buckets}")

def upsert_file_row(ticker: str, year: int, quarter: str, file_type: str, file_format: str,
                    storage_path: str, source_url: str, text_content: Optional[str],
                    sha256: str):
    sb = get_client()
    
    # Validate all parameters are correct types
    if not isinstance(ticker, str):
        raise RuntimeError(f"ticker must be string, got {type(ticker)}: {ticker}")
    if not isinstance(year, int):
        raise RuntimeError(f"year must be int, got {type(year)}: {year}")
    if not isinstance(quarter, str):
        raise RuntimeError(f"quarter must be string, got {type(quarter)}: {quarter}")
    if not isinstance(file_type, str):
        raise RuntimeError(f"file_type must be string, got {type(file_type)}: {file_type}")
    if not isinstance(file_format, str):
        raise RuntimeError(f"file_format must be string, got {type(file_format)}: {file_format}")
    if not isinstance(storage_path, str):
        raise RuntimeError(f"storage_path must be string, got {type(storage_path)}: {storage_path}")
    if not isinstance(source_url, str):
        raise RuntimeError(f"source_url must be string, got {type(source_url)}: {source_url}")
    if text_content is not None and not isinstance(text_content, str):
        raise RuntimeError(f"text_content must be string or None, got {type(text_content)}: {text_content}")
    
    payload = {
        "ticker": ticker.upper(),
        "year": year,
        "quarter": quarter,
        "file_type": file_type,
        "file_format": file_format,
        "storage_path": storage_path,
        "source_url": source_url,
        "text_content": text_content,
    }
    
    # Use simple insert since storage_path is now guaranteed unique with timestamp
    return sb.table("earnings_files").insert(payload).execute()

def already_ingested(ticker: str, year: int, quarter: str, file_type: str, file_format: str) -> bool:
    sb = get_client()
    q = sb.table("earnings_files").select("id").eq("ticker", ticker.upper()) \
        .eq("year", year).eq("quarter", quarter).eq("file_type", file_type).eq("file_format", file_format) \
        .limit(1).execute()
    return bool(q.data)

def get_uploaded_documents(ticker: str = None, year: int = None, quarter: str = None) -> List[Dict[str, Any]]:
    """Retrieve uploaded documents from Supabase with optional filtering"""
    sb = get_client()
    query = sb.table("earnings_files").select("*")
    
    if ticker:
        query = query.eq("ticker", ticker.upper())
    if year:
        query = query.eq("year", year)
    if quarter:
        query = query.eq("quarter", quarter)
    
    # Only get user-uploaded documents (including new timestamp-based file_types)
    query = query.like("file_type", "uploaded_document%")
    query = query.order("created_at", desc=True)
    
    result = query.execute()
    return result.data if result.data else []

def ensure_bucket_exists(bucket_name: str) -> bool:
    """Ensure a storage bucket exists, create if it doesn't"""
    sb = get_client()
    try:
        # Try to list files in bucket to check if it exists
        sb.storage.from_(bucket_name).list()
        return True
    except Exception:
        try:
            # Bucket doesn't exist, try to create it
            sb.storage.create_bucket(bucket_name, {"public": False})
            return True
        except Exception as e:
            print(f"Failed to create bucket {bucket_name}: {str(e)}")
            return False

def download_document(storage_path: str) -> bytes:
    """Download document content from Supabase storage"""
    sb = get_client()
    config = get_supabase_config()
    
    # Try to ensure the primary bucket exists
    bucket_name = config["bucket"]
    if ensure_bucket_exists(bucket_name):
        try:
            result = sb.storage.from_(bucket_name).download(storage_path)
            return result
        except Exception as e:
            # File might not exist in this bucket, but bucket exists
            raise RuntimeError(f"File not found in bucket '{bucket_name}': {storage_path}. Error: {str(e)}")
    
    # If primary bucket creation failed, try other common names
    fallback_buckets = ["earnings", "earnings-files", "documents", "files", "storage", "uploads"]
    
    for fallback_bucket in fallback_buckets:
        if ensure_bucket_exists(fallback_bucket):
            try:
                result = sb.storage.from_(fallback_bucket).download(storage_path)
                # Update config to use this working bucket
                config["bucket"] = fallback_bucket
                return result
            except Exception:
                continue
    
    # If all fails, raise comprehensive error
    raise RuntimeError(f"Could not create or access any storage bucket. Tried: {[bucket_name] + fallback_buckets}")

def delete_document(document_id: int, storage_path: str) -> bool:
    """Delete document from both Supabase storage and database"""
    sb = get_client()
    config = get_supabase_config()
    
    try:
        # Delete from storage
        sb.storage.from_(config["bucket"]).remove([storage_path])
        
        # Delete from database
        result = sb.table("earnings_files").delete().eq("id", document_id).execute()
        
        return True
    except Exception as e:
        raise RuntimeError(f"Failed to delete document: {str(e)}")

def clear_all_uploaded_documents() -> Dict[str, int]:
    """Clear all uploaded documents from both Supabase storage and database"""
    sb = get_client()
    config = get_supabase_config()
    
    try:
        # Get all uploaded documents (same filter as UI)
        result = sb.table("earnings_files").select("*").in_("file_type", ["presentation", "prepared_remarks", "uploaded_document"]).execute()
        documents = result.data
        
        deleted_count = 0
        storage_deleted = 0
        
        # Delete each document
        for doc in documents:
            try:
                # Delete from storage
                if doc.get('storage_path'):
                    sb.storage.from_(config["bucket"]).remove([doc['storage_path']])
                    storage_deleted += 1
                
                # Delete from database
                sb.table("earnings_files").delete().eq("id", doc['id']).execute()
                deleted_count += 1
                
            except Exception as e:
                print(f"Failed to delete document {doc.get('id', 'unknown')}: {str(e)}")
                continue
        
        return {
            "database_deleted": deleted_count,
            "storage_deleted": storage_deleted,
            "total_found": len(documents)
        }
        
    except Exception as e:
        raise RuntimeError(f"Failed to clear documents: {str(e)}")

def upload_user_document(ticker: str, year: int, quarter: str, 
                        filename: str, file_data: bytes, content_type: str) -> Dict[str, Any]:
    """Upload a user document to Supabase storage and database"""
    
    # Validate input data type
    if not isinstance(file_data, bytes):
        raise RuntimeError(f"Expected bytes for file_data, got {type(file_data)}: {repr(file_data)}")
    
    # Ensure correct types for database
    ticker = str(ticker)
    year = int(year) if year else None
    quarter = str(quarter) if quarter else None
    filename = str(filename)
    content_type = str(content_type)
    
    if not year:
        raise RuntimeError(f"Invalid year: {year}")
    if not quarter:
        raise RuntimeError(f"Invalid quarter: {quarter}")
    
    # Generate storage path
    file_extension = filename.split('.')[-1].lower() if '.' in filename else 'txt'
    storage_file_path = storage_path("uploads", ticker, year, quarter, filename)
    
    # Calculate hash
    file_hash = sha256_bytes(file_data)
    
    # Extract text content for searchability
    text_content = None
    if content_type.startswith("text/"):
        try:
            text_content = file_data.decode('utf-8')
        except:
            pass
    
    # Upload to storage
    upload_bytes(storage_file_path, file_data, content_type)
    
    # Use timestamp-based file_type to avoid constraint violations
    import time
    timestamp = int(time.time() * 1000)
    unique_file_type = f"uploaded_document_{timestamp}"
    
    # Store in database with unique file_type
    result = upsert_file_row(
        ticker=ticker,
        year=year,
        quarter=quarter,
        file_type=unique_file_type,
        file_format=file_extension,
        storage_path=storage_file_path,
        source_url=f"user_upload_{filename}",
        text_content=text_content,
        sha256=file_hash  # Keep parameter for compatibility but won't be used in payload
    )
    
    return {
        "storage_path": storage_file_path,
        "sha256": file_hash,
        "database_result": result
    }

def increment_app_usage_counter():
    """Increment the app usage counter in Supabase"""
    try:
        sb = get_client()
        
        # Use the existing earnings_files table to store the counter
        # This avoids needing table creation permissions
        counter_record = {
            "ticker": "APP_COUNTER",
            "year": 2024,
            "quarter": "STATS",
            "file_type": "usage_counter",
            "file_format": "counter",
            "storage_path": "internal/counter",
            "source_url": "app_usage_tracking",
            "text_content": None
        }
        
        # Try to get existing counter
        result = sb.table("earnings_files").select("*").eq("ticker", "APP_COUNTER").eq("file_type", "usage_counter").execute()
        
        if result.data:
            # Counter exists, increment it by updating the year field (using it as counter)
            current_count = result.data[0]["year"]
            new_count = current_count + 1
            counter_record["year"] = new_count
            sb.table("earnings_files").update(counter_record).eq("id", result.data[0]["id"]).execute()
        else:
            # Counter doesn't exist, create it with count = 1
            counter_record["year"] = 1
            sb.table("earnings_files").insert(counter_record).execute()
            
    except Exception as e:
        # Silently fail - we don't want to break the app if counter fails
        print(f"Failed to increment usage counter: {str(e)}")
        pass
