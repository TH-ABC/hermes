#!/usr/bin/env python3
"""
Setup GitHub -> Vercel CI/CD Pipeline Manager
Automates setting up the new GitHub repository and pushing the clean codebase
so Vercel deploys automatically via standard Git Integration.
"""

import os
import sys
sys.stdout.reconfigure(encoding='utf-8')
import subprocess
from pathlib import Path

VERCEL_DIR = Path("D:/hermes-main/hermes-agent-vercel")


def setup_git_repo_and_push(repo_url: str, github_token: str, branch: str = "main"):
    """
    Configures git credentials, sets the remote origin, and pushes code to the new repo.
    """
    if not repo_url or not github_token:
        print("❌ Error: repo_url and github_token are required!")
        return False

    # Normalize repo_url: strip https:// and add token
    clean_url = repo_url.replace("https://", "").replace("http://", "").strip()
    if clean_url.endswith("/"):
        clean_url = clean_url[:-1]
    
    # Authenticated remote URL
    auth_remote_url = f"https://oauth2:{github_token}@{clean_url}"

    print(f"🚀 Initializing Git repository in: {VERCEL_DIR}")
    os.chdir(VERCEL_DIR)

    # Git init if needed
    if not (VERCEL_DIR / ".git").exists():
        subprocess.run(["git", "init"], check=True)
        print("✅ Git init completed.")

    # Configure user info
    subprocess.run(["git", "config", "user.name", "Hermes Agent"], check=True)
    subprocess.run(["git", "config", "user.email", "admin@sever-hermes.local"], check=True)

    # Set remote origin
    remotes = subprocess.run(["git", "remote"], capture_output=True, text=True).stdout.split()
    if "origin" in remotes:
        subprocess.run(["git", "remote", "set-url", "origin", auth_remote_url], check=True)
    else:
        subprocess.run(["git", "remote", "add", "origin", auth_remote_url], check=True)
    print("✅ Remote origin set to new GitHub repository.")

    # Stage and commit
    subprocess.run(["git", "add", "."], check=True)
    subprocess.run(["git", "commit", "-m", "Deploy: Standardize BE/FE Architecture & Dashboard Suite"], check=False)

    # Push to branch
    print(f"📦 Pushing to {branch}...")
    res = subprocess.run(["git", "push", "-u", "origin", f"HEAD:{branch}", "--force"], capture_output=True, text=True)
    if res.returncode == 0:
        print("🎉 PUSH SUCCESSFUL! Vercel will now auto-deploy from GitHub.")
        return True
    else:
        print(f"❌ Git push failed: {res.stderr}")
        return False


if __name__ == "__main__":
    if len(sys.argv) >= 3:
        repo = sys.argv[1]
        token = sys.argv[2]
        setup_git_repo_and_push(repo, token)
    else:
        print("Usage: python setup_github_vercel_cicd.py <REPO_URL> <GITHUB_TOKEN>")
