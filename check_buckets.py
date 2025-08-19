#!/usr/bin/env python3
"""
Quick script to check what buckets exist in Supabase
"""
import os
from dotenv import load_dotenv
from supabase import create_client, Client

# Load environment variables
load_dotenv()

def main():
    # Get Supabase credentials
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    
    if not url or not key:
        print("ERROR: Missing Supabase credentials in .env file")
        return
    
    # Create client
    supabase: Client = create_client(url, key)
    
    try:
        print("Checking existing buckets in Supabase...")
        buckets = supabase.storage.list_buckets()
        
        if buckets:
            print(f"Found {len(buckets)} buckets:")
            for bucket in buckets:
                print(f"  - {bucket.name} (ID: {bucket.id}, Public: {bucket.public})")
        else:
            print("No buckets found")
            
        # Also try to check if we can access some common bucket names
        common_names = ["earnings", "earnings-files", "documents", "files", "storage", "uploads"]
        print("\nTesting access to common bucket names:")
        
        for name in common_names:
            try:
                files = supabase.storage.from_(name).list()
                print(f"  ✅ {name}: Accessible ({len(files)} items)")
            except Exception as e:
                print(f"  ❌ {name}: {str(e)}")
                
    except Exception as e:
        print(f"ERROR: {str(e)}")

if __name__ == "__main__":
    main()
