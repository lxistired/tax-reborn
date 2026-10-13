package io.github.lxistired.taxreborn;

import java.io.*;
import java.util.*;

/** Private, bounded transfer files. No tax data is stored in Activity Bundles. */
public final class LocalTransferStore {
    public static final int MAX_BYTES = 15_000_000;
    private static final String UUID_PATTERN="[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}";
    private static final String CAPTURE_PREFIX="content://io.github.lxistired.taxreborn.capture/";
    private LocalTransferStore() {}

    public static boolean validId(String value) {return value!=null && value.matches(UUID_PATTERN);}

    public static String captureId(String uri) {
        if(uri==null || !uri.startsWith(CAPTURE_PREFIX) || !uri.endsWith(".jpg"))return null;
        String id=uri.substring(CAPTURE_PREFIX.length(),uri.length()-4);
        return validId(id)?id:null;
    }

    public static File captureFile(File cache,String uri)throws IOException {
        String id=captureId(uri);if(id==null)throw new IOException("Invalid temporary photo");
        return new File(new File(cache,"captures"),id+".jpg");
    }

    public static File exportFile(File cache,String name)throws IOException {
        if(name==null || !name.endsWith(".bin") || !validId(name.substring(0,name.length()-4)))throw new IOException("Invalid temporary export");
        return new File(new File(cache,"exports"),name);
    }

    public static File stageExport(File cache,byte[] bytes)throws IOException {
        if(bytes==null || bytes.length==0 || bytes.length>MAX_BYTES)throw new IOException("Export size is not supported");
        File folder=new File(cache,"exports");if(!folder.isDirectory() && !folder.mkdirs())throw new IOException("Private export folder is unavailable");
        File destination=exportFile(cache,UUID.randomUUID().toString()+".bin");
        try(FileOutputStream stream=new FileOutputStream(destination)){stream.write(bytes);stream.getFD().sync();}
        catch(IOException error){destination.delete();throw error;}
        return destination;
    }

    public static byte[] readBounded(InputStream stream)throws IOException {
        if(stream==null)throw new IOException("Document stream is unavailable");
        ByteArrayOutputStream buffer=new ByteArrayOutputStream();byte[] chunk=new byte[16384];int count;
        while((count=stream.read(chunk))!=-1){if(buffer.size()+count>MAX_BYTES)throw new IOException("Document is too large");buffer.write(chunk,0,count);}
        if(buffer.size()==0)throw new IOException("Document is empty");return buffer.toByteArray();
    }

    public static String[] acceptedMimeTypes(String[] requested) {
        LinkedHashSet<String> result=new LinkedHashSet<>();
        if(requested!=null)for(String entry:requested){if(entry==null)continue;for(String type:entry.split(",")){
            type=type.trim().toLowerCase(Locale.ROOT);
            if(type.equals(".json"))type="application/json";
            if(type.equals(".csv"))type="text/csv";
            if(type.equals(".pdf"))type="application/pdf";
            if(type.equals("image/*") || type.equals("image/jpeg") || type.equals("image/png") || type.equals("application/pdf") || type.equals("application/json") || type.equals("text/csv"))result.add(type);
        }}
        if(result.isEmpty()){result.add("image/*");result.add("application/pdf");}
        return result.toArray(new String[0]);
    }

    public static boolean documentPicker(String[] accepted) {
        if(accepted==null || accepted.length==0)return false;
        for(String type:accepted)if(!type.startsWith("image/") && !type.equals("application/pdf"))return false;
        return true;
    }
}
