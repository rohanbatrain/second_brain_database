import subprocess
import os

def run_command(command, cwd):
    try:
        # print(f"Running: {command} in {cwd}")
        result = subprocess.run(command, cwd=cwd, check=True, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        return True
    except subprocess.CalledProcessError as e:
        print(f"Error running '{command}' in {cwd}: {e.stderr.strip()}")
        return False

def sync_repo(path):
    print(f"Processing {path}...")
    
    # Fetch all remotes
    run_command("git fetch --all", path)
    
    # Sync main
    # Check if main exists (local or remote)
    if run_command("git checkout main", path):
        run_command("git fetch origin main", path)
        run_command("git reset --hard origin/main", path)
    
    # Sync dev
    # Try to checkout dev. If it doesn't exist locally, git checkout dev will try to track origin/dev
    if run_command("git checkout dev", path):
        run_command("git fetch origin dev", path)
        run_command("git reset --hard origin/dev", path)
    else:
        print(f"  'dev' branch issue in {path}. It might not exist.")
        # If dev fails, we might want to stay on main or try to create it?
        # For now, just report.
        return

    # Ensure we are on dev
    run_command("git checkout dev", path)
    print(f"  Successfully synced and checked out 'dev' in {path}")

if __name__ == "__main__":
    root_dir = os.getcwd()
    
    # Sync Root Repo
    print("=== Syncing Root Repository ===")
    sync_repo(root_dir)
    
    # Sync Submodules
    print("\n=== Syncing Submodules ===")
    # Get list of submodule paths
    try:
        result = subprocess.run("git submodule foreach --quiet 'echo $path'", shell=True, capture_output=True, text=True, check=True)
        submodules = result.stdout.strip().split('\n')
        
        for submodule in submodules:
            if submodule:
                submodule_path = os.path.join(root_dir, submodule)
                if os.path.exists(submodule_path):
                    sync_repo(submodule_path)
                else:
                    print(f"Submodule path {submodule} does not exist (maybe not initialized?)")
    except subprocess.CalledProcessError as e:
        print(f"Failed to list submodules: {e}")
