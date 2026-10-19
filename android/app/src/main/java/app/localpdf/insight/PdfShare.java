package app.localpdf.insight;

import android.app.Activity;
import android.content.ClipData;
import android.content.Intent;
import android.net.Uri;
import androidx.core.content.FileProvider;
import java.io.File;
import java.io.IOException;
import java.util.Locale;
import java.util.UUID;

/** Explicit PDF handoff using Android's existing FileProvider and read-only URI grant. */
final class PdfShare {
    private PdfShare() { }

    static File createFile(Activity activity, String name) throws IOException {
        if (!new File(name).getName().equals(name) || !name.toLowerCase(Locale.ROOT).endsWith(".pdf"))
            throw new IOException("Invalid PDF name");
        File root = new File(activity.getCacheDir(), "pdf-shares");
        if (!root.isDirectory() && !root.mkdir()) throw new IOException("No share cache");
        File session = new File(root, UUID.randomUUID().toString());
        if (!session.mkdir()) throw new IOException("No share session");
        return new File(session, name);
    }

    static void open(Activity activity, File pdf) {
        Uri uri = FileProvider.getUriForFile(activity, activity.getPackageName() + ".pdfshare", pdf);
        Intent send = new Intent(Intent.ACTION_SEND).setType("application/pdf")
                .putExtra(Intent.EXTRA_STREAM, uri)
                .addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);
        send.setClipData(ClipData.newRawUri(pdf.getName(), uri));
        Intent chooser = Intent.createChooser(send, activity.getString(R.string.share_pdf));
        chooser.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);
        activity.startActivity(chooser);
    }

    static void remove(File pdf) {
        pdf.delete();
        pdf.getParentFile().delete(); // Only the now-empty, per-share session directory.
    }

    static void cleanOld(Activity activity) throws IOException {
        File root = new File(activity.getCacheDir(), "pdf-shares");
        File[] sessions = root.listFiles();
        if (sessions == null) return;
        long cutoff = System.currentTimeMillis() - 24L * 60 * 60 * 1000;
        for (File session : sessions) {
            if (!session.isDirectory() || session.lastModified() >= cutoff
                    || !session.getCanonicalFile().getParentFile().equals(root.getCanonicalFile())) continue;
            File[] files = session.listFiles();
            if (files != null) for (File file : files)
                if (file.isFile() && file.getCanonicalFile().getParentFile().equals(session.getCanonicalFile())) file.delete();
            session.delete();
        }
    }
}
