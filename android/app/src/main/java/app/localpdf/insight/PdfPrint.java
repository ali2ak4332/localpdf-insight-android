package app.localpdf.insight;

import android.app.Activity;
import android.graphics.pdf.PdfRenderer;
import android.os.Bundle;
import android.os.CancellationSignal;
import android.os.ParcelFileDescriptor;
import android.print.PageRange;
import android.print.PrintAttributes;
import android.print.PrintDocumentAdapter;
import android.print.PrintDocumentInfo;
import android.print.PrintManager;

import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.IOException;
import java.util.Locale;
import java.util.UUID;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

/**
 * Hands one finished PDF copy to Android's print framework (installed printers and
 * "Save as PDF"). The exact PDF bytes are passed through, so vector text, signatures,
 * highlights and form appearances print at printer resolution. No permission is needed.
 */
final class PdfPrint {
    static final String DIRECTORY = "pdf-prints";
    /** Older sessions can only be leftovers of a killed process; recent ones may still be printing. */
    static final long MAX_AGE_MILLIS = 6L * 60 * 60 * 1000;

    private PdfPrint() { }

    static File createFile(Activity activity, String name) throws IOException {
        if (!new File(name).getName().equals(name) || !name.toLowerCase(Locale.ROOT).endsWith(".pdf"))
            throw new IOException("Invalid PDF name");
        File root = new File(activity.getCacheDir(), DIRECTORY);
        if (!root.isDirectory() && !root.mkdir()) throw new IOException("No print cache");
        File session = new File(root, UUID.randomUUID().toString());
        if (!session.mkdir()) throw new IOException("No print session");
        return new File(session, name);
    }

    /**
     * Returns the page count, or {@link PrintDocumentInfo#PAGE_COUNT_UNKNOWN} when Android's
     * renderer cannot read it. Throws SecurityException for password-protected PDFs, which
     * the system print preview cannot open either.
     */
    static int countPages(File pdf) {
        try (ParcelFileDescriptor descriptor = ParcelFileDescriptor.open(pdf, ParcelFileDescriptor.MODE_READ_ONLY);
             PdfRenderer renderer = new PdfRenderer(descriptor)) {
            return renderer.getPageCount();
        } catch (SecurityException protectedPdf) {
            throw protectedPdf;
        } catch (IOException | RuntimeException unreadable) {
            return PrintDocumentInfo.PAGE_COUNT_UNKNOWN;
        }
    }

    /** Must run on the UI thread. Throws if Android printing is unavailable. */
    static void open(Activity activity, File pdf, int pages) {
        PrintManager manager = activity.getSystemService(PrintManager.class);
        if (manager == null) throw new IllegalStateException("No print service");
        String job = pdf.getName().substring(0, pdf.getName().length() - 4);
        manager.print(job.isEmpty() ? "PDF" : job, new Adapter(pdf, pages), null);
    }

    static void remove(File pdf) {
        pdf.delete();
        File session = pdf.getParentFile();
        if (session != null) session.delete(); // Only the now-empty, per-print session directory.
    }

    static void cleanOld(Activity activity) throws IOException {
        File root = new File(activity.getCacheDir(), DIRECTORY);
        File[] sessions = root.listFiles();
        if (sessions == null) return;
        long cutoff = System.currentTimeMillis() - MAX_AGE_MILLIS;
        for (File session : sessions) {
            if (!session.isDirectory() || session.lastModified() >= cutoff
                    || !session.getCanonicalFile().getParentFile().equals(root.getCanonicalFile())) continue;
            File[] files = session.listFiles();
            if (files != null) for (File file : files)
                if (file.isFile() && file.getCanonicalFile().getParentFile().equals(session.getCanonicalFile())) file.delete();
            session.delete();
        }
    }

    /** Streams the stored PDF unchanged; the print spooler selects requested pages itself. */
    static final class Adapter extends PrintDocumentAdapter {
        private final File pdf;
        private final int pages;
        private final ExecutorService io = Executors.newSingleThreadExecutor();

        Adapter(File pdf, int pages) {
            this.pdf = pdf;
            this.pages = pages;
        }

        @Override
        public void onLayout(PrintAttributes oldAttributes, PrintAttributes newAttributes,
                             CancellationSignal cancellationSignal, LayoutResultCallback callback, Bundle extras) {
            if (cancellationSignal.isCanceled()) {
                callback.onLayoutCancelled();
                return;
            }
            PrintDocumentInfo info = new PrintDocumentInfo.Builder(pdf.getName())
                    .setContentType(PrintDocumentInfo.CONTENT_TYPE_DOCUMENT)
                    .setPageCount(pages)
                    .build();
            // The content never depends on paper size or margins: only the first layout changes it.
            callback.onLayoutFinished(info, oldAttributes == null);
        }

        @Override
        public void onWrite(PageRange[] pageRanges, ParcelFileDescriptor destination,
                            CancellationSignal cancellationSignal, WriteResultCallback callback) {
            io.execute(() -> {
                try (FileInputStream input = new FileInputStream(pdf)) {
                    // The spooler owns and closes the destination descriptor.
                    FileOutputStream output = new FileOutputStream(destination.getFileDescriptor());
                    byte[] buffer = new byte[64 * 1024];
                    int count;
                    while ((count = input.read(buffer)) != -1) {
                        if (cancellationSignal.isCanceled()) {
                            callback.onWriteCancelled();
                            return;
                        }
                        output.write(buffer, 0, count);
                    }
                    output.flush();
                    callback.onWriteFinished(new PageRange[] {PageRange.ALL_PAGES});
                } catch (IOException | RuntimeException failed) {
                    callback.onWriteFailed(failed.getMessage());
                }
            });
        }

        @Override
        public void onFinish() {
            io.execute(() -> remove(pdf)); // Printed, saved or cancelled: the private copy is no longer needed.
            io.shutdown();
        }
    }
}
