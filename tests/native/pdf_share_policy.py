"""Run production PdfShare with minimal Android API doubles, not a device.

Verifies intent/cache policy; actual Android URI grants and recipient app access
still require installed Android validation.
"""
import json, os, pathlib, shlex, subprocess, tempfile
import xml.etree.ElementTree as ET

ROOT = pathlib.Path(__file__).resolve().parents[2]
FILES = {
'android/net/Uri.java': '''package android.net; public class Uri { public final String value; public Uri(String v){value=v;} }''',
'android/content/ClipData.java': '''package android.content; public class ClipData { public String label; public android.net.Uri uri; public static ClipData newRawUri(String l,android.net.Uri u){ClipData c=new ClipData();c.label=l;c.uri=u;return c;} }''',
'android/content/Intent.java': '''package android.content; public class Intent {
 public static final String ACTION_SEND="android.intent.action.SEND", EXTRA_STREAM="android.intent.extra.STREAM";
 public static final int FLAG_GRANT_READ_URI_PERMISSION=1;
 public String action,type,key,title; public android.net.Uri stream; public ClipData clip; public int flags; public Intent target;
 public Intent(String a){action=a;} public Intent setType(String t){type=t;return this;} public Intent putExtra(String k,android.net.Uri u){key=k;stream=u;return this;}
 public Intent addFlags(int f){flags|=f;return this;} public void setClipData(ClipData c){clip=c;}
 public static Intent createChooser(Intent i,CharSequence t){Intent c=new Intent("chooser");c.target=i;c.title=t.toString();return c;}
}''',
'android/app/Activity.java': '''package android.app; public class Activity {
 public java.io.File cache; public android.content.Intent launched; public boolean unavailable;
 public Activity(java.io.File c){cache=c;} public java.io.File getCacheDir(){return cache;} public String getPackageName(){return "app.localpdf.insight";}
 public String getString(int id){return "Share PDF";} public void startActivity(android.content.Intent i){if(unavailable)throw new IllegalStateException("No receiver");launched=i;}
}''',
'androidx/core/content/FileProvider.java': '''package androidx.core.content; public class FileProvider {
 public static java.io.File file; public static String authority;
 public static android.net.Uri getUriForFile(android.app.Activity a,String auth,java.io.File f){file=f;authority=auth;return new android.net.Uri("content://"+auth+"/shared_pdfs/session/"+f.getName());}
}''',
'app/localpdf/insight/R.java': '''package app.localpdf.insight; public class R {public static class string {public static int share_pdf=1;}}''',
'app/localpdf/insight/PdfSharePolicyTest.java': '''package app.localpdf.insight;
import java.io.*; import java.nio.file.*; import android.app.Activity; import android.content.Intent; import androidx.core.content.FileProvider;
public class PdfSharePolicyTest {
 static int checks; static void check(boolean b,String m){checks++;if(!b)throw new AssertionError(m);}
 public static void main(String[] args)throws Exception {
  Activity a=new Activity(new File(args[0]));byte[] bytes={37,80,68,70,45,49,46,55,10,(byte)255};
  File first=PdfShare.createFile(a,"عقد.pdf"),second=PdfShare.createFile(a,"عقد.pdf");
  check(first.getName().equals("عقد.pdf"),"friendly Arabic name");check(!first.getParentFile().equals(second.getParentFile()),"unique share session");
  check(first.getCanonicalPath().startsWith(new File(a.cache,"pdf-shares").getCanonicalPath()+File.separator),"private cache only");
  for(String bad:new String[]{"../x.pdf","/tmp/x.pdf","x.txt"}){boolean rejected=false;try{PdfShare.createFile(a,bad);}catch(IOException expected){rejected=true;}check(rejected,"reject unsafe/non-PDF name");}
  Files.write(first.toPath(),bytes);PdfShare.open(a,first);Intent chooser=a.launched,send=chooser.target;
  check(send.action.equals(Intent.ACTION_SEND),"system send action");check(send.type.equals("application/pdf"),"PDF MIME");
  check(send.key.equals(Intent.EXTRA_STREAM)&&send.stream==send.clip.uri,"same URI in stream and ClipData");
  check(send.clip.label.equals(first.getName()),"friendly attachment label");
  check(FileProvider.authority.equals("app.localpdf.insight.pdfshare")&&FileProvider.file.equals(first),"exact private provider authority/file");
  check(send.stream.value.startsWith("content://"),"content URI never file URI");
  check(send.flags==1&&chooser.flags==1,"read-only grants on send and chooser; no write/broad grant");
  check(chooser.action.equals("chooser")&&chooser.title.equals("Share PDF"),"user chooses receiving app");
  check(java.util.Arrays.equals(Files.readAllBytes(first.toPath()),bytes),"sharing never rewrites bytes");
  PdfShare.cleanOld(a);check(first.exists(),"recent shared file survives activity recreation cleanup");
  File old=PdfShare.createFile(a,"old.pdf");Files.write(old.toPath(),bytes);old.getParentFile().setLastModified(System.currentTimeMillis()-25L*60*60*1000);
  File outside=new File(a.cache,"unrelated.pdf");Files.write(outside.toPath(),bytes);
  PdfShare.cleanOld(a);check(!old.exists()&&!old.getParentFile().exists(),"expired share removed");check(first.exists()&&outside.exists(),"recent share and unrelated cache retained");
  a.unavailable=true;boolean failed=false;try{PdfShare.open(a,first);}catch(RuntimeException expected){failed=true;}check(failed,"missing receiver failure propagates for controller cleanup");
  PdfShare.remove(first);check(!first.exists()&&!first.getParentFile().exists()&&second.getParentFile().exists(),"failure cleanup only removes own session");
  System.out.println(checks);
 }
}''',
}

with tempfile.TemporaryDirectory(prefix='localpdf-share-test-') as directory:
    root = pathlib.Path(directory)
    for name, content in FILES.items():
        p = root/name; p.parent.mkdir(parents=True, exist_ok=True); p.write_text(content)
    source = ROOT/'android/app/src/main/java/app/localpdf/insight'
    subprocess.run([*shlex.split(os.environ.get('JAVAC', 'javac')), '-d', str(root/'classes'),
                    str(source/'PdfShare.java'), str(source/'PdfShareProvider.java'),
                    *[str(root/name) for name in FILES]], check=True)
    cache = root/'cache'; cache.mkdir()
    result = subprocess.run(['java', '-cp', str(root/'classes'), 'app.localpdf.insight.PdfSharePolicyTest', str(cache)],
                            check=True, text=True, capture_output=True)
    checks = int(result.stdout.strip())

android = '{http://schemas.android.com/apk/res/android}'
manifest = ET.parse(ROOT/'android/app/src/main/AndroidManifest.xml').getroot()
provider = manifest.find('application/provider')
assert provider.get(android+'name') == '.PdfShareProvider'
assert provider.get(android+'authorities') == '${applicationId}.pdfshare'
assert provider.get(android+'exported') == 'false' and provider.get(android+'grantUriPermissions') == 'true'
assert provider.find('meta-data').get(android+'resource') == '@xml/pdf_share_paths'
paths = ET.parse(ROOT/'android/app/src/main/res/xml/pdf_share_paths.xml').getroot()
assert len(paths) == 1 and paths[0].tag == 'cache-path' and paths[0].get('path') == 'pdf-shares/'
assert not manifest.findall('uses-permission')
print(json.dumps({'passed': checks+6, 'java_policy_checks': checks, 'manifest_checks': 6,
                  'environment': 'Production helper compiled with API doubles and manifest inspected; not Android framework/recipient testing'}))
