# Branch Protection Setup Guide

This guide provides step-by-step instructions for configuring GitHub branch protection rules for all Second Brain Database submodules.

## 📋 Overview

Branch protection ensures that:
- ✅ All changes go through Pull Requests
- ✅ CI checks must pass before merging
- ✅ Direct pushes to protected branches are blocked
- ✅ Code review is enforced

## 🎯 Protected Branches

For each submodule, protect the following branches:
- `main` (production)
- `dev` (development) - optional

## 🔧 Configuration Steps

### Method 1: GitHub Web UI (Recommended for First-Time Setup)

For each submodule repository:

#### 1. Navigate to Branch Protection Settings

1. Go to `https://github.com/rohanbatrain/<SUBMODULE_NAME>`
2. Click **Settings** → **Branches** (left sidebar)
3. Click **Add branch protection rule**

#### 2. Configure Branch Name Pattern

Enter: `main`

#### 3. Enable Required Settings

Check the following options:

**Require a pull request before merging**
- ☑️ Require a pull request before merging
- ☑️ Require approvals: `1` (adjust based on team size)
- ☑️ Dismiss stale pull request approvals when new commits are pushed
- ☐ Require review from Code Owners (optional)

**Require status checks to pass before merging**
- ☑️ Require status checks to pass before merging
- ☑️ Require branches to be up to date before merging

**Select required status checks:**
- ☑️ `validate-branch` (Branch Validation)
- ☑️ `validate-pr-title` (PR Title Validation)
- ☑️ `lint` (Lint & Format Check)
- ☑️ `type-check` (TypeScript Type Check)
- ☑️ `build` (Build Verification)
- ☑️ `test` (Run Tests) - if applicable

**Additional protections**
- ☐ Require conversation resolution before merging (optional)
- ☐ Require signed commits (optional, enhanced security)
- ☐ Require linear history (optional)

**Do not allow bypassing the above settings**
- ☑️ Do not allow bypassing the above settings
- Exceptions: (leave empty for strict enforcement)

**Rules applied to everyone including administrators**
- ☑️ Include administrators

#### 4. Save Changes

Click **Create** or **Save changes**

---

### Method 2: GitHub CLI (Batch Setup)

For automated setup across all submodules, use the GitHub CLI:

```bash
#!/bin/bash
# Branch Protection Setup Script

SUBMODULES=(
    "sbd-nextjs-blog-platform"
    "sbd-nextjs-chat"
    "sbd-nextjs-cluster-dashboard"
    "sbd-nextjs-digital-shop"
    "sbd-nextjs-family-hub"
    "sbd-nextjs-ipam"
    "sbd-nextjs-landing-page"
    "sbd-nextjs-memex"
    "sbd-nextjs-myaccount"
    "sbd-nextjs-raunak-ai"
    "sbd-nextjs-university-clubs-platform"
    "sbd-flutter-emotion_tracker"
    "sbd-mkdocs"
    "n8n-nodes-second-brain-database"
)

for REPO in "${SUBMODULES[@]}"; do
    echo "🔒 Protecting main branch for: rohanbatrain/$REPO"
    
    gh api \
        --method PUT \
        -H "Accept: application/vnd.github+json" \
        -H "X-GitHub-Api-Version: 2022-11-28" \
        "/repos/rohanbatrain/$REPO/branches/main/protection" \
        -f "required_status_checks[strict]=true" \
        -f "required_status_checks[checks][][context]=validate-branch" \
        -f "required_status_checks[checks][][context]=validate-pr-title" \
        -f "required_status_checks[checks][][context]=lint" \
        -f "required_status_checks[checks][][context]=type-check" \
        -f "required_status_checks[checks][][context]=build" \
        -f "required_pull_request_reviews[required_approving_review_count]=1" \
        -f "required_pull_request_reviews[dismiss_stale_reviews]=true" \
        -f "enforce_admins=true" \
        -f "restrictions=null"
    
    echo "✅ Protected: rohanbatrain/$REPO"
done

echo "🎉 All repositories protected!"
```

**To run:**

```bash
# Make executable
chmod +x scripts/setup-branch-protection.sh

# Execute
./scripts/setup-branch-protection.sh
```

---

### Method 3: Terraform (Infrastructure as Code)

For version-controlled infrastructure:

```hcl
# terraform/branch-protection.tf

variable "submodules" {
  type = list(string)
  default = [
    "sbd-nextjs-blog-platform",
    "sbd-nextjs-chat",
    "sbd-nextjs-cluster-dashboard",
    # ... add all submodules
  ]
}

resource "github_branch_protection" "main" {
  for_each = toset(var.submodules)
  
  repository_id = each.value
  pattern       = "main"

  required_status_checks {
    strict = true
    contexts = [
      "validate-branch",
      "validate-pr-title",
      "lint",
      "type-check",
      "build"
    ]
  }

  required_pull_request_reviews {
    required_approving_review_count = 1
    dismiss_stale_reviews           = true
  }

  enforce_admins = true
}
```

---

## ✅ Verification

### Test Protected Branch

After enabling protection, verify it works:

```bash
cd submodules/sbd-nextjs-cluster-dashboard

# Try direct push to main (should FAIL)
git checkout main
git commit --allow-empty -m "test: direct push"
git push origin main

# Expected error:
# remote: error: GH006: Protected branch update failed for refs/heads/main.
```

### Test PR Workflow

```bash
# Create feature branch (should SUCCEED)
git checkout -b feat/test-protection
git commit --allow-empty -m "feat: test PR workflow"
git push origin feat/test-protection

# Create PR
gh pr create --title "feat: Test Branch Protection" --body "Testing protection rules"

# Verify:
# - CI checks run automatically
# - Cannot merge until checks pass
# - Requires approval before merge
```

---

## 📊 Status Check Reference

### Next.js Submodules

| Check Name | Workflow | Purpose |
|------------|----------|---------|
| `validate-branch` | `.github/workflows/ci.yml` | Branch naming validation |
| `validate-pr-title` | `.github/workflows/ci.yml` | PR title format validation |
| `lint` | `.github/workflows/ci.yml` | ESLint check (zero warnings) |
| `type-check` | `.github/workflows/ci.yml` | TypeScript type check |
| `build` | `.github/workflows/ci.yml` | Next.js build verification |
| `test` | `.github/workflows/ci.yml` | Unit/integration tests |

### Flutter Submodule

| Check Name | Workflow | Purpose |
|------------|----------|---------|
| `validate-branch` | `.github/workflows/ci.yml` | Branch naming validation |
| `validate-pr-title` | `.github/workflows/ci.yml` | PR title format validation |
| `analyze` | `.github/workflows/ci.yml` | Dart analyze & format check |
| `test` | `.github/workflows/ci.yml` | Flutter tests |
| `build` | `.github/workflows/ci.yml` | APK build verification |

### MkDocs Submodule

| Check Name | Workflow | Purpose |
|------------|----------|---------|
| `validate-branch` | `.github/workflows/ci.yml` | Branch naming validation |
| `validate-pr-title` | `.github/workflows/ci.yml` | PR title format validation |
| `lint` | `.github/workflows/ci.yml` | Markdown/YAML linting |
| `build` | `.github/workflows/ci.yml` | MkDocs build (strict mode) |

---

## 🔍 Troubleshooting

### Issue: Status checks not appearing

**Solution:**
1. Push a commit to trigger the workflow
2. Wait for workflow to complete at least once
3. Check Actions tab for workflow runs
4. Status checks appear after first successful run

### Issue: Cannot select status checks in UI

**Solution:**
1. Ensure workflows are in `.github/workflows/` directory
2. Push workflows to the repository
3. Create a test PR to trigger workflows
4. Wait for workflows to complete
5. Status checks will then appear in branch protection UI

### Issue: Admins can still bypass protection

**Solution:**
- Ensure "Include administrators" is checked
- Ensure "Do not allow bypassing the above settings" is enabled

### Issue: Old PRs fail new checks

**Solution:**
- Rebase PRs on latest main branch
- Or: Add new checks gradually, mark as optional initially

---

## 📝 Best Practices

1. **Start with 1 approval**: Increase to 2+ for production-critical repos
2. **Enable "Require branches to be up to date"**: Prevents merge conflicts
3. **Use "Dismiss stale reviews"**: Ensures reviews reflect latest changes
4. **Lock status checks**: Only enable checks that consistently pass
5. **Document exceptions**: If admins need bypass access, document why

---

## 🔄 Maintenance

Review protection rules:
- **Monthly**: Verify all checks are still relevant
- **After workflow changes**: Update required status checks list
- **After team changes**: Adjust approval requirements

---

## 📚 Additional Resources

- [GitHub Branch Protection Docs](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches)
- [GitHub CLI Reference](https://cli.github.com/manual/gh_api)
- [Terraform GitHub Provider](https://registry.terraform.io/providers/integrations/github/latest/docs/resources/branch_protection)
