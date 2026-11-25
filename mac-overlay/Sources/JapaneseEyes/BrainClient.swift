import Foundation

/// Talks to the brain service (brain/server.py). Every platform client uses the same API.
struct TextLine: Decodable { let text: String; let box: [Double] }   // box = x,y,w,h in image pixels
struct DetectResponse: Decodable { let width: Int; let height: Int; let lines: [TextLine] }
struct JobResponse: Decodable { let job: String }
private struct ErrorResponse: Decodable { let detail: String }

final class BrainClient {
    let base: URL
    init(base: URL) { self.base = base }

    func health() async -> Bool {
        var req = URLRequest(url: base.appendingPathComponent("health"))
        req.timeoutInterval = 2
        guard let (_, resp) = try? await URLSession.shared.data(for: req) else { return false }
        return (resp as? HTTPURLResponse)?.statusCode == 200
    }

    func detect(png: Data) async throws -> DetectResponse {
        try await post("detect", fields: [:], png: png, timeout: 60)
    }

    /// Starts a staged breakdown and returns its job id right away. The results page
    /// (served by the brain at /panel) follows the job and shows each stage as it's ready.
    func startJob(png: Data, box: CGRect, text: String) async throws -> String {
        let b = box.integral
        let fields = ["text": text, "save": "true",
                      "box": "\(Int(b.minX)),\(Int(b.minY)),\(Int(b.width)),\(Int(b.height))"]
        let r: JobResponse = try await post("jobs", fields: fields, png: png, timeout: 60)
        return r.job
    }

    private func post<T: Decodable>(_ path: String, fields: [String: String], png: Data,
                                    timeout: TimeInterval) async throws -> T {
        try JSONDecoder().decode(T.self, from: try await postRaw(path, fields: fields, png: png, timeout: timeout))
    }

    private func postRaw(_ path: String, fields: [String: String], png: Data,
                         timeout: TimeInterval) async throws -> Data {
        let boundary = "jp-\(UUID().uuidString)"
        var body = Data()
        func add(_ s: String) { body.append(s.data(using: .utf8)!) }
        for (k, v) in fields {
            add("--\(boundary)\r\nContent-Disposition: form-data; name=\"\(k)\"\r\n\r\n\(v)\r\n")
        }
        add("--\(boundary)\r\nContent-Disposition: form-data; name=\"image\"; filename=\"screen.png\"\r\n")
        add("Content-Type: image/png\r\n\r\n")
        body.append(png)
        add("\r\n--\(boundary)--\r\n")

        var req = URLRequest(url: base.appendingPathComponent(path))
        req.httpMethod = "POST"
        req.timeoutInterval = timeout
        req.setValue("multipart/form-data; boundary=\(boundary)", forHTTPHeaderField: "Content-Type")
        let (data, resp) = try await URLSession.shared.upload(for: req, from: body)
        let code = (resp as? HTTPURLResponse)?.statusCode ?? 0
        guard code == 200 else {
            let msg = (try? JSONDecoder().decode(ErrorResponse.self, from: data).detail)
                ?? String(data: data, encoding: .utf8) ?? "HTTP \(code)"
            throw NSError(domain: "Brain", code: code, userInfo: [NSLocalizedDescriptionKey: msg])
        }
        return data
    }
}
