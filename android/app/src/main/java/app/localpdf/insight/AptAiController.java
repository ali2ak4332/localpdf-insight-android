package app.localpdf.insight;

import android.app.Activity;
import android.content.Intent;
import android.net.Uri;
import android.os.Handler;
import android.os.Looper;
import android.webkit.WebView;
import androidx.webkit.JavaScriptReplyProxy;
import androidx.webkit.WebMessageCompat;
import androidx.webkit.WebViewCompat;
import androidx.webkit.WebViewFeature;
import java.io.File;
import java.nio.charset.StandardCharsets;
import java.util.Collections;
import java.util.concurrent.*;
import java.util.concurrent.atomic.AtomicBoolean;
import org.json.JSONObject;

/** Main-frame, origin-scoped model channel. No socket, download or generic JavaScript interface. */
final class AptAiController {
    private static final String OBJECT="AptOfflineAI";
    private static final int PICK_MODEL=78;
    private final Activity activity;
    private final WebView webView;
    private final Handler main=new Handler(Looper.getMainLooper());
    private final ExecutorService worker=Executors.newSingleThreadExecutor();
    private final AtomicBoolean busy=new AtomicBoolean(),cancelled=new AtomicBoolean();
    private final File directory,model;
    private volatile boolean closed,verified;
    private volatile long nativeHandle;
    private JavaScriptReplyProxy pickerReply;
    private String pickerId;

    static AptAiController install(Activity activity,WebView view){
        if(!WebViewFeature.isFeatureSupported(WebViewFeature.WEB_MESSAGE_LISTENER))return null;
        AptAiController controller=new AptAiController(activity,view);
        WebViewCompat.addWebMessageListener(view,OBJECT,Collections.singleton("https://appassets.androidplatform.net"),
            (web,message,origin,mainFrame,reply)->{
                if(controller.closed||!mainFrame||origin==null||!"https".equals(origin.getScheme())
                    ||!"appassets.androidplatform.net".equals(origin.getHost())||origin.getUserInfo()!=null
                    ||(origin.getPort()!=-1&&origin.getPort()!=443)||message.getType()!=WebMessageCompat.TYPE_STRING)return;
                controller.message(message.getData(),reply);
            });
        return controller;
    }
    private AptAiController(Activity a,WebView v){
        activity=a;webView=v;directory=new File(a.getNoBackupFilesDir(),"apt-model");model=new File(directory,AptModelFile.NAME);
        worker.execute(()->AptModelFile.cleanInterruptedImports(directory));
    }
    private void reply(JavaScriptReplyProxy proxy,String id,JSONObject data,String error){
        main.post(()->{if(closed)return;try{
            JSONObject out=new JSONObject().put("id",id).put("ok",error==null);
            if(error==null)out.put("data",data);else out.put("error",error);
            proxy.postMessage(out.toString());
        }catch(RuntimeException|org.json.JSONException ignored){/* WebView may have been destroyed. */}});
    }
    private void message(String raw,JavaScriptReplyProxy reply){
        if(raw==null||raw.length()>26000)return;
        String id="";
        try{
            JSONObject request=new JSONObject(raw);id=request.getString("id");
            if(!id.matches("[a-zA-Z0-9-]{1,64}"))return;
            final String requestId=id;String action=request.getString("action");
            if("cancel".equals(action)){cancel();reply(reply,id,new JSONObject(),null);return;}
            if(!AptNative.AVAILABLE){reply(reply,id,null,"Offline model runtime is unavailable on this device; reading still works.");return;}
            if("status".equals(action)){
                reply(reply,id,new JSONObject().put("present",model.isFile()&&model.length()==AptModelFile.BYTES)
                    .put("verified",verified).put("busy",busy.get()).put("modelBytes",AptModelFile.BYTES)
                    .put("sha256",AptModelFile.SHA256).put("fineTuned",false),null);return;
            }
            if("import".equals(action)){
                if(pickerReply!=null||!busy.compareAndSet(false,true)){reply(reply,id,null,"Finish or cancel the current analysis first.");return;}
                pickerReply=reply;pickerId=id;
                try{activity.startActivityForResult(new Intent(Intent.ACTION_OPEN_DOCUMENT).addCategory(Intent.CATEGORY_OPENABLE)
                    .setType("*/*").addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION),PICK_MODEL);}
                catch(RuntimeException error){pickerReply=null;pickerId=null;busy.set(false);throw error;}
                return;
            }
            if(!"generate".equals(action))throw new IllegalArgumentException("Unknown model action");
            String prompt=request.getString("prompt");byte[] bytes=prompt.getBytes(StandardCharsets.UTF_8);
            if(bytes.length<1||bytes.length>24000)throw new IllegalArgumentException("Section is too large for the local model");
            if(!busy.compareAndSet(false,true)){reply(reply,id,null,"Model is busy");return;}
            cancelled.set(false);
            if(nativeHandle==0)nativeHandle=AptNative.create();
            AptNative.reset(nativeHandle);
            worker.execute(()->{
                try{
                    if(!verified){if(!AptModelFile.verify(model))throw new IllegalStateException("Import the verified Gemma Q4_0 model first");verified=true;}
                    if(cancelled.get())throw new IllegalStateException("Analysis cancelled");
                    long start=System.nanoTime();String text=AptNative.generate(nativeHandle,model.getAbsolutePath(),bytes);
                    if(cancelled.get())throw new IllegalStateException("Analysis cancelled");
                    reply(reply,requestId,new JSONObject().put("text",text).put("milliseconds",(System.nanoTime()-start)/1000000),null);
                }catch(Exception|LinkageError error){reply(reply,requestId,null,error.getMessage()==null?"Offline analysis failed":error.getMessage());}
                finally{busy.set(false);}
            });
        }catch(Exception|LinkageError error){reply(reply,id,null,error.getMessage()==null?"Invalid model request":error.getMessage());}
    }
    boolean onActivityResult(int request,int result,Intent data){
        if(request!=PICK_MODEL)return false;
        JavaScriptReplyProxy target=pickerReply;String id=pickerId;pickerReply=null;pickerId=null;
        if(target==null){busy.set(false);return true;}
        Uri uri=data==null?null:data.getData();
        if(result!=Activity.RESULT_OK||uri==null){busy.set(false);reply(target,id,null,"Model import cancelled");return true;}
        cancelled.set(false);
        worker.execute(()->{
            try{
                AptModelFile.cleanInterruptedImports(directory);
                AptModelFile.install(activity.getContentResolver().openInputStream(uri),directory,()->closed||cancelled.get());
                verified=true;
                reply(target,id,new JSONObject().put("present",true).put("verified",true).put("modelBytes",model.length()),null);
            }catch(Exception error){reply(target,id,null,error.getMessage()==null?"Could not import model":error.getMessage());}
            finally{busy.set(false);}
        });
        return true;
    }
    void cancel(){cancelled.set(true);if(nativeHandle!=0)AptNative.cancel(nativeHandle);}
    void close(){
        closed=true;cancel();pickerReply=null;pickerId=null;
        WebViewCompat.removeWebMessageListener(webView,OBJECT);
        worker.execute(()->{if(nativeHandle!=0){AptNative.close(nativeHandle);nativeHandle=0;}});worker.shutdown();
        main.removeCallbacksAndMessages(null);
    }
}
