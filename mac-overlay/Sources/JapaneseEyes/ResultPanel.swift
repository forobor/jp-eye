import AppKit
import WebKit

/// Small floating window that shows breakdowns, newest on top. It doesn't take focus from the game.
/// The page itself is served by the brain (GET /panel), so its design changes without rebuilding this app.
final class ResultPanel: NSObject, WKNavigationDelegate {
    let panel: NSPanel
    private let web: WKWebView
    private let pageURL: URL
    private var ready = false
    private var queued: [String] = []

    init(brainBase: URL) {
        pageURL = brainBase.appendingPathComponent("panel")
        panel = NSPanel(contentRect: NSRect(x: 0, y: 0, width: 560, height: 720),
                        styleMask: [.titled, .closable, .resizable, .utilityWindow, .nonactivatingPanel],
                        backing: .buffered, defer: false)
        panel.title = "Japanese Eyes"
        // above the scan overlay (.screenSaver), so results show up even while it's open
        panel.level = NSWindow.Level(rawValue: NSWindow.Level.screenSaver.rawValue + 1)
        panel.isFloatingPanel = true
        panel.hidesOnDeactivate = false
        panel.isReleasedWhenClosed = false
        panel.collectionBehavior = [.canJoinAllSpaces, .fullScreenAuxiliary]
        web = WKWebView(frame: panel.contentView!.bounds)
        web.autoresizingMask = [.width, .height]
        super.init()
        web.navigationDelegate = self
        panel.contentView!.addSubview(web)
        web.load(URLRequest(url: pageURL))
        if !panel.setFrameUsingName("JapaneseEyesPanel"), let s = NSScreen.main?.visibleFrame {
            panel.setFrameOrigin(NSPoint(x: s.maxX - 580, y: s.maxY - 740))
        }
        panel.setFrameAutosaveName("JapaneseEyesPanel")
    }

    func show() {
        if !ready { web.load(URLRequest(url: pageURL)) }
        panel.orderFrontRegardless()
    }

    func addPending(id: Int, thumb: Data?, text: String) {
        js("addPending(\(id), \(q(thumb?.base64EncodedString() ?? "")), \(q(text)))")
    }
    /// The page streams the job's stages from the brain itself.
    func follow(id: Int, job: String) { js("follow(\(id), \(q(job)))") }
    func setError(id: Int, msg: String) { js("setError(\(id), \(q(msg)))") }

    func webView(_ webView: WKWebView, didFinish navigation: WKNavigation!) {
        ready = true
        queued.forEach { web.evaluateJavaScript($0) }
        queued = []
    }

    func webView(_ webView: WKWebView, didFailProvisionalNavigation navigation: WKNavigation!,
                 withError error: Error) {
        ready = false   // brain not up yet: try again shortly
        DispatchQueue.main.asyncAfter(deadline: .now() + 2) { [weak self] in
            guard let self, !self.ready else { return }
            self.web.load(URLRequest(url: self.pageURL))
        }
    }

    private func js(_ s: String) { if ready { web.evaluateJavaScript(s) } else { queued.append(s) } }
    private func q(_ s: String) -> String {
        String(data: (try? JSONEncoder().encode(s)) ?? Data("\"\"".utf8), encoding: .utf8)!
    }
}
