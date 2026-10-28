#!/bin/bash
set -euo pipefail

echo "=== WellPoint Clinic: Vercel Static Build ==="

# 1. Create an isolated virtual environment to adhere to PEP 668
echo "Creating isolated virtual environment (.venv)..."
python3 -m venv .venv

# 2. Activate the virtual environment
echo "Activating virtual environment..."
source .venv/bin/activate

# 3. Upgrade pip and install application dependencies
echo "Installing application dependencies from requirements.txt..."
pip install --upgrade pip
pip install -r requirements.txt

# 4. Run Django static asset collection
echo "Collecting static assets..."
python manage.py collectstatic --noinput --clear

echo "=== Static Build Completed Successfully ==="
