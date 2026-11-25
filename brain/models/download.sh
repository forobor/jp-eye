#!/bin/zsh
# Download the manga text-block detector (comic-text-detector, ~95 MB) used by brain/ocr.py.
# Source: https://github.com/zyddnys/manga-image-translator (release beta-0.3)
set -e
cd "$(dirname "$0")"
curl -L --fail -o comictextdetector.pt.onnx \
  https://github.com/zyddnys/manga-image-translator/releases/download/beta-0.3/comictextdetector.pt.onnx
echo "Saved $(pwd)/comictextdetector.pt.onnx"
