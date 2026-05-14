#!/bin/bash
# pre-push-check.sh — GitHub Policy: Security checks before push
# Usage: .claude/scripts/pre-push-check.sh [remote] [branch]
# This script prevents pushing secrets, tokens, and sensitive files to GitHub

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
REMOTE="${1:-origin}"
BRANCH="${2:-HEAD}"
MAX_FILE_SIZE=$((100 * 1024 * 1024))  # 100MB
CHECKS_PASSED=0
CHECKS_FAILED=0

echo "🔒 GitHub Policy: Pre-Push Security Check"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Remote: $REMOTE"
echo "Branch: $BRANCH"
echo ""

# Function to print results
print_check() {
    local name="$1"
    local status="$2"
    local message="${3:-}"

    if [ "$status" = "PASS" ]; then
        echo -e "${GREEN}✅ PASS${NC} — $name"
        CHECKS_PASSED=$((CHECKS_PASSED + 1))
    else
        echo -e "${RED}❌ FAIL${NC} — $name"
        if [ -n "$message" ]; then
            echo "   $message"
        fi
        CHECKS_FAILED=$((CHECKS_FAILED + 1))
    fi
}

# Check 1: Detect API keys and tokens
check_secrets() {
    echo "1️⃣  Scanning for API keys and tokens..."

    local patterns=(
        "sk_[a-zA-Z0-9]"          # Stripe keys
        "gsk_[a-zA-Z0-9]"         # Groq API
        "re_[a-zA-Z0-9]"          # Resend API
        "AAH[a-zA-Z0-9]"          # Telegram-like tokens
        "BEGIN.*PRIVATE.*KEY"      # Private keys
        "-----BEGIN CERTIFICATE"   # Certificates
    )

    local found_secrets=0
    local staged_files=$(git diff --cached --name-only)

    for file in $staged_files; do
        # Skip binary files
        if file "$file" | grep -q "binary"; then
            continue
        fi

        for pattern in "${patterns[@]}"; do
            if grep -E "$pattern" "$file" 2>/dev/null; then
                echo -e "   ${RED}Found potential secret in: $file${NC}"
                grep -n "$pattern" "$file" 2>/dev/null | head -3 || true
                found_secrets=1
            fi
        done
    done

    if [ $found_secrets -eq 0 ]; then
        print_check "API keys/tokens detection" "PASS"
    else
        print_check "API keys/tokens detection" "FAIL" "Potential secrets found in staged files. Remove them before pushing."
    fi
}

# Check 2: Detect credential patterns
check_credentials() {
    echo ""
    echo "2️⃣  Scanning for hardcoded credentials..."

    local staged_files=$(git diff --cached --name-only)
    local found_creds=0

    for file in $staged_files; do
        # Skip non-text files
        if ! file "$file" | grep -q "text\|source\|JSON"; then
            continue
        fi

        # Look for password/api_key assignments
        if { grep -i "password.*=\|api.?key.*=\|secret.*=" "$file" 2>/dev/null || true; } | grep -qv "password.*()"; then
            echo -e "   ${YELLOW}⚠️  Possible credential in: $file${NC}"
            found_creds=1
        fi
    done

    if [ $found_creds -eq 0 ]; then
        print_check "Hardcoded credentials detection" "PASS"
    else
        print_check "Hardcoded credentials detection" "FAIL" "Review potential credential assignments (they should use env vars, not hardcoding)"
    fi
}

# Check 3: Verify .gitignore excludes sensitive files
check_gitignore() {
    echo ""
    echo "3️⃣  Verifying .gitignore configuration..."

    local required_ignores=(
        ".env"
        ".secret"
        "*.key"
        "*.pem"
        "__pycache__"
        "node_modules"
        "*.db"
    )

    local missing=0

    for pattern in "${required_ignores[@]}"; do
        if ! grep -q "^$pattern" .gitignore 2>/dev/null; then
            echo -e "   ${YELLOW}⚠️  Missing in .gitignore: $pattern${NC}"
            missing=1
        fi
    done

    if [ $missing -eq 0 ]; then
        print_check ".gitignore coverage" "PASS"
    else
        print_check ".gitignore coverage" "FAIL" "Add missing patterns to .gitignore"
    fi
}

# Check 4: Detect large files
check_large_files() {
    echo ""
    echo "4️⃣  Scanning for large files..."

    local staged_files=$(git diff --cached --name-only)
    local found_large=0

    for file in $staged_files; do
        if [ -f "$file" ]; then
            local size=$(stat -f%z "$file" 2>/dev/null || stat -c%s "$file" 2>/dev/null)
            if [ "$size" -gt "$MAX_FILE_SIZE" ]; then
                echo -e "   ${RED}Large file ($(($size / 1024 / 1024))MB): $file${NC}"
                found_large=1
            fi
        fi
    done

    if [ $found_large -eq 0 ]; then
        print_check "Large file detection" "PASS"
    else
        print_check "Large file detection" "FAIL" "Files over 100MB should not be committed. Use Git LFS or exclude them."
    fi
}

# Check 5: Verify no cache/temp files
check_caches() {
    echo ""
    echo "5️⃣  Scanning for cache and temp files..."

    local staged_files=$(git diff --cached --name-only)
    local cache_patterns=(
        "__pycache__"
        ".pytest_cache"
        "node_modules"
        ".next/cache"
        "*.pyc"
        "*.tmp"
        ".DS_Store"
    )

    local found_cache=0

    for file in $staged_files; do
        for pattern in "${cache_patterns[@]}"; do
            if [[ "$file" == *"$pattern"* ]]; then
                echo -e "   ${YELLOW}⚠️  Cache/temp file: $file${NC}"
                found_cache=1
            fi
        done
    done

    if [ $found_cache -eq 0 ]; then
        print_check "Cache/temp file detection" "PASS"
    else
        print_check "Cache/temp file detection" "FAIL" "Remove cache and temporary files from staging"
    fi
}

# Run all checks
check_secrets
check_credentials
check_gitignore
check_large_files
check_caches

# Summary
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Summary: ${GREEN}$CHECKS_PASSED passed${NC}, ${RED}$CHECKS_FAILED failed${NC}"
echo ""

if [ $CHECKS_FAILED -eq 0 ]; then
    echo -e "${GREEN}✅ All checks passed. Safe to push.${NC}"
    exit 0
else
    echo -e "${RED}❌ Pre-push checks failed. Fix issues before pushing.${NC}"
    echo ""
    echo "Actions:"
    echo "1. Remove secrets/credentials from staged files"
    echo "2. Update .gitignore if needed"
    echo "3. Remove large files (>100MB)"
    echo "4. Exclude cache/temp files"
    echo "5. Run: git reset HEAD <file> to unstage"
    echo "6. After fixing, stage again and retry push"
    exit 1
fi
