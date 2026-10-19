"""Create a portable output/checkpoint/code archive with integrity manifest.

No source cache deletion and no uploads. Copy the archive outside AWS and verify
its SHA256 there before considering cleanup. Raw caches remain separately on EBS.
"""
import argparse
import hashlib
import json
from pathlib import Path
import tempfile
import zipfile


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir',type=Path,required=True)
    args=parser.parse_args()
    root=Path(__file__).resolve().parents[2]
    bases=['data/processed','data/benchmark-logs','docs','pipeline','app']
    files=[]
    for base in bases:
        for path in (root/base).rglob('*'):
            if path.is_file() and not path.is_symlink() and '__pycache__' not in path.parts:
                if args.output_dir.resolve()==path.parent.resolve() or args.output_dir.resolve() in path.parents:
                    raise SystemExit('Export directory must be outside the selected source folders')
                files.append(path)
    args.output_dir.mkdir(parents=True,exist_ok=True)
    target=args.output_dir/'climate-assessment-export.zip'
    if target.exists():
        raise SystemExit('Choose a new directory; existing export will not be replaced')
    checksums={}
    # Same-directory temp + rename prevents a partial ZIP looking complete.
    with tempfile.NamedTemporaryFile(dir=args.output_dir,suffix='.tmp',delete=False) as temp:
        temporary=Path(temp.name)
    try:
        with zipfile.ZipFile(temporary,'w',zipfile.ZIP_DEFLATED) as archive:
            for path in sorted(files):
                data=path.read_bytes()
                name=str(path.relative_to(root))
                checksums[name]=hashlib.sha256(data).hexdigest()
                archive.writestr(name,data)
            archive.writestr('FILE-SHA256.json',json.dumps(checksums,indent=2)+'\n')
        temporary.replace(target)
    finally:
        temporary.unlink(missing_ok=True)
    with zipfile.ZipFile(target) as archive:
        for name,digest in checksums.items():
            if hashlib.sha256(archive.read(name)).hexdigest()!=digest:
                raise RuntimeError('Export verification failed: '+name)
    checksum=hashlib.sha256(target.read_bytes()).hexdigest()
    target.with_suffix('.zip.sha256').write_text(f'{checksum}  {target.name}\n')
    print(f'Export verified: {target}. Copy outside AWS and verify before cleanup. Raw source caches not included.')


if __name__=='__main__':
    main()
