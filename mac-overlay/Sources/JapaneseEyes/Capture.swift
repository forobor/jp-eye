import AppKit
import ScreenCaptureKit

enum Capture {
    static func screenUnderMouse() -> NSScreen {
        let p = NSEvent.mouseLocation
        return NSScreen.screens.first { NSMouseInRect(p, $0.frame, false) } ?? NSScreen.main!
    }

    /// Full-resolution screenshot of one display, without our own windows and without the cursor.
    static func capture(_ screen: NSScreen) async throws -> CGImage {
        let key = NSDeviceDescriptionKey("NSScreenNumber")
        let id = (screen.deviceDescription[key] as! NSNumber).uint32Value
        let content = try await SCShareableContent.excludingDesktopWindows(false, onScreenWindowsOnly: true)
        guard let display = content.displays.first(where: { $0.displayID == id }) else {
            throw NSError(domain: "JapaneseEyes", code: 1,
                          userInfo: [NSLocalizedDescriptionKey: "Display not found"])
        }
        let me = ProcessInfo.processInfo.processIdentifier
        let mine = content.windows.filter { $0.owningApplication?.processID == me }
        let filter = SCContentFilter(display: display, excludingWindows: mine)
        let cfg = SCStreamConfiguration()
        let scale = screen.backingScaleFactor
        cfg.width = Int(CGFloat(display.width) * scale)
        cfg.height = Int(CGFloat(display.height) * scale)
        cfg.showsCursor = false
        return try await SCScreenshotManager.captureImage(contentFilter: filter, configuration: cfg)
    }

    static func png(_ img: CGImage) -> Data {
        NSBitmapImageRep(cgImage: img).representation(using: .png, properties: [:]) ?? Data()
    }
}
