#!/bin/bash

# Get the absolute path of the directory this script resides in
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR" || exit 1

# Attempt to free up port 5000
if command -v fuser &> /dev/null
then
    echo "Attempting to free port 5000..."
    fuser -k 5000/tcp
    sleep 1 # Give a moment for the port to be released
else
    echo "fuser command not found, cannot automatically free port. Please ensure port 5000 is free."
fi

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