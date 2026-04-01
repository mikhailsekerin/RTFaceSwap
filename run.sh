#!/bin/bash
# RTFaceSwap Launcher Script

cd "$(dirname "$0")"

echo "========================================="
echo "  RTFaceSwap - Real-Time Face Swapping"
echo "========================================="
echo ""
echo "Controls:"
echo "  Press '1' - Enable face swap mode"
echo "  Press '2' - Disable face swap mode"
echo "  Press 'q' - Quit"
echo ""
echo "Starting application..."
echo "========================================="
echo ""

# Activate virtual environment and run
source venv/bin/activate
python RTFaceSwap.py

echo ""
echo "Application closed."
