package app.localpdf.insight;

import java.io.*;
import java.nio.file.*;
import java.security.*;
import java.util.function.BooleanSupplier;

/** Byte-exact pinned model import. Never reads or changes the reader library. */
final class AptModelFile {
    static final String NAME="gemma-3-270m-it-qat-Q4_0.gguf";
    static final long BYTES=241410624L;
    static final String SHA256="3626e245220ca4a1c5911eb4010b3ecb7bdbf5bc53c79403c21355354d1e2dc6";
    private static MessageDigest digest() {
        try{return MessageDigest.getInstance("SHA-256");}
        catch(NoSuchAlgorithmException impossible){throw new IllegalStateException(impossible);}
    }
    private static String hex(byte[] bytes){StringBuilder b=new StringBuilder();for(byte v:bytes)b.append(String.format(java.util.Locale.ROOT,"%02x",v&255));return b.toString();}
    static boolean verify(File model) throws IOException {
        if(!model.isFile()||model.length()!=BYTES)return false;
        MessageDigest hash=digest();byte[] buffer=new byte[65536];
        try(InputStream in=new FileInputStream(model)){int n;while((n=in.read(buffer))!=-1)hash.update(buffer,0,n);}
        return SHA256.equals(hex(hash.digest()));
    }
    static File install(InputStream source,File directory,BooleanSupplier cancelled) throws IOException {
        if(!directory.isDirectory()&&!directory.mkdirs())throw new IOException("Could not prepare model storage");
        File pending=File.createTempFile("apt-model-pending-",".tmp",directory);
        try{
            MessageDigest hash=digest();long total=0;byte[] buffer=new byte[65536];
            try(InputStream in=source;FileOutputStream out=new FileOutputStream(pending)){
                if(in==null)throw new IOException("Could not read selected model");
                while(true){
                    if(cancelled.getAsBoolean())throw new IOException("Model import cancelled");
                    int n=in.read(buffer);if(n<0)break;if(n==0)continue;
                    total+=n;if(total>BYTES)throw new IOException("Wrong model size; use the pinned Gemma Q4_0 file");
                    hash.update(buffer,0,n);out.write(buffer,0,n);
                }
                out.getFD().sync();
            }
            if(total!=BYTES||!SHA256.equals(hex(hash.digest())))throw new IOException("Model checksum mismatch; existing model was retained");
            if(cancelled.getAsBoolean())throw new IOException("Model import cancelled");
            File model=new File(directory,NAME);
            Files.move(pending.toPath(),model.toPath(),StandardCopyOption.ATOMIC_MOVE,StandardCopyOption.REPLACE_EXISTING);
            return model;
        }finally{if(pending.exists())pending.delete();}
    }
    static void cleanInterruptedImports(File directory){
        File[] files=directory.listFiles((dir,name)->name.startsWith("apt-model-pending-")&&name.endsWith(".tmp"));
        if(files!=null)for(File file:files)file.delete();
    }
}
