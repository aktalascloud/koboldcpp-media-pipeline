"""Verify the portable production bundle against its local SHA256 manifest."""
import hashlib,json,time
from pathlib import Path
from RuntimePaths import ROOT
def verify():
    manifest=ROOT/'portable-manifest.json';data=json.loads(manifest.read_text(encoding='utf-8'));failures=[];total=0;start=time.perf_counter()
    for row in data['files']:
        relative=Path(row['path']);path=(ROOT/relative).resolve()
        if relative.is_absolute() or not path.is_relative_to(ROOT):raise ValueError('Manifest path escaped portable root')
        if not path.is_file():failures.append(dict(path=row['path'],error='missing'));continue
        if path.stat().st_size!=row['bytes']:failures.append(dict(path=row['path'],error='size'));continue
        digest=hashlib.sha256()
        with path.open('rb') as stream:
            for chunk in iter(lambda:stream.read(8*1024*1024),b''):digest.update(chunk)
        if digest.hexdigest()!=row['sha256']:failures.append(dict(path=row['path'],error='sha256'))
        total+=row['bytes']
    result=dict(ok=not failures,root=str(ROOT),checked_files=len(data['files']),checked_bytes=total,seconds=round(time.perf_counter()-start,3),failures=failures)
    (ROOT/'logs').mkdir(exist_ok=True);(ROOT/'logs'/'portable-integrity.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result),flush=True);return 0 if result['ok'] else 2
