package org.merlin.studio;

/** Android ABI only. No unqualified model weights are loaded automatically. */
public final class LocalModelRuntime {
    static { System.loadLibrary("merlin_local_ai"); }
    private LocalModelRuntime() {}
    public static native boolean nativeLoadModel(String privateVerifiedModelPath);
    public static native String nativeGenerate(String formattedPrompt, int maxNewTokens);
    public static native void nativeRelease();
}
