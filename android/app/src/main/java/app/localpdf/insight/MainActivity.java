package app.localpdf.insight;

import android.app.Activity;
import android.app.AlertDialog;
import android.content.ActivityNotFoundException;
import android.content.ClipData;
import android.content.Intent;
import android.graphics.Color;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.text.InputType;
import android.view.View;
import android.view.WindowInsets;
import android.webkit.ConsoleMessage;
import android.webkit.JsPromptResult;
import android.webkit.JsResult;
import android.webkit.ValueCallback;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceError;
import android.webkit.WebResourceRequest;
import android.webkit.WebResourceResponse;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.EditText;
import android.widget.FrameLayout;
import android.widget.Toast;
import android.window.OnBackInvokedDispatcher;

import androidx.webkit.WebViewAssetLoader;

import java.io.ByteArrayInputStream;
import java.io.IOException;
import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.Collections;
import java.util.HashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

/** A local-only PDF.js container with a narrowly scoped, user-confirmed PDF export channel. */
public final class MainActivity extends Activity {
    private static final String APP_HOST = "appassets.androidplatform.net";
    private static final String START_URL = "https://" + APP_HOST + "/?platform=android";
    private static final int PICK_PDFS = 21;
    private static final Map<String, String> RESPONSE_HEADERS;
    static {
        Map<String, String> headers = new HashMap<>();
        headers.put("X-Content-Type-Options", "nosniff");
        headers.put("Cache-Control", "no-cache");
        headers.put("Content-Security-Policy", "default-src 'none'; script-src 'self' 'wasm-unsafe-eval'; "
                + "style-src 'self' 'unsafe-inline'; img-src 'self' blob: data:; "
                + "font-src 'self' blob: data:; connect-src 'self' blob:; "
                + "worker-src 'self' blob:; base-uri 'none'; form-action 'none'; "
                + "frame-ancestors 'none'");
        RESPONSE_HEADERS = Collections.unmodifiableMap(headers);
    }

    private final Handler mainHandler = new Handler(Looper.getMainLooper());
    private final ExecutorService fileChecks = Executors.newSingleThreadExecutor();
    private WebView webView;
    private WebViewAssetLoader assetLoader;
    private PdfExportController pdfExport;
    private ReadingScreenController readingScreen;
    private ValueCallback<Uri[]> fileCallback;
    private AlertDialog exitDialog;
    private boolean backPending;
    private boolean compatibilityWarning;

    @Override
    @SuppressWarnings("deprecation")
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        FrameLayout container = new FrameLayout(this);
        container.setBackgroundColor(Color.rgb(23, 63, 59));
        webView = new WebView(this);
        webView.setBackgroundColor(Color.rgb(251, 252, 248));
        container.addView(webView, new FrameLayout.LayoutParams(
                FrameLayout.LayoutParams.MATCH_PARENT, FrameLayout.LayoutParams.MATCH_PARENT));
        setContentView(container);

        if (Build.VERSION.SDK_INT >= 30) {
            getWindow().setDecorFitsSystemWindows(false);
            container.setOnApplyWindowInsetsListener((view, insets) -> {
                android.graphics.Insets safe = insets.getInsets(
                        WindowInsets.Type.systemBars() | WindowInsets.Type.displayCutout());
                android.graphics.Insets keyboard = insets.getInsets(WindowInsets.Type.ime());
                view.setPadding(safe.left, safe.top, safe.right, Math.max(safe.bottom, keyboard.bottom));
                return WindowInsets.CONSUMED;
            });
            container.requestApplyInsets();
        } else {
            container.setFitsSystemWindows(true);
        }

        assetLoader = new WebViewAssetLoader.Builder()
                .addPathHandler("/static/", path -> bundledAsset("static/" + path))
                .addPathHandler("/", path -> path.isEmpty()
                        ? bundledAsset("static/index.html") : blockedResponse(404, "Not found"))
                .build();

        WebSettings settings = webView.getSettings();
        settings.setJavaScriptEnabled(true);
        settings.setDomStorageEnabled(true);
        settings.setAllowFileAccess(false);
        // SAF grants only the documents selected by the user. WebViewClient
        // rejects every content: navigation/request; this setting permits the
        // picker File objects to be read by PDF.js, without broad storage access.
        settings.setAllowContentAccess(true);
        settings.setAllowFileAccessFromFileURLs(false);
        settings.setAllowUniversalAccessFromFileURLs(false);
        settings.setMixedContentMode(WebSettings.MIXED_CONTENT_NEVER_ALLOW);
        settings.setBlockNetworkLoads(true);
        settings.setJavaScriptCanOpenWindowsAutomatically(false);
        settings.setSupportMultipleWindows(false);
        settings.setMediaPlaybackRequiresUserGesture(true);
        settings.setSafeBrowsingEnabled(true);
        settings.setSupportZoom(false); // PDF.js handles page zoom and touch gestures.
        WebView.setWebContentsDebuggingEnabled(BuildConfig.DEBUG);

        webView.setWebViewClient(new WebViewClient() {
            @Override
            public void onPageStarted(WebView view, String url, android.graphics.Bitmap favicon) {
                if (readingScreen != null) readingScreen.reset();
            }
            @Override
            public WebResourceResponse shouldInterceptRequest(WebView view, WebResourceRequest request) {
                // PDF.js thumbnails and font faces may be inline data resources.
                // CSP permits these only where appropriate; they cannot use a network.
                if ("data".equals(request.getUrl().getScheme())
                        || "blob".equals(request.getUrl().getScheme())) return null;
                if (!isLocalOrigin(request.getUrl())) return blockedResponse(403, "Local content only");
                WebResourceResponse response = assetLoader.shouldInterceptRequest(request.getUrl());
                return response != null ? response : blockedResponse(404, "Not found");
            }

            @Override
            public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest request) {
                if (isLocalOrigin(request.getUrl()) && "/".equals(request.getUrl().getPath())) {
                    if (!"android".equals(request.getUrl().getQueryParameter("platform"))) {
                        view.loadUrl(START_URL);
                        return true;
                    }
                    return false;
                }
                toast(R.string.external_links_disabled);
                return true;
            }

            @Override
            public void onReceivedError(WebView view, WebResourceRequest request, WebResourceError error) {
                if (request.isForMainFrame()) {
                    if (readingScreen != null) readingScreen.reset();
                    toast(R.string.webview_error);
                }
            }

            @Override
            public void onPageFinished(WebView view, String url) {
                if (!isLocalOrigin(Uri.parse(url))) return;
                view.evaluateJavascript("Boolean(typeof Promise.withResolvers === 'function'"
                        + " && 'noModule' in document.createElement('script')"
                        + " && typeof Uint8Array.prototype.toHex === 'function'"
                        + " && typeof Uint8Array.prototype.toBase64 === 'function'"
                        + " && typeof Uint8Array.fromBase64 === 'function')", ready -> {
                    if (!"true".equals(ready) && !compatibilityWarning && !isDestroyed()) {
                        compatibilityWarning = true;
                        webView.setVisibility(View.INVISIBLE);
                        new AlertDialog.Builder(MainActivity.this)
                                .setTitle(R.string.update_webview_title)
                                .setMessage(R.string.update_webview_detail)
                                .setCancelable(false)
                                .setPositiveButton(R.string.exit, (dialog, which) -> finish())
                                .show();
                    }
                });
            }
        });
        webView.setWebChromeClient(new ReaderChromeClient());
        webView.setDownloadListener((url, userAgent, disposition, mime, length) ->
                toast(R.string.downloads_disabled));
        pdfExport = PdfExportController.install(this, webView);
        readingScreen = ReadingScreenController.install(this, webView);

        if (Build.VERSION.SDK_INT >= 33) {
            getOnBackInvokedDispatcher().registerOnBackInvokedCallback(
                    OnBackInvokedDispatcher.PRIORITY_DEFAULT, this::handleBack);
        }
        // Reopening uses the persisted IndexedDB library and reading position.
        // Rotation stays in this Activity, preserving PDF bytes and picker callbacks.
        webView.loadUrl(START_URL);
    }

    private boolean isLocalOrigin(Uri uri) {
        return uri != null && "https".equals(uri.getScheme())
                && APP_HOST.equals(uri.getHost()) && uri.getUserInfo() == null
                && (uri.getPort() == -1 || uri.getPort() == 443);
    }

    private WebResourceResponse bundledAsset(String path) {
        if (path.contains("..") || path.contains("\\") || path.startsWith("/"))
            return blockedResponse(403, "Invalid asset path");
        String extension = path.substring(path.lastIndexOf('.') + 1).toLowerCase(Locale.ROOT);
        String mime;
        switch (extension) {
            case "html": mime = "text/html"; break;
            case "js":
            case "mjs": mime = "text/javascript"; break;
            case "css": mime = "text/css"; break;
            case "json":
            case "webmanifest": mime = "application/json"; break;
            case "svg": mime = "image/svg+xml"; break;
            case "png": mime = "image/png"; break;
            case "jpg":
            case "jpeg": mime = "image/jpeg"; break;
            case "gif": mime = "image/gif"; break;
            case "wasm": mime = "application/wasm"; break;
            case "ttf": mime = "font/ttf"; break;
            case "otf": mime = "font/otf"; break;
            case "woff": mime = "font/woff"; break;
            case "woff2": mime = "font/woff2"; break;
            default: mime = "application/octet-stream";
        }
        String encoding = mime.startsWith("text/") || mime.endsWith("json")
                || mime.equals("image/svg+xml") ? "UTF-8" : null;
        try {
            return new WebResourceResponse(mime, encoding, 200, "OK", RESPONSE_HEADERS,
                    getAssets().open(path));
        } catch (IOException missing) {
            return blockedResponse(404, "Not found");
        }
    }

    private WebResourceResponse blockedResponse(int status, String message) {
        return new WebResourceResponse("text/plain", "UTF-8", status, message,
                RESPONSE_HEADERS, new ByteArrayInputStream(message.getBytes(StandardCharsets.UTF_8)));
    }

    private final class ReaderChromeClient extends WebChromeClient {
        @Override
        public boolean onShowFileChooser(WebView view, ValueCallback<Uri[]> callback,
                                         FileChooserParams params) {
            cancelFileCallback();
            fileCallback = callback;
            if (params.getMode() != FileChooserParams.MODE_OPEN
                    && params.getMode() != FileChooserParams.MODE_OPEN_MULTIPLE) {
                cancelFileCallback();
                return true;
            }
            Intent intent = new Intent(Intent.ACTION_OPEN_DOCUMENT)
                    .addCategory(Intent.CATEGORY_OPENABLE)
                    .setType("application/pdf")
                    .putExtra(Intent.EXTRA_ALLOW_MULTIPLE,
                            params.getMode() == FileChooserParams.MODE_OPEN_MULTIPLE)
                    .addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);
            try {
                startActivityForResult(intent, PICK_PDFS);
            } catch (ActivityNotFoundException unavailable) {
                cancelFileCallback();
                toast(R.string.picker_unavailable);
            }
            return true;
        }

        @Override
        public boolean onJsAlert(WebView view, String url, String message, JsResult result) {
            new AlertDialog.Builder(MainActivity.this)
                    .setTitle(R.string.app_name).setMessage(message)
                    .setPositiveButton(R.string.ok, (dialog, which) -> result.confirm())
                    .setOnCancelListener(dialog -> result.cancel()).show();
            return true;
        }

        @Override
        public boolean onJsConfirm(WebView view, String url, String message, JsResult result) {
            new AlertDialog.Builder(MainActivity.this)
                    .setTitle(R.string.app_name).setMessage(message)
                    .setPositiveButton(R.string.ok, (dialog, which) -> result.confirm())
                    .setNegativeButton(R.string.cancel, (dialog, which) -> result.cancel())
                    .setOnCancelListener(dialog -> result.cancel()).show();
            return true;
        }

        @Override
        public boolean onJsPrompt(WebView view, String url, String message, String defaultValue,
                                  JsPromptResult result) {
            EditText input = new EditText(MainActivity.this);
            input.setSingleLine(true);
            input.setText(defaultValue);
            String lower = message.toLowerCase(Locale.ROOT);
            if (lower.contains("password") || lower.contains("كلمة المرور"))
                input.setInputType(InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_VARIATION_PASSWORD);
            FrameLayout wrapper = new FrameLayout(MainActivity.this);
            int margin = Math.round(24 * getResources().getDisplayMetrics().density);
            FrameLayout.LayoutParams layout = new FrameLayout.LayoutParams(
                    FrameLayout.LayoutParams.MATCH_PARENT, FrameLayout.LayoutParams.WRAP_CONTENT);
            layout.setMargins(margin, 0, margin, 0);
            wrapper.addView(input, layout);
            new AlertDialog.Builder(MainActivity.this)
                    .setTitle(R.string.app_name).setMessage(message).setView(wrapper)
                    .setPositiveButton(R.string.ok,
                            (dialog, which) -> result.confirm(input.getText().toString()))
                    .setNegativeButton(R.string.cancel, (dialog, which) -> result.cancel())
                    .setOnCancelListener(dialog -> result.cancel()).show();
            return true;
        }

        @Override
        public boolean onConsoleMessage(ConsoleMessage message) {
            // Documents, notes and selected passages never enter Android logs.
            return true;
        }
    }

    @Override
    @SuppressWarnings("deprecation")
    protected void onActivityResult(int requestCode, int resultCode, Intent data) {
        super.onActivityResult(requestCode, resultCode, data);
        if (pdfExport != null && pdfExport.onActivityResult(requestCode, resultCode, data)) return;
        if (requestCode != PICK_PDFS || fileCallback == null) return;
        if (resultCode != RESULT_OK || data == null) {
            cancelFileCallback();
            return;
        }
        ValueCallback<Uri[]> expectedCallback = fileCallback;
        LinkedHashSet<Uri> candidates = new LinkedHashSet<>();
        ClipData clip = data.getClipData();
        if (clip != null) {
            for (int i = 0; i < clip.getItemCount(); i++)
                candidates.add(clip.getItemAt(i).getUri());
        } else if (data.getData() != null) {
            candidates.add(data.getData());
        }
        fileChecks.execute(() -> {
            List<Uri> accepted = new ArrayList<>();
            for (Uri candidate : candidates) if (isReadablePdf(candidate)) accepted.add(candidate);
            mainHandler.post(() -> {
                if (isDestroyed() || fileCallback != expectedCallback) return;
                fileCallback = null;
                expectedCallback.onReceiveValue(accepted.isEmpty() ? null : accepted.toArray(new Uri[0]));
                if (accepted.size() != candidates.size() || accepted.isEmpty()) toast(R.string.invalid_pdf);
            });
        });
    }

    private boolean isReadablePdf(Uri uri) {
        if (uri == null || !"content".equals(uri.getScheme())
                || uri.getAuthority() == null || uri.getAuthority().isEmpty()) return false;
        // The picker may label a valid PDF as application/octet-stream. Inspect
        // its small header instead of trusting MIME types, names or file URLs.
        try (InputStream stream = getContentResolver().openInputStream(uri)) {
            if (stream == null) return false;
            byte[] header = new byte[1024];
            int length = 0;
            while (length < header.length) {
                int count = stream.read(header, length, header.length - length);
                if (count <= 0) break;
                length += count;
            }
            for (int i = 0; i + 4 < length; i++) {
                if (header[i] == '%' && header[i + 1] == 'P' && header[i + 2] == 'D'
                        && header[i + 3] == 'F' && header[i + 4] == '-') return true;
            }
        } catch (IOException | RuntimeException unavailable) {
            return false;
        }
        return false;
    }

    private void cancelFileCallback() {
        if (fileCallback != null) {
            ValueCallback<Uri[]> callback = fileCallback;
            fileCallback = null;
            callback.onReceiveValue(null);
        }
    }

    @Override
    @SuppressWarnings("deprecation")
    public void onBackPressed() {
        handleBack();
    }

    private void handleBack() {
        if (backPending || (exitDialog != null && exitDialog.isShowing())) return;
        backPending = true;
        webView.evaluateJavascript("Boolean(window.localPDFBack && window.localPDFBack())", handled -> {
            if (isDestroyed() || webView == null) { backPending = false; return; }
            if ("true".equals(handled)) {
                backPending = false;
                return;
            }
            webView.evaluateJavascript("Boolean(window.localPDFHasUnsavedEdits"
                    + " && window.localPDFHasUnsavedEdits())", dirty -> {
                backPending = false;
                if (isDestroyed() || webView == null) return;
                boolean unsaved = "true".equals(dirty);
                if (!unsaved && webView.canGoBack()) {
                    webView.goBack();
                    return;
                }
                exitDialog = new AlertDialog.Builder(this)
                        .setTitle(R.string.exit_title)
                        .setMessage(unsaved ? R.string.exit_unsaved_detail : R.string.exit_detail)
                        .setPositiveButton(unsaved ? R.string.close_without_saving : R.string.exit,
                                (dialog, which) -> finish())
                        .setNegativeButton(R.string.cancel, null).create();
                exitDialog.show();
            });
        });
    }

    private void toast(int message) {
        Toast.makeText(this, message, Toast.LENGTH_LONG).show();
    }

    @Override
    protected void onPause() {
        if (readingScreen != null) readingScreen.setResumed(false);
        super.onPause();
        if (webView != null) webView.onPause();
    }

    @Override
    protected void onResume() {
        super.onResume();
        if (webView != null) webView.onResume();
        if (readingScreen != null) readingScreen.setResumed(true);
    }

    @Override
    public void onWindowFocusChanged(boolean hasFocus) {
        super.onWindowFocusChanged(hasFocus);
        if (readingScreen != null) readingScreen.setFocused(hasFocus);
    }

    @Override
    protected void onDestroy() {
        cancelFileCallback();
        if (pdfExport != null) pdfExport.close();
        if (readingScreen != null) readingScreen.close();
        fileChecks.shutdownNow();
        mainHandler.removeCallbacksAndMessages(null);
        if (webView != null) {
            webView.stopLoading();
            ((FrameLayout) webView.getParent()).removeView(webView);
            webView.destroy();
            webView = null;
        }
        super.onDestroy();
    }
}
