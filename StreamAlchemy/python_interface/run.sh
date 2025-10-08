#!/bin/bash

# StreamAlchemy Unix/Linux/macOS Launcher
# This script sets up and runs StreamAlchemy on Unix-like systems

echo "StreamAlchemy Unix/macOS Launcher"
echo "================================="

# Get the absolute path of the directory this script resides in
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR" || exit 1

# Check if Python is available
if ! command -v python3 &> /dev/null; then
    echo "Error: Python 3 is not installed or not in PATH"
    echo "Please install Python 3.8+ and try again"
    exit 1
fi

# Check if FFmpeg is available
if ! command -v ffmpeg &> /dev/null; then
    echo "Error: FFmpeg is not installed or not in PATH"
    echo "Please install FFmpeg and try again"
    exit 1
fi

# Check if yt-dlp is available (optional)
if ! command -v yt-dlp &> /dev/null; then
    echo "Warning: yt-dlp not found. YouTube support will be limited."
fi

# Attempt to free up port 5000
echo "Freeing up port 5000..."
if command -v lsof &> /dev/null; then
    # Use lsof (more reliable than fuser)
    PIDS=$(lsof -ti :5000)
    if [ ! -z "$PIDS" ]; then
        echo "Killing processes on port 5000: $PIDS"
        echo "$PIDS" | xargs kill -9 2>/dev/null
    fi
elif command -v fuser &> /dev/null; then
    fuser -k 5000/tcp 2>/dev/null
else
    echo "Warning: Cannot automatically free port 5000. Please ensure it's available."
fi
sleep 1

VENV_DIR="venv"

# Check if venv exists, if not create it
if [ ! -d "$VENV_DIR" ]; then
    echo "Creating virtual environment in $VENV_DIR..."
    python3 -m venv "$VENV_DIR"
    if [ $? -ne 0 ]; then
        echo "Failed to create virtual environment. Please ensure python3-venv is installed."
        exit 1
    fi
else
    echo "Virtual environment in $VENV_DIR already exists."
fi

# Install dependencies using the venv's pip
echo "Installing dependencies..."
"$VENV_DIR/bin/pip" install -r requirements.txt
if [ $? -ne 0 ]; then
    echo "Failed to install dependencies."
    exit 1
fi

# Run the Flask app using the venv's python
echo "Running the Flask app..."
# Use exec to replace the shell process with Python so signals are handled properly
exec "$VENV_DIR/bin/python3" app.py 