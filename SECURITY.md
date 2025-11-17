# Security Guide

## Protecting Secrets

This repository has been configured to prevent committing sensitive information. Follow these guidelines to keep your secrets safe.

### Configuration Files

**Never commit files containing real credentials:**
- `config.yaml` - Your local configuration (gitignored) - Put secrets here for local dev
- `.env` - Environment variables (gitignored)

**Safe to commit:**
- `config.example.yaml` - Example configuration with placeholders (no secrets)

### Environment Variables

The recommended way to configure secrets is via environment variables:

```bash
export FS_RPC_USER="your_rpc_username"
export FS_RPC_PASS="your_rpc_password"
export FS_SSH_SERVER="user@hostname"
```

You can also create a `.env` file (which is gitignored) and source it:

```bash
# .env file
FS_RPC_USER=your_rpc_username
FS_RPC_PASS=your_rpc_password
FS_SSH_SERVER=user@hostname

# Source it
source .env
```

### SSH Tunnel Configuration

SSH server information should be set via environment variables:

```bash
export SSH_SERVER="user@hostname"
# or
export FS_SSH_SERVER="user@hostname"
```

### Git History Cleanup

**IMPORTANT:** If you've already committed secrets to this repository, you must clean them from git history before making the repo public.

#### Option 1: Using git filter-repo (Recommended)

```bash
# Install git-filter-repo if needed
pip install git-filter-repo

# Remove secrets from history
git filter-repo --path config.yaml --invert-paths
git filter-repo --path scripts/common_calls.py --invert-paths
git filter-repo --path start_tunnel.sh --invert-paths
git filter-repo --path start_tunnel_bg.sh --invert-paths

# Force push (WARNING: This rewrites history)
git push origin --force --all
```

#### Option 2: Using BFG Repo-Cleaner

```bash
# Download BFG from https://rtyley.github.io/bfg-repo-cleaner/

# Create a file with secrets to remove
echo "jwkkwj1218" > passwords.txt
echo "joelwk" >> passwords.txt
echo "joel@10.0.0.251" >> passwords.txt

# Clean history
java -jar bfg.jar --replace-text passwords.txt

# Clean up and force push
git reflog expire --expire=now --all
git gc --prune=now --aggressive
git push origin --force --all
```

#### Option 3: Start Fresh (If history cleanup is too risky)

If you're not comfortable rewriting git history, consider:

1. Create a new repository
2. Copy only the files you want to make public
3. Make an initial commit
4. Update the remote URL

### Simplest Approach: Use Environment Variables

For production, use environment variables (no files to worry about):

```bash
export FS_RPC_USER="your_username"
export FS_RPC_PASS="your_password"
export SSH_SERVER="user@hostname"
```

For local development, since `config.yaml` is gitignored, you can put secrets directly in it.

### Rotating Compromised Secrets

If secrets have been exposed in git history:

1. **Immediately rotate all exposed credentials:**
   - Change Bitcoin RPC password
   - Rotate SSH keys if necessary
   - Update any webhook URLs if they contain tokens

2. **Clean git history** (see above)

3. **Verify cleanup:**
   ```bash
   git log --all --full-history -- config.yaml
   git log --all --full-history -- scripts/common_calls.py
   ```

### Logging Security

Logs may contain sensitive information. Ensure:
- Log files are in `.gitignore` (already configured)
- Log rotation is enabled (configured in `config.yaml`)
- Log levels are appropriate (avoid DEBUG in production)
- Logs are stored securely and not exposed publicly

### Pre-Public Checklist

Before making this repository public:

- [ ] All secrets removed from tracked files
- [ ] `.gitignore` includes all sensitive files
- [ ] `config.example.yaml` exists with safe defaults
- [ ] Git history cleaned of secrets (if previously committed)
- [ ] All exposed credentials rotated
- [ ] No hardcoded credentials in code
- [ ] Environment variable usage documented
- [ ] Logs directory is gitignored
- [ ] State files (databases) are gitignored

