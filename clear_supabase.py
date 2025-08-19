#!/usr/bin/env python3
"""
Script to clear all stale uploaded documents from Supabase storage and database
"""

from supabase_store import clear_all_uploaded_documents

def main():
    print("Clearing all uploaded documents from Supabase...")
    
    try:
        result = clear_all_uploaded_documents()
        
        print(f"Cleanup completed!")
        print(f"   Total documents found: {result['total_found']}")
        print(f"   Database records deleted: {result['database_deleted']}")
        print(f"   Storage files deleted: {result['storage_deleted']}")
        
        if result['total_found'] == 0:
            print("   No uploaded documents found - database is already clean")
        elif result['database_deleted'] == result['total_found']:
            print("   All documents successfully removed")
        else:
            print(f"   Some documents may not have been deleted completely")
            
    except Exception as e:
        print(f"Error during cleanup: {str(e)}")
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main())
