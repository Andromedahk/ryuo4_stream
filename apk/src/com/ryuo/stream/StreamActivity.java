package com.ryuo.stream;

import android.app.Activity;
import android.content.Intent;
import android.graphics.Color;
import android.media.MediaPlayer;
import android.net.Uri;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.util.Log;
import android.view.Gravity;
import android.view.View;
import android.view.Window;
import android.view.WindowInsets;
import android.view.WindowInsetsController;
import android.view.WindowManager;
import android.widget.FrameLayout;
import android.widget.TextView;
import android.widget.VideoView;

/**
 * Minimal fullscreen video/stream player for the RYUO IV panel.
 *
 * Extras:
 *   url     (String)  http/https/rtsp URL or file:// URI. Default http://127.0.0.1:18080/live.ts
 *   restart (boolean) auto-restart after completion/error/timeout, default true
 *   hud     (boolean) show the debug HUD, default true
 *
 * NOTE: all listener/task types are STATIC nested classes that hold an explicit
 * reference to the activity. Reason: d8 from build-tools 33.0.2 (R8 3.3.20)
 * crashes with an internal NPE on non-static inner classes compiled by the
 * JDK 21 javac (synthetic outer-instance constructor parameter + MethodParameters
 * attribute). Static nested classes dex fine.
 */
public class StreamActivity extends Activity {

    private static final String TAG = "RYUO_STREAM";
    private static final String DEFAULT_URL = "http://127.0.0.1:18080/live.ts";
    private static final long RESTART_DELAY_MS = 800L;
    private static final long OPEN_TIMEOUT_MS = 15000L;

    private VideoView videoView;
    private TextView hud;
    private Handler handler;

    private String url;
    private boolean autoRestart = true;
    private boolean hudEnabled = true;
    private boolean prepared = false;
    private int restartCount = 0;
    private String lastState = "";

    private Runnable restartTask;
    private Runnable openTimeoutTask;

    private static final class RestartTask implements Runnable {
        private final StreamActivity host;

        RestartTask(StreamActivity host) {
            this.host = host;
        }

        @Override
        public void run() {
            host.restartCount++;
            Log.i(TAG, "auto-restart #" + host.restartCount);
            host.open();
        }
    }

    private static final class OpenTimeoutTask implements Runnable {
        private final StreamActivity host;

        OpenTimeoutTask(StreamActivity host) {
            this.host = host;
        }

        @Override
        public void run() {
            if (!host.prepared) {
                Log.e(TAG, "open timeout after " + OPEN_TIMEOUT_MS + "ms, url=" + host.url);
                host.setState("TIMEOUT " + OPEN_TIMEOUT_MS + "ms");
                host.scheduleRestart();
            }
        }
    }

    private static final class PreparedListener implements MediaPlayer.OnPreparedListener {
        private final StreamActivity host;

        PreparedListener(StreamActivity host) {
            this.host = host;
        }

        @Override
        public void onPrepared(MediaPlayer mp) {
            host.handler.removeCallbacks(host.openTimeoutTask);
            host.prepared = true;
            try {
                mp.setScreenOnWhilePlaying(true);
            } catch (Throwable ignored) {
            }
            host.videoView.start();
            String size = mp.getVideoWidth() + "x" + mp.getVideoHeight();
            host.setState("PLAYING " + size + (host.restartCount > 0 ? " r=" + host.restartCount : ""));
            Log.i(TAG, "prepared " + size
                    + " durationMs=" + host.safeDuration(mp)
                    + " restartCount=" + host.restartCount
                    + " url=" + host.url);
        }
    }

    private static final class CompletionListener implements MediaPlayer.OnCompletionListener {
        private final StreamActivity host;

        CompletionListener(StreamActivity host) {
            this.host = host;
        }

        @Override
        public void onCompletion(MediaPlayer mp) {
            host.prepared = false;
            Log.i(TAG, "completion url=" + host.url);
            host.setState("COMPLETED");
            host.scheduleRestart();
        }
    }

    private static final class ErrorListener implements MediaPlayer.OnErrorListener {
        private final StreamActivity host;

        ErrorListener(StreamActivity host) {
            this.host = host;
        }

        @Override
        public boolean onError(MediaPlayer mp, int what, int extra) {
            host.prepared = false;
            host.handler.removeCallbacks(host.openTimeoutTask);
            Log.e(TAG, "error what=" + what + " extra=" + extra + " url=" + host.url);
            host.setState("ERROR " + what + "/" + extra);
            host.scheduleRestart();
            return true; // swallow: retry is handled here
        }
    }

    private static final class InfoListener implements MediaPlayer.OnInfoListener {
        private final StreamActivity host;

        InfoListener(StreamActivity host) {
            this.host = host;
        }

        @Override
        public boolean onInfo(MediaPlayer mp, int what, int extra) {
            Log.i(TAG, "info what=" + what + " extra=" + extra);
            if (what == MediaPlayer.MEDIA_INFO_BUFFERING_START) {
                host.setState("BUFFERING");
            } else if (what == MediaPlayer.MEDIA_INFO_BUFFERING_END) {
                host.setState("PLAYING");
            } else if (what == MediaPlayer.MEDIA_INFO_VIDEO_RENDERING_START) {
                host.setState("RENDERING");
            }
            return false;
        }
    }

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        Log.i(TAG, "onCreate sdk=" + android.os.Build.VERSION.SDK_INT);

        getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);

        handler = new Handler(Looper.getMainLooper());
        restartTask = new RestartTask(this);
        openTimeoutTask = new OpenTimeoutTask(this);

        Intent intent = getIntent();
        url = intent != null ? intent.getStringExtra("url") : null;
        if (url != null) {
            url = url.trim();
        }
        if (url == null || url.isEmpty()) {
            Uri data = intent != null ? intent.getData() : null;
            url = data != null ? data.toString() : DEFAULT_URL;
        }
        autoRestart = intent == null || intent.getBooleanExtra("restart", true);
        hudEnabled = intent == null || intent.getBooleanExtra("hud", true);

        Log.i(TAG, "url=" + url + " autoRestart=" + autoRestart + " hud=" + hudEnabled
                + " extent=" + getResources().getDisplayMetrics().widthPixels + "x"
                + getResources().getDisplayMetrics().heightPixels);

        buildUi();
        setupListeners();
        enterImmersive();
    }

    private void buildUi() {
        FrameLayout root = new FrameLayout(this);
        root.setBackgroundColor(Color.BLACK);

        videoView = new VideoView(this);
        FrameLayout.LayoutParams videoLp = new FrameLayout.LayoutParams(
                FrameLayout.LayoutParams.MATCH_PARENT,
                FrameLayout.LayoutParams.MATCH_PARENT);
        root.addView(videoView, videoLp);

        hud = new TextView(this);
        hud.setTextColor(Color.WHITE);
        hud.setTextSize(11f);
        hud.setBackgroundColor(Color.argb(140, 0, 0, 0));
        hud.setPadding(12, 6, 12, 6);
        hud.setText("RYUO_STREAM starting");
        hud.setVisibility(hudEnabled ? View.VISIBLE : View.GONE);
        FrameLayout.LayoutParams hudLp = new FrameLayout.LayoutParams(
                FrameLayout.LayoutParams.WRAP_CONTENT,
                FrameLayout.LayoutParams.WRAP_CONTENT,
                Gravity.TOP | Gravity.START);
        hudLp.setMargins(10, 10, 10, 10);
        root.addView(hud, hudLp);

        setContentView(root);
    }

    private void setupListeners() {
        videoView.setOnPreparedListener(new PreparedListener(this));
        videoView.setOnCompletionListener(new CompletionListener(this));
        videoView.setOnErrorListener(new ErrorListener(this));
        videoView.setOnInfoListener(new InfoListener(this));
    }

    private long safeDuration(MediaPlayer mp) {
        try {
            long d = mp.getDuration();
            return d < 0 ? -1L : d;
        } catch (Throwable t) {
            return -1L;
        }
    }

    private void open() {
        handler.removeCallbacks(restartTask);
        handler.removeCallbacks(openTimeoutTask);
        prepared = false;
        try {
            Log.i(TAG, "open attempt=" + (restartCount + 1) + " url=" + url);
            setState("OPENING");
            videoView.stopPlayback();
            videoView.setVideoURI(Uri.parse(url));
            videoView.requestFocus();
            handler.postDelayed(openTimeoutTask, OPEN_TIMEOUT_MS);
        } catch (Throwable t) {
            Log.e(TAG, "open failed", t);
            setState("OPEN FAILED " + t.getClass().getSimpleName());
            scheduleRestart();
        }
    }

    private void scheduleRestart() {
        if (!autoRestart) {
            Log.i(TAG, "auto-restart disabled, staying idle");
            return;
        }
        handler.removeCallbacks(restartTask);
        setState(lastState + " | restart in " + RESTART_DELAY_MS + "ms");
        handler.postDelayed(restartTask, RESTART_DELAY_MS);
    }

    private void setState(String text) {
        lastState = text;
        final String line = text + "\n" + shorten(url);
        if (hud != null) {
            hud.setText(line);
        }
    }

    private static String shorten(String s) {
        if (s == null) {
            return "";
        }
        return s.length() <= 64 ? s : s.substring(0, 61) + "...";
    }

    private void enterImmersive() {
        Window window = getWindow();
        window.setDecorFitsSystemWindows(false);
        WindowInsetsController controller = window.getInsetsController();
        if (controller != null) {
            controller.hide(WindowInsets.Type.statusBars() | WindowInsets.Type.navigationBars());
            controller.setSystemBarsBehavior(
                    WindowInsetsController.BEHAVIOR_SHOW_TRANSIENT_BARS_BY_SWIPE);
        }
        window.addFlags(WindowManager.LayoutParams.FLAG_FULLSCREEN);
    }

    @Override
    public void onWindowFocusChanged(boolean hasFocus) {
        super.onWindowFocusChanged(hasFocus);
        if (hasFocus) {
            enterImmersive();
        }
    }

    @Override
    protected void onStart() {
        super.onStart();
        Log.i(TAG, "onStart");
        open();
    }

    @Override
    protected void onResume() {
        super.onResume();
        Log.i(TAG, "onResume");
        enterImmersive();
        if (prepared && videoView != null && !videoView.isPlaying()) {
            videoView.start();
        }
    }

    @Override
    protected void onPause() {
        super.onPause();
        Log.i(TAG, "onPause");
    }

    @Override
    protected void onStop() {
        super.onStop();
        Log.i(TAG, "onStop");
        handler.removeCallbacks(openTimeoutTask);
        handler.removeCallbacks(restartTask);
        try {
            videoView.stopPlayback();
        } catch (Throwable ignored) {
        }
        prepared = false;
    }

    @Override
    protected void onDestroy() {
        super.onDestroy();
        Log.i(TAG, "onDestroy");
        handler.removeCallbacksAndMessages(null);
        try {
            videoView.stopPlayback();
        } catch (Throwable ignored) {
        }
    }
}
