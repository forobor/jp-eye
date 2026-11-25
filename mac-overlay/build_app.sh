#!/bin/zsh
# Build "Japanese Eyes.app" next to this script.
set -e
cd "$(dirname "$0")"
swift build -c release
APP="Japanese Eyes.app"
rm -rf "$APP"
mkdir -p "$APP/Contents/MacOS"
cp .build/release/JapaneseEyes "$APP/Contents/MacOS/JapaneseEyes"
cat > "$APP/Contents/Info.plist" <<'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>CFBundleName</key><string>Japanese Eyes</string>
  <key>CFBundleDisplayName</key><string>Japanese Eyes</string>
  <key>CFBundleIdentifier</key><string>local.japanese-eyes</string>
  <key>CFBundleExecutable</key><string>JapaneseEyes</string>
  <key>CFBundlePackageType</key><string>APPL</string>
  <key>CFBundleShortVersionString</key><string>0.1</string>
  <key>CFBundleVersion</key><string>1</string>
  <key>LSMinimumSystemVersion</key><string>14.0</string>
  <key>LSUIElement</key><true/>
  <key>NSHighResolutionCapable</key><true/>
</dict></plist>
PLIST
codesign --force --sign - --identifier local.japanese-eyes "$APP"
echo "Built $(pwd)/$APP"
