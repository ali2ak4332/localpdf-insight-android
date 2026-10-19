"""Run production PdfPrint with minimal Android API doubles, not a device.

Verifies the print hand-off/cache policy: exact bytes reach the print framework, cancellation
and failure paths, cleanup ownership and protected-PDF refusal. Actual Android print preview,
printer drivers and "Save as PDF" still require installed Android validation.
"""
import json, os, pathlib, shlex, subprocess, tempfile
import xml.etree.ElementTree as ET

ROOT = pathlib.Path(__file__).resolve().parents[2]
FILES = {
'android/os/Bundle.java': '''package android.os; public class Bundle {}''',
'android/os/CancellationSignal.java': '''package android.os; public class CancellationSignal { public boolean cancelled; public boolean isCanceled(){return cancelled;} }''',
'android/os/ParcelFileDescriptor.java': '''package android.os; public class ParcelFileDescriptor implements java.io.Closeable {
 public static final int MODE_READ_ONLY=0x10000000; public final java.io.File file; public final java.io.FileDescriptor fd;
 public ParcelFileDescriptor(java.io.File f, java.io.FileDescriptor d){file=f;fd=d;}
 public static ParcelFileDescriptor open(java.io.File f,int mode)throws java.io.FileNotFoundException{if(!f.isFile())throw new java.io.FileNotFoundException();return new ParcelFileDescriptor(f,null);}
 public java.io.FileDescriptor getFileDescriptor(){return fd;} public void close(){} }''',
'android/graphics/pdf/PdfRenderer.java': '''package android.graphics.pdf; public final class PdfRenderer implements AutoCloseable {
 private final int pages;
 public PdfRenderer(android.os.ParcelFileDescriptor d)throws java.io.IOException{
  String text=new String(java.nio.file.Files.readAllBytes(d.file.toPath()),java.nio.charset.StandardCharsets.ISO_8859_1);
  if(!text.startsWith("%PDF-"))throw new java.io.IOException("not a PDF");
  if(text.contains("/Encrypt"))throw new SecurityException("password required");
  pages=text.split("/Type /Page\\\\b",-1).length-1; }
 public int getPageCount(){return pages;} public void close(){} }''',
'android/print/PageRange.java': '''package android.print; public final class PageRange { public static final PageRange ALL_PAGES=new PageRange(); }''',
'android/print/PrintAttributes.java': '''package android.print; public final class PrintAttributes {}''',
'android/print/PrintDocumentInfo.java': '''package android.print; public final class PrintDocumentInfo {
 public static final int PAGE_COUNT_UNKNOWN=-1, CONTENT_TYPE_DOCUMENT=0; public String name; public int pages=PAGE_COUNT_UNKNOWN, type=-9;
 public static final class Builder { private final PrintDocumentInfo info=new PrintDocumentInfo();
  public Builder(String n){info.name=n;} public Builder setContentType(int t){info.type=t;return this;}
  public Builder setPageCount(int p){info.pages=p;return this;} public PrintDocumentInfo build(){return info;} } }''',
'android/print/PrintDocumentAdapter.java': '''package android.print; public abstract class PrintDocumentAdapter {
 public static abstract class LayoutResultCallback { public void onLayoutFinished(PrintDocumentInfo i,boolean changed){} public void onLayoutFailed(CharSequence e){} public void onLayoutCancelled(){} }
 public static abstract class WriteResultCallback { public void onWriteFinished(PageRange[] p){} public void onWriteFailed(CharSequence e){} public void onWriteCancelled(){} }
 public void onStart(){}
 public abstract void onLayout(PrintAttributes o,PrintAttributes n,android.os.CancellationSignal c,LayoutResultCallback cb,android.os.Bundle e);
 public abstract void onWrite(PageRange[] p,android.os.ParcelFileDescriptor d,android.os.CancellationSignal c,WriteResultCallback cb);
 public void onFinish(){} }''',
'android/print/PrintManager.java': '''package android.print; public final class PrintManager {
 public String job; public PrintDocumentAdapter adapter; public PrintAttributes attributes; public int calls;
 public Object print(String j,PrintDocumentAdapter a,PrintAttributes at){job=j;adapter=a;attributes=at;calls++;return null;} }''',
'android/app/Activity.java': '''package android.app; public class Activity {
 public java.io.File cache; public android.print.PrintManager printing=new android.print.PrintManager();
 public Activity(java.io.File c){cache=c;} public java.io.File getCacheDir(){return cache;}
 @SuppressWarnings("unchecked") public <T> T getSystemService(Class<T> c){return c==android.print.PrintManager.class?(T)printing:null;} }''',
'app/localpdf/insight/PdfPrintPolicyTest.java': '''package app.localpdf.insight;
import java.io.*; import java.nio.file.*; import java.util.concurrent.*; import android.app.Activity; import android.os.*; import android.print.*;
public class PdfPrintPolicyTest {
 static int checks; static void check(boolean b,String m){checks++;if(!b)throw new AssertionError(m);}
 static final class Layout extends PrintDocumentAdapter.LayoutResultCallback { PrintDocumentInfo info; Boolean changed; boolean cancelled;
  public void onLayoutFinished(PrintDocumentInfo i,boolean c){info=i;changed=c;} public void onLayoutCancelled(){cancelled=true;} }
 static final class Write extends PrintDocumentAdapter.WriteResultCallback { final CountDownLatch done=new CountDownLatch(1); PageRange[] pages; String failed; boolean cancelled;
  public void onWriteFinished(PageRange[] p){pages=p;done.countDown();} public void onWriteFailed(CharSequence e){failed=String.valueOf(e);done.countDown();} public void onWriteCancelled(){cancelled=true;done.countDown();} }
 static Write write(PrintDocumentAdapter adapter,File out,boolean cancel)throws Exception{
  try(FileOutputStream target=new FileOutputStream(out)){CancellationSignal c=new CancellationSignal();c.cancelled=cancel;Write w=new Write();
   adapter.onWrite(new PageRange[]{PageRange.ALL_PAGES},new ParcelFileDescriptor(out,target.getFD()),c,w);check(w.done.await(10,TimeUnit.SECONDS),"write callback arrives");return w;} }
 static void awaitGone(File f)throws Exception{for(int i=0;i<200&&f.exists();i++)Thread.sleep(10);}
 public static void main(String[] args)throws Exception {
  Activity a=new Activity(new File(args[0]));
  byte[] bytes=("%PDF-1.7\\n1 0 obj <</Type /Page>> endobj 2 0 obj <</Type /Page>> endobj 3 0 obj <</Type /Pages>> endobj\\n").getBytes("ISO-8859-1");
  byte[] tail={(byte)0x80,(byte)0xff,0,10};byte[] pdfBytes=new byte[bytes.length+tail.length];System.arraycopy(bytes,0,pdfBytes,0,bytes.length);System.arraycopy(tail,0,pdfBytes,bytes.length,tail.length);
  File first=PdfPrint.createFile(a,"عقد-edited.pdf"),second=PdfPrint.createFile(a,"عقد-edited.pdf");
  check(first.getName().equals("عقد-edited.pdf"),"friendly Arabic job/file name");check(!first.getParentFile().equals(second.getParentFile()),"unique print session");
  check(first.getCanonicalPath().startsWith(new File(a.cache,"pdf-prints").getCanonicalPath()+File.separator),"private cache only, separate from shares");
  for(String bad:new String[]{"../x.pdf","/tmp/x.pdf","x.txt"}){boolean rejected=false;try{PdfPrint.createFile(a,bad);}catch(IOException expected){rejected=true;}check(rejected,"reject unsafe/non-PDF name");}
  Files.write(first.toPath(),pdfBytes);
  check(PdfPrint.countPages(first)==2,"page count from Android renderer for print preview");
  File junk=PdfPrint.createFile(a,"junk.pdf");Files.write(junk.toPath(),new byte[]{1,2,3});
  check(PdfPrint.countPages(junk)==PrintDocumentInfo.PAGE_COUNT_UNKNOWN,"unreadable count falls back to unknown, not a crash");PdfPrint.remove(junk);
  File locked=PdfPrint.createFile(a,"locked.pdf");Files.write(locked.toPath(),"%PDF-1.7 /Encrypt 5 0 R".getBytes("ISO-8859-1"));
  boolean refused=false;try{PdfPrint.countPages(locked);}catch(SecurityException expected){refused=true;}check(refused,"password-protected PDF is reported, not sent to a failing preview");PdfPrint.remove(locked);
  PdfPrint.open(a,first,2);PrintManager pm=a.printing;
  check(pm.calls==1&&pm.job.equals("عقد-edited"),"one system print job named after the document");check(pm.attributes==null,"user chooses printer/paper in Android print UI");
  PrintDocumentAdapter adapter=pm.adapter;Layout layout=new Layout();
  adapter.onLayout(null,new PrintAttributes(),new CancellationSignal(),layout,new Bundle());
  check(layout.info.pages==2&&layout.info.type==PrintDocumentInfo.CONTENT_TYPE_DOCUMENT&&layout.info.name.equals(first.getName()),"document layout info");
  check(layout.changed,"first layout reports new content");Layout again=new Layout();adapter.onLayout(new PrintAttributes(),new PrintAttributes(),new CancellationSignal(),again,new Bundle());
  check(!again.changed,"paper/margin changes do not re-render PDF bytes");
  Layout stopped=new Layout();CancellationSignal cancel=new CancellationSignal();cancel.cancelled=true;adapter.onLayout(null,new PrintAttributes(),cancel,stopped,new Bundle());check(stopped.cancelled&&stopped.info==null,"cancelled layout");
  File out=new File(a.cache,"spooler.pdf");Write w=write(adapter,out,false);
  check(w.pages!=null&&w.pages.length==1&&w.pages[0]==PageRange.ALL_PAGES,"reports all pages; spooler selects requested range");
  check(java.util.Arrays.equals(Files.readAllBytes(out.toPath()),pdfBytes),"printing passes exact bytes, including 0x80-0xff");
  Write c=write(adapter,new File(a.cache,"cancelled.pdf"),true);check(c.cancelled&&c.pages==null,"cancelled write reports cancellation");
  check(first.exists(),"copy kept while print UI may still re-write it");
  PdfPrint.cleanOld(a);check(first.exists(),"launch cleanup keeps a recent, possibly active print session");
  File old=PdfPrint.createFile(a,"old.pdf");Files.write(old.toPath(),pdfBytes);old.getParentFile().setLastModified(System.currentTimeMillis()-7L*60*60*1000);
  File outside=new File(a.cache,"unrelated.pdf");Files.write(outside.toPath(),pdfBytes);
  File share=new File(new File(a.cache,"pdf-shares/s"),"x.pdf");share.getParentFile().mkdirs();Files.write(share.toPath(),pdfBytes);share.getParentFile().setLastModified(0);
  PdfPrint.cleanOld(a);check(!old.exists()&&!old.getParentFile().exists(),"stale print session removed");
  check(first.exists()&&outside.exists()&&share.exists(),"recent print, unrelated cache and share sessions retained");
  adapter.onFinish();awaitGone(first);check(!first.exists()&&!first.getParentFile().exists()&&second.getParentFile().exists(),"finishing the job removes only its own session");
  Activity none=new Activity(new File(args[0])){public <T> T getSystemService(Class<T> c){return null;}};
  boolean failed=false;try{PdfPrint.open(none,second,1);}catch(RuntimeException expected){failed=true;}check(failed,"missing print service propagates for controller cleanup");
  PdfPrint.remove(second);check(!second.getParentFile().exists(),"failure cleanup removes its session");
  System.out.println(checks);
 }
}''',
}

with tempfile.TemporaryDirectory(prefix='localpdf-print-test-') as directory:
    root = pathlib.Path(directory)
    for name, content in FILES.items():
        p = root/name; p.parent.mkdir(parents=True, exist_ok=True); p.write_text(content)
    source = ROOT/'android/app/src/main/java/app/localpdf/insight'
    subprocess.run([*shlex.split(os.environ.get('JAVAC', 'javac')), '-d', str(root/'classes'),
                    str(source/'PdfPrint.java'), *[str(root/name) for name in FILES]], check=True)
    cache = root/'cache'; cache.mkdir()
    result = subprocess.run(['java', '-cp', str(root/'classes'), 'app.localpdf.insight.PdfPrintPolicyTest', str(cache)],
                            check=True, text=True, capture_output=True)
    checks = int(result.stdout.strip())

# Static checks: no new permission/provider/component, both languages carry the native messages,
# and the controller routes print purpose only through PdfPrint.
android = '{http://schemas.android.com/apk/res/android}'
manifest = ET.parse(ROOT/'android/app/src/main/AndroidManifest.xml').getroot()
assert not manifest.findall('uses-permission')
assert len(manifest.findall('application/provider')) == 1
assert manifest.find('application').get(android+'allowBackup') == 'false'
for lang in ['values', 'values-ar']:
    names = {s.get('name') for s in ET.parse(ROOT/f'android/app/src/main/res/{lang}/strings.xml').getroot()}
    assert {'print_unavailable', 'print_protected'} <= names, lang
controller = (ROOT/'android/app/src/main/java/app/localpdf/insight/PdfExportController.java').read_text()
assert '"print".equals(purpose)' in controller and 'PdfPrint.open(activity, completed.file, pages)' in controller
assert 'PdfPrint.cleanOld(activity)' in controller and 'PdfPrint.remove(abandoned.file)' in controller
print(json.dumps({'passed': checks+6, 'java_policy_checks': checks, 'static_checks': 6,
                  'environment': 'Production PdfPrint compiled with API doubles; manifest/resources/controller inspected; not Android print framework testing'}))
