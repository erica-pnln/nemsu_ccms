#!/bin/bash
echo "Installing Python dependencies..."
pip install -r requirements.txt

echo "Creating upload directory..."
mkdir -p static/uploads

echo "Build completed successfully!"
