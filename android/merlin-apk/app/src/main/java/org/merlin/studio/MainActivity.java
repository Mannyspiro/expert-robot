package org.merlin.studio;

import android.app.Activity;
import android.os.Bundle;
import android.graphics.Color;
import android.view.View;
import android.widget.LinearLayout;
import android.widget.TextView;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.webkit.WebResourceRequest;
import android.webkit.WebResourceResponse;
import android.webkit.WebChromeClient;
import android.graphics.Bitmap;
import android.net.Uri;
import com.chaquo.python.Python;

import java.io.File;
import java.io.InputStream;
import java.io.FileOutputStream;
import java.io.ByteArrayInputStream;
import java.io.IOException;

public final class MainActivity extends Activity {
    private static final int STUDIO_PORT = 8771;
    private WebView web;
    private TextView status;
    private boolean started = false;

    private static boolean isLocal(Uri uri) {
        if (uri == null || !"http".equalsIgnoreCase(uri.getScheme())) return false;
        String host = uri.getHost();
        return ("127.0.0.1".equals(host) || "localhost".equalsIgnoreCase(host))
                && uri.getPort() == STUDIO_PORT;
    }

    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        getWindow().setStatusBarColor(Color.rgb(19, 23, 33));
        getWindow().setNavigationBarColor(Color.rgb(19, 23, 33));
        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setBackgroundColor(Color.rgb(19, 23, 33));
        status = new TextView(this);
        status.setTextColor(Color.WHITE);
        status.setPadding(24, 24, 24, 24);
        status.setText("Starting Merlin Studio locally...");
        root.addView(status);
        web = new WebView(this);
        WebSettings settings = web.getSettings();
        settings.setJavaScriptEnabled(true);
        settings.setDomStorageEnabled(true);
        settings.setAllowFileAccess(false);
        settings.setAllowContentAccess(false);
        settings.setJavaScriptCanOpenWindowsAutomatically(false);
        settings.setSupportMultipleWindows(false);
        settings.setMixedContentMode(WebSettings.MIXED_CONTENT_NEVER_ALLOW);
        web.setWebChromeClient(new WebChromeClient());
        web.setWebViewClient(new WebViewClient() {
            @Override public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest request) {
                return !isLocal(request.getUrl());
            }
            @Override public WebResourceResponse shouldInterceptRequest(WebView view, WebResourceRequest request) {
                Uri uri = request.getUrl();
                if (isLocal(uri) || "data".equalsIgnoreCase(uri.getScheme())) return null;
                return new WebResourceResponse("text/plain", "UTF-8", new ByteArrayInputStream(new byte[0]));
            }
            @Override public void onPageFinished(WebView view, String url) {
                if (url.startsWith("http://127.0.0.1:" + STUDIO_PORT + "/")) status.setVisibility(View.GONE);
            }
        });
        root.addView(web, new LinearLayout.LayoutParams(-1, 0, 1f));
        setContentView(root);
        new Thread(() -> {
            try {
                File source = new File(getCacheDir(), "merlin-studio-pinned.zip");
                try (InputStream input = getAssets().open("merlin-studio-pinned.zip");
                     FileOutputStream output = new FileOutputStream(source)) {
                    byte[] data = new byte[65536];
                    int count;
                    while ((count = input.read(data)) != -1) output.write(data, 0, count);
                }
                int port = Python.getInstance().getModule("merlin_android").callAttr(
                        "start", source.getAbsolutePath(), getFilesDir().getAbsolutePath()).toInt();
                if (port != STUDIO_PORT) throw new IllegalStateException("Unexpected local server port");
                runOnUiThread(() -> {
                    started = true;
                    web.loadUrl("http://127.0.0.1:" + STUDIO_PORT + "/studio/");
                });
            } catch (Exception ex) {
                android.util.Log.e("MerlinStudio", "Local engine startup failed", ex);
                runOnUiThread(() -> {
                    status.setVisibility(View.VISIBLE);
                    status.setText("Merlin could not start its local engine. See Android app logs. "
                            + ex.getClass().getSimpleName() + ": " + ex.getMessage());
                });
            }
        }, "merlin-python-bootstrap").start();
    }

    @Override public void onBackPressed() {
        if (started && web != null && web.canGoBack()) web.goBack();
        else super.onBackPressed();
    }

    @Override protected void onDestroy() {
        if (web != null) {
            web.stopLoading();
            web.destroy();
        }
        super.onDestroy();
    }
}
