import os

BASE_DOCS_DIR = "submodules/sbd-mkdocs/docs"

MODULES = {
    "micro-frontends": [
        "blog-platform",
        "chat",
        "digital-shop",
        "family-hub",
        "ipam",
        "landing-page",
        "memex",
        "myaccount",
        "raunak-ai",
        "university-clubs-platform",
    ],
    "integrations": [
        "n8n",
    ],
    "backend": [
        "." # Root of backend
    ]
}

SECTIONS = ["users", "developers", "maintainers"]

TEMPLATES = {
    "users": {
        "index.md": "# {module_name} - User Guide\n\nWelcome to the user guide for {module_name}.\n\n## Getting Started\n\nCheck out the [Getting Started](getting-started.md) guide.",
        "getting-started.md": "# Getting Started with {module_name}\n\nStep-by-step guide to get started with {module_name}."
    },
    "developers": {
        "index.md": "# {module_name} - Developer Guide\n\nWelcome to the developer guide for {module_name}.\n\n## Topics\n\n- [Setup](setup.md)\n- [Architecture](architecture.md)",
        "setup.md": "# Local Development Setup\n\nHow to set up {module_name} locally.",
        "architecture.md": "# Architecture of {module_name}\n\nTechnical design and architecture details."
    },
    "maintainers": {
        "index.md": "# {module_name} - Maintenance Guide\n\nWelcome to the maintenance guide for {module_name}.\n\n## Topics\n\n- [Deployment](deployment.md)",
        "deployment.md": "# Deploying {module_name}\n\nInstructions for deploying {module_name}."
    }
}

def create_structure():
    for category, modules in MODULES.items():
        for module in modules:
            if module == ".":
                module_path = os.path.join(BASE_DOCS_DIR, category)
                module_name = "Second Brain Database Backend"
            else:
                module_path = os.path.join(BASE_DOCS_DIR, category, module)
                module_name = module.replace("-", " ").title()

            print(f"Processing {module_name} at {module_path}")
            os.makedirs(module_path, exist_ok=True)
            
            # Create root index if missing
            if not os.path.exists(os.path.join(module_path, "index.md")):
                 with open(os.path.join(module_path, "index.md"), "w") as f:
                    f.write(f"# {module_name}\n\nOverview of {module_name}.\n")

            for section in SECTIONS:
                section_path = os.path.join(module_path, section)
                os.makedirs(section_path, exist_ok=True)
                
                for filename, content in TEMPLATES[section].items():
                    file_path = os.path.join(section_path, filename)
                    if not os.path.exists(file_path):
                        with open(file_path, "w") as f:
                            f.write(content.format(module_name=module_name))
                        print(f"  Created {file_path}")
                    else:
                        print(f"  Skipped {file_path} (exists)")

if __name__ == "__main__":
    create_structure()
