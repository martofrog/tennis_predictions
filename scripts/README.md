# Git Hooks for Tennis Predictions

This directory contains Git hooks to ensure code quality and security before pushing to the repository.

## 🎯 Available Hooks

### Pre-Push Hook

The pre-push hook runs automatically before every `git push` and performs two critical checks:

1. **🧪 Test Validation**
   - Runs all pytest tests
   - Blocks push if any tests fail
   - Ensures code quality before sharing

2. **🔐 Secret Detection**
   - Scans for leaked API keys, tokens, and passwords
   - Checks common secret patterns:
     - API keys (OpenAI, Stripe, Google, AWS, etc.)
     - Authentication tokens
     - Private keys
     - Database URLs with credentials
     - Hardcoded passwords
   - Blocks push if secrets are detected

## 📦 Installation

### For New Developers

When cloning the repository for the first time, run:

```bash
./scripts/install-hooks.sh
```

This will install all hooks into your local `.git/hooks/` directory.

### Manual Installation

If you prefer to install manually:

```bash
cp scripts/pre-push .git/hooks/pre-push
chmod +x .git/hooks/pre-push
```

## 🚀 Usage

Once installed, the hooks run automatically:

```bash
git push origin main
```

Output example:
```
🔍 Pre-push validation starting...
=================================

📋 Step 1/2: Running tests...
---------------------------------
38 passed in 0.36s
✓ All tests passed

🔐 Step 2/2: Checking for leaked secrets...
---------------------------------
Scanning files for secrets...
✓ No secrets detected

=================================
✅ Pre-push validation passed!
=================================
```

## ⚠️ Bypassing Hooks (Emergency Only)

In rare cases where you need to push despite failing tests or detected secrets:

```bash
git push --no-verify
```

**⚠️ WARNING:** Only use `--no-verify` if you're absolutely sure it's safe!

## 🔧 Customization

### Adding Secret Pattern Exceptions

If you encounter false positives, edit `scripts/pre-push` and add patterns to skip:

```bash
# Around line 85, modify SKIP_PATTERNS
SKIP_PATTERNS="(\.git/|your_file_to_skip\.py)"
```

### Adding New Secret Patterns

To detect additional secret types, edit the `SECRET_PATTERNS` array in `scripts/pre-push`:

```bash
declare -a SECRET_PATTERNS=(
    # Your custom pattern here
    "your-secret-pattern-regex"
)
```

## 🐛 Troubleshooting

### Hook Not Running

1. Check if hook is installed:
   ```bash
   ls -la .git/hooks/pre-push
   ```

2. Ensure it's executable:
   ```bash
   chmod +x .git/hooks/pre-push
   ```

3. Reinstall:
   ```bash
   ./scripts/install-hooks.sh
   ```

### Tests Failing

Run tests locally to see detailed output:
```bash
bin/python -m pytest tests/ -v
```

### False Positive Secrets

If the hook incorrectly flags something as a secret:
1. Check if it's actually a secret (better safe than sorry!)
2. If it's truly a false positive, add it to the skip patterns
3. Document why it's safe in a comment

## 📚 Best Practices

1. **Never bypass hooks casually** - They protect your codebase
2. **Always use environment variables** for secrets - Never hardcode
3. **Keep .env files in .gitignore** - They should never be committed
4. **Rotate secrets immediately** if accidentally pushed
5. **Run tests locally** before committing to save time

## 🔗 Related Files

- `scripts/pre-push` - The actual hook script (committed to repo)
- `.git/hooks/pre-push` - Installed hook (not in repo)
- `scripts/install-hooks.sh` - Hook installation script
- `pytest.ini` - Test configuration
- `tests/` - Test suite

## 💡 Tips

- Run tests frequently during development: `bin/python -m pytest tests/ -v`
- Use `git push --dry-run` to simulate a push without actually pushing
- Keep your test suite fast so hooks don't slow you down
- Add more tests as you add features

## 🆘 Support

If you encounter issues with the hooks:
1. Check this README for solutions
2. Review the hook output for specific errors
3. Run tests and secret scans manually to debug
4. Ask the team for help if needed

---

**Remember:** These hooks are your friends, not obstacles. They catch issues early and keep the codebase secure! 🛡️



