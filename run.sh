#!/bin/bash
cd "$(dirname "$0")"

if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt
else
    source venv/bin/activate
fi

echo ""
echo "  RS Dragonwilds Save Editor"
echo "  =========================="
echo "  Open http://localhost:5000 in your browser"
echo ""

python app.py
