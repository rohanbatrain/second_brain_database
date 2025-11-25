#!/usr/bin/env python3
"""
Sync dev and main branches script.
Ensures dev is an exact clone of main across all repositories.
"""
import subprocess
import sys
import os

# Configuration
REPO_ROOT = "/Users/rohan/Documents/repos/second_brain_database"
SUBMODULES_DIR = os.path.join(REPO_ROOT, "submodules")

def run_git(args, cwd):
    """Run git command in specified directory."""
    cmd = ["git", "-C", cwd] + args
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.returncode, result.stdout, result.stderr

def sync_repo(path, name):
    """Sync dev and main branches for a repository."""
    print(f"\n=== Processing {name} ===")
    
    # Fetch all
    code, _, stderr = run_git(["fetch", "--all"], path)
    if code != 0:
        print(f"  ❌ Failed to fetch: {stderr}")
        return False

    # 1. Ensure main is current
    # Try checkout main or master
    main_branch = "main"
    code, _, _ = run_git(["checkout", "main"], path)
    if code != 0:
        code, _, _ = run_git(["checkout", "master"], path)
        if code == 0:
            main_branch = "master"
        else:
            print(f"  ❌ Failed to checkout main/master")
            return False
            
    print(f"  ✓ Checked out {main_branch}")
    
    # Pull latest main
    code, _, stderr = run_git(["pull", "origin", main_branch], path)
    if code != 0:
        print(f"  ⚠️ Pull failed (might be no remote changes): {stderr}")
        
    # Push main to ensure remote is up to date
    code, _, stderr = run_git(["push", "origin", main_branch], path)
    if code != 0:
        print(f"  ❌ Failed to push {main_branch}: {stderr}")
        return False
    print(f"  ✓ {main_branch} up to date")

    # 2. Sync dev to main
    # Checkout dev or create it
    code, _, _ = run_git(["checkout", "dev"], path)
    if code != 0:
        print(f"  Creating dev branch...")
        code, _, stderr = run_git(["checkout", "-b", "dev"], path)
        if code != 0:
            print(f"  ❌ Failed to create/checkout dev: {stderr}")
            return False
            
    # Reset dev to match main exactly
    code, _, stderr = run_git(["reset", "--hard", main_branch], path)
    if code != 0:
        print(f"  ❌ Failed to reset dev to {main_branch}: {stderr}")
        return False
    print(f"  ✓ Reset dev to match {main_branch}")
    
    # Force push dev
    code, _, stderr = run_git(["push", "-f", "origin", "dev"], path)
    if code != 0:
        print(f"  ❌ Failed to push dev: {stderr}")
        return False
    print(f"  ✓ Pushed dev (clone of {main_branch})")
    
    # Switch back to main/master
    run_git(["checkout", main_branch], path)
    
    return True

def main():
    print("=== SYNCING DEV AND MAIN BRANCHES ===\n")
    
    success_count = 0
    fail_count = 0
    
    # 1. Process Main Repository
    if sync_repo(REPO_ROOT, "MAIN REPOSITORY"):
        success_count += 1
    else:
        fail_count += 1
        
    # 2. Process Submodules
    if os.path.isdir(SUBMODULES_DIR):
        submodules = sorted([d for d in os.listdir(SUBMODULES_DIR) 
                            if os.path.isdir(os.path.join(SUBMODULES_DIR, d))])
        
        for submodule in submodules:
            path = os.path.join(SUBMODULES_DIR, submodule)
            if os.path.isdir(os.path.join(path, ".git")):
                if sync_repo(path, submodule):
                    success_count += 1
                else:
                    fail_count += 1
    
    print(f"\n=== SUMMARY ===")
    print(f"✓ Successful repos: {success_count}")
    print(f"❌ Failed repos: {fail_count}")
    
    return 0 if fail_count == 0 else 1

if __name__ == "__main__":
    sys.exit(main())
