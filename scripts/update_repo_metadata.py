import subprocess
import time

OWNER = "rohanbatrain"

# Configuration for each repo
REPO_METADATA = {
    "second_brain_database": {
        "description": "A comprehensive, containerized Second Brain Database built with FastAPI, MongoDB, and Redis. Features advanced RAG, family management, and micro-frontend architecture.",
        "homepage": "https://rohanbatrain.github.io/second_brain_database/",
        "topics": ["fastapi", "mongodb", "redis", "second-brain", "knowledge-management", "rag", "ai", "microservices", "docker"]
    },
    "sbd-mkdocs": {
        "description": "Official Documentation for the Second Brain Database ecosystem. Built with MkDocs Material.",
        "homepage": "https://rohanbatrain.github.io/second_brain_database/",
        "topics": ["documentation", "mkdocs", "material-design", "second-brain", "technical-writing"]
    },
    "sbd-nextjs-cluster-dashboard": {
        "description": "Cluster Management Dashboard for Second Brain Database. Monitor and manage your distributed SBD nodes.",
        "homepage": "",
        "topics": ["nextjs", "react", "dashboard", "cluster-management", "monitoring", "second-brain"]
    },
    "sbd-nextjs-blog-platform": {
        "description": "A modern, feature-rich Blog Platform micro-frontend for the Second Brain ecosystem.",
        "homepage": "",
        "topics": ["nextjs", "react", "blog", "cms", "second-brain", "micro-frontend"]
    },
    "sbd-nextjs-chat": {
        "description": "Real-time Chat application with AI integration for Second Brain Database.",
        "homepage": "",
        "topics": ["nextjs", "react", "chat", "ai", "llm", "second-brain", "websocket"]
    },
    "sbd-nextjs-digital-shop": {
        "description": "Digital Asset Shop for the Second Brain ecosystem. Buy and sell digital goods.",
        "homepage": "",
        "topics": ["nextjs", "react", "ecommerce", "digital-assets", "second-brain", "shop"]
    },
    "sbd-nextjs-family-hub": {
        "description": "Family management and shared resources hub for Second Brain users.",
        "homepage": "",
        "topics": ["nextjs", "react", "family", "collaboration", "second-brain"]
    },
    "sbd-nextjs-ipam": {
        "description": "IP Address Management (IPAM) tool integrated into the Second Brain Database.",
        "homepage": "",
        "topics": ["nextjs", "react", "ipam", "networking", "second-brain"]
    },
    "sbd-nextjs-landing-page": {
        "description": "Main landing page and entry point for the Second Brain Database platform.",
        "homepage": "https://rohanbatrain.github.io/second_brain_database/",
        "topics": ["nextjs", "react", "landing-page", "marketing", "second-brain"]
    },
    "sbd-nextjs-memex": {
        "description": "MemEx: Memory Extension interface for browsing and organizing your Second Brain knowledge.",
        "homepage": "",
        "topics": ["nextjs", "react", "memex", "knowledge-graph", "second-brain", "pkm"]
    },
    "sbd-nextjs-myaccount": {
        "description": "User account management portal for Second Brain Database.",
        "homepage": "",
        "topics": ["nextjs", "react", "user-management", "profile", "second-brain"]
    },
    "sbd-nextjs-raunak-ai": {
        "description": "AI-powered assistant interface for interacting with your Second Brain.",
        "homepage": "",
        "topics": ["nextjs", "react", "ai", "assistant", "llm", "second-brain"]
    },
    "sbd-nextjs-university-clubs-platform": {
        "description": "Platform for managing university clubs and events within the Second Brain ecosystem.",
        "homepage": "",
        "topics": ["nextjs", "react", "university", "clubs", "events", "second-brain"]
    },
    "n8n-nodes-second-brain-database": {
        "description": "Custom n8n nodes for integrating with Second Brain Database API.",
        "homepage": "",
        "topics": ["n8n", "workflow-automation", "integration", "second-brain", "low-code"]
    },
    "sbd-flutter-emotion_tracker": {
        "description": "Mobile emotion tracking application built with Flutter for Second Brain.",
        "homepage": "",
        "topics": ["flutter", "dart", "mobile", "emotion-tracker", "quantified-self", "second-brain"]
    }
}

def update_repo(repo, data):
    print(f"Updating {repo}...")
    
    args = ["repo", "edit", f"{OWNER}/{repo}"]
    
    if data["description"]:
        args.extend(["--description", data["description"]])
    
    if data["homepage"]:
        args.extend(["--homepage", data["homepage"]])
    
    if data["topics"]:
        # gh repo edit --add-topic topic1 --add-topic topic2 ...
        # But wait, --add-topic adds to existing. To overwrite/set, we might need to remove old ones first or just add.
        # The prompt implies "prod ready" which usually means setting them correctly.
        # 'gh repo edit' doesn't have a simple --set-topics. It has --add-topic and --remove-topic.
        # However, verifying via API and then adding missing ones is safer.
        # For simplicity in this script, we will just add them.
        for topic in data["topics"]:
            args.extend(["--add-topic", topic])

    # Run command
    result = subprocess.run(["gh"] + args, capture_output=True, text=True)
    
    if result.returncode == 0:
        print(f"  Successfully updated {repo}")
    else:
        print(f"  Failed to update {repo}: {result.stderr}")

if __name__ == "__main__":
    for repo, data in REPO_METADATA.items():
        update_repo(repo, data)
        time.sleep(1) # Rate limit niceness
