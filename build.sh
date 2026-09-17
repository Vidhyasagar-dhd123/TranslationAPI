#!/usr/bin/env bash
# Exit immediately if a command exits with a non-zero status
set -o errexit

echo "==> Upgrading pip..."
pip install --upgrade pip

echo "==> Installing PyTorch (CPU version)..."
pip install torch --extra-index-url https://download.pytorch.org/whl/cpu

echo "==> Installing project dependencies..."
pip install -r requirements.txt

echo "==> Downloading NLTK models..."
python -c "import nltk; nltk.download('punkt'); nltk.download('punkt_tab', quiet=True)"

echo "==> Collecting static files..."
python manage.py collectstatic --no-input

echo "==> Running database migrations..."
python manage.py migrate --no-input

echo "==> Build completed successfully!"
