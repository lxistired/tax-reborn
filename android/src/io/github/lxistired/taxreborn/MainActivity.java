package io.github.lxistired.taxreborn;

import android.app.Activity;
import android.content.Intent;
import android.content.ClipData;
import android.net.Uri;
import android.os.Bundle;
import android.util.Base64;
import android.webkit.*;
import android.widget.Toast;
import java.io.*;
import java.util.*;

/** Bundled offline tax calculation. No account, tax-server or network permission. */
public final class MainActivity extends Activity {
    private static final String HOST = "appassets.androidplatform.net";
    private static final int FILE_CHOICE = 100;
    private static final int FILE_SAVE = 101;
    private static final int FILE_CAMERA = 102;
    private Uri cameraUri;
    private WebView view;
    private ValueCallback<Uri[]> chooser;
    private byte[] pendingSave;

    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        view = new WebView(this);
        setContentView(view);
        WebSettings settings = view.getSettings();
        settings.setJavaScriptEnabled(true);
        settings.setDomStorageEnabled(true);
        settings.setAllowFileAccess(false);
        settings.setAllowContentAccess(false);
        settings.setMixedContentMode(WebSettings.MIXED_CONTENT_NEVER_ALLOW);
        settings.setSafeBrowsingEnabled(true);
        view.setWebViewClient(new WebViewClient() {
            @Override public WebResourceResponse shouldInterceptRequest(WebView web, WebResourceRequest request) {
                return assetResponse(request.getUrl());
            }
            @Override public boolean shouldOverrideUrlLoading(WebView web, WebResourceRequest request) {
                Uri uri = request.getUrl();
                if (HOST.equals(uri.getHost()) && "https".equals(uri.getScheme())) return false;
                if (request.isForMainFrame() && ("https".equals(uri.getScheme()) || "http".equals(uri.getScheme()))) {
                    startActivity(new Intent(Intent.ACTION_VIEW, uri));
                }
                return true;
            }
        });
        ServiceWorkerController.getInstance().setServiceWorkerClient(new ServiceWorkerClient() {
            @Override public WebResourceResponse shouldInterceptRequest(WebResourceRequest request) {
                return assetResponse(request.getUrl());
            }
        });
        view.setWebChromeClient(new WebChromeClient() {
            @Override public boolean onShowFileChooser(WebView web, ValueCallback<Uri[]> callback, FileChooserParams params) {
                if (chooser != null) chooser.onReceiveValue(null);
                chooser = callback;
                if(params.isCaptureEnabled()){
                    File folder=new File(getCacheDir(),"captures");folder.mkdirs();
                    for(File previous:folder.listFiles()==null?new File[0]:folder.listFiles())if(System.currentTimeMillis()-previous.lastModified()>86400000L)previous.delete();
                    cameraUri=Uri.parse("content://io.github.lxistired.taxreborn.capture/"+UUID.randomUUID()+".jpg");
                    Intent camera=new Intent(android.provider.MediaStore.ACTION_IMAGE_CAPTURE);
                    camera.putExtra(android.provider.MediaStore.EXTRA_OUTPUT,cameraUri);
                    camera.addFlags(Intent.FLAG_GRANT_WRITE_URI_PERMISSION|Intent.FLAG_GRANT_READ_URI_PERMISSION);
                    camera.setClipData(ClipData.newRawUri("Document photo",cameraUri));
                    try{startActivityForResult(camera,FILE_CAMERA);return true;}catch(Exception unavailable){cameraUri=null;}
                }
                Intent intent = new Intent(Intent.ACTION_OPEN_DOCUMENT);
                intent.addCategory(Intent.CATEGORY_OPENABLE);
                intent.setType("*/*");
                intent.putExtra(Intent.EXTRA_MIME_TYPES, new String[]{"image/jpeg","image/png","application/pdf"});
                intent.putExtra(Intent.EXTRA_ALLOW_MULTIPLE, params.getMode()==FileChooserParams.MODE_OPEN_MULTIPLE);
                try {startActivityForResult(intent, FILE_CHOICE);} catch(Exception e) {chooser.onReceiveValue(null);chooser=null;return false;}
                return true;
            }
        });
        view.addJavascriptInterface(new ExportBridge(), "TaxRebornAndroid");
        view.loadUrl("https://"+HOST+"/index.html?offline=1");
    }

    private WebResourceResponse assetResponse(Uri uri) {
        if (!HOST.equals(uri.getHost()) || !"https".equals(uri.getScheme())) return failure(403,"External requests blocked");
        String path = uri.getPath();
        if (path==null || path.contains("..") || path.contains("\\") || path.startsWith("/api/")) return failure(404,"Asset not found");
        path = path.equals("/") ? "index.html" : path.substring(1);
        String mime = "application/octet-stream";
        if(path.endsWith(".html"))mime="text/html";
        else if(path.endsWith(".js")||path.endsWith(".mjs"))mime="text/javascript";
        else if(path.endsWith(".css"))mime="text/css";
        else if(path.endsWith(".json")||path.endsWith(".webmanifest"))mime="application/json";
        else if(path.endsWith(".wasm"))mime="application/wasm";
        else if(path.endsWith(".svg"))mime="image/svg+xml";
        else if(path.endsWith(".png"))mime="image/png";
        else if(path.endsWith(".pdf"))mime="application/pdf";
        else if(path.endsWith(".zip")||path.endsWith(".whl"))mime="application/zip";
        try {
            InputStream content=getAssets().open(path);
            Map<String,String> headers=new HashMap<>();
            headers.put("Cache-Control","no-cache");
            headers.put("Content-Security-Policy","default-src 'self'; script-src 'self' 'wasm-unsafe-eval'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; worker-src 'self'; connect-src 'self'; object-src 'none'; frame-src 'none'");
            headers.put("X-Content-Type-Options","nosniff");
            return new WebResourceResponse(mime,"UTF-8",200,"OK",headers,content);
        } catch(IOException e) {return failure(404,"Asset not found");}
    }

    private WebResourceResponse failure(int status,String text) {
        return new WebResourceResponse("text/plain","UTF-8",status,text,Collections.emptyMap(),new ByteArrayInputStream(text.getBytes()));
    }

    public final class ExportBridge {
        @JavascriptInterface public void saveFile(String filename,String mime,String encoded) {
            if (encoded==null || encoded.length()>20_000_000 || pendingSave!=null) return;
            try {
                byte[] bytes=Base64.decode(encoded,Base64.DEFAULT);
                String safeName=filename==null?"tax-reborn-draft":filename.replaceAll("[^A-Za-z0-9._-]","_");
                String safeMime=Arrays.asList("application/json","application/pdf","text/html","image/png","image/jpeg").contains(mime)?mime:"application/octet-stream";
                runOnUiThread(()->{
                    if(pendingSave!=null)return;
                    pendingSave=bytes;
                    Intent intent=new Intent(Intent.ACTION_CREATE_DOCUMENT);
                    intent.addCategory(Intent.CATEGORY_OPENABLE);
                    intent.setType(safeMime);
                    intent.putExtra(Intent.EXTRA_TITLE,safeName);
                    try {startActivityForResult(intent,FILE_SAVE);} catch(Exception e) {pendingSave=null;Toast.makeText(MainActivity.this,"Could not open the save picker",Toast.LENGTH_LONG).show();}
                });
            } catch(IllegalArgumentException e) {runOnUiThread(()->Toast.makeText(MainActivity.this,"Draft export data was invalid",Toast.LENGTH_LONG).show());}
        }
    }

    @Override protected void onActivityResult(int request,int result,Intent data) {
        super.onActivityResult(request,result,data);
        if(request==FILE_CAMERA && chooser!=null){
            chooser.onReceiveValue(result==RESULT_OK && cameraUri!=null?new Uri[]{cameraUri}:null);
            chooser=null;cameraUri=null;
        }
        if(request==FILE_CHOICE && chooser!=null){
            chooser.onReceiveValue(WebChromeClient.FileChooserParams.parseResult(result,data));
            chooser=null;
        }
        if(request==FILE_SAVE){
            byte[] bytes=pendingSave;pendingSave=null;
            if(result==RESULT_OK && data!=null && data.getData()!=null && bytes!=null){
                try(OutputStream out=getContentResolver().openOutputStream(data.getData())) {
                    if(out==null)throw new IOException("No save destination");
                    out.write(bytes);Toast.makeText(this,"Draft saved on this device. No return was filed.",Toast.LENGTH_LONG).show();
                } catch(IOException e) {Toast.makeText(this,"Draft export was not saved",Toast.LENGTH_LONG).show();}
            }
        }
    }

    @Override public void onBackPressed() {
        if(view.canGoBack())view.goBack();else super.onBackPressed();
    }
    @Override protected void onDestroy() {
        if(chooser!=null){chooser.onReceiveValue(null);chooser=null;}
        view.removeJavascriptInterface("TaxRebornAndroid");view.destroy();super.onDestroy();
    }
}
