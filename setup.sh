#!/bin/bash
# =============================================================================
# ZIM GeoFence - Setup Script
# =============================================================================
# This script sets up the development environment for the ZIM GeoFence demo.
# Run this after cloning the repository.
#
# Usage: ./setup.sh [--skip-data]
#   --skip-data: Skip importing geofence data (useful if data already exists)
# =============================================================================

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Parse arguments
SKIP_DATA=false
for arg in "$@"; do
    case $arg in
        --skip-data)
            SKIP_DATA=true
            shift
            ;;
    esac
done

echo -e "${BLUE}"
echo "============================================================"
echo "        ZIM GeoFence - Development Setup"
echo "============================================================"
echo -e "${NC}"

# Check prerequisites
echo -e "${YELLOW}Checking prerequisites...${NC}"

# Check Python
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}Error: Python 3 is not installed.${NC}"
    echo "Please install Python 3.7+ and try again."
    exit 1
fi
PYTHON_VERSION=$(python3 --version 2>&1 | cut -d' ' -f2)
echo -e "  ${GREEN}✓${NC} Python $PYTHON_VERSION"

# Check Node.js
if ! command -v node &> /dev/null; then
    echo -e "${RED}Error: Node.js is not installed.${NC}"
    echo "Please install Node.js 16+ and try again."
    exit 1
fi
NODE_VERSION=$(node --version)
echo -e "  ${GREEN}✓${NC} Node.js $NODE_VERSION"

# Check npm
if ! command -v npm &> /dev/null; then
    echo -e "${RED}Error: npm is not installed.${NC}"
    exit 1
fi
NPM_VERSION=$(npm --version)
echo -e "  ${GREEN}✓${NC} npm $NPM_VERSION"

echo ""

# =============================================================================
# Step 1: Create Python virtual environment
# =============================================================================
echo -e "${YELLOW}Step 1: Setting up Python virtual environment...${NC}"

if [ ! -d "venv" ]; then
    python3 -m venv venv
    echo -e "  ${GREEN}✓${NC} Virtual environment created"
else
    echo -e "  ${GREEN}✓${NC} Virtual environment already exists"
fi

# Activate virtual environment
source venv/bin/activate
echo -e "  ${GREEN}✓${NC} Virtual environment activated"

# =============================================================================
# Step 2: Install Python dependencies
# =============================================================================
echo -e "${YELLOW}Step 2: Installing Python dependencies...${NC}"

pip install --upgrade pip -q
pip install -r requirements.txt -q
echo -e "  ${GREEN}✓${NC} Root dependencies installed"

pip install -r app/backend/requirements.txt -q
echo -e "  ${GREEN}✓${NC} Backend dependencies installed"

echo ""

# =============================================================================
# Step 3: Install Node.js dependencies
# =============================================================================
echo -e "${YELLOW}Step 3: Installing Node.js dependencies...${NC}"

cd app/frontend
npm install --silent
cd ../..
echo -e "  ${GREEN}✓${NC} Frontend dependencies installed"

echo ""

# =============================================================================
# Step 4: Setup environment file
# =============================================================================
echo -e "${YELLOW}Step 4: Setting up environment configuration...${NC}"

if [ ! -f ".env" ]; then
    cp .env.example .env
    echo -e "  ${GREEN}✓${NC} Created .env file from .env.example"
    echo -e "  ${YELLOW}!${NC} Please edit .env with your MongoDB connection string"
else
    echo -e "  ${GREEN}✓${NC} .env file already exists"
fi

echo ""

# =============================================================================
# Step 5: Import geofence data (optional)
# =============================================================================
if [ "$SKIP_DATA" = false ]; then
    echo -e "${YELLOW}Step 5: Importing Zim geofence data...${NC}"

    # Check if Zim Data folder exists
    if [ -d "Zim Data" ] && [ -f "Zim Data/Geofences.geojson" ]; then
        echo "  Importing geofences from Zim Data/Geofences.geojson..."
        python3 simulator/import_geofences.py 2>/dev/null || {
            echo -e "  ${YELLOW}!${NC} Could not import geofences (MongoDB may not be running)"
            echo -e "  ${YELLOW}!${NC} Run 'python3 simulator/import_geofences.py' later"
        }
    else
        echo -e "  ${YELLOW}!${NC} Zim Data folder not found - skipping geofence import"
        echo -e "  ${YELLOW}!${NC} Place Geofences.geojson in 'Zim Data/' folder and run:"
        echo -e "      python3 simulator/import_geofences.py"
    fi
else
    echo -e "${YELLOW}Step 5: Skipping data import (--skip-data flag)${NC}"
fi

echo ""

# =============================================================================
# Setup Complete
# =============================================================================
echo -e "${GREEN}"
echo "============================================================"
echo "        Setup Complete!"
echo "============================================================"
echo -e "${NC}"

echo -e "To start the application, open ${YELLOW}two terminals${NC}:"
echo ""
echo -e "${BLUE}Terminal 1 - Backend:${NC}"
echo "  source venv/bin/activate"
echo "  cd app/backend && python main_zim.py"
echo ""
echo -e "${BLUE}Terminal 2 - Frontend:${NC}"
echo "  cd app/frontend && npm run dev"
echo ""
echo -e "${BLUE}Optional - Run Simulator:${NC}"
echo "  source venv/bin/activate"
echo "  python3 simulator/simulator.py -n 50 -s 3600"
echo ""
echo -e "Then open ${GREEN}http://localhost:3000${NC} in your browser."
echo ""
echo -e "${YELLOW}Note:${NC} Make sure MongoDB is running before starting the backend."
echo ""
