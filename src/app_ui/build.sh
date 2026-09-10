#!/bin/bash
set -e

echo "Building Sentiva Chat Frontend..."
cd "$(dirname "$0")/frontend"

echo "Installing dependencies..."
npm ci

echo "Building with Vite..."
npm run build

echo "Build complete! Frontend output in: ./dist"
