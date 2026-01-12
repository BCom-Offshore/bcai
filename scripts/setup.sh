#!/bin/bash

echo "Setting up BCom AI Services API..."

if [ ! -f .env ]; then
    echo "Creating .env file from .env.example..."
    cp .env.example .env
    echo "Please update .env file with your database credentials"
fi

echo "Creating virtual environment..."
python3.12 -m venv venv

echo "Activating virtual environment..."
source venv/bin/activate

echo "Installing dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

echo "Setup complete!"
echo "To start the server:"
echo "  1. Activate virtual environment: source venv/bin/activate"
echo "  2. Update .env file with your credentials"
echo "  3. Run: python run.py"
