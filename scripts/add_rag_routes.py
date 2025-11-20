#!/usr/bin/env python3
"""
RAG Route Integration Script

This script helps integrate the RAG routes into your main FastAPI application.

Usage:
    python scripts/add_rag_routes.py [--dry-run] [--backup]
"""

import sys
import os
from pathlib import Path
import shutil
from datetime import datetime

def backup_file(file_path: str) -> str:
    """Create a backup of the file."""
    backup_path = f"{file_path}.backup.{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    shutil.copy2(file_path, backup_path)
    return backup_path

def add_rag_import(main_py_content: str) -> str:
    """Add RAG router import to main.py."""
    
    # Find the imports section
    lines = main_py_content.split('\n')
    import_section_end = -1
    
    # Find where the route imports are
    for i, line in enumerate(lines):
        if 'from second_brain_database.routes.documents import router as documents_router' in line:
            import_section_end = i
            break
    
    if import_section_end == -1:
        print("❌ Could not find documents router import. Manual integration required.")
        return main_py_content
    
    # Add RAG import after documents import
    rag_import = "from second_brain_database.routes.rag import router as rag_router"
    
    # Check if already imported
    if rag_import in main_py_content:
        print("✅ RAG router import already exists")
        return main_py_content
    
    lines.insert(import_section_end + 1, rag_import)
    print("✅ Added RAG router import")
    
    return '\n'.join(lines)

def add_rag_router_config(main_py_content: str) -> str:
    """Add RAG router to the routers_config list."""
    
    lines = main_py_content.split('\n')
    
    # Find the routers_config section
    config_start = -1
    config_end = -1
    
    for i, line in enumerate(lines):
        if 'routers_config = [' in line:
            config_start = i
        elif config_start != -1 and line.strip() == ']':
            config_end = i
            break
    
    if config_start == -1 or config_end == -1:
        print("❌ Could not find routers_config section. Manual integration required.")
        return main_py_content
    
    # Check if RAG router already configured
    for i in range(config_start, config_end):
        if 'rag_router' in lines[i]:
            print("✅ RAG router configuration already exists")
            return main_py_content
    
    # Add RAG router config before the closing bracket
    rag_config = '    ("rag", rag_router, "RAG and AI-powered document search endpoints"),'
    lines.insert(config_end, rag_config)
    
    print("✅ Added RAG router configuration")
    return '\n'.join(lines)

def integrate_rag_routes(dry_run: bool = False, create_backup: bool = True) -> bool:
    """Integrate RAG routes into the main application."""
    
    print("🔧 RAG Route Integration")
    print("=" * 40)
    
    # Check if main.py exists
    main_py_path = "src/second_brain_database/main.py"
    
    if not os.path.exists(main_py_path):
        print(f"❌ Main application file not found: {main_py_path}")
        return False
    
    # Check if RAG routes exist
    rag_routes_path = "src/second_brain_database/routes/rag.py"
    
    if not os.path.exists(rag_routes_path):
        print(f"❌ RAG routes file not found: {rag_routes_path}")
        print("   Run the RAG setup script first to create the routes.")
        return False
    
    print(f"📂 Found main application: {main_py_path}")
    print(f"📂 Found RAG routes: {rag_routes_path}")
    
    # Read main.py
    try:
        with open(main_py_path, 'r') as f:
            original_content = f.read()
    except Exception as e:
        print(f"❌ Error reading main.py: {e}")
        return False
    
    # Create backup if requested
    backup_path = None
    if create_backup and not dry_run:
        try:
            backup_path = backup_file(main_py_path)
            print(f"💾 Created backup: {backup_path}")
        except Exception as e:
            print(f"⚠️  Could not create backup: {e}")
    
    # Modify content
    modified_content = original_content
    
    # Add import
    modified_content = add_rag_import(modified_content)
    
    # Add router configuration
    modified_content = add_rag_router_config(modified_content)
    
    # Check if anything changed
    if modified_content == original_content:
        print("ℹ️  No changes needed - RAG routes already integrated")
        return True
    
    if dry_run:
        print("\n🔍 DRY RUN - Changes that would be made:")
        print("   • RAG router import would be added")
        print("   • RAG router configuration would be added")
        print("   • No files would be modified")
        return True
    
    # Write modified content
    try:
        with open(main_py_path, 'w') as f:
            f.write(modified_content)
        
        print("✅ Successfully integrated RAG routes into main application")
        
        # Provide next steps
        print("\n📋 Next Steps:")
        print("   1. Restart your FastAPI application")
        print("   2. Check http://localhost:8000/docs for new RAG endpoints:")
        print("      • POST /rag/query - AI-powered document queries")
        print("      • POST /rag/search - Vector search only")
        print("      • GET  /rag/status - System status check")
        print("      • GET  /rag/documents - List indexed documents")
        print("   3. Test with: python examples/rag_example.py")
        
        if backup_path:
            print(f"   💾 Backup available at: {backup_path}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error writing main.py: {e}")
        
        # Restore from backup if available
        if backup_path and os.path.exists(backup_path):
            try:
                shutil.copy2(backup_path, main_py_path)
                print(f"🔄 Restored from backup: {backup_path}")
            except Exception as restore_e:
                print(f"❌ Could not restore from backup: {restore_e}")
        
        return False

def main():
    """Main function."""
    
    import argparse
    
    parser = argparse.ArgumentParser(description="Integrate RAG routes into main FastAPI app")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be changed without making changes")
    parser.add_argument("--no-backup", action="store_true", help="Don't create backup file")
    args = parser.parse_args()
    
    print("🧠 Second Brain Database - RAG Route Integration")
    print("=" * 60)
    print(f"⏰ Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # Check we're in the right directory
    if not os.path.exists("src/second_brain_database"):
        print("❌ Please run this script from the project root directory")
        print("   (The directory containing src/second_brain_database/)")
        return False
    
    success = integrate_rag_routes(
        dry_run=args.dry_run,
        create_backup=not args.no_backup
    )
    
    if success:
        print(f"\n✅ Integration completed successfully at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        if not args.dry_run:
            print("\n🎉 RAG routes are now available in your FastAPI application!")
    else:
        print(f"\n❌ Integration failed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        return False
    
    return True

if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\nIntegration interrupted. Goodbye!")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Integration failed: {e}")
        sys.exit(1)