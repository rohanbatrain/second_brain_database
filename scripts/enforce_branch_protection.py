import subprocess
import json
import time

OWNER = "rohanbatrain"
# List of repos to protect
REPOS = [
    "second_brain_database",
    "sbd-mkdocs",
    "sbd-nextjs-cluster-dashboard",
    "sbd-nextjs-blog-platform",
    "sbd-nextjs-chat",
    "sbd-nextjs-digital-shop",
    "sbd-nextjs-family-hub",
    "sbd-nextjs-ipam",
    "sbd-nextjs-landing-page",
    "sbd-nextjs-memex",
    "sbd-nextjs-myaccount",
    "sbd-nextjs-raunak-ai",
    "sbd-nextjs-university-clubs-platform",
    "n8n-nodes-second-brain-database",
    "sbd-flutter-emotion_tracker"
]

def run_gh_command(args):
    result = subprocess.run(["gh"] + args, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"Error running gh command: {result.stderr}")
        return None
    return result.stdout

def get_existing_rulesets(repo):
    output = run_gh_command(["api", f"repos/{OWNER}/{repo}/rulesets"])
    if output:
        return json.loads(output)
    return []

def create_ruleset(repo):
    print(f"Applying ruleset to {repo}...")
    
    # Check if ruleset already exists and delete it to allow update
    existing = get_existing_rulesets(repo)
    for ruleset in existing:
        if ruleset["name"] == "SBD Production Protection":
            print(f"  Ruleset 'SBD Production Protection' exists for {repo}. Deleting to update...")
            run_gh_command(["api", f"repos/{OWNER}/{repo}/rulesets/{ruleset['id']}", "--method", "DELETE"])

    # Define the ruleset
    # Target: main, v*, and dev
    # Rules: PR required, No deletion, No force push
    ruleset_data = {
        "name": "SBD Production Protection",
        "target": "branch",
        "enforcement": "active",
        "conditions": {
            "ref_name": {
                "include": [
                    "refs/heads/main",
                    "refs/heads/dev",
                    "refs/heads/v*"
                ],
                "exclude": []
            }
        },
        "rules": [
            {
                "type": "deletion"
            },
            {
                "type": "non_fast_forward"
            },
            {
                "type": "pull_request",
                "parameters": {
                    "required_approving_review_count": 0,
                    "dismiss_stale_reviews_on_push": True,
                    "require_code_owner_review": False,
                    "require_last_push_approval": False,
                    "required_review_thread_resolution": False
                }
            }
        ]
    }

    # Convert python bools to json bools for the command (actually json.dumps handles it)
    # But we need to write it to a temp file or pass as string
    
    # Using gh api input via stdin
    json_str = json.dumps(ruleset_data)
    
    # We use subprocess directly to pipe input
    process = subprocess.Popen(
        ["gh", "api", f"repos/{OWNER}/{repo}/rulesets", "--method", "POST", "--input", "-"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    stdout, stderr = process.communicate(input=json_str)
    
    if process.returncode == 0:
        print(f"  Successfully applied ruleset to {repo}")
    else:
        print(f"  Failed to apply ruleset to {repo}: {stderr}")

if __name__ == "__main__":
    for repo in REPOS:
        create_ruleset(repo)
        time.sleep(1) # Rate limit niceness
