import subprocess, shutil, tempfile
from pathlib import Path

bob = shutil.which('bob')
print('bob exe:', bob)

prompt = "explain what a FastAPI router is in one sentence"

# Strategy: redirect stdout to a temp file — avoids pipe deadlock on Windows .CMD
out_file = Path(tempfile.mktemp(suffix='.json'))
try:
    with open(out_file, 'w', encoding='utf-8') as fout:
        proc = subprocess.run(
            [bob, 'run', '--format', 'json', '--max-cost', '0.1', '--max-turns', '5', prompt],
            stdout=fout,
            stderr=subprocess.PIPE,
            text=True,
            encoding='utf-8',
            timeout=30,
        )
    print('returncode:', proc.returncode)
    print('stderr[:200]:', proc.stderr[:200])
    content = out_file.read_text(encoding='utf-8')
    print('stdout[:400]:', content[:400])
finally:
    out_file.unlink(missing_ok=True)
