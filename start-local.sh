#!/bin/bash
# Start NDK Dashboard locally for development

set -e

echo "=========================================="
echo "NDK Dashboard - Local Development"
echo "=========================================="
echo ""

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "✗ Python 3 not found. Please install Python 3.11+"
    exit 1
fi

echo "✓ Python found: $(python3 --version)"

# Check kubectl
if ! command -v kubectl &> /dev/null; then
    echo "✗ kubectl not found. Please install kubectl"
    exit 1
fi

echo "✓ kubectl found"

# Check cluster connectivity
if ! kubectl cluster-info &> /dev/null; then
    echo "✗ Cannot connect to Kubernetes cluster"
    echo "Please configure kubectl to connect to your cluster"
    exit 1
fi

echo "✓ Connected to Kubernetes cluster"
echo ""

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
    echo "✓ Virtual environment created"
fi

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate

# Install dependencies
echo "Installing dependencies..."
pip install -q --upgrade pip
pip install -q -r requirements.txt
echo "✓ Dependencies installed"
echo ""

# Check .env file
if [ ! -f ".env" ]; then
    echo "⚠ .env file not found. Using defaults."
fi

echo "=========================================="
echo "Starting NDK Dashboard..."
echo "=========================================="
echo ""
echo "Dashboard will be available at: http://localhost:5000"
echo "Default credentials: admin / admin"
echo ""
echo "Press Ctrl+C to stop"
echo ""

# Start the application
python run.py