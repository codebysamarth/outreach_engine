#!/bin/bash
# Setup Script for Outreach Engine (Linux/Mac)

echo "🚀 Outreach Engine - Setup Script"
echo "================================="
echo ""

# Check Python
echo "✓ Checking Python..."
python3 --version || { echo "❌ Python not found. Please install Python 3.11+"; exit 1; }

# Check Node
echo "✓ Checking Node.js..."
node --version || { echo "❌ Node.js not found. Please install Node.js 18+"; exit 1; }

# Check Docker
echo "✓ Checking Docker..."
docker --version || { echo "❌ Docker not found. Please install Docker"; exit 1; }

echo ""
echo "📦 Installing Python dependencies..."
pip install -r requirements.txt

echo ""
echo "📦 Installing frontend dependencies..."
cd frontend
npm install
cd ..

echo ""
echo "🐳 Starting Docker services..."
docker compose up -d

echo ""
echo "⏳ Waiting for services to start..."
sleep 10

echo ""
echo "🤖 Pulling Ollama model (this may take a few minutes)..."
docker exec -it outreach_ollama ollama pull mistral

echo ""
echo "🗄️ Running database migrations..."
alembic upgrade head

echo ""
echo "✅ Setup complete!"
echo ""
echo "To start the application:"
echo "  1. Backend:  python -m uvicorn app.api.main:app --reload --port 8080"
echo "  2. Frontend: cd frontend && npm run dev"
echo ""
echo "Then open: http://localhost:5173"
