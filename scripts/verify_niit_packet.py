"""Save actual synthetic HTTP packet exports and their independent field proof."""
from pathlib import Path
import argparse
import json
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tests'))
from niit_packet_qa import check_http_packet

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output-dir',type=Path,required=True)
    args = parser.parse_args()
    report = check_http_packet(args.output_dir)
    (args.output_dir/'HTTP-SQLite-official-packet-receipt.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'cases':report['cases'],'passed':report['passed']}))
