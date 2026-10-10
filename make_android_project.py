#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TITAN PRO -> Android project generator.
GitHub Actions runs this file. It creates the whole Android (Gradle + Chaquopy)
project from scratch, so you never have to upload any folders yourself.
Run:  python make_android_project.py
Result: ./android_build/  (then: gradle assembleRelease)
"""
import glob
import os
import shutil
import sys
import textwrap

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(ROOT, "android_build")
PKG = "com.titan.pro"
PKG_DIR = PKG.replace(".", "/")


def write(rel, content):
    path = os.path.join(OUT, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(textwrap.dedent(content).lstrip("\n"))


def find_titan_source():
    cands = sorted(glob.glob(os.path.join(ROOT, "TITAN*.py")))
    cands = [c for c in cands if os.path.basename(c) != "make_android_project.py"]
    if not cands:
        sys.exit("ERROR: TITAN_PRO_V75_PWA.py not found next to make_android_project.py")
    return cands[-1]


def main():
    if os.path.isdir(OUT):
        shutil.rmtree(OUT)
    os.makedirs(OUT)

    src = find_titan_source()
    print("TITAN source:", os.path.basename(src))

    # ---------------------------------------------------------- python side
    py_dir = os.path.join(OUT, "app/src/main/python")
    os.makedirs(py_dir, exist_ok=True)
    shutil.copyfile(src, os.path.join(py_dir, "titan_pro.py"))

    write("app/src/main/python/android_entry.py", '''
        """Android launcher for TITAN PRO (runs the Flask dashboard on 127.0.0.1:8080)."""
        import importlib
        import os
        import sys
        import threading
        import traceback

        STATUS = {"state": "idle", "error": ""}
        _LOCK = threading.Lock()


        def status():
            return STATUS["state"] + "|" + STATUS["error"]


        def run():
            """Blocking. Called from a dedicated Java thread inside the foreground service."""
            with _LOCK:
                if STATUS["state"] in ("starting", "running"):
                    return
                STATUS["state"] = "starting"
                STATUS["error"] = ""
            try:
                os.environ["TITAN_HOST"] = "127.0.0.1"      # local only, not exposed to Wi-Fi
                os.environ["TITAN_PORT"] = "8080"
                os.environ["TITAN_OPEN_BROWSER"] = "0"
                os.environ["PYTHONUNBUFFERED"] = "1"
                sys.setrecursionlimit(max(sys.getrecursionlimit(), 5000))
                mod = importlib.import_module("titan_pro")   # storage check happens here (LLL)
                STATUS["state"] = "running"
                mod.run_titan(open_browser=False)           # blocks (Flask / waitress)
                STATUS["state"] = "stopped"
            except BaseException as exc:                     # noqa
                STATUS["state"] = "error"
                STATUS["error"] = (type(exc).__name__ + ": " + str(exc))[:1500]
                traceback.print_exc()
    ''')

    # ---------------------------------------------------------- gradle files
    write("settings.gradle", '''
        pluginManagement {
            repositories {
                google()
                mavenCentral()
                gradlePluginPortal()
            }
        }
        dependencyResolutionManagement {
            repositoriesMode.set(RepositoriesMode.FAIL_ON_PROJECT_REPOS)
            repositories {
                google()
                mavenCentral()
            }
        }
        rootProject.name = "TitanPro"
        include ":app"
    ''')

    write("build.gradle", '''
        plugins {
            id 'com.android.application' version '8.5.2' apply false
            id 'com.chaquo.python' version '17.0.0' apply false
        }
    ''')

    write("gradle.properties", '''
        org.gradle.jvmargs=-Xmx3g -Dfile.encoding=UTF-8
        org.gradle.daemon=false
        android.useAndroidX=false
        android.nonTransitiveRClass=true
    ''')

    write("app/build.gradle", '''
        plugins {
            id 'com.android.application'
            id 'com.chaquo.python'
        }

        android {
            namespace 'com.titan.pro'
            compileSdk 34

            defaultConfig {
                applicationId "com.titan.pro"
                minSdk 24
                targetSdk 34
                versionCode 75
                versionName "75"
                ndk {
                    abiFilters "arm64-v8a", "armeabi-v7a"
                }
            }

            buildTypes {
                release {
                    minifyEnabled false
                    shrinkResources false
                    // signed with the standard debug key so it installs directly
                    signingConfig signingConfigs.debug
                }
            }

            lint {
                abortOnError false
                checkReleaseBuilds false
            }
        }

        chaquopy {
            defaultConfig {
                version = "3.11"
                pip {
                    install "numpy==1.26.2"
                    install "pandas==2.1.3"
                    install "markupsafe==3.0.3"
                    install "tzdata"
                    install "flask==3.0.3"
                    install "werkzeug==3.0.6"
                    install "requests"
                    install "waitress"
                    install "websocket-client"
                }
            }
        }
    ''')

    # ---------------------------------------------------------- manifest
    write("app/src/main/AndroidManifest.xml", '''
        <?xml version="1.0" encoding="utf-8"?>
        <manifest xmlns:android="http://schemas.android.com/apk/res/android">

            <uses-permission android:name="android.permission.INTERNET" />
            <uses-permission android:name="android.permission.ACCESS_NETWORK_STATE" />
            <uses-permission android:name="android.permission.FOREGROUND_SERVICE" />
            <uses-permission android:name="android.permission.FOREGROUND_SERVICE_SPECIAL_USE" />
            <uses-permission android:name="android.permission.POST_NOTIFICATIONS" />
            <uses-permission android:name="android.permission.WAKE_LOCK" />
            <uses-permission android:name="android.permission.REQUEST_IGNORE_BATTERY_OPTIMIZATIONS" />
            <uses-permission android:name="android.permission.MANAGE_EXTERNAL_STORAGE" />
            <uses-permission android:name="android.permission.READ_EXTERNAL_STORAGE" android:maxSdkVersion="32" />
            <uses-permission android:name="android.permission.WRITE_EXTERNAL_STORAGE" android:maxSdkVersion="32" />

            <application
                android:name="com.chaquo.python.android.PyApplication"
                android:label="TITAN PRO"
                android:icon="@drawable/ic_launcher"
                android:roundIcon="@drawable/ic_launcher"
                android:allowBackup="false"
                android:usesCleartextTraffic="true"
                android:requestLegacyExternalStorage="true"
                android:largeHeap="true"
                android:theme="@style/AppTheme">

                <activity
                    android:name=".MainActivity"
                    android:exported="true"
                    android:configChanges="orientation|screenSize|keyboardHidden|smallestScreenSize|screenLayout|uiMode"
                    android:windowSoftInputMode="adjustResize"
                    android:launchMode="singleTask">
                    <intent-filter>
                        <action android:name="android.intent.action.MAIN" />
                        <category android:name="android.intent.category.LAUNCHER" />
                    </intent-filter>
                </activity>

                <service
                    android:name=".TitanService"
                    android:exported="false"
                    android:foregroundServiceType="specialUse">
                    <property
                        android:name="android.app.PROPERTY_SPECIAL_USE_FGS_SUBTYPE"
                        android:value="Local crypto analysis server (no order execution)" />
                </service>
            </application>
        </manifest>
    ''')

    # ---------------------------------------------------------- resources
    write("app/src/main/res/values/styles.xml", '''
        <?xml version="1.0" encoding="utf-8"?>
        <resources>
            <style name="AppTheme" parent="@android:style/Theme.Material.NoActionBar">
                <item name="android:statusBarColor">#050816</item>
                <item name="android:navigationBarColor">#050816</item>
                <item name="android:windowBackground">#050816</item>
            </style>
        </resources>
    ''')

    write("app/src/main/res/drawable/ic_launcher.xml", '''
        <?xml version="1.0" encoding="utf-8"?>
        <vector xmlns:android="http://schemas.android.com/apk/res/android"
            android:width="108dp"
            android:height="108dp"
            android:viewportWidth="108"
            android:viewportHeight="108">
            <path android:fillColor="#050816" android:pathData="M0,0h108v108h-108z" />
            <path android:fillColor="#22D3EE" android:pathData="M62,16 L34,60 L51,60 L45,92 L76,46 L58,46 Z" />
        </vector>
    ''')

    # ---------------------------------------------------------- java
    write("app/src/main/java/%s/TitanService.java" % PKG_DIR, '''
        package com.titan.pro;

        import android.app.Notification;
        import android.app.NotificationChannel;
        import android.app.NotificationManager;
        import android.app.PendingIntent;
        import android.app.Service;
        import android.content.Intent;
        import android.content.pm.ServiceInfo;
        import android.os.Build;
        import android.os.IBinder;
        import android.os.PowerManager;
        import android.util.Log;

        import com.chaquo.python.PyException;
        import com.chaquo.python.Python;
        import com.chaquo.python.android.AndroidPlatform;

        public class TitanService extends Service {
            static final String CHANNEL_ID = "titan_engine";
            static final String ACTION_STOP = "com.titan.pro.STOP";
            private static final int NOTIF_ID = 75;
            private static volatile boolean started = false;
            private PowerManager.WakeLock wakeLock;

            @Override
            public IBinder onBind(Intent intent) {
                return null;
            }

            @Override
            public int onStartCommand(Intent intent, int flags, int startId) {
                if (intent != null && ACTION_STOP.equals(intent.getAction())) {
                    stopForeground(true);
                    stopSelf();
                    android.os.Process.killProcess(android.os.Process.myPid());
                    return START_NOT_STICKY;
                }
                try {
                    showNotification();
                } catch (Throwable t) {
                    Log.w("TITAN", "foreground start failed: " + t);
                }
                acquireWakeLock();
                startPythonOnce();
                return START_STICKY;
            }

            private void showNotification() {
                NotificationManager nm = (NotificationManager) getSystemService(NOTIFICATION_SERVICE);
                if (Build.VERSION.SDK_INT >= 26) {
                    NotificationChannel ch = new NotificationChannel(
                            CHANNEL_ID, "TITAN Engine", NotificationManager.IMPORTANCE_LOW);
                    nm.createNotificationChannel(ch);
                }
                int piFlags = PendingIntent.FLAG_UPDATE_CURRENT;
                if (Build.VERSION.SDK_INT >= 23) piFlags |= PendingIntent.FLAG_IMMUTABLE;
                PendingIntent open = PendingIntent.getActivity(
                        this, 0, new Intent(this, MainActivity.class), piFlags);
                Intent stopIntent = new Intent(this, TitanService.class).setAction(ACTION_STOP);
                PendingIntent stop = PendingIntent.getService(this, 1, stopIntent, piFlags);

                Notification.Builder b = (Build.VERSION.SDK_INT >= 26)
                        ? new Notification.Builder(this, CHANNEL_ID)
                        : new Notification.Builder(this);
                b.setContentTitle("TITAN PRO")
                        .setContentText("موتور تحلیل فعال است (فقط تحلیل، بدون معامله)")
                        .setSmallIcon(android.R.drawable.stat_notify_sync)
                        .setContentIntent(open)
                        .setOngoing(true)
                        .addAction(new Notification.Action.Builder(
                                android.graphics.drawable.Icon.createWithResource(
                                        this, android.R.drawable.ic_menu_close_clear_cancel),
                                "توقف", stop).build());
                Notification n = b.build();
                if (Build.VERSION.SDK_INT >= 29) {
                    startForeground(NOTIF_ID, n, ServiceInfo.FOREGROUND_SERVICE_TYPE_MANIFEST);
                } else {
                    startForeground(NOTIF_ID, n);
                }
            }

            private void acquireWakeLock() {
                try {
                    if (wakeLock == null) {
                        PowerManager pm = (PowerManager) getSystemService(POWER_SERVICE);
                        wakeLock = pm.newWakeLock(PowerManager.PARTIAL_WAKE_LOCK, "titan:engine");
                        wakeLock.setReferenceCounted(false);
                    }
                    if (!wakeLock.isHeld()) wakeLock.acquire();
                } catch (Throwable t) {
                    Log.w("TITAN", "wakelock: " + t);
                }
            }

            private synchronized void startPythonOnce() {
                if (started) return;
                started = true;
                Runnable r = new Runnable() {
                    @Override
                    public void run() {
                        try {
                            if (!Python.isStarted()) {
                                Python.start(new AndroidPlatform(TitanService.this));
                            }
                            Python.getInstance().getModule("android_entry").callAttr("run");
                        } catch (PyException e) {
                            Log.e("TITAN", "python error", e);
                        } catch (Throwable t) {
                            Log.e("TITAN", "python fatal", t);
                        } finally {
                            started = false;
                        }
                    }
                };
                // big stack (16 MB): the analysis code is deep
                Thread t = new Thread(null, r, "titan-python", 16L * 1024L * 1024L);
                t.setDaemon(true);
                t.start();
            }

            @Override
            public void onDestroy() {
                try {
                    if (wakeLock != null && wakeLock.isHeld()) wakeLock.release();
                } catch (Throwable ignored) {
                }
                super.onDestroy();
            }
        }
    ''')

    write("app/src/main/java/%s/MainActivity.java" % PKG_DIR, '''
        package com.titan.pro;

        import android.Manifest;
        import android.app.Activity;
        import android.content.Context;
        import android.content.Intent;
        import android.content.SharedPreferences;
        import android.content.pm.PackageManager;
        import android.graphics.Color;
        import android.net.Uri;
        import android.os.Build;
        import android.os.Bundle;
        import android.os.Environment;
        import android.os.Handler;
        import android.os.Looper;
        import android.os.PowerManager;
        import android.provider.Settings;
        import android.view.Gravity;
        import android.view.View;
        import android.view.ViewGroup;
        import android.webkit.WebChromeClient;
        import android.webkit.WebSettings;
        import android.webkit.WebView;
        import android.webkit.WebViewClient;
        import android.widget.Button;
        import android.widget.FrameLayout;
        import android.widget.LinearLayout;
        import android.widget.TextView;

        import com.chaquo.python.Python;

        import java.io.File;
        import java.net.HttpURLConnection;
        import java.net.URL;

        public class MainActivity extends Activity {
            private static final String URL_HOME = "http://127.0.0.1:8080/";
            private static final int REQ_LEGACY = 101;
            private static final int REQ_NOTIF = 102;

            private WebView web;
            private LinearLayout overlay;
            private TextView msg;
            private Button actionBtn;
            private final Handler ui = new Handler(Looper.getMainLooper());
            private volatile boolean polling = false;
            private boolean serviceStarted = false;
            private boolean loaded = false;
            private long pollStart = 0;

            @Override
            protected void onCreate(Bundle savedInstanceState) {
                super.onCreate(savedInstanceState);
                FrameLayout root = new FrameLayout(this);
                root.setBackgroundColor(Color.parseColor("#050816"));

                web = new WebView(this);
                web.setBackgroundColor(Color.parseColor("#050816"));
                web.setVisibility(View.INVISIBLE);
                WebSettings s = web.getSettings();
                s.setJavaScriptEnabled(true);
                s.setDomStorageEnabled(true);
                s.setDatabaseEnabled(true);
                s.setCacheMode(WebSettings.LOAD_DEFAULT);
                s.setMediaPlaybackRequiresUserGesture(false);
                s.setMixedContentMode(WebSettings.MIXED_CONTENT_ALWAYS_ALLOW);
                s.setAllowFileAccess(false);
                web.setWebChromeClient(new WebChromeClient());
                web.setWebViewClient(new WebViewClient() {
                    @Override
                    public boolean shouldOverrideUrlLoading(WebView v, String url) {
                        if (url.startsWith("http://127.0.0.1") || url.startsWith("http://localhost")) {
                            return false;
                        }
                        try {
                            startActivity(new Intent(Intent.ACTION_VIEW, Uri.parse(url)));
                        } catch (Throwable ignored) {
                        }
                        return true;
                    }
                });
                web.setDownloadListener((url, ua, cd, mime, len) -> {
                    try {
                        startActivity(new Intent(Intent.ACTION_VIEW, Uri.parse(url)));
                    } catch (Throwable ignored) {
                    }
                });
                root.addView(web, new FrameLayout.LayoutParams(
                        ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT));

                overlay = new LinearLayout(this);
                overlay.setOrientation(LinearLayout.VERTICAL);
                overlay.setGravity(Gravity.CENTER);
                overlay.setPadding(48, 48, 48, 48);
                overlay.setBackgroundColor(Color.parseColor("#050816"));
                msg = new TextView(this);
                msg.setTextColor(Color.parseColor("#E8ECFF"));
                msg.setTextSize(16f);
                msg.setGravity(Gravity.CENTER);
                msg.setText("TITAN PRO\\nدر حال آماده‌سازی…");
                overlay.addView(msg);
                actionBtn = new Button(this);
                actionBtn.setVisibility(View.GONE);
                overlay.addView(actionBtn);
                root.addView(overlay, new FrameLayout.LayoutParams(
                        ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT));
                setContentView(root);

                if (Build.VERSION.SDK_INT >= 33
                        && checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS)
                        != PackageManager.PERMISSION_GRANTED) {
                    requestPermissions(new String[]{Manifest.permission.POST_NOTIFICATIONS}, REQ_NOTIF);
                }
            }

            @Override
            protected void onResume() {
                super.onResume();
                proceed();
            }

            private boolean hasStorageAccess() {
                if (Build.VERSION.SDK_INT >= 30) return Environment.isExternalStorageManager();
                if (Build.VERSION.SDK_INT >= 23) {
                    return checkSelfPermission(Manifest.permission.WRITE_EXTERNAL_STORAGE)
                            == PackageManager.PERMISSION_GRANTED;
                }
                return true;
            }

            private void proceed() {
                if (!hasStorageAccess()) {
                    showStepStorage();
                    return;
                }
                // make sure /storage/emulated/0/LLL exists before Python starts
                try {
                    File lll = new File(Environment.getExternalStorageDirectory(), "LLL");
                    if (!lll.exists()) lll.mkdirs();
                } catch (Throwable ignored) {
                }
                actionBtn.setVisibility(View.GONE);
                if (!serviceStarted) {
                    serviceStarted = true;
                    Intent svc = new Intent(this, TitanService.class);
                    if (Build.VERSION.SDK_INT >= 26) startForegroundService(svc);
                    else startService(svc);
                }
                askBatteryOnce();
                startPolling();
            }

            private void showStepStorage() {
                msg.setText("برای ذخیره‌ی داده‌ها فقط در پوشه‌ی LLL، اجازه‌ی «دسترسی به همه‌ی فایل‌ها» لازم است.\\n\\n"
                        + "روی دکمه بزنید، TITAN PRO را پیدا کنید و روشن کنید، سپس برگردید.");
                actionBtn.setText("دادن دسترسی");
                actionBtn.setVisibility(View.VISIBLE);
                actionBtn.setOnClickListener(v -> {
                    if (Build.VERSION.SDK_INT >= 30) {
                        try {
                            Intent i = new Intent(Settings.ACTION_MANAGE_APP_ALL_FILES_ACCESS_PERMISSION,
                                    Uri.parse("package:" + getPackageName()));
                            startActivity(i);
                        } catch (Throwable t) {
                            startActivity(new Intent(Settings.ACTION_MANAGE_ALL_FILES_ACCESS_PERMISSION));
                        }
                    } else {
                        requestPermissions(new String[]{
                                Manifest.permission.READ_EXTERNAL_STORAGE,
                                Manifest.permission.WRITE_EXTERNAL_STORAGE}, REQ_LEGACY);
                    }
                });
            }

            @Override
            public void onRequestPermissionsResult(int code, String[] perms, int[] res) {
                super.onRequestPermissionsResult(code, perms, res);
                if (code == REQ_LEGACY) proceed();
            }

            private void askBatteryOnce() {
                try {
                    SharedPreferences sp = getSharedPreferences("titan", Context.MODE_PRIVATE);
                    if (sp.getBoolean("battery_asked", false)) return;
                    sp.edit().putBoolean("battery_asked", true).apply();
                    PowerManager pm = (PowerManager) getSystemService(POWER_SERVICE);
                    if (Build.VERSION.SDK_INT >= 23 && !pm.isIgnoringBatteryOptimizations(getPackageName())) {
                        Intent i = new Intent(Settings.ACTION_REQUEST_IGNORE_BATTERY_OPTIMIZATIONS,
                                Uri.parse("package:" + getPackageName()));
                        startActivity(i);
                    }
                } catch (Throwable ignored) {
                }
            }

            private void startPolling() {
                if (polling || loaded) return;
                polling = true;
                pollStart = System.currentTimeMillis();
                msg.setText("TITAN PRO\\nدر حال راه‌اندازی موتور تحلیل…\\n(بار اول ممکن است ۳۰ تا ۶۰ ثانیه طول بکشد)");
                new Thread(() -> {
                    while (polling) {
                        boolean up = serverUp();
                        if (up) {
                            polling = false;
                            ui.post(() -> {
                                loaded = true;
                                web.setVisibility(View.VISIBLE);
                                overlay.setVisibility(View.GONE);
                                web.loadUrl(URL_HOME);
                            });
                            return;
                        }
                        final String err = pythonError();
                        if (err != null) {
                            polling = false;
                            ui.post(() -> showError(err));
                            return;
                        }
                        if (System.currentTimeMillis() - pollStart > 180000) {
                            polling = false;
                            ui.post(() -> showError("سرور تا ۳ دقیقه بالا نیامد."));
                            return;
                        }
                        try {
                            Thread.sleep(700);
                        } catch (InterruptedException ignored) {
                        }
                    }
                }, "titan-poll").start();
            }

            private boolean serverUp() {
                try {
                    HttpURLConnection c = (HttpURLConnection) new URL(URL_HOME + "health").openConnection();
                    c.setConnectTimeout(600);
                    c.setReadTimeout(1500);
                    int code = c.getResponseCode();
                    c.disconnect();
                    return code > 0 && code < 600;
                } catch (Throwable t) {
                    return false;
                }
            }

            private String pythonError() {
                try {
                    if (!Python.isStarted()) return null;
                    String st = Python.getInstance().getModule("android_entry").callAttr("status").toString();
                    if (st.startsWith("error|")) return st.substring(6);
                    if (st.startsWith("stopped|")) return "موتور متوقف شد.";
                } catch (Throwable ignored) {
                }
                return null;
            }

            private void showError(String err) {
                overlay.setVisibility(View.VISIBLE);
                web.setVisibility(View.INVISIBLE);
                msg.setText("خطا در راه‌اندازی:\\n\\n" + err);
                actionBtn.setText("تلاش دوباره");
                actionBtn.setVisibility(View.VISIBLE);
                actionBtn.setOnClickListener(v -> {
                    serviceStarted = false;
                    loaded = false;
                    proceed();
                });
            }

            @Override
            public void onBackPressed() {
                if (loaded && web.canGoBack()) web.goBack();
                else moveTaskToBack(true);
            }

            @Override
            protected void onDestroy() {
                polling = false;
                super.onDestroy();
            }
        }
    ''')

    write(".gitignore", "android_build/\n*.apk\n")
    print("Project generated at:", OUT)


if __name__ == "__main__":
    main()
