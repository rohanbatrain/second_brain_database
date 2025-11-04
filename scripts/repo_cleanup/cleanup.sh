#!/bin/bash
#
# Repository Cleanup - Master Script
# 
# Usage: ./cleanup.sh [command]
#

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Get script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
REPO_ROOT="$(dirname "$(dirname "$SCRIPT_DIR")")"

# Function to print colored output
print_info() {
    echo -e "${BLUE}ℹ${NC}  $1"
}

print_success() {
    echo -e "${GREEN}✓${NC}  $1"
}

print_warning() {
    echo -e "${YELLOW}⚠${NC}  $1"
}

print_error() {
    echo -e "${RED}✖${NC}  $1"
}

# Function to run Python script
run_script() {
    local script_name=$1
    shift
    python3 "$SCRIPT_DIR/$script_name" "$@"
}

# Show help
show_help() {
    cat << EOF

🧹 Repository Cleanup System

Usage: ./cleanup.sh [command]

Commands:
    start           Run interactive quick-start wizard
    full            Run full cleanup process
    analyze         Analyze repository files
    validate        Validate repository structure
    backup          Create a backup snapshot
    info            Display system information
    help            Show this help message

Examples:
    ./cleanup.sh start         # Interactive mode (recommended)
    ./cleanup.sh full          # Run complete cleanup
    ./cleanup.sh analyze       # Analyze files only
    ./cleanup.sh backup        # Create backup only

For more information, see: scripts/repo_cleanup/README.md

EOF
}

# Main command handler
case "${1:-help}" in
    start)
        print_info "Starting interactive wizard..."
        run_script "quick_start.py"
        ;;
    
    full)
        print_info "Running full cleanup..."
        run_script "run_cleanup.py"
        ;;
    
    analyze)
        print_info "Analyzing repository..."
        run_script "file_analyzer.py"
        ;;
    
    validate)
        print_info "Validating structure..."
        run_script "structure_validator.py"
        ;;
    
    backup)
        description="${2:-Manual backup from shell script}"
        print_info "Creating backup..."
        run_script "backup_manager.py" create "$description"
        ;;
    
    info)
        run_script "system_info.py"
        ;;
    
    help|--help|-h)
        show_help
        ;;
    
    *)
        print_error "Unknown command: $1"
        show_help
        exit 1
        ;;
esac
