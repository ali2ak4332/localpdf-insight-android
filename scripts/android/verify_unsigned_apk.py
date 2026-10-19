#!/usr/bin/env python3
"""Verify that a source-built APK has the exact reader assets and native classes."""
import hashlib
import json
from pathlib import Path
import zipfile

project = Path(__file__).resolve().parents[2]
apk = project / 'android/app/build/outputs/apk/release/app-release-unsigned.apk'
assets = project / 'src/localpdf_insight/static'
for module in ('pdf.mjs', 'pdf.worker.mjs', 'pdf.sandbox.mjs',
               'pdf.min.mjs', 'pdf.worker.min.mjs', 'pdf.sandbox.min.mjs'):
    assert (assets / 'vendor/pdfjs/build' / module).is_file(), f'Missing PDF.js runtime: {module}'
with zipfile.ZipFile(apk) as z:
    names = set(z.namelist())
    expected = {'assets/static/' + p.relative_to(assets).as_posix(): p for p in assets.rglob('*') if p.is_file()}
    packaged = {p for p in names if p.startswith('assets/static/') and not p.endswith('/')}
    assert packaged == set(expected), f'Asset inventory mismatch: missing={set(expected)-packaged}; extra={packaged-set(expected)}'
    for name, path in expected.items():
        assert z.read(name) == path.read_bytes(), f'Stale asset: {name}'
    dex_files = [n for n in names if n.startswith('classes') and n.endswith('.dex')]
    assert dex_files, 'Missing classes.dex'
    dex = b''.join(z.read(n) for n in dex_files)
    for class_name in ('MainActivity', 'PdfExportController', 'ReadingScreenController',
                       'PdfPrint', 'PdfShare', 'PdfShareProvider'):
        descriptor = f'Lapp/localpdf/insight/{class_name};'.encode()
        assert descriptor in dex, f'Missing app class {class_name}'
    for descriptor in (b'Landroidx/webkit/WebViewAssetLoader;', b'Landroidx/webkit/WebViewCompat;',
                       b'Landroidx/core/app/CoreComponentFactory;'):
        assert descriptor in dex, f'Missing AndroidX dependency {descriptor!r}'
    assert not any(n.startswith('META-INF/') and n.endswith(('.RSA', '.DSA', '.EC', '.SF')) for n in names), 'Unexpected JAR signature'
report = {
    'apk': str(apk), 'sha256': hashlib.sha256(apk.read_bytes()).hexdigest(),
    'bytes': apk.stat().st_size, 'verified_asset_files': len(expected),
    'dex_files': dex_files, 'native_controller_classes': 'present',
    'androidx_webkit_classes': 'present', 'asset_content_match': True,
}
out = project / 'validation-artifacts/android-source-build.json'
out.parent.mkdir(exist_ok=True)
out.write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps(report, indent=2))
