"""Run the independent IRS capital/final-summary fixtures against an App checkout."""
from pathlib import Path
import argparse
import json
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tests'))
from capital_final_summary_qa import check_app

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--app-dir', type=Path, required=True)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    sys.path.insert(0, str(args.app_dir.resolve()))
    import tax_engine
    result = check_app(tax_engine)
    if args.output:
        args.output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'cases': result['cases'], 'passed': result['passed']}))
