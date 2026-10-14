import io.github.lxistired.taxreborn.LocalTransferStore;
import java.util.Arrays;

/** Actual HTML accept strings must reach Android's document picker as usable MIME filters. */
public final class LocalTransferStoreMimeTypesTest {
    static void require(boolean value, String message) {
        if (!value) throw new AssertionError(message);
    }
    public static void main(String[] args) {
        String[] xml = LocalTransferStore.acceptedMimeTypes(new String[]{
            ".xml,.tax,.zip,application/xml,text/xml,application/zip"});
        require(Arrays.asList(xml).contains("application/xml"), "XML fixture must be selectable");
        require(Arrays.asList(xml).contains("text/xml"), "text/xml providers must be selectable");
        require(Arrays.asList(xml).contains("application/zip"), "declared plaintext ZIP must be selectable");
        require(Arrays.asList(xml).contains("application/octet-stream"), "unknown .tax MIME must remain selectable for inspection");
        require(!LocalTransferStore.documentPicker(xml), "TaxML picker must not become camera/document recovery");
        String[] xprf = LocalTransferStore.acceptedMimeTypes(new String[]{".xprf,application/octet-stream"});
        require(Arrays.asList(xprf).contains("application/octet-stream"), "XPRF fixture must be selectable");
        require(!LocalTransferStore.documentPicker(xprf), "XPRF picker must not become camera/document recovery");
        String[] json = LocalTransferStore.acceptedMimeTypes(new String[]{".json,application/json"});
        require(Arrays.asList(json).contains("application/json"), "profile JSON must be selectable");
        require(!LocalTransferStore.documentPicker(json), "JSON picker must not become camera/document recovery");
        String[] camera = LocalTransferStore.acceptedMimeTypes(new String[]{"image/*,.pdf"});
        require(LocalTransferStore.documentPicker(camera), "existing photo/PDF recovery must be preserved");
        require(!Arrays.asList(camera).contains("application/octet-stream"), "photo picker must not widen to arbitrary files");
        String[] bad = LocalTransferStore.acceptedMimeTypes(new String[]{"text/javascript,.exe"});
        require(!Arrays.asList(bad).contains("text/javascript"), "unsupported MIME must not be admitted");
        require(!Arrays.asList(bad).contains("application/octet-stream"), "unsupported extensions must not widen selection");
        System.out.println("Android real accept strings: XML, ZIP, XPRF, JSON and unchanged photo/PDF recovery passed");
    }
}
