package app.localpdf.insight;

final class AptNative {
    static final boolean AVAILABLE;
    static {boolean ready;try{System.loadLibrary("apt_reader");ready=true;}catch(UnsatisfiedLinkError unavailable){ready=false;}AVAILABLE=ready;}
    static native long create();
    static native void reset(long handle);
    static native String generate(long handle,String model,byte[] prompt);
    static native void cancel(long handle);
    static native void close(long handle);
    private AptNative(){}
}
