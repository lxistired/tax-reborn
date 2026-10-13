import UIKit
import WebKit
import PhotosUI
import UniformTypeIdentifiers
import AVFoundation

final class TaxViewController: UIViewController, WKNavigationDelegate, WKUIDelegate,
    WKScriptMessageHandler, UIDocumentPickerDelegate, PHPickerViewControllerDelegate,
    UIImagePickerControllerDelegate, UINavigationControllerDelegate {
    private var webView: WKWebView!
    private var server: LoopbackAssetServer?
    private let status = UILabel()
    private var pendingID: String?
    private var pendingAction: String?
    private var exportFile: URL?
    private let maxFile = 24 * 1024 * 1024

    override func viewDidLoad() {
        super.viewDidLoad()
        view.backgroundColor = .systemBackground
        let config = WKWebViewConfiguration()
        config.websiteDataStore = .default() // Persistent IndexedDB; never nonPersistent().
        config.preferences.javaScriptCanOpenWindowsAutomatically = false
        config.userContentController.add(self, name: "taxReborn")
        if let scriptURL = Bundle.main.url(forResource: "NativeBridge", withExtension: "js"),
           let script = try? String(contentsOf: scriptURL, encoding: .utf8) {
            config.userContentController.addUserScript(WKUserScript(source: script, injectionTime: .atDocumentStart, forMainFrameOnly: true))
        }
        webView = WKWebView(frame: .zero, configuration: config)
        webView.navigationDelegate = self; webView.uiDelegate = self
        webView.isInspectable = false
        webView.translatesAutoresizingMaskIntoConstraints = false
        webView.accessibilityIdentifier = "tax-workspace"
        view.addSubview(webView)
        let bar = UIToolbar()
        bar.translatesAutoresizingMaskIntoConstraints = false
        let title = UIBarButtonItem(title: "Tax Reborn", style: .plain, target: nil, action: nil)
        title.isEnabled = false
        let add = UIBarButtonItem(title: "Add document", style: .plain, target: self, action: #selector(addDocument))
        add.accessibilityIdentifier = "native-add-document"
        bar.items = [title, UIBarButtonItem(barButtonSystemItem: .flexibleSpace, target: nil, action: nil), add]
        view.addSubview(bar)
        NSLayoutConstraint.activate([
            bar.topAnchor.constraint(equalTo: view.safeAreaLayoutGuide.topAnchor),
            bar.leadingAnchor.constraint(equalTo: view.leadingAnchor), bar.trailingAnchor.constraint(equalTo: view.trailingAnchor),
            bar.heightAnchor.constraint(equalToConstant: 40),
            webView.topAnchor.constraint(equalTo: bar.bottomAnchor), webView.leadingAnchor.constraint(equalTo: view.leadingAnchor),
            webView.trailingAnchor.constraint(equalTo: view.trailingAnchor), webView.bottomAnchor.constraint(equalTo: view.safeAreaLayoutGuide.bottomAnchor)
        ])
        status.text = "Opening local tax workspace…"
        status.numberOfLines = 0; status.textAlignment = .center
        status.accessibilityIdentifier = "native-load-status"
        status.translatesAutoresizingMaskIntoConstraints = false
        view.addSubview(status)
        NSLayoutConstraint.activate([status.centerYAnchor.constraint(equalTo: view.centerYAnchor),
            status.leadingAnchor.constraint(equalTo: view.leadingAnchor, constant: 20),
            status.trailingAnchor.constraint(equalTo: view.trailingAnchor, constant: -20)])
        startServer()
    }

    private func startServer() {
        do {
            guard let root = Bundle.main.url(forResource: "assets", withExtension: nil) else { throw NativeError.message("Bundled tax resources are missing.") }
            let server = try LoopbackAssetServer(root: root)
            self.server = server
            try server.start { [weak self] result in
                guard let self = self else { return }
                switch result {
                case .success:
                    self.webView.load(URLRequest(url: URL(string: AssetRequest.origin + "/index.html?offline=1")!))
                case .failure:
                    self.status.text = "The private local service could not start. Close and reopen Tax Reborn. A conflicting local port is not replaced, so saved return storage remains stable."
                }
            }
        } catch { status.text = "The local tax workspace could not start. \(error.localizedDescription)" }
    }

    func webView(_ webView: WKWebView, didFinish navigation: WKNavigation!) { status.isHidden = true }
    func webView(_ webView: WKWebView, didFailProvisionalNavigation navigation: WKNavigation!, withError error: Error) {
        status.isHidden = false; status.text = "Local workspace unavailable. Close and reopen the app."
    }
    func webViewWebContentProcessDidTerminate(_ webView: WKWebView) {
        status.isHidden = false; status.text = "The workspace restarted. Saved returns remain on this device."
        webView.reload()
    }
    private func local(_ url: URL?) -> Bool {
        guard let url = url else { return false }
        return url.scheme == "http" && url.host == AssetRequest.host && url.port == Int(AssetRequest.port)
            && url.user == nil && url.password == nil
    }
    func webView(_ webView: WKWebView, decidePolicyFor navigationAction: WKNavigationAction,
                 decisionHandler: @escaping (WKNavigationActionPolicy) -> Void) {
        decisionHandler(local(navigationAction.request.url) ? .allow : .cancel)
    }
    func webView(_ webView: WKWebView, createWebViewWith configuration: WKWebViewConfiguration,
                 for navigationAction: WKNavigationAction, windowFeatures: WKWindowFeatures) -> WKWebView? { nil }
    func webView(_ webView: WKWebView, runJavaScriptAlertPanelWithMessage message: String,
                 initiatedByFrame frame: WKFrameInfo, completionHandler: @escaping () -> Void) {
        let alert = UIAlertController(title: "Tax Reborn", message: message, preferredStyle: .alert)
        alert.addAction(UIAlertAction(title: "OK", style: .default) { _ in completionHandler() }); present(alert, animated: true)
    }
    func webView(_ webView: WKWebView, runJavaScriptConfirmPanelWithMessage message: String,
                 initiatedByFrame frame: WKFrameInfo, completionHandler: @escaping (Bool) -> Void) {
        let alert = UIAlertController(title: "Tax Reborn", message: message, preferredStyle: .alert)
        alert.addAction(UIAlertAction(title: "Cancel", style: .cancel) { _ in completionHandler(false) })
        alert.addAction(UIAlertAction(title: "Continue", style: .default) { _ in completionHandler(true) }); present(alert, animated: true)
    }

    func userContentController(_ userContentController: WKUserContentController, didReceive message: WKScriptMessage) {
        guard message.frameInfo.isMainFrame, local(message.frameInfo.request.url),
              let body = message.body as? [String: Any], let id = body["id"] as? String,
              id.count <= 64, let action = body["action"] as? String else { return }
        guard pendingID == nil, presentedViewController == nil else { reply(id, error: "Finish or cancel the open file operation first."); return }
        pendingID = id; pendingAction = action
        switch action {
        case "saveFile": saveFile(body)
        case "pickFile": pickFile(accept: body["accept"] as? String ?? "")
        case "pickPhoto": pickPhoto()
        case "capturePhoto": capturePhoto()
        default: finish(error: "Unknown native operation.")
        }
    }

    @objc private func addDocument() {
        guard pendingID == nil else { return }
        let sheet = UIAlertController(title: "Add a local document", message: "Choose only the document you want to attach. Review extracted amounts before using them.", preferredStyle: .actionSheet)
        for (title, action) in [("Take photo", "capturePhoto"), ("Choose photo", "pickPhoto"), ("Choose file", "pickFile")] {
            sheet.addAction(UIAlertAction(title: title, style: .default) { [weak self] _ in
                guard let self = self else { return }
                self.pendingID = "native-" + UUID().uuidString; self.pendingAction = action
                switch action { case "capturePhoto": self.capturePhoto(); case "pickPhoto": self.pickPhoto(); default: self.pickFile(accept: "") }
            })
        }
        sheet.addAction(UIAlertAction(title: "Cancel", style: .cancel))
        sheet.popoverPresentationController?.sourceView = view
        sheet.popoverPresentationController?.sourceRect = CGRect(x: view.bounds.maxX - 20, y: 50, width: 1, height: 1)
        present(sheet, animated: true)
    }
    private func saveFile(_ body: [String: Any]) {
        guard let filename = body["filename"] as? String, !filename.isEmpty, filename.count <= 180,
              filename == (filename as NSString).lastPathComponent, !filename.contains("\\"), !filename.hasPrefix("."),
              !filename.unicodeScalars.contains(where: { $0.value < 32 || $0.value == 127 }),
              let base64 = body["base64"] as? String, base64.count <= 48 * 1024 * 1024,
              let bytes = Data(base64Encoded: base64), bytes.count <= 32 * 1024 * 1024 else {
            finish(error: "Invalid export name or file larger than 32 MB."); return
        }
        do {
            let directory = FileManager.default.temporaryDirectory.appendingPathComponent("TaxReborn-" + UUID().uuidString, isDirectory: true)
            try FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true)
            let file = directory.appendingPathComponent(filename)
            try bytes.write(to: file, options: [.atomic, .completeFileProtection])
            exportFile = file
            let picker = UIDocumentPickerViewController(forExporting: [file], asCopy: true)
            picker.delegate = self; present(picker, animated: true)
        } catch { finish(error: "The temporary export could not be written.") }
    }
    private func pickFile(accept: String) {
        let type: UTType = accept.contains("json") ? .json : accept.contains("csv") ? .commaSeparatedText : .data
        let picker = UIDocumentPickerViewController(forOpeningContentTypes: [type], asCopy: true)
        picker.delegate = self; picker.allowsMultipleSelection = false; present(picker, animated: true)
    }
    func documentPicker(_ controller: UIDocumentPickerViewController, didPickDocumentsAt urls: [URL]) {
        if pendingAction == "saveFile" { finish(result: ["saved": true, "cancelled": false]); return }
        guard let file = urls.first else { finish(result: ["cancelled": true]); return }
        let access = file.startAccessingSecurityScopedResource()
        defer { if access { file.stopAccessingSecurityScopedResource() } }
        do {
            let values = try file.resourceValues(forKeys: [.fileSizeKey, .contentTypeKey])
            guard (values.fileSize ?? maxFile + 1) <= maxFile else { throw NativeError.message("Choose a file smaller than 24 MB.") }
            let data = try Data(contentsOf: file)
            guard data.count <= maxFile else { throw NativeError.message("Choose a file smaller than 24 MB.") }
            finish(result: fileResult(data: data, name: file.lastPathComponent, mime: values.contentType?.preferredMIMEType ?? "application/octet-stream"))
        } catch { finish(error: "This file could not be read, or is larger than 24 MB.") }
    }
    func documentPickerWasCancelled(_ controller: UIDocumentPickerViewController) { finish(result: ["cancelled": true]) }
    private func pickPhoto() {
        var config = PHPickerConfiguration(); config.filter = .images; config.selectionLimit = 1
        let picker = PHPickerViewController(configuration: config); picker.delegate = self; present(picker, animated: true)
    }
    func picker(_ picker: PHPickerViewController, didFinishPicking results: [PHPickerResult]) {
        picker.dismiss(animated: true)
        guard let provider = results.first?.itemProvider else { finish(result: ["cancelled": true]); return }
        guard provider.canLoadObject(ofClass: UIImage.self) else { finish(error: "Choose a supported image."); return }
        provider.loadObject(ofClass: UIImage.self) { [weak self] image, _ in
            DispatchQueue.main.async {
                guard let self = self else { return }
                guard let image = image as? UIImage else { self.finish(error: "The selected photo could not be opened."); return }
                self.finishImage(image)
            }
        }
    }
    private func capturePhoto() {
        guard UIImagePickerController.isSourceTypeAvailable(.camera) else { finish(error: "A camera is not available on this device."); return }
        AVCaptureDevice.requestAccess(for: .video) { [weak self] allowed in
            DispatchQueue.main.async {
                guard let self = self else { return }
                guard allowed else { self.finish(error: "Camera permission was denied. Choose a file or photo instead."); return }
                let picker = UIImagePickerController(); picker.sourceType = .camera; picker.delegate = self
                picker.mediaTypes = [UTType.image.identifier]; self.present(picker, animated: true)
            }
        }
    }
    func imagePickerController(_ picker: UIImagePickerController, didFinishPickingMediaWithInfo info: [UIImagePickerController.InfoKey: Any]) {
        picker.dismiss(animated: true)
        guard let image = info[.originalImage] as? UIImage else { finish(error: "The camera image could not be read."); return }
        finishImage(image)
    }
    func imagePickerControllerDidCancel(_ picker: UIImagePickerController) { picker.dismiss(animated: true); finish(result: ["cancelled": true]) }
    private func finishImage(_ image: UIImage) {
        guard let bytes = image.jpegData(compressionQuality: 0.92), bytes.count <= maxFile else { finish(error: "This image is larger than 24 MB. Choose a smaller image."); return }
        finish(result: fileResult(data: bytes, name: "tax-document-" + UUID().uuidString.prefix(8) + ".jpg", mime: "image/jpeg"))
    }
    private func fileResult(data: Data, name: String, mime: String) -> [String: Any] {
        ["cancelled": false, "file": ["name": name, "mime": mime, "base64": data.base64EncodedString(), "bytes": data.count]]
    }
    private func finish(result: [String: Any] = [:], error: String? = nil) {
        guard let id = pendingID else { return }
        pendingID = nil; pendingAction = nil
        if let file = exportFile { try? FileManager.default.removeItem(at: file.deletingLastPathComponent()); exportFile = nil }
        if id.hasPrefix("native-") {
            if let error = error {
                let alert = UIAlertController(title: "Document unavailable", message: error, preferredStyle: .alert)
                alert.addAction(UIAlertAction(title: "OK", style: .default)); present(alert, animated: true)
            } else if result["cancelled"] as? Bool != true {
                sendJavaScript("window.dispatchEvent(new CustomEvent('tax-reborn-native-document',{detail:PAYLOAD}));", payload: result)
            }
        } else { reply(id, result: result, error: error) }
    }
    private func reply(_ id: String, result: [String: Any] = [:], error: String? = nil) {
        var message: [String: Any] = ["id": id, "result": result]
        if let error = error { message["error"] = error }
        sendJavaScript("window.__taxRebornNativeReply(PAYLOAD);", payload: message)
    }
    private func sendJavaScript(_ script: String, payload: [String: Any]) {
        guard let json = try? JSONSerialization.data(withJSONObject: payload), let encoded = String(data: json, encoding: .utf8) else { return }
        webView.evaluateJavaScript(script.replacingOccurrences(of: "PAYLOAD", with: encoded), completionHandler: nil)
    }
}

private enum NativeError: LocalizedError {
    case message(String)
    var errorDescription: String? { if case .message(let value) = self { return value }; return nil }
}
