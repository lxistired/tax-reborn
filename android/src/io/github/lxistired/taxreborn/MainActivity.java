package io.github.lxistired.taxreborn;

import android.app.Activity;
import android.content.Intent;
import android.content.ClipData;
import android.content.SharedPreferences;
import android.net.Uri;
import android.os.Bundle;
import android.os.SystemClock;
import android.util.Log;
import android.util.Base64;
import android.webkit.*;
import android.widget.Toast;
import java.io.*;
import java.util.*;
import org.json.JSONObject;

/** Bundled offline tax calculation. No account, tax-server or network permission. */
public final class MainActivity extends Activity {
    private static final String LIFE_TAG = "TaxRebornLife";
    private long diagnosticSerial;
    private static final String HOST = "appassets.androidplatform.net";
    private static final int FILE_CHOICE = 100;
    private static final int FILE_SAVE = 101;
    private static final int FILE_CAMERA = 102;
    private Uri cameraUri;
    private WebView view;
    private ValueCallback<Uri[]> chooser;
    private String activeReturnId, cameraReturnId, pendingSaveName, pendingSaveTitle, pendingSaveMime;
    private String pendingDocumentId, pendingDocumentUri, pendingDocumentReturnId, pendingDocumentName, pendingDocumentMime;
    private boolean workspaceReady, documentDispatchInFlight, pickerForDocuments;
    private volatile boolean destroyed;
    private SharedPreferences transfers;

    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        lifecycleEvent("create", "recreated="+(state!=null));
        transfers=getSharedPreferences("local_transfers",MODE_PRIVATE);
        restoreTransfers(state);
        view = new WebView(this);
        android.widget.FrameLayout content = new android.widget.FrameLayout(this);
        content.setBackgroundColor(android.graphics.Color.WHITE);
        content.addView(view,new android.widget.FrameLayout.LayoutParams(
            android.view.ViewGroup.LayoutParams.MATCH_PARENT,
            android.view.ViewGroup.LayoutParams.MATCH_PARENT));
        if(android.os.Build.VERSION.SDK_INT>=30){
            // Target35 enforces edge-to-edge on Android15. Keep the WebView's
            // tappable header/footer outside system bars, cutouts and the IME.
            // https://developer.android.com/develop/ui/views/layout/edge-to-edge
            getWindow().setDecorFitsSystemWindows(false);
            content.setOnApplyWindowInsetsListener((root,insets)->{
                android.graphics.Insets bars=insets.getInsets(
                    android.view.WindowInsets.Type.systemBars()|
                    android.view.WindowInsets.Type.displayCutout());
                android.graphics.Insets keyboard=insets.getInsets(android.view.WindowInsets.Type.ime());
                root.setPadding(bars.left,bars.top,bars.right,Math.max(bars.bottom,keyboard.bottom));
                return android.view.WindowInsets.CONSUMED;
            });
        }else{
            content.setFitsSystemWindows(true);
        }
        setContentView(content);
        content.post(()->{
            if(android.os.Build.VERSION.SDK_INT>=30){
                android.view.WindowInsetsController controller=getWindow().getInsetsController();
                if(controller!=null){
                    int light=android.view.WindowInsetsController.APPEARANCE_LIGHT_STATUS_BARS|
                        android.view.WindowInsetsController.APPEARANCE_LIGHT_NAVIGATION_BARS;
                    controller.setSystemBarsAppearance(light,light);
                }
            }
            content.requestApplyInsets();
        });
        WebSettings settings = view.getSettings();
        settings.setJavaScriptEnabled(true);
        settings.setDomStorageEnabled(true);
        settings.setAllowFileAccess(false);
        settings.setAllowContentAccess(false);
        settings.setMixedContentMode(WebSettings.MIXED_CONTENT_NEVER_ALLOW);
        settings.setSafeBrowsingEnabled(true);
        view.setWebViewClient(new WebViewClient() {
            @Override public void onPageStarted(WebView web,String url,android.graphics.Bitmap icon) {
                lifecycleEvent("page_started","urlClass="+urlClass(url));
            }
            @Override public void onPageCommitVisible(WebView web,String url) {
                lifecycleEvent("page_visible","urlClass="+urlClass(url));
                diagnoseWebView("page_visible");
            }
            @Override public void onPageFinished(WebView web,String url) {
                lifecycleEvent("page_finished","urlClass="+urlClass(url));
                diagnoseWebView("page_finished");
            }
            @Override public void onReceivedError(WebView web,WebResourceRequest request,WebResourceError error) {
                if(request.isForMainFrame())lifecycleEvent("main_frame_error","code="+error.getErrorCode());
            }
            @Override public boolean onRenderProcessGone(WebView web,RenderProcessGoneDetail detail) {
                lifecycleEvent("renderer_gone","crashed="+detail.didCrash()+" priority="+detail.rendererPriorityAtExit());
                // Diagnostic build keeps the platform's failure behavior. A
                // broken renderer is never reused or speculatively reloaded.
                return false;
            }
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
                if(pendingDocumentId!=null){callback.onReceiveValue(null);Toast.makeText(MainActivity.this,"Wait for the current document to finish saving",Toast.LENGTH_LONG).show();return true;}
                if (chooser != null) chooser.onReceiveValue(null);
                chooser = callback;
                pickerForDocuments=LocalTransferStore.documentPicker(LocalTransferStore.acceptedMimeTypes(params.getAcceptTypes()));
                transfers.edit().putBoolean("picker_documents",pickerForDocuments).putString("picker_return",activeReturnId).commit();
                if(params.isCaptureEnabled()){
                    File folder=new File(getCacheDir(),"captures");folder.mkdirs();
                    for(File previous:folder.listFiles()==null?new File[0]:folder.listFiles())if(System.currentTimeMillis()-previous.lastModified()>86400000L)previous.delete();
                    cameraUri=Uri.parse("content://io.github.lxistired.taxreborn.capture/"+UUID.randomUUID()+".jpg");
                    cameraReturnId=activeReturnId;
                    transfers.edit().putString("camera_uri",cameraUri.toString()).putString("camera_return",cameraReturnId).commit();
                    Intent camera=new Intent(android.provider.MediaStore.ACTION_IMAGE_CAPTURE);
                    camera.putExtra(android.provider.MediaStore.EXTRA_OUTPUT,cameraUri);
                    camera.addFlags(Intent.FLAG_GRANT_WRITE_URI_PERMISSION|Intent.FLAG_GRANT_READ_URI_PERMISSION);
                    camera.setClipData(ClipData.newRawUri("Document photo",cameraUri));
                    try{startActivityForResult(camera,FILE_CAMERA);return true;}catch(Exception unavailable){clearCamera(true);}
                }
                Intent intent = new Intent(Intent.ACTION_OPEN_DOCUMENT);
                intent.addCategory(Intent.CATEGORY_OPENABLE);
                intent.setType("*/*");
                intent.putExtra(Intent.EXTRA_MIME_TYPES,LocalTransferStore.acceptedMimeTypes(params.getAcceptTypes()));
                intent.putExtra(Intent.EXTRA_ALLOW_MULTIPLE, params.getMode()==FileChooserParams.MODE_OPEN_MULTIPLE);
                try {startActivityForResult(intent, FILE_CHOICE);} catch(Exception e) {chooser.onReceiveValue(null);chooser=null;transfers.edit().remove("picker_documents").remove("picker_return").commit();return true;}
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
        @JavascriptInterface public void workspaceReady(String returnId) {
            runOnUiThread(()->{if(destroyed)return;activeReturnId=LocalTransferStore.validId(returnId)?returnId:null;workspaceReady=true;lifecycleEvent("workspace_ready","retained=true");dispatchPendingDocument();});
        }
        @JavascriptInterface public void acknowledgeDocument(String documentId) {
            runOnUiThread(()->{if(destroyed || pendingDocumentId==null || !pendingDocumentId.equals(documentId))return;clearPendingDocument(true);});
        }
        @JavascriptInterface public void saveFile(String filename,String mime,String encoded) {
            if (encoded==null || encoded.length()>20_000_000) return;
            try {
                byte[] bytes=Base64.decode(encoded,Base64.DEFAULT);
                String safeName=filename==null?"tax-reborn-draft":filename.replaceAll("[^A-Za-z0-9._-]","_");
                String safeMime=Arrays.asList("application/json","application/pdf","text/html","image/png","image/jpeg","application/xml","text/xml").contains(mime)?mime:"application/octet-stream";
                runOnUiThread(()->{
                    if(destroyed || pendingSaveName!=null)return;
                    try{pendingSaveName=LocalTransferStore.stageExport(getCacheDir(),bytes).getName();}
                    catch(IOException failed){Toast.makeText(MainActivity.this,"Could not retain the local export",Toast.LENGTH_LONG).show();return;}
                    pendingSaveTitle=safeName;pendingSaveMime=safeMime;
                    transfers.edit().putString("save_name",pendingSaveName).putString("save_title",safeName).putString("save_mime",safeMime).commit();
                    Intent intent=new Intent(Intent.ACTION_CREATE_DOCUMENT);
                    intent.addCategory(Intent.CATEGORY_OPENABLE);
                    intent.setType(safeMime);
                    intent.putExtra(Intent.EXTRA_TITLE,safeName);
                    lifecycleEvent("save_picker_open","pending=true");
                    try {startActivityForResult(intent,FILE_SAVE);} catch(Exception e) {clearPendingSave();Toast.makeText(MainActivity.this,"Could not open the save picker",Toast.LENGTH_LONG).show();}
                });
            } catch(IllegalArgumentException e) {runOnUiThread(()->Toast.makeText(MainActivity.this,"Draft export data was invalid",Toast.LENGTH_LONG).show());}
        }
    }

    @Override protected void onActivityResult(int request,int result,Intent data) {
        super.onActivityResult(request,result,data);
        lifecycleEvent("activity_result","request="+request+" result="+result+" pendingSave="+(pendingSaveName!=null));
        if(request==FILE_CAMERA){
            if(chooser!=null){chooser.onReceiveValue(null);chooser=null;}
            if(result==RESULT_OK && cameraUri!=null){
                String id=LocalTransferStore.captureId(cameraUri.toString());
                if(id!=null)queueDocument(cameraUri,id,cameraReturnId,"document-photo-"+id+".jpg","image/jpeg");
                else Toast.makeText(this,"The temporary camera result was unavailable",Toast.LENGTH_LONG).show();
                clearCamera(false);
            }else clearCamera(true);
        }
        if(request==FILE_CHOICE){
            Uri[] selected=WebChromeClient.FileChooserParams.parseResult(result,data);
            if(chooser!=null){chooser.onReceiveValue(selected);chooser=null;}
            else if(selected!=null && selected.length==1 && pickerForDocuments){
                Uri chosen=selected[0];String mime=getContentResolver().getType(chosen);
                if("content".equals(chosen.getScheme()) && mime!=null && (mime.startsWith("image/") || mime.equals("application/pdf"))){
                    try{getContentResolver().takePersistableUriPermission(chosen,Intent.FLAG_GRANT_READ_URI_PERMISSION);}catch(SecurityException unavailable){}
                    String id=UUID.randomUUID().toString();queueDocument(chosen,id,transfers.getString("picker_return",null),"selected-document-"+id+(mime.equals("application/pdf")?".pdf":".jpg"),mime);
                }else Toast.makeText(this,"Choose the document again after the workspace finishes reopening",Toast.LENGTH_LONG).show();
            }else if(selected!=null)Toast.makeText(this,"The file picker was interrupted. Reopen the import after the workspace restores.",Toast.LENGTH_LONG).show();
            transfers.edit().remove("picker_documents").remove("picker_return").commit();
        }
        if(request==FILE_SAVE){
            String savedName=pendingSaveName;
            if(result==RESULT_OK && data!=null && data.getData()!=null && savedName!=null){
                try(InputStream input=new FileInputStream(LocalTransferStore.exportFile(getCacheDir(),savedName));OutputStream out=getContentResolver().openOutputStream(data.getData())) {
                    if(out==null)throw new IOException("No save destination");
                    byte[] chunk=new byte[16384];int count;while((count=input.read(chunk))!=-1)out.write(chunk,0,count);
                    lifecycleEvent("save_write_complete","saved=true");
                    Toast.makeText(this,"Draft saved on this device. No return was filed.",Toast.LENGTH_LONG).show();
                } catch(IOException e) {lifecycleEvent("save_write_failed","saved=false");Toast.makeText(this,"Draft export was not saved",Toast.LENGTH_LONG).show();}
            }
            clearPendingSave();
            diagnoseWebView("save_result");
        }
    }

    private void restoreTransfers(Bundle state) {
        String camera=state!=null?state.getString("camera_uri",transfers.getString("camera_uri",null)):transfers.getString("camera_uri",null);
        if(LocalTransferStore.captureId(camera)!=null)cameraUri=Uri.parse(camera);
        cameraReturnId=transfers.getString("camera_return",null);pickerForDocuments=transfers.getBoolean("picker_documents",false);
        pendingSaveName=transfers.getString("save_name",null);pendingSaveTitle=transfers.getString("save_title",null);pendingSaveMime=transfers.getString("save_mime",null);
        if(pendingSaveName!=null)try{if(!LocalTransferStore.exportFile(getCacheDir(),pendingSaveName).isFile())clearPendingSave();}catch(IOException invalid){clearPendingSave();}
        pendingDocumentId=transfers.getString("document_id",null);pendingDocumentUri=transfers.getString("document_uri",null);pendingDocumentReturnId=transfers.getString("document_return",null);pendingDocumentName=transfers.getString("document_name",null);pendingDocumentMime=transfers.getString("document_mime",null);
        if(pendingDocumentId!=null && (!LocalTransferStore.validId(pendingDocumentId) || pendingDocumentUri==null))clearPendingDocument(false);
    }

    private void queueDocument(Uri uri,String id,String returnId,String name,String mime) {
        pendingDocumentId=id;pendingDocumentUri=uri.toString();pendingDocumentReturnId=LocalTransferStore.validId(returnId)?returnId:null;pendingDocumentName=name;pendingDocumentMime=mime;
        transfers.edit().putString("document_id",id).putString("document_uri",pendingDocumentUri).putString("document_return",pendingDocumentReturnId).putString("document_name",name).putString("document_mime",mime).commit();
        dispatchPendingDocument();
    }

    private void dispatchPendingDocument() {
        if(destroyed || !workspaceReady || documentDispatchInFlight || pendingDocumentId==null)return;
        final String id=pendingDocumentId,uri=pendingDocumentUri,returnId=pendingDocumentReturnId,name=pendingDocumentName,mime=pendingDocumentMime;
        documentDispatchInFlight=true;
        new Thread(()->{
            try(InputStream stream=getContentResolver().openInputStream(Uri.parse(uri))){
                byte[] bytes=LocalTransferStore.readBounded(stream);
                JSONObject file=new JSONObject().put("name",name).put("mime",mime).put("bytes",bytes.length).put("base64",Base64.encodeToString(bytes,Base64.NO_WRAP));
                JSONObject detail=new JSONObject().put("documentId",id).put("returnId",returnId==null?JSONObject.NULL:returnId).put("file",file);
                final String script="window.dispatchEvent(new CustomEvent('tax-reborn-native-document',{detail:"+detail.toString().replace("\u2028","\\u2028").replace("\u2029","\\u2029")+"}));";
                runOnUiThread(()->{if(destroyed)return;view.evaluateJavascript(script,value->documentDispatchInFlight=false);});
            }catch(Exception unavailable){runOnUiThread(()->{if(destroyed)return;clearPendingDocument(false);Toast.makeText(MainActivity.this,"The local document could not be recovered. Keep the draft and choose a smaller document.",Toast.LENGTH_LONG).show();});}
        },"local-document-restore").start();
    }

    private void clearCamera(boolean removePhoto) {
        if(removePhoto && cameraUri!=null)try{LocalTransferStore.captureFile(getCacheDir(),cameraUri.toString()).delete();}catch(IOException ignored){}
        cameraUri=null;cameraReturnId=null;transfers.edit().remove("camera_uri").remove("camera_return").commit();
    }

    private void clearPendingDocument(boolean acknowledged) {
        if(acknowledged && pendingDocumentUri!=null)try{LocalTransferStore.captureFile(getCacheDir(),pendingDocumentUri).delete();}catch(IOException notOwnPhoto){}
        pendingDocumentId=null;pendingDocumentUri=null;pendingDocumentReturnId=null;pendingDocumentName=null;pendingDocumentMime=null;documentDispatchInFlight=false;
        transfers.edit().remove("document_id").remove("document_uri").remove("document_return").remove("document_name").remove("document_mime").commit();
    }

    private void clearPendingSave() {
        if(pendingSaveName!=null)try{LocalTransferStore.exportFile(getCacheDir(),pendingSaveName).delete();}catch(IOException ignored){}
        pendingSaveName=null;pendingSaveTitle=null;pendingSaveMime=null;transfers.edit().remove("save_name").remove("save_title").remove("save_mime").commit();
    }

    @Override protected void onSaveInstanceState(Bundle state) {
        lifecycleEvent("save_instance","workspaceReady="+workspaceReady);
        if(cameraUri!=null)state.putString("camera_uri",cameraUri.toString());
        // SPA draft data lives in private IndexedDB; no photo/export bytes enter
        // Binder state. The small transfer journal survives Activity recreation.
        super.onSaveInstanceState(state);
    }

    @Override protected void onResume(){
        super.onResume();lifecycleEvent("resume","workspaceReady="+workspaceReady);
        if(view!=null){view.onResume();reactivateWebView("resume");}
        dispatchPendingDocument();
    }
    @Override protected void onPause(){lifecycleEvent("pause","workspaceReady="+workspaceReady);if(view!=null)view.onPause();super.onPause();}
    @Override public void onWindowFocusChanged(boolean focused){
        super.onWindowFocusChanged(focused);lifecycleEvent("window_focus","focused="+focused);
        if(focused && view!=null && !destroyed)reactivateWebView("focus_restored");
    }

    private void lifecycleEvent(String event,String facts){
        // Only fixed event names, enums, counts and booleans. No URL, filename,
        // document contents, tax values or exception text enters this log.
        Log.i(LIFE_TAG,"t="+SystemClock.elapsedRealtime()+" event="+event+" "+facts);
    }
    private String urlClass(String value){
        if(value==null || value.equals("about:blank"))return "blank";
        try{Uri uri=Uri.parse(value);return HOST.equals(uri.getHost()) && "https".equals(uri.getScheme())?"local":"other";}catch(Exception ignored){return "other";}
    }
    private void reactivateWebView(String reason){
        final WebView web=view;
        web.post(()->{
            if(destroyed || view!=web)return;
            web.requestLayout();web.invalidate();
            final long serial=++diagnosticSerial;
            lifecycleEvent("visual_requested","serial="+serial+" reason="+reason);
            web.postVisualStateCallback(serial,new WebView.VisualStateCallback(){
                @Override public void onComplete(long requestId){
                    if(!destroyed && view==web){web.invalidate();lifecycleEvent("visual_complete","serial="+requestId);}
                }
            });
            diagnoseWebView(reason);
        });
    }
    private void diagnoseWebView(String reason){
        final WebView web=view;if(web==null || destroyed)return;
        final long serial=++diagnosticSerial;
        final boolean[] completed={false};
        lifecycleEvent("diagnostic_requested","serial="+serial+" reason="+reason+" nativeUrlClass="+urlClass(web.getUrl())+" width="+web.getWidth()+" height="+web.getHeight());
        final String script="(function(){var d=document,b=d.body,r=d.documentElement;return {urlClass:location.protocol==='https:'&&location.hostname==='appassets.androidplatform.net'?'local':location.href==='about:blank'?'blank':'other',readyState:d.readyState,visibility:d.visibilityState,bodyChildCount:b?b.children.length:0,bodyWidth:b?b.clientWidth:0,bodyHeight:b?b.clientHeight:0,rootWidth:r?r.clientWidth:0,rootHeight:r?r.clientHeight:0,shellPresent:!!(d.getElementById('main')&&d.getElementById('brand'))};})()";
        web.evaluateJavascript(script,result->{
            completed[0]=true;if(destroyed || view!=web)return;
            try{
                JSONObject received=new JSONObject(result),safe=new JSONObject();
                safe.put("serial",serial);
                for(String key:new String[]{"urlClass","readyState","visibility"}){
                    String value=received.optString(key,"unknown");
                    String allowed=key.equals("urlClass")?"local|blank|other":key.equals("readyState")?"loading|interactive|complete":"visible|hidden|prerender";
                    safe.put(key,value.matches(allowed)?value:"unknown");
                }
                for(String key:new String[]{"bodyChildCount","bodyWidth","bodyHeight","rootWidth","rootHeight"}){
                    int count=received.optInt(key,-1);safe.put(key,count>=0 && count<=100000?count:-1);
                }
                safe.put("shellPresent",received.optBoolean("shellPresent",false));
                lifecycleEvent("diagnostic_result",safe.toString());
            }catch(Exception invalid){lifecycleEvent("diagnostic_invalid","serial="+serial);}
        });
        web.postDelayed(()->{if(!destroyed && view==web && !completed[0])lifecycleEvent("diagnostic_timeout","serial="+serial);},3000);
    }

    @Override public void onBackPressed() {
        lifecycleEvent("back","canGoBack="+(view!=null && view.canGoBack())+" nativeUrlClass="+(view==null?"blank":urlClass(view.getUrl())));
        if(view!=null && view.canGoBack())view.goBack();else super.onBackPressed();
    }
    @Override protected void onDestroy() {
        lifecycleEvent("destroy","finishing="+isFinishing());
        destroyed=true;workspaceReady=false;
        if(chooser!=null){chooser.onReceiveValue(null);chooser=null;}
        view.removeJavascriptInterface("TaxRebornAndroid");view.destroy();super.onDestroy();
    }
}
