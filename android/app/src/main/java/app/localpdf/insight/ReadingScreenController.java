package app.localpdf.insight;

import android.app.Activity;
import android.view.WindowManager;
import android.webkit.WebView;
import androidx.webkit.WebMessageCompat;
import androidx.webkit.WebViewCompat;
import androidx.webkit.WebViewFeature;
import java.util.Collections;

/** A foreground-only screen flag. No wake lock, permission or general JS bridge. */
final class ReadingScreenController {
    private static final String OBJECT = "LocalPDFReader";
    private final Activity activity;
    private final WebView webView;
    private boolean requested, resumed, focused, closed;

    static ReadingScreenController install(Activity activity, WebView webView) {
        if (!WebViewFeature.isFeatureSupported(WebViewFeature.WEB_MESSAGE_LISTENER)) return null;
        ReadingScreenController controller = new ReadingScreenController(activity, webView);
        WebViewCompat.addWebMessageListener(webView, OBJECT,
                Collections.singleton("https://appassets.androidplatform.net"),
                (view, message, origin, mainFrame, reply) -> {
                    if (controller.closed || !mainFrame || origin == null
                            || !"https".equals(origin.getScheme())
                            || !"appassets.androidplatform.net".equals(origin.getHost())
                            || origin.getUserInfo() != null
                            || (origin.getPort() != -1 && origin.getPort() != 443)
                            || message.getType() != WebMessageCompat.TYPE_STRING) return;
                    if ("keep-screen-on".equals(message.getData())) controller.requested = true;
                    else if ("allow-screen-off".equals(message.getData())) controller.requested = false;
                    else return;
                    controller.apply();
                });
        return controller;
    }

    private ReadingScreenController(Activity activity, WebView webView) {
        this.activity = activity;
        this.webView = webView;
    }
    void setResumed(boolean value) { resumed = value; apply(); }
    void setFocused(boolean value) { focused = value; apply(); }
    void reset() { requested = false; apply(); }
    private void apply() {
        if (!closed && requested && resumed && focused)
            activity.getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
        else activity.getWindow().clearFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
    }
    void close() {
        closed = true;
        apply();
        if (WebViewFeature.isFeatureSupported(WebViewFeature.WEB_MESSAGE_LISTENER))
            WebViewCompat.removeWebMessageListener(webView, OBJECT);
    }
}
