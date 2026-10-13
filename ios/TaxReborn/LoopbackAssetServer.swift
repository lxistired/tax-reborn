import Foundation
import Network

final class LoopbackAssetServer {
    private let root: URL
    private let allowed: Set<String>
    private let queue = DispatchQueue(label: "TaxReborn.bundled-assets")
    private var listener: NWListener?
    private var clients: [UUID: NWConnection] = [:]
    private let maxHeader = 16_384

    init(root: URL) throws {
        self.root = root.resolvingSymlinksInPath()
        let manifest = try Data(contentsOf: root.appendingPathComponent("native-asset-manifest.json"))
        guard let entries = try JSONSerialization.jsonObject(with: manifest) as? [String: String] else {
            throw NSError(domain: "TaxReborn.assets", code: 1)
        }
        allowed = Set(entries.keys)
    }

    func start(ready: @escaping (Result<Void, Error>) -> Void) throws {
        guard listener == nil else { return }
        let parameters = NWParameters.tcp
        parameters.requiredLocalEndpoint = .hostPort(host: .ipv4(IPv4Address("127.0.0.1")!),
                                                     port: NWEndpoint.Port(rawValue: AssetRequest.port)!)
        parameters.allowLocalEndpointReuse = false
        let listener = try NWListener(using: parameters)
        self.listener = listener
        var delivered = false
        listener.stateUpdateHandler = { state in
            if delivered { return }
            switch state {
            case .ready: delivered = true; DispatchQueue.main.async { ready(.success(())) }
            case .failed(let error): delivered = true; DispatchQueue.main.async { ready(.failure(error)) }
            default: break
            }
        }
        listener.newConnectionHandler = { [weak self] connection in self?.accept(connection) }
        listener.start(queue: queue)
    }

    func stop() {
        queue.async { [weak self] in
            guard let self = self else { return }
            self.listener?.cancel(); self.listener = nil
            for client in self.clients.values { client.cancel() }
            self.clients.removeAll()
        }
    }

    private func accept(_ connection: NWConnection) {
        // Binding is loopback-only. Reject any other peer even if parameters drift.
        guard case let .hostPort(host, _) = connection.endpoint,
              host == .ipv4(IPv4Address("127.0.0.1")!) else { connection.cancel(); return }
        guard clients.count < 24 else { connection.cancel(); return }
        let id = UUID()
        clients[id] = connection
        connection.stateUpdateHandler = { [weak self] state in
            switch state { case .cancelled, .failed: self?.clients.removeValue(forKey: id); default: break }
        }
        connection.start(queue: queue)
        queue.asyncAfter(deadline: .now() + 20) { [weak self, weak connection] in
            if self?.clients[id] != nil { connection?.cancel() }
        }
        receive(connection, accumulated: Data())
    }

    private func receive(_ connection: NWConnection, accumulated: Data) {
        connection.receive(minimumIncompleteLength: 1, maximumLength: maxHeader) { [weak self] data, _, done, error in
            guard let self = self else { connection.cancel(); return }
            var header = accumulated
            if let data = data { header.append(data) }
            guard header.count <= self.maxHeader else { self.respond(connection, status: 413, body: Data()); return }
            if let boundary = header.range(of: Data("\r\n\r\n".utf8)) {
                guard boundary.upperBound == header.endIndex,
                      let string = String(data: header, encoding: .utf8),
                      let request = AssetRequest(header: string) else {
                    self.respond(connection, status: 400, body: Data()); return
                }
                self.serve(connection, request: request)
            } else if done || error != nil { connection.cancel() }
            else { self.receive(connection, accumulated: header) }
        }
    }

    private func serve(_ connection: NWConnection, request: AssetRequest) {
        guard allowed.contains(request.relativePath) else { respond(connection, status: 404, body: Data()); return }
        let file = root.appendingPathComponent(request.relativePath).resolvingSymlinksInPath()
        guard file.path.hasPrefix(root.path + "/"),
              let body = try? Data(contentsOf: file, options: .mappedIfSafe) else {
            respond(connection, status: 404, body: Data()); return
        }
        respond(connection, status: 200, body: body, mime: AssetRequest.mime(request.relativePath), head: request.method == "HEAD")
    }

    private func respond(_ connection: NWConnection, status: Int, body: Data,
                         mime: String = "text/plain", head: Bool = false) {
        let reason = [200: "OK", 400: "Bad Request", 404: "Not Found", 413: "Payload Too Large"][status] ?? "Error"
        let csp = "default-src 'self'; script-src 'self' 'wasm-unsafe-eval'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; worker-src 'self'; connect-src 'self'; object-src 'none'; frame-src 'none'; base-uri 'none'"
        let header = "HTTP/1.1 \(status) \(reason)\r\nContent-Length: \(body.count)\r\nContent-Type: \(mime)\r\nCache-Control: no-cache\r\nConnection: close\r\nX-Content-Type-Options: nosniff\r\nReferrer-Policy: no-referrer\r\nContent-Security-Policy: \(csp)\r\n\r\n"
        connection.send(content: Data(header.utf8), completion: .contentProcessed { error in
            if error != nil || head || body.isEmpty { connection.cancel(); return }
            connection.send(content: body, completion: .contentProcessed { _ in connection.cancel() })
        })
    }
}
