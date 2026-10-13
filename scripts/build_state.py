#!/usr/bin/env python3
"""Rebuild pinned, locally bundled AGPL state engine from corresponding source."""
import argparse,subprocess,tarfile,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('--work-dir',type=Path,required=True);args=p.parse_args()
work=args.work_dir.resolve();work.mkdir(parents=True,exist_ok=True)
with tarfile.open(ROOT/'vendor/opentax/corresponding-source.tar.gz')as archive:archive.extractall(work,filter='data')
shutil.copy2(ROOT/'scripts/state-worker-entry.mjs',work/'tax-reborn-state-entry.mjs')
for command in [['pnpm','install','--frozen-lockfile','--ignore-scripts'],['pnpm','-r','build'],['pnpm','exec','esbuild','tax-reborn-state-entry.mjs','--bundle','--platform=browser','--format=iife','--target=es2022','--minify','--outfile='+str(ROOT/'web/state-worker.js')]]:subprocess.run(command,cwd=work,check=True)
