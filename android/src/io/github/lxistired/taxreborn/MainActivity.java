package io.github.lxistired.taxreborn;

import android.app.Activity;
import android.content.Intent;
import android.content.ClipData;
import android.content.SharedPreferences;
import android.net.Uri;
import android.os.Bundle;
import android.util.Base64;
import android.webkit.*;
import android.widget.Toast;
import java.io.*;
import java.util.*;
import org.json.JSONObject;

/** Bundled offline tax calculation. No account, tax-server or network permission. */
public final class MainActivity extends Activity {
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
        transfers=getSharedPreferences("local_transfers",MODE_PRIVATE);
        restoreTransfers(state);
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
            runOnUiThread(()->{if(destroyed)return;activeReturnId=LocalTransferStore.validId(returnId)?returnId:null;workspaceReady=true;dispatchPendingDocument();});
        }
        @JavascriptInterface public void acknowledgeDocument(String documentId) {
            runOnUiThread(()->{if(destroyed || pendingDocumentId==null || !pendingDocumentId.equals(documentId))return;clearPendingDocument(true);});
        }
        @JavascriptInterface public void saveFile(String filename,String mime,String encoded) {
            if (encoded==null || encoded.length()>20_000_000) return;
            try {
                byte[] bytes=Base64.decode(encoded,Base64.DEFAULT);
                String safeName=filename==null?"tax-reborn-draft":filename.replaceAll("[^A-Za-z0-9._-]","_");
                String safeMime=Arrays.asList("application/json","application/pdf","text/html","image/png","image/jpeg").contains(mime)?mime:"application/octet-stream";
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
                    try {startActivityForResult(intent,FILE_SAVE);} catch(Exception e) {clearPendingSave();Toast.makeText(MainActivity.this,"Could not open the save picker",Toast.LENGTH_LONG).show();}
                });
            } catch(IllegalArgumentException e) {runOnUiThread(()->Toast.makeText(MainActivity.this,"Draft export data was invalid",Toast.LENGTH_LONG).show());}
        }
    }

    @Override protected void onActivityResult(int request,int result,Intent data) {
        super.onActivityResult(request,result,data);
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
                    Toast.makeText(this,"Draft saved on this device. No return was filed.",Toast.LENGTH_LONG).show();
                } catch(IOException e) {Toast.makeText(this,"Draft export was not saved",Toast.LENGTH_LONG).show();}
            }
            clearPendingSave();
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
        if(cameraUri!=null)state.putString("camera_uri",cameraUri.toString());
        // SPA draft data lives in private IndexedDB; no photo/export bytes enter
        // Binder state. The small transfer journal survives Activity recreation.
        super.onSaveInstanceState(state);
    }

    @Override protected void onResume(){super.onResume();if(view!=null)view.onResume();dispatchPendingDocument();}
    @Override protected void onPause(){if(view!=null)view.onPause();super.onPause();}

    @Override public void onBackPressed() {
        if(view.canGoBack())view.goBack();else super.onBackPressed();
    }
    @Override protected void onDestroy() {
        destroyed=true;workspaceReady=false;
        if(chooser!=null){chooser.onReceiveValue(null);chooser=null;}
        view.removeJavascriptInterface("TaxRebornAndroid");view.destroy();super.onDestroy();
    }
}
