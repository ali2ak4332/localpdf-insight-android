"""Compile the production screen controller against minimal Android API test doubles.
This checks message validation/lifecycle policy, not an installed Android/WebView.
"""
import json, os, pathlib, shlex, subprocess, tempfile
ROOT=pathlib.Path(__file__).resolve().parents[2]
FILES={
'android/app/Activity.java':'''package android.app; public class Activity { private final android.view.Window w=new android.view.Window(); public android.view.Window getWindow(){return w;} }''',
'android/view/Window.java':'''package android.view; public class Window { public int flags; public void addFlags(int f){flags|=f;} public void clearFlags(int f){flags&=~f;} }''',
'android/view/WindowManager.java':'''package android.view; public interface WindowManager { public static class LayoutParams { public static final int FLAG_KEEP_SCREEN_ON=128; } }''',
'android/webkit/WebView.java':'''package android.webkit; public class WebView {}''',
'androidx/webkit/WebMessageCompat.java':'''package androidx.webkit; public class WebMessageCompat { public static final int TYPE_STRING=0; private final String data; public WebMessageCompat(String d){data=d;} public String getData(){return data;} public int getType(){return TYPE_STRING;} }''',
'androidx/webkit/WebViewFeature.java':'''package androidx.webkit; public class WebViewFeature { public static final String WEB_MESSAGE_LISTENER="messages"; public static boolean supported=true; public static boolean isFeatureSupported(String f){return supported;} }''',
'androidx/webkit/WebViewCompat.java':'''package androidx.webkit; public class WebViewCompat { public interface Listener { void receive(android.webkit.WebView v,WebMessageCompat m,java.net.URI origin,boolean frame,Object reply); } public static Listener listener; public static java.util.Set<String> allowed; public static void addWebMessageListener(android.webkit.WebView v,String name,java.util.Set<String> origins,Listener l){listener=l;allowed=origins;} public static void removeWebMessageListener(android.webkit.WebView v,String name){listener=null;} }''',
'app/localpdf/insight/ReadingScreenPolicyTest.java':'''package app.localpdf.insight;
import android.app.Activity; import android.webkit.WebView; import androidx.webkit.*; import java.net.URI;
public class ReadingScreenPolicyTest {
 static int checks; static Activity activity=new Activity(); static WebView view=new WebView();
 static void check(boolean condition,String message){checks++;if(!condition)throw new AssertionError(message);}
 static boolean lit(){return (activity.getWindow().flags&128)!=0;}
 static void message(String data,String origin,boolean frame){WebViewCompat.listener.receive(view,new WebMessageCompat(data),URI.create(origin),frame,null);}
 public static void main(String[] args){
  ReadingScreenController c=ReadingScreenController.install(activity,view);check(c!=null&&!lit(),"off at installation");
  check(WebViewCompat.allowed.equals(java.util.Collections.singleton("https://appassets.androidplatform.net")),"exact origin allowlist");
  message("keep-screen-on","https://evil.example",true);c.setResumed(true);c.setFocused(true);check(!lit(),"untrusted origin blocked");
  message("keep-screen-on","https://appassets.androidplatform.net",false);check(!lit(),"subframes blocked");
  message("keep-screen-on","https://user@appassets.androidplatform.net",true);check(!lit(),"userinfo blocked");
  message("keep-screen-on","https://appassets.androidplatform.net:444",true);check(!lit(),"alternate port blocked");
  message("unknown","https://appassets.androidplatform.net",true);check(!lit(),"unknown messages ignored");
  message("keep-screen-on","https://appassets.androidplatform.net",true);check(lit(),"explicit preference foreground activates");
  c.setResumed(false);check(!lit(),"pause releases");c.setResumed(true);check(lit(),"resume restores active reader");
  c.setFocused(false);check(!lit(),"dialogs/pickers release");c.setFocused(true);check(lit(),"focus restores");
  message("allow-screen-off","https://appassets.androidplatform.net",true);check(!lit(),"off switch releases");
  c.setFocused(false);message("keep-screen-on","https://appassets.androidplatform.net",true);check(!lit(),"background messages cannot wake");
  c.setFocused(true);c.reset();check(!lit(),"navigation/error resets");c.setResumed(false);c.setResumed(true);check(!lit(),"reset not restored by resume");
  message("keep-screen-on","https://appassets.androidplatform.net",true);c.close();check(!lit()&&WebViewCompat.listener==null,"destroy clears flag and bridge");
  WebViewFeature.supported=false;check(ReadingScreenController.install(activity,view)==null,"unsupported WebView has no bridge");
  System.out.println("{\\"passed\\":"+checks+",\\"environment\\":\\"Production controller compiled with API test doubles; not a device test\\"}");
 }
}'''
}
with tempfile.TemporaryDirectory(prefix='localpdf-screen-test-') as directory:
 root=pathlib.Path(directory)
 for name,content in FILES.items():
  p=root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(content)
 production=ROOT/'android/app/src/main/java/app/localpdf/insight/ReadingScreenController.java'
 subprocess.run([*shlex.split(os.environ.get('JAVAC','javac')),'-d',str(root/'classes'),str(production),*[str(root/name) for name in FILES]],check=True)
 result=subprocess.run(['java','-cp',str(root/'classes'),'app.localpdf.insight.ReadingScreenPolicyTest'],check=True,text=True,capture_output=True)
 print(result.stdout.strip())
