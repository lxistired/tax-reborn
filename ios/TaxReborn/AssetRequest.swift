import Foundation

/// Only bundled, public application assets are served. No tax data route exists.
struct AssetRequest {
    static let host = "127.0.0.1"
    static let port: UInt16 = 18786
    static let authority = "127.0.0.1:18786"
    static let origin = "http://127.0.0.1:18786"
    let method: String
    let relativePath: String

    init?(header: String) {
        let rows = header.components(separatedBy: "\r\n")
        guard let first = rows.first else { return nil }
        let words = first.split(separator: " ", omittingEmptySubsequences: false)
        guard words.count == 3, ["GET", "HEAD"].contains(String(words[0])),
              words[2] == "HTTP/1.1" || words[2] == "HTTP/1.0" else { return nil }
        var headers: [String: String] = [:]
        for row in rows.dropFirst() where !row.isEmpty {
            guard let colon = row.firstIndex(of: ":") else { return nil }
            let key = row[..<colon].lowercased()
            guard headers[key] == nil else { return nil }
            headers[key] = row[row.index(after: colon)...].trimmingCharacters(in: .whitespaces)
        }
        guard headers["host"] == Self.authority,
              headers["origin"] == nil || headers["origin"] == Self.origin,
              headers["content-length"] == nil || headers["content-length"] == "0",
              headers["transfer-encoding"] == nil else { return nil }
        let target = String(words[1])
        guard target.hasPrefix("/"), !target.hasPrefix("//"), !target.contains("#") else { return nil }
        let rawPath = String(target.split(separator: "?", maxSplits: 1, omittingEmptySubsequences: false)[0])
        guard let path = rawPath.removingPercentEncoding,
              !path.contains("%"), !path.contains("\\"), !path.contains("\0"),
              !path.unicodeScalars.contains(where: { $0.value < 32 || $0.value == 127 }),
              !path.split(separator: "/", omittingEmptySubsequences: false).contains(".."),
              !path.split(separator: "/", omittingEmptySubsequences: false).contains("."),
              path != "/api", !path.hasPrefix("/api/") else { return nil }
        method = String(words[0])
        relativePath = path == "/" ? "index.html" : String(path.dropFirst())
    }

    static func mime(_ path: String) -> String {
        switch (path as NSString).pathExtension.lowercased() {
        case "html": return "text/html; charset=utf-8"
        case "js", "mjs": return "text/javascript; charset=utf-8"
        case "css": return "text/css; charset=utf-8"
        case "json", "webmanifest": return "application/json"
        case "wasm": return "application/wasm"
        case "svg": return "image/svg+xml"
        case "png": return "image/png"
        case "jpg", "jpeg": return "image/jpeg"
        case "pdf": return "application/pdf"
        case "zip", "whl": return "application/zip"
        case "gz": return "application/gzip"
        default: return "application/octet-stream"
        }
    }
}
