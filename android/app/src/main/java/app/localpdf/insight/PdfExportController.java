package app.localpdf.insight;

import android.app.Activity;
import android.content.ActivityNotFoundException;
import android.content.Intent;
import android.net.Uri;
import android.os.Handler;
import android.os.Looper;
import android.provider.DocumentsContract;
import android.util.Base64;
import android.webkit.WebView;
import android.widget.Toast;

import androidx.webkit.JavaScriptReplyProxy;
import androidx.webkit.WebMessageCompat;
import androidx.webkit.WebViewCompat;
import androidx.webkit.WebViewFeature;

import org.json.JSONException;
import org.json.JSONObject;

import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.OutputStream;
import java.util.Collections;
import java.util.UUID;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.atomic.AtomicBoolean;

/** Narrow, origin-restricted PDF export channel. No general JavaScript bridge. */
final class PdfExportController {
    private static final String ORIGIN = "https://appassets.androidplatform.net";
    private static final String OBJECT = "LocalPDFExport";
    private static final int CREATE_PDF = 22;
    private static final long MAX_BYTES = 220L * 1024 * 1024;
    private static final int MAX_CHUNK = 192 * 1024;
    private final Activity activity;
    private final WebView webView;
    private final Handler ui = new Handler(Looper.getMainLooper());
    private final ExecutorService worker = Executors.newSingleThreadExecutor();
    private final AtomicBoolean messagePending = new AtomicBoolean();
    private final File directory;
    private volatile boolean closed;
    private volatile boolean pickerPending;
    // Captured on the UI thread: a late picker result must never bind to a newer export.
    private Export pickerExport;
    // Only the single worker reads/writes this state.
    private Export current;

    private static final class Export {
        final String id;
        final String name;
        final long size;
        final File file;
        final JavaScriptReplyProxy reply;
        FileOutputStream stream;
        long written;
        int nextChunk;
        boolean choosing;
        volatile boolean cancelled;
        Export(String id, String name, long size, File file,
               FileOutputStream stream, JavaScriptReplyProxy reply) {
            this.id = id;
            this.name = name;
            this.size = size;
            this.file = file;
            this.stream = stream;
            this.reply = reply;
        }
    }

    static PdfExportController install(Activity activity, WebView webView) {
        if (!WebViewFeature.isFeatureSupported(WebViewFeature.WEB_MESSAGE_LISTENER)) return null;
        PdfExportController controller = new PdfExportController(activity, webView);
        WebViewCompat.addWebMessageListener(webView, OBJECT, Collections.singleton(ORIGIN),
                (view, message, origin, mainFrame, reply) -> {
                    if (!mainFrame || origin == null || !"https".equals(origin.getScheme())
                            || !"appassets.androidplatform.net".equals(origin.getHost())
                            || origin.getUserInfo() != null
                            || (origin.getPort() != -1 && origin.getPort() != 443)
                            || controller.closed || message.getType() != WebMessageCompat.TYPE_STRING)
                        return;
                    String data = message.getData();
                    if (data == null || data.length() > MAX_CHUNK * 4 / 3 + 1024) return;
                    // Backpressure bounds queued bytes even if a faulty caller floods the channel.
                    if (!controller.messagePending.compareAndSet(false, true)) return;
                    controller.worker.execute(() -> controller.receive(data, reply));
                });
        return controller;
    }

    private PdfExportController(Activity activity, WebView webView) {
        this.activity = activity;
        this.webView = webView;
        directory = new File(activity.getCacheDir(), "pdf-exports");
        worker.execute(() -> {
            // Abandoned exports contain private document data: purge them after a process restart.
            File[] abandoned = directory.listFiles();
            if (abandoned != null) for (File file : abandoned) if (file.isFile()) file.delete();
        });
    }

    private void receive(String data, JavaScriptReplyProxy reply) {
        String id = "";
        try {
            if (closed) return;
            JSONObject message = new JSONObject(data);
            id = message.getString("id");
            if (!id.matches("[A-Za-z0-9_-]{1,64}")) throw new JSONException("Invalid ID");
            String action = message.getString("action");
            if ("begin".equals(action)) {
                if (current != null || pickerPending) {
                    send(reply, id, "error", -1, R.string.export_busy);
                    return;
                }
                Object sizeValue = message.get("size");
                if (!(sizeValue instanceof Number)) throw new JSONException("Invalid size");
                long size = ((Number) sizeValue).longValue();
                if (size < 5 || size > MAX_BYTES || ((Number) sizeValue).doubleValue() != size)
                    throw new JSONException("Invalid size");
                String name = safeName(message.getString("filename"));
                if (!directory.isDirectory() && !directory.mkdir()) throw new IOException("No cache");
                File file = new File(directory, UUID.randomUUID() + ".pdf");
                current = new Export(id, name, size, file, new FileOutputStream(file), reply);
                send(reply, id, "ready", -1, 0);
                return;
            }
            if (current == null || !current.id.equals(id)) {
                send(reply, id, "error", -1, R.string.export_invalid);
                return;
            }
            if ("cancel".equals(action)) {
                discard();
                send(reply, id, "cancelled", -1, 0);
                return;
            }
            if (current.choosing) {
                // A duplicate finish/chunk must not discard the file behind an open save picker.
                send(reply, id, "error", -1, R.string.export_busy);
                return;
            }
            if ("chunk".equals(action)) {
                Object indexValue = message.get("index");
                if (!(indexValue instanceof Number)
                        || ((Number) indexValue).doubleValue() != current.nextChunk)
                    throw new JSONException("Out-of-order chunk");
                String encoded = message.getString("data");
                if (encoded.isEmpty() || encoded.length() > MAX_CHUNK * 4 / 3
                        || encoded.length() % 4 != 0 || !encoded.matches("[A-Za-z0-9+/]*={0,2}"))
                    throw new JSONException("Invalid chunk");
                byte[] bytes = Base64.decode(encoded, Base64.NO_WRAP);
                if (bytes.length == 0 || bytes.length > MAX_CHUNK
                        || current.written + bytes.length > current.size)
                    throw new JSONException("Invalid chunk size");
                current.stream.write(bytes);
                current.written += bytes.length;
                send(reply, id, "chunk", current.nextChunk++, 0);
            } else if ("finish".equals(action)) {
                if (current.written != current.size) throw new JSONException("Incomplete PDF");
                current.stream.close();
                current.stream = null;
                if (!hasPdfHeader(current.file)) throw new JSONException("Invalid PDF");
                current.choosing = true;
                pickerPending = true;
                Export completed = current;
                send(reply, id, "choosing", -1, 0);
                ui.post(() -> chooseDestination(completed));
            } else throw new JSONException("Invalid action");
        } catch (JSONException | IllegalArgumentException malformed) {
            if (current != null && current.id.equals(id)) discard();
            send(reply, id.matches("[A-Za-z0-9_-]{1,64}") ? id : "", "error", -1,
                    R.string.export_invalid);
        } catch (IOException unavailable) {
            if (current != null && current.id.equals(id)) discard();
            send(reply, id, "error", -1, R.string.export_failed);
        }
    }

    @SuppressWarnings("deprecation")
    private void chooseDestination(Export completed) {
        if (closed || activity.isDestroyed() || completed.cancelled) {
            pickerPending = false;
            return;
        }
        pickerExport = completed;
        Intent intent = new Intent(Intent.ACTION_CREATE_DOCUMENT)
                .addCategory(Intent.CATEGORY_OPENABLE)
                .setType("application/pdf")
                .putExtra(Intent.EXTRA_TITLE, completed.name)
                .addFlags(Intent.FLAG_GRANT_WRITE_URI_PERMISSION);
        try { activity.startActivityForResult(intent, CREATE_PDF); }
        catch (ActivityNotFoundException unavailable) {
            pickerPending = false;
            pickerExport = null;
            worker.execute(() -> {
                if (current != completed) return;
                discard();
                send(completed.reply, completed.id, "error", -1, R.string.picker_unavailable);
            });
        }
    }

    boolean onActivityResult(int requestCode, int resultCode, Intent data) {
        if (requestCode != CREATE_PDF) return false;
        Uri destination = data == null ? null : data.getData();
        Export expected = pickerExport;
        pickerExport = null;
        pickerPending = false;
        worker.execute(() -> {
            Export completed = current;
            if (closed || completed == null || completed != expected || !completed.choosing) {
                // Cancellation or process recreation can leave a late picker result. It must
                // neither attach to another export nor leave a newly created empty PDF behind.
                if (resultCode == Activity.RESULT_OK) deleteCreatedDocument(destination);
                if (!closed && expected == null && resultCode == Activity.RESULT_OK) ui.post(() -> {
                    if (!activity.isDestroyed()) Toast.makeText(activity,
                            R.string.export_failed, Toast.LENGTH_LONG).show();
                });
                return;
            }
            if (resultCode != Activity.RESULT_OK || destination == null) {
                discard();
                send(completed.reply, completed.id, "cancelled", -1, 0);
                return;
            }
            if (!"content".equals(destination.getScheme()) || destination.getAuthority() == null
                    || destination.getAuthority().isEmpty()) {
                discard();
                send(completed.reply, completed.id, "error", -1, R.string.export_failed);
                return;
            }
            boolean success = false;
            try (FileInputStream input = new FileInputStream(completed.file);
                 OutputStream output = activity.getContentResolver().openOutputStream(destination, "wt")) {
                if (output == null) throw new IOException("No output stream");
                byte[] buffer = new byte[64 * 1024];
                int count;
                while ((count = input.read(buffer)) != -1) {
                    if (closed) throw new IOException("Export closed");
                    output.write(buffer, 0, count);
                }
                output.flush();
                success = true;
            } catch (IOException | RuntimeException failed) {
                success = false;
                // Only a destination returned by CREATE_DOCUMENT is touched. Remove partial copies.
                deleteCreatedDocument(destination);
            } finally {
                discard();
            }
            send(completed.reply, completed.id, success ? "saved" : "error", -1,
                    success ? 0 : R.string.export_failed);
        });
        return true;
    }

    private void deleteCreatedDocument(Uri destination) {
        if (destination == null || !"content".equals(destination.getScheme())) return;
        try {
            if (DocumentsContract.isDocumentUri(activity, destination))
                DocumentsContract.deleteDocument(activity.getContentResolver(), destination);
        } catch (Exception ignored) { /* Provider may not support deletion. */ }
    }

    private static String safeName(String name) {
        String cleaned = name.replaceAll("[\\p{Cntrl}/\\\\:*?\"<>|]", "_").trim();
        if (cleaned.length() > 120) cleaned = cleaned.substring(0, 120);
        if (cleaned.isEmpty() || cleaned.equals(".") || cleaned.equals("..")) cleaned = "document-signed";
        if (!cleaned.toLowerCase(java.util.Locale.ROOT).endsWith(".pdf")) cleaned += ".pdf";
        return cleaned;
    }

    private static boolean hasPdfHeader(File file) throws IOException {
        try (FileInputStream input = new FileInputStream(file)) {
            byte[] header = new byte[1024];
            int count = input.read(header);
            for (int i = 0; i + 4 < count; i++) {
                if (header[i] == '%' && header[i + 1] == 'P' && header[i + 2] == 'D'
                        && header[i + 3] == 'F' && header[i + 4] == '-') return true;
            }
        }
        return false;
    }

    private void discard() {
        Export abandoned = current;
        current = null;
        if (abandoned == null) return;
        abandoned.cancelled = true;
        if (abandoned.stream != null) try { abandoned.stream.close(); } catch (IOException ignored) { }
        abandoned.file.delete();
    }

    private void send(JavaScriptReplyProxy reply, String id, String status, int index, int message) {
        JSONObject response = new JSONObject();
        try {
            response.put("id", id).put("status", status);
            if (index >= 0) response.put("index", index);
            if (message != 0) response.put("message", activity.getString(message));
        } catch (JSONException impossible) { return; }
        ui.post(() -> {
            // Clear backpressure immediately before the ACK, so its next chunk cannot race it.
            messagePending.set(false);
            if (!WebViewFeature.isFeatureSupported(WebViewFeature.WEB_MESSAGE_LISTENER)) return;
            if (!closed && !activity.isDestroyed()) reply.postMessage(response.toString());
        });
    }

    void close() {
        closed = true;
        if (WebViewFeature.isFeatureSupported(WebViewFeature.WEB_MESSAGE_LISTENER))
            WebViewCompat.removeWebMessageListener(webView, OBJECT);
        worker.execute(this::discard);
        worker.shutdown();
        ui.removeCallbacksAndMessages(null);
    }
}
