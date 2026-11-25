import AppKit

// Menu-bar app: no Dock icon. Press ⌃⌥J to scan the screen under the mouse.
let app = NSApplication.shared
let delegate = AppDelegate()
app.delegate = delegate
app.setActivationPolicy(.accessory)
app.run()
