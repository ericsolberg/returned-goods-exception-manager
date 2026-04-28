#!/bin/bash
# Script to install dependencies for App Foundation agent
# This script runs pip install and provides clear progress feedback
# DO NOT INTERRUPT - the script will indicate when complete

set -e

echo "=========================================="
echo "  App Foundation Dependencies Installer"
echo "=========================================="
echo ""

# Check Python version (requires 3.13+)
PYTHON_CMD="${PYTHON:-python3}"
PYTHON_VERSION=$("$PYTHON_CMD" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
REQUIRED_VERSION="3.13"

version_ge() {
    printf '%s\n%s' "$2" "$1" | sort -V -C
}

if ! version_ge "$PYTHON_VERSION" "$REQUIRED_VERSION"; then
    echo "ERROR: Python $REQUIRED_VERSION+ is required, but found Python $PYTHON_VERSION"
    echo ""
    echo "Solutions:"
    echo "  1. Install Python 3.13+ and ensure it's in your PATH"
    echo "  2. Specify the correct Python executable:"
    echo "     PYTHON=python3.13 bash install_deps.sh"
    echo "     PYTHON=/usr/local/bin/python3.13 bash install_deps.sh"
    echo ""
    echo "To check available Python versions:"
    echo "  which python3.13"
    echo "  ls /usr/local/bin/python*"
    exit 1
fi

echo "Python version: $PYTHON_VERSION ✓"
echo ""

# Find the project root (where requirements.txt is)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# Navigate up to find project root (works with any skills directory structure)
PROJECT_ROOT="$SCRIPT_DIR"
while [[ ! -f "$PROJECT_ROOT/requirements.txt" && "$PROJECT_ROOT" != "/" ]]; do
    PROJECT_ROOT="$(dirname "$PROJECT_ROOT")"
done

# Check if we're in a project with requirements.txt
if [[ ! -f "$PROJECT_ROOT/requirements.txt" ]]; then
    # Try current directory
    if [[ -f "requirements.txt" ]]; then
        PROJECT_ROOT="$(pwd)"
    else
        echo "ERROR: requirements.txt not found"
        echo "Please run this script from the project root directory"
        exit 1
    fi
fi

cd "$PROJECT_ROOT"
echo "Project root: $PROJECT_ROOT"

# Setup virtual environment
VENV_DIR=".venv"
if [[ ! -d "$VENV_DIR" ]]; then
    echo "Creating virtual environment with Python $PYTHON_VERSION..."
    "$PYTHON_CMD" -m venv "$VENV_DIR"
    echo "Virtual environment created at: $PROJECT_ROOT/$VENV_DIR"
else
    # Check existing venv Python version
    VENV_PYTHON_VERSION=$("$PROJECT_ROOT/$VENV_DIR/bin/python" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
    if ! version_ge "$VENV_PYTHON_VERSION" "$REQUIRED_VERSION"; then
        echo "WARNING: Existing venv uses Python $VENV_PYTHON_VERSION (requires $REQUIRED_VERSION+)"
        echo "Recreating virtual environment..."
        rm -rf "$VENV_DIR"
        "$PYTHON_CMD" -m venv "$VENV_DIR"
        echo "Virtual environment recreated at: $PROJECT_ROOT/$VENV_DIR"
    else
        echo "Using existing virtual environment: $PROJECT_ROOT/$VENV_DIR (Python $VENV_PYTHON_VERSION)"
    fi
fi

# Enforce SAP PyPI proxy via pip.conf in the virtualenv
# This ensures any pip install within this venv uses only the SAP proxy
PIP_CONF="$PROJECT_ROOT/$VENV_DIR/pip.conf"
if [[ ! -f "$PIP_CONF" ]]; then
    cat > "$PIP_CONF" <<'PIPCONF'
[global]
index-url = https://int.repositories.cloud.sap/artifactory/api/pypi/proxy-3rd-party-pypi/simple
trusted-host = int.repositories.cloud.sap
PIPCONF
    echo "Created pip.conf in virtualenv (SAP proxy enforced)"
fi

# Use the venv's pip directly (no need to source activate)
PIP_CMD="$PROJECT_ROOT/$VENV_DIR/bin/pip"
PYTHON_CMD="$PROJECT_ROOT/$VENV_DIR/bin/python"

echo "Python: $PYTHON_CMD"
echo "Pip: $PIP_CMD"

echo ""
echo "=========================================="
echo "  Starting pip install..."
echo "  This will take 3-5 minutes."
echo "  DO NOT INTERRUPT - wait for completion."
echo "=========================================="
echo ""

# Create a log file for the installation
LOG_FILE="/tmp/pip_install_$$.log"

# Run pip install using the venv's pip directly
"$PIP_CMD" install -r requirements.txt \
    --index-url "https://int.repositories.cloud.sap/artifactory/api/pypi/proxy-3rd-party-pypi/simple" \
    --progress-bar on \
    2>&1 | tee "$LOG_FILE"

# Check if installation succeeded
if [[ ${PIPESTATUS[0]} -eq 0 ]]; then
    echo ""
    echo "=========================================="
    echo "  SUCCESS! Dependencies installed."
    echo "=========================================="
    echo ""
    echo "Next step: Run the agent:"
    echo ""
    echo "  export \$(grep -v '^#' app/.env.local | xargs) && .venv/bin/python app/main.py --host 0.0.0.0 --port 9000"
    echo ""
    rm -f "$LOG_FILE"
    exit 0
else
    echo ""
    echo "=========================================="
    echo "  FAILED! See errors above."
    echo "=========================================="
    echo "Log saved to: $LOG_FILE"
    exit 1
fi
