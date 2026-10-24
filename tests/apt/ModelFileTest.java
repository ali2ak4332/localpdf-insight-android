package app.localpdf.insight;
import java.io.*;
import java.nio.file.*;
public final class ModelFileTest {
 public static void main(String[] args) throws Exception {
  File dir=Files.createTempDirectory("apt-model-test").toFile();
  File old=new File(dir,AptModelFile.NAME);Files.writeString(old.toPath(),"existing model");
  try {AptModelFile.install(new ByteArrayInputStream("bad".getBytes()),dir,()->false);throw new AssertionError("bad file accepted");}
  catch(IOException expected){}
  if(!Files.readString(old.toPath()).equals("existing model"))throw new AssertionError("old model replaced");
  try {AptModelFile.install(new ByteArrayInputStream(new byte[4]),dir,()->true);throw new AssertionError("cancel ignored");}
  catch(IOException expected){}
  for(File f:dir.listFiles())if(f.getName().contains("pending"))throw new AssertionError("partial file retained");
  File interrupted=new File(dir,"apt-model-pending-crash.tmp");Files.writeString(interrupted.toPath(),"interrupted");
  AptModelFile.cleanInterruptedImports(dir);
  if(interrupted.exists()||!old.exists())throw new AssertionError("startup pending cleanup failed or removed installed model");
  if(args.length>0){
   File model=new File(args[0]);if(!AptModelFile.verify(model))throw new AssertionError("real model rejected");
   File installed=AptModelFile.install(new FileInputStream(model),dir,()->false);
   if(installed.length()!=AptModelFile.BYTES||!AptModelFile.verify(installed))throw new AssertionError("install failed");
  }
  for(File f:dir.listFiles())f.delete();dir.delete();
  System.out.println("Model file checks passed: corrupt import, atomic retention, cancellation, cleanup, pinned real-model digest/install");
 }
}
