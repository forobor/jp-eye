import AppKit

/// Borderless full-screen window above everything (including full-screen games).
final class OverlayWindow: NSWindow {
    override var canBecomeKey: Bool { true }
    override var canBecomeMain: Bool { true }
}

/// Shows the frozen screenshot, outlines detected Japanese lines, and lets you
/// click a line or drag a box. Esc, right-click or clicking empty space closes it.
final class OverlayView: NSView {
    let image: CGImage
    var lines: [TextLine] = [] { didSet { needsDisplay = true } }
    var status = "Finding Japanese text…" { didSet { needsDisplay = true } }
    /// rect in image pixels, OCR text ("" for a dragged box), keepOpen = Shift held (pick several)
    var onPick: ((CGRect, String, Bool) -> Void)?
    var onCancel: (() -> Void)?

    private var dragStart: NSPoint?
    private var dragRect: NSRect?
    private var hover: Int?
    private var picked: [NSRect] = []

    init(frame: NSRect, image: CGImage) {
        self.image = image
        super.init(frame: frame)
    }
    required init?(coder: NSCoder) { fatalError() }

    override var isFlipped: Bool { true }            // top-left origin, same as image pixels
    override var acceptsFirstResponder: Bool { true }
    override func acceptsFirstMouse(for event: NSEvent?) -> Bool { true }

    private var pxPerPt: CGFloat { CGFloat(image.width) / bounds.width }

    private func rectPt(_ l: TextLine) -> NSRect {
        let s = pxPerPt
        return NSRect(x: l.box[0] / s, y: l.box[1] / s, width: l.box[2] / s, height: l.box[3] / s)
            .insetBy(dx: -4, dy: -4)
    }

    private func hit(_ p: NSPoint) -> Int? { lines.firstIndex { rectPt($0).contains(p) } }

    override func updateTrackingAreas() {
        super.updateTrackingAreas()
        trackingAreas.forEach(removeTrackingArea)
        addTrackingArea(NSTrackingArea(rect: bounds, options: [.mouseMoved, .activeAlways, .inVisibleRect],
                                       owner: self))
    }

    override func draw(_ dirtyRect: NSRect) {
        guard let ctx = NSGraphicsContext.current?.cgContext else { return }
        ctx.saveGState()
        ctx.translateBy(x: 0, y: bounds.height)
        ctx.scaleBy(x: 1, y: -1)
        ctx.draw(image, in: CGRect(origin: .zero, size: bounds.size))
        ctx.restoreGState()
        NSColor.black.withAlphaComponent(0.25).setFill()
        bounds.fill()

        let accent = NSColor.systemOrange
        for (i, l) in lines.enumerated() {
            let p = NSBezierPath(roundedRect: rectPt(l), xRadius: 4, yRadius: 4)
            accent.withAlphaComponent(i == hover ? 0.35 : 0.10).setFill()
            p.fill()
            accent.setStroke()
            p.lineWidth = 2
            p.stroke()
        }
        for r in picked {
            let p = NSBezierPath(roundedRect: r, xRadius: 4, yRadius: 4)
            NSColor.systemGreen.withAlphaComponent(0.25).setFill()
            p.fill()
            NSColor.systemGreen.setStroke()
            p.lineWidth = 3
            p.stroke()
        }
        if let d = dragRect {
            let p = NSBezierPath(rect: d)
            p.lineWidth = 2
            p.setLineDash([6, 4], count: 2, phase: 0)
            accent.withAlphaComponent(0.15).setFill()
            p.fill()
            NSColor.white.setStroke()
            p.stroke()
        }

        let text = status as NSString
        let attrs: [NSAttributedString.Key: Any] = [.font: NSFont.systemFont(ofSize: 15, weight: .medium),
                                                    .foregroundColor: NSColor.white]
        let size = text.size(withAttributes: attrs)
        let pill = NSRect(x: (bounds.width - size.width) / 2 - 18, y: 44,
                          width: size.width + 36, height: size.height + 14)
        NSColor.black.withAlphaComponent(0.78).setFill()
        NSBezierPath(roundedRect: pill, xRadius: pill.height / 2, yRadius: pill.height / 2).fill()
        text.draw(at: NSPoint(x: pill.minX + 18, y: pill.minY + 7), withAttributes: attrs)
    }

    override func mouseMoved(with e: NSEvent) {
        let h = hit(convert(e.locationInWindow, from: nil))
        if h != hover { hover = h; needsDisplay = true }
    }

    override func mouseDown(with e: NSEvent) {
        dragStart = convert(e.locationInWindow, from: nil)
        dragRect = nil
    }

    override func mouseDragged(with e: NSEvent) {
        guard let s = dragStart else { return }
        let p = convert(e.locationInWindow, from: nil)
        dragRect = NSRect(x: min(s.x, p.x), y: min(s.y, p.y), width: abs(p.x - s.x), height: abs(p.y - s.y))
        needsDisplay = true
    }

    override func mouseUp(with e: NSEvent) {
        let p = convert(e.locationInWindow, from: nil)
        let keepOpen = e.modifierFlags.contains(.shift)
        defer { dragStart = nil; dragRect = nil; needsDisplay = true }
        if let d = dragRect, d.width > 8, d.height > 8 {
            let s = pxPerPt
            picked.append(d)
            onPick?(CGRect(x: d.minX * s, y: d.minY * s, width: d.width * s, height: d.height * s), "", keepOpen)
            return
        }
        if let i = hit(p) {
            let l = lines[i]
            picked.append(rectPt(l))
            onPick?(CGRect(x: l.box[0], y: l.box[1], width: l.box[2], height: l.box[3]), l.text, keepOpen)
            return
        }
        onCancel?()
    }

    override func rightMouseDown(with e: NSEvent) { onCancel?() }

    override func keyDown(with e: NSEvent) {
        if e.keyCode == 53 { onCancel?() } else { super.keyDown(with: e) }   // 53 = Esc
    }
}
