"""Serial smoke/manual validation for external radio review (no third-party runner).

Run with the project interpreter and an output directory. Captures full logs,
return codes and durations without treating the known radiation failure as PASS.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import time


def main():
    root = Path(__file__).resolve().parents[1]
    output = Path(sys.argv[1]).resolve()
    output.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, PYTHONPATH='src:.:tests', SDL_AUDIODRIVER='dummy', SDL_VIDEODRIVER='dummy')
    scripts = sorted(set(root.glob('tests/*smoke*.py')) | {root/'tests/manuals_style_check.py'})
    results = []
    for script in scripts:
        start = time.monotonic()
        try:
            run = subprocess.run([sys.executable, str(script)], cwd=root, env=env,
                capture_output=True, text=True, timeout=300)
            text, code = run.stdout + run.stderr, run.returncode
        except subprocess.TimeoutExpired as exc:
            text, code = str(exc), 124
        (output/(script.stem+'.log')).write_text(text)
        row = dict(script=script.name, code=code, seconds=round(time.monotonic()-start, 3))
        results.append(row)
        print(json.dumps(row), flush=True)
        (output/'results.json').write_text(json.dumps(results, indent=2)+'\n')
    print(f'{sum(r["code"] == 0 for r in results)}/{len(results)} PASS', flush=True)
    return int(any(r['code'] for r in results))


if __name__ == '__main__':
    raise SystemExit(main())
