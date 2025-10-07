#!/bin/bash
# Pre-deployment verification script
# Run this to verify the repository structure before deploying

echo "=== Repository Structure Verification ==="
echo

ERRORS=0

# Check directory structure
echo "[1/5] Checking directory structure..."
if [ ! -d "audio-receiver" ]; then
    echo "  ❌ ERROR: audio-receiver/ directory not found"
    ERRORS=$((ERRORS + 1))
else
    echo "  ✓ audio-receiver/ directory exists"
fi

if [ ! -d "web-ui" ]; then
    echo "  ❌ ERROR: web-ui/ directory not found"
    ERRORS=$((ERRORS + 1))
else
    echo "  ✓ web-ui/ directory exists"
fi

# Check required files
echo
echo "[2/5] Checking required files..."
REQUIRED_FILES=(
    "audio-receiver/receiver.py"
    "audio-receiver/requirements.txt"
    "audio-receiver/audio-receiver.service"
    "web-ui/app.py"
    "web-ui/requirements.txt"
    "web-ui/web-ui.service"
    "web-ui/templates/index.html"
    "web-ui/templates/date.html"
    "setup.sh"
    "deploy.sh"
    "cleanup-old-files.sh"
    "README.md"
)

for file in "${REQUIRED_FILES[@]}"; do
    if [ ! -f "$file" ]; then
        echo "  ❌ ERROR: Missing file: $file"
        ERRORS=$((ERRORS + 1))
    else
        echo "  ✓ $file"
    fi
done

# Check Python files for syntax errors
echo
echo "[3/5] Checking Python syntax..."
PYTHON_CMD=""
if command -v python3 &> /dev/null; then
    # Check if it's a real python and not a Windows stub
    if python3 --version &> /dev/null 2>&1; then
        PYTHON_CMD="python3"
    fi
elif command -v python &> /dev/null; then
    # Check if it's a real python and not a Windows stub
    if python --version &> /dev/null 2>&1; then
        PYTHON_CMD="python"
    fi
fi

if [ -n "$PYTHON_CMD" ]; then
    for pyfile in audio-receiver/receiver.py web-ui/app.py; do
        if $PYTHON_CMD -m py_compile "$pyfile" 2>&1 >/dev/null; then
            echo "  ✓ $pyfile syntax OK"
        else
            echo "  ❌ ERROR: Python syntax error in $pyfile"
            ERRORS=$((ERRORS + 1))
        fi
    done
else
    echo "  ⚠ INFO: Python not available, skipping syntax check (OK on non-Linux systems)"
fi

# Check shell scripts for syntax errors
echo
echo "[4/5] Checking shell script syntax..."
for script in setup.sh deploy.sh cleanup-old-files.sh; do
    if bash -n "$script" 2>/dev/null; then
        echo "  ✓ $script syntax OK"
    else
        echo "  ❌ ERROR: Syntax error in $script"
        ERRORS=$((ERRORS + 1))
    fi
done

# Check for execute permissions
echo
echo "[5/5] Checking execute permissions..."
for script in setup.sh deploy.sh cleanup-old-files.sh; do
    if [ -x "$script" ]; then
        echo "  ✓ $script is executable"
    else
        echo "  ⚠ WARNING: $script is not executable (run: chmod +x $script)"
    fi
done

# Summary
echo
echo "=== Verification Complete ==="
if [ $ERRORS -eq 0 ]; then
    echo "✓ All checks passed! Repository is ready for deployment."
    echo
    echo "Next steps:"
    echo "  1. Run: sudo bash setup.sh"
    echo "  2. Set environment variables:"
    echo "     export WEB_UI_USERNAME=\"admin\""
    echo "     export WEB_UI_PASSWORD=\"your-secure-password\""
    echo "  3. Run: sudo bash deploy.sh"
    exit 0
else
    echo "❌ Found $ERRORS error(s). Please fix them before deploying."
    exit 1
fi
