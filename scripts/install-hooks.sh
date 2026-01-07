#!/bin/bash
#
# Install Git hooks for Tennis Predictions
#
# This script installs the pre-push hook that:
# - Runs all tests before pushing
# - Checks for leaked secrets
#

set -e

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}Installing Git hooks...${NC}"
echo ""

# Get the root directory of the git repo
ROOT_DIR=$(git rev-parse --show-toplevel 2>/dev/null)

if [ -z "$ROOT_DIR" ]; then
    echo "Error: Not in a git repository"
    exit 1
fi

cd "$ROOT_DIR"

# Check if hooks directory exists
if [ ! -d ".git/hooks" ]; then
    echo "Error: .git/hooks directory not found"
    exit 1
fi

# Install pre-push hook
echo "Installing pre-push hook..."
cp scripts/pre-push .git/hooks/pre-push
chmod +x .git/hooks/pre-push

echo ""
echo -e "${GREEN}✓ Git hooks installed successfully!${NC}"
echo ""
echo "The following hooks are now active:"
echo "  • pre-push: Validates tests and checks for secrets"
echo ""
echo "To bypass hooks (emergency only): git push --no-verify"
echo ""

