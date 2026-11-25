import AppKit
import Carbon

final class AppDelegate: NSObject, NSApplicationDelegate {
    static var shared: AppDelegate!

    let brain = BrainClient(base: URL(string: "http://127.0.0.1:8765")!)
    lazy var panel = ResultPanel(brainBase: brain.base)
    private var statusItem: NSStatusItem!
    private var brainItem: NSMenuItem!
    private var brainProcess: Process?
    private var overlay: OverlayWindow?
    private var previousApp: NSRunningApplication?
    private var nextId = 0

    /// Folder with run_brain.sh, japanese.xlsx and grammar.md.
    /// Change with: defaults write local.japanese-eyes projectDir /path/to/folder
    let projectDir: URL = {
        if let p = UserDefaults.standard.string(forKey: "projectDir") { return URL(fileURLWithPath: p) }
        return FileManager.default.homeDirectoryForCurrentUser.appendingPathComponent("Documents/Japanese")
    }()

    func applicationDidFinishLaunching(_ notification: Notification) {
        Self.shared = self
        statusItem = NSStatusBar.system.statusItem(withLength: NSStatusItem.variableLength)
        statusItem.button?.title = "目"
        let menu = NSMenu()
        menu.addItem(withTitle: "Scan screen  (⌃⌥J)", action: #selector(scanAction), keyEquivalent: "")
        menu.addItem(withTitle: "Show results", action: #selector(showPanel), keyEquivalent: "")
        menu.addItem(.separator())
        brainItem = menu.addItem(withTitle: "Brain: checking…", action: nil, keyEquivalent: "")
        menu.addItem(withTitle: "Open spreadsheet", action: #selector(openSheet), keyEquivalent: "")
        menu.addItem(withTitle: "Open grammar notes", action: #selector(openGrammar), keyEquivalent: "")
        menu.addItem(.separator())
        menu.addItem(withTitle: "Quit Japanese Eyes", action: #selector(quit), keyEquivalent: "q")
        menu.items.forEach { $0.target = self }
        statusItem.menu = menu
        registerHotKey()
        Task { @MainActor in _ = await ensureBrain() }
    }

    func applicationWillTerminate(_ notification: Notification) {
        brainProcess?.terminate()
    }

    // MARK: brain

    /// Make sure the brain service is up; start run_brain.sh if it isn't.
    @MainActor func ensureBrain() async -> Bool {
        if await brain.health() { brainItem.title = "Brain: running"; return true }
        if brainProcess?.isRunning != true {
            let p = Process()
            p.executableURL = URL(fileURLWithPath: "/bin/zsh")
            p.arguments = [projectDir.appendingPathComponent("run_brain.sh").path]
            let log = FileManager.default.homeDirectoryForCurrentUser
                .appendingPathComponent("Library/Logs/JapaneseEyes-brain.log")
            FileManager.default.createFile(atPath: log.path, contents: nil)
            if let h = try? FileHandle(forWritingTo: log) { p.standardOutput = h; p.standardError = h }
            do { try p.run(); brainProcess = p } catch {
                brainItem.title = "Brain: couldn't start"
                return false
            }
        }
        brainItem.title = "Brain: starting…"
        for _ in 0..<40 {
            try? await Task.sleep(nanoseconds: 500_000_000)
            if await brain.health() { brainItem.title = "Brain: running"; return true }
        }
        brainItem.title = "Brain: not responding (see ~/Library/Logs/JapaneseEyes-brain.log)"
        return false
    }

    // MARK: hotkey ⌃⌥J

    private func registerHotKey() {
        var ref: EventHotKeyRef?
        let id = EventHotKeyID(signature: OSType(0x4A50_4E45), id: 1)   // 'JPNE'
        RegisterEventHotKey(UInt32(kVK_ANSI_J), UInt32(controlKey | optionKey), id,
                            GetApplicationEventTarget(), 0, &ref)
        var spec = EventTypeSpec(eventClass: OSType(kEventClassKeyboard), eventKind: UInt32(kEventHotKeyPressed))
        InstallEventHandler(GetApplicationEventTarget(), { _, _, _ in
            DispatchQueue.main.async { AppDelegate.shared.scan() }
            return noErr
        }, 1, &spec, nil, nil)
    }

    // MARK: scanning

    @objc func scanAction() { scan() }

    func scan() {
        if overlay != nil { closeOverlay(); return }   // the hotkey toggles
        previousApp = NSWorkspace.shared.frontmostApplication
        let screen = Capture.screenUnderMouse()
        Task { @MainActor in
            do {
                let img = try await Capture.capture(screen)
                showOverlay(img, on: screen)
            } catch {
                showError("Japanese Eyes can't see the screen yet.\n\nAllow it in System Settings → Privacy & Security → Screen & System Audio Recording, then quit and reopen it.\n\n(\(error.localizedDescription))",
                          openPrivacy: true)
            }
        }
    }

    @MainActor private func showOverlay(_ img: CGImage, on screen: NSScreen) {
        let w = OverlayWindow(contentRect: screen.frame, styleMask: .borderless, backing: .buffered, defer: false)
        w.setFrame(screen.frame, display: false)
        w.level = .screenSaver
        w.isOpaque = false
        w.backgroundColor = .clear
        w.hasShadow = false
        w.isReleasedWhenClosed = false
        w.collectionBehavior = [.canJoinAllSpaces, .fullScreenAuxiliary, .stationary]
        let v = OverlayView(frame: NSRect(origin: .zero, size: screen.frame.size), image: img)
        w.contentView = v
        let png = Capture.png(img)
        v.onCancel = { [weak self] in self?.closeOverlay() }
        v.onPick = { [weak self] rect, text, keepOpen in
            self?.explain(png: png, image: img, rect: rect, text: text)
            if !keepOpen { self?.closeOverlay() }   // back to the game; Shift-click to pick several
        }
        overlay = w
        NSApp.activate(ignoringOtherApps: true)
        w.makeKeyAndOrderFront(nil)
        w.makeFirstResponder(v)

        Task { @MainActor in
            guard await ensureBrain() else { v.status = "The brain isn't running. Check the 目 menu."; return }
            do {
                let r = try await brain.detect(png: png)
                v.lines = r.lines
                v.status = r.lines.isEmpty
                    ? "No text found. Drag a box around it · Esc to close"
                    : "Click a line or drag a box · ⇧ Shift to pick several · Esc to close"
            } catch {
                v.status = "Couldn't find text: \(error.localizedDescription)"
            }
        }
    }

    private func closeOverlay() {
        overlay?.orderOut(nil)
        overlay = nil
        previousApp?.activate()
        previousApp = nil
    }

    private func explain(png: Data, image: CGImage, rect: CGRect, text: String) {
        nextId += 1
        let id = nextId
        let thumb = image.cropping(to: rect.integral).map { Capture.png($0) }
        panel.show()
        panel.addPending(id: id, thumb: thumb, text: text)
        Task { @MainActor in
            do {
                let job = try await brain.startJob(png: png, box: rect, text: text)
                panel.follow(id: id, job: job)
            } catch {
                panel.setError(id: id, msg: error.localizedDescription)
            }
        }
    }

    // MARK: menu actions

    @objc func showPanel() { panel.show() }
    @objc func openSheet() { NSWorkspace.shared.open(projectDir.appendingPathComponent("japanese.xlsx")) }
    @objc func openGrammar() { NSWorkspace.shared.open(projectDir.appendingPathComponent("grammar.md")) }
    @objc func quit() { NSApp.terminate(nil) }

    private func showError(_ msg: String, openPrivacy: Bool) {
        NSApp.activate(ignoringOtherApps: true)
        let a = NSAlert()
        a.messageText = "Japanese Eyes"
        a.informativeText = msg
        a.addButton(withTitle: openPrivacy ? "Open Settings" : "OK")
        if openPrivacy { a.addButton(withTitle: "Cancel") }
        if a.runModal() == .alertFirstButtonReturn, openPrivacy,
           let url = URL(string: "x-apple.systempreferences:com.apple.preference.security?Privacy_ScreenCapture") {
            NSWorkspace.shared.open(url)
        }
    }
}
