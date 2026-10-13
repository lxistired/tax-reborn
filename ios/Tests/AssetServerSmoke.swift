import Foundation

private final class SmokeChecks {
    var values = [String]()
    func add(_ condition: Bool, _ message: String) {
        guard condition else { fatalError(message) }; values.append(message)
    }
}

@main
enum AssetServerSmoke {
    static func main() throws {
        let recorder = SmokeChecks()
        let check = recorder.add
        let valid = "GET /index.html?offline=1 HTTP/1.1\r\nHost: 127.0.0.1:18786\r\n\r\n"
        check(AssetRequest(header: valid)?.relativePath == "index.html", "Stable local origin accepts the real offline start path")
        check(AssetRequest(header: "HEAD /vendor/pyodide/pyodide.asm.wasm HTTP/1.1\r\nHost: 127.0.0.1:18786\r\n\r\n")?.method == "HEAD", "Local HEAD requests parse")
        for path in ["/../secret", "/%2e%2e/secret", "/%252e%252e/secret", "/vendor/./file", "/api", "/api/returns", "//evil.test/file", "/bad%00name", "/bad%0aname", "/bad%5cname", "https://evil.test/index.html"] {
            check(AssetRequest(header: "GET \(path) HTTP/1.1\r\nHost: 127.0.0.1:18786\r\n\r\n") == nil, "Reject path " + path)
        }
        for headers in ["Host: evil.test", "Host: 127.0.0.1:18786\r\nHost: evil.test", "Host: 127.0.0.1:18786\r\nOrigin: https://evil.test", "Host: 127.0.0.1:18786\r\nContent-Length: 10", "Host: 127.0.0.1:18786\r\nTransfer-Encoding: chunked"] {
            check(AssetRequest(header: "GET /index.html HTTP/1.1\r\n" + headers + "\r\n\r\n") == nil, "Reject foreign Host/Origin, duplicate headers or body framing")
        }
        check(AssetRequest(header: "POST /index.html HTTP/1.1\r\nHost: 127.0.0.1:18786\r\n\r\n") == nil, "No mutation route or POST handler")
        let directory = FileManager.default.temporaryDirectory.appendingPathComponent("TaxRebornAssetTest-" + UUID().uuidString)
        try FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true)
        try Data("<h1>Synthetic bundled asset</h1>".utf8).write(to: directory.appendingPathComponent("index.html"))
        try Data("{\"index.html\":\"synthetic-only\"}".utf8).write(to: directory.appendingPathComponent("native-asset-manifest.json"))
        let service = try LoopbackAssetServer(root: directory)
        let reportPath = CommandLine.arguments.count > 1 ? CommandLine.arguments[1] : nil
        try service.start { result in
            if case .failure(let error) = result { fatalError("Actual listener failed: \(error)") }
            DispatchQueue.global().async {
                func request(_ path: String, host: String? = nil) -> (Int, Data, String?) {
                    let gate = DispatchSemaphore(value: 0)
                    var value = (0, Data(), Optional<String>.none)
                    var request = URLRequest(url: URL(string: AssetRequest.origin + path)!)
                    if let host = host { request.setValue(host, forHTTPHeaderField: "Host") }
                    let task = URLSession.shared.dataTask(with: request) { data, response, error in
                        guard error == nil, let response = response as? HTTPURLResponse else { gate.signal(); return }
                        value = (response.statusCode, data ?? Data(), response.value(forHTTPHeaderField: "Content-Security-Policy")); gate.signal()
                    }
                    task.resume()
                    guard gate.wait(timeout: .now() + 5) == .success else { fatalError("Actual loopback request timed out") }
                    return value
                }
                let page = request("/index.html?offline=1")
                check(page.0 == 200 && String(data: page.1, encoding: .utf8) == "<h1>Synthetic bundled asset</h1>", "Actual NWListener serves only the bundled allowlisted file")
                check(page.2?.contains("connect-src 'self'") == true, "Actual response constrains worker/connect resources to local origin")
                check(request("/missing.txt").0 == 404, "Unlisted static file is not served")
                check(request("/api/returns").0 == 400, "Actual server rejects tax API route")
                check(request("/index.html", host: "evil.test").0 == 400, "Actual server rejects DNS-rebinding Host")
                let report: [String: Any] = ["all_passed": true, "passed": recorder.values.count, "checks": recorder.values, "scope": "Actual macOS Network.framework server and shared iOS request parser; not UIKit compilation or Simulator validation"]
                let output = try! JSONSerialization.data(withJSONObject: report, options: [.prettyPrinted, .sortedKeys])
                if let reportPath = reportPath { try! output.write(to: URL(fileURLWithPath: reportPath)) }
                print(String(data: output, encoding: .utf8)!)
                service.stop(); try? FileManager.default.removeItem(at: directory)
                exit(0)
            }
        }
        dispatchMain()
    }
}
