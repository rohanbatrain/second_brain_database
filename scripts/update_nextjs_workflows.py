#!/usr/bin/env python3
"""
Update Docker workflows for all Next.js submodules to add Docker Hub support
"""

import os
from pathlib import Path

# Base directory
BASE_DIR = Path("/Users/rohan/Documents/repos/second_brain_database/submodules")

# All Next.js submodules
NEXTJS_SUBMODULES = [
    "sbd-nextjs-blog-platform",
    "sbd-nextjs-chat",
    "sbd-nextjs-cluster-dashboard",
    "sbd-nextjs-digital-shop",
    # "sbd-nextjs-family-hub",  # Already updated manually
    "sbd-nextjs-ipam",
    "sbd-nextjs-landing-page",
    "sbd-nextjs-memex",
    "sbd-nextjs-myaccount",
    "sbd-nextjs-raunak-ai",
    "sbd-nextjs-university-clubs-platform",
]

DOCKER_DEV_TEMPLATE = """name: Build and Push Docker Dev Image

on:
  push:
    branches:
      - dev

jobs:
  build:
    runs-on: ubuntu-latest

    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3

      - name: Login to Docker Hub
        uses: docker/login-action@v3
        with:
          username: rohanbatra
          password: ${{{{ secrets.DOCKER_HUB_TOKEN }}}}

      - name: Login to GitHub Container Registry
        uses: docker/login-action@v3
        with:
          registry: ghcr.io
          username: ${{{{ github.actor }}}}
          password: ${{{{ secrets.GITHUB_TOKEN }}}}

      - name: Build and push
        uses: docker/build-push-action@v5
        with:
          context: .
          file: ./Dockerfile
          push: true
          tags: |
            rohanbatra/{image_name}:dev
            ghcr.io/${{{{ github.repository }}}}:dev
          cache-from: type=gha
          cache-to: type=gha,mode=max
"""

DOCKER_PROD_TEMPLATE = """name: Docker Production Build

on:
  push:
    branches: [main]
    tags: ['v*']
  workflow_dispatch:

env:
  REGISTRY_GHCR: ghcr.io
  REGISTRY_DOCKERHUB: rohanbatra
  IMAGE_NAME: ${{{{ github.repository }}}}
  IMAGE_NAME_SHORT: {image_name}

jobs:
  build:
    name: Build Multi-Platform Images
    runs-on: ubuntu-latest
    
    strategy:
      matrix:
        platform:
          - linux/amd64
          - linux/arm64
    
    steps:
      - name: Checkout code
        uses: actions/checkout@v4
      
      - name: Set up QEMU
        uses: docker/setup-qemu-action@v3
      
      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3
      
      - name: Login to Docker Hub
        if: github.event_name != 'pull_request'
        uses: docker/login-action@v3
        with:
          username: rohanbatra
          password: ${{{{ secrets.DOCKER_HUB_TOKEN }}}}
      
      - name: Login to GitHub Container Registry
        if: github.event_name != 'pull_request'
        uses: docker/login-action@v3
        with:
          registry: ${{{{ env.REGISTRY_GHCR }}}}
          username: ${{{{ github.actor }}}}
          password: ${{{{ secrets.GITHUB_TOKEN }}}}
      
      - name: Extract metadata
        id: meta
        uses: docker/metadata-action@v5
        with:
          images: |
            ${{{{ env.REGISTRY_DOCKERHUB }}}}/${{{{ env.IMAGE_NAME_SHORT }}}}
            ${{{{ env.REGISTRY_GHCR }}}}/${{{{ env.IMAGE_NAME }}}}
          tags: |
            type=ref,event=branch
            type=ref,event=pr
            type=semver,pattern={{{{version}}}}
            type=semver,pattern={{{{major}}}}.{{{{minor}}}}
            type=sha
      
      - name: Build and push by digest (Docker Hub)
        id: build-dockerhub
        uses: docker/build-push-action@v5
        with:
          context: .
          file: ./Dockerfile
          platforms: ${{{{ matrix.platform }}}}
          labels: ${{{{ steps.meta.outputs.labels }}}}
          outputs: type=image,name=${{{{ env.REGISTRY_DOCKERHUB }}}}/${{{{ env.IMAGE_NAME_SHORT }}}},push-by-digest=true,name-canonical=true,push=${{{{ github.event_name != 'pull_request' }}}}
          cache-from: type=gha
          cache-to: type=gha,mode=max
      
      - name: Build and push by digest (GHCR)
        id: build-ghcr
        uses: docker/build-push-action@v5
        with:
          context: .
          file: ./Dockerfile
          platforms: ${{{{ matrix.platform }}}}
          labels: ${{{{ steps.meta.outputs.labels }}}}
          outputs: type=image,name=${{{{ env.REGISTRY_GHCR }}}}/${{{{ env.IMAGE_NAME }}}},push-by-digest=true,name-canonical=true,push=${{{{ github.event_name != 'pull_request' }}}}
          cache-from: type=gha
          cache-to: type=gha,mode=max
      
      - name: Export digests
        if: github.event_name != 'pull_request'
        run: |
          mkdir -p /tmp/digests-dockerhub
          mkdir -p /tmp/digests-ghcr
          
          digest_dockerhub="${{{{ steps.build-dockerhub.outputs.digest }}}}"
          touch "/tmp/digests-dockerhub/${{{{digest_dockerhub#sha256:}}}}"
          
          digest_ghcr="${{{{ steps.build-ghcr.outputs.digest }}}}"
          touch "/tmp/digests-ghcr/${{{{digest_ghcr#sha256:}}}}"
      
      - name: Upload digests
        if: github.event_name != 'pull_request'
        uses: actions/upload-artifact@v4
        with:
          name: digests-${{{{ strategy.job-index }}}}
          path: /tmp/digests-*
          if-no-files-found: error
          retention-days: 1

  merge:
    name: Merge and Push Multi-Platform Images
    runs-on: ubuntu-latest
    needs: build
    if: github.event_name != 'pull_request'
    
    steps:
      - name: Download digests
        uses: actions/download-artifact@v4
        with:
          path: /tmp/digests
          pattern: digests-*
          merge-multiple: true
      
      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3
      
      - name: Login to Docker Hub
        uses: docker/login-action@v3
        with:
          username: rohanbatra
          password: ${{{{ secrets.DOCKER_HUB_TOKEN }}}}
      
      - name: Login to GitHub Container Registry
        uses: docker/login-action@v3
        with:
          registry: ${{{{ env.REGISTRY_GHCR }}}}
          username: ${{{{ github.actor }}}}
          password: ${{{{ secrets.GITHUB_TOKEN }}}}
      
      - name: Extract metadata
        id: meta
        uses: docker/metadata-action@v5
        with:
          images: |
            ${{{{ env.REGISTRY_DOCKERHUB }}}}/${{{{ env.IMAGE_NAME_SHORT }}}}
            ${{{{ env.REGISTRY_GHCR }}}}/${{{{ env.IMAGE_NAME }}}}
          tags: |
            type=ref,event=branch
            type=semver,pattern={{{{version}}}}
            type=semver,pattern={{{{major}}}}.{{{{minor}}}}
            type=sha
            type=raw,value=latest,enable={{{{is_default_branch}}}}
      
      - name: Create manifest list and push (Docker Hub)
        working-directory: /tmp/digests/digests-dockerhub
        run: |
          docker buildx imagetools create \\
            $(jq -cr '.tags | map(select(contains("rohanbatra"))) | map("-t " + .) | join(" ")' <<< "$DOCKER_METADATA_OUTPUT_JSON") \\
            $(printf '${{{{ env.REGISTRY_DOCKERHUB }}}}/${{{{ env.IMAGE_NAME_SHORT }}}}@sha256:%s ' *)
      
      - name: Create manifest list and push (GHCR)
        working-directory: /tmp/digests/digests-ghcr
        run: |
          docker buildx imagetools create \\
            $(jq -cr '.tags | map(select(contains("ghcr.io"))) | map("-t " + .) | join(" ")' <<< "$DOCKER_METADATA_OUTPUT_JSON") \\
            $(printf '${{{{ env.REGISTRY_GHCR }}}}/${{{{ env.IMAGE_NAME }}}}@sha256:%s ' *)
      
      - name: Inspect images
        run: |
          echo "=== Docker Hub Image ==="
          docker buildx imagetools inspect ${{{{ env.REGISTRY_DOCKERHUB }}}}/${{{{ env.IMAGE_NAME_SHORT }}}}:${{{{ steps.meta.outputs.version }}}}
          echo "=== GHCR Image ==="
          docker buildx imagetools inspect ${{{{ env.REGISTRY_GHCR }}}}/${{{{ env.IMAGE_NAME }}}}:${{{{ steps.meta.outputs.version }}}}
      
      - name: Create GitHub Release
        if: startsWith(github.ref, 'refs/tags/v')
        uses: softprops/action-gh-release@v1
        with:
          generate_release_notes: true
        env:
          GITHUB_TOKEN: ${{{{ secrets.GITHUB_TOKEN }}}}

  security-scan:
    name: Security Scan
    runs-on: ubuntu-latest
    needs: merge
    if: github.event_name != 'pull_request' && github.ref == 'refs/heads/main'
    
    steps:
      - name: Run Trivy vulnerability scanner
        uses: aquasecurity/trivy-action@master
        with:
          image-ref: ${{{{ env.REGISTRY_DOCKERHUB }}}}/${{{{ env.IMAGE_NAME_SHORT }}}}:latest
          format: 'sarif'
          output: 'trivy-results.sarif'
      
      - name: Upload Trivy results to GitHub Security tab
        uses: github/codeql-action/upload-sarif@v3
        with:
          sarif_file: 'trivy-results.sarif'
      
      - name: Run Trivy vulnerability scanner (table output)
        uses: aquasecurity/trivy-action@master
        with:
          image-ref: ${{{{ env.REGISTRY_DOCKERHUB }}}}/${{{{ env.IMAGE_NAME_SHORT }}}}:latest
          format: 'table'
          exit-code: '0'
          ignore-unfixed: true
          severity: 'CRITICAL,HIGH'
"""


def update_workflows():
    """Update all Next.js submodule workflows"""
    
    for submodule in NEXTJS_SUBMODULES:
        print(f"Updating {submodule}...")
        
        workflows_dir = BASE_DIR / submodule / ".github" / "workflows"
        workflows_dir.mkdir(parents=True, exist_ok=True)
        
        # Update docker-dev.yml
        dev_file = workflows_dir / "docker-dev.yml"
        with open(dev_file, "w") as f:
            f.write(DOCKER_DEV_TEMPLATE.format(image_name=submodule))
        print(f"  ✓ Updated docker-dev.yml")
        
        # Update docker-prod.yml
        prod_file = workflows_dir / "docker-prod.yml"
        with open(prod_file, "w") as f:
            f.write(DOCKER_PROD_TEMPLATE.format(image_name=submodule))
        print(f"  ✓ Updated docker-prod.yml")
    
    print(f"\nSuccessfully updated {len(NEXTJS_SUBMODULES)} Next.js submodules!")


if __name__ == "__main__":
    update_workflows()
