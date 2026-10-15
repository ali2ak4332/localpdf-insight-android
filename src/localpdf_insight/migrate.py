"""Copy the previous desktop library into managed snapshots, preserving document IDs."""
import json
import os
import shutil
import time
from pathlib import Path
from .core import LibraryStore
from .document import inspect_pdf
from .evidence import digest
from .metadata import read_json, write_json


def migrate_desktop(root: Path, store=None):
    root=Path(root);root.mkdir(parents=True,exist_ok=True)
    metadata=root/'library.json'
    library=read_json(metadata)
    store=store or LibraryStore();added=0;warnings=list(store.warnings)
    for old in store.items:
        if old.id in library:continue
        source=Path(old.path)
        try:
            info=inspect_pdf(str(source));revision=digest(source)
            destination=root/'documents'/(old.id+'.pdf');destination.parent.mkdir(exist_ok=True)
            temp=destination.with_suffix('.tmp');shutil.copyfile(source,temp)
            if digest(temp)!=revision:raise ValueError('The PDF changed while it was being copied.')
            os.replace(temp,destination);stat=destination.stat()
            library[old.id]={'id':old.id,'revision':revision,'path':str(destination),
                'title':old.name,'filename':source.name,'page_count':info['page_count'],'outline':info['outline'],
                'size':stat.st_size,'mtime_ns':stat.st_mtime_ns,'tags':[],'collection':'',
                'imported_at':old.indexed_at or time.time(),'opened_at':old.indexed_at or time.time()}
            added+=1
        except Exception as exc:warnings.append(f'{old.name}: {exc}')
    write_json(metadata,library)
    return added,warnings
