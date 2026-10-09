"""Fail release CI on absent, skipped, or failed required contract tests."""
import argparse
import json
from pathlib import Path
import xml.etree.ElementTree as ET


def check_report(report, required):
    if not isinstance(required, list) or not required:
        raise ValueError("required_test_ids must be a nonempty list")
    tests = {}
    for case in ET.parse(report).iter('testcase'):
        key = case.get('classname', '').removeprefix('_sys.tests.unit.') + '::' + case.get('name', '').split('[')[0]
        tests.setdefault(key, []).append(case)
    for test_id in required:
        cases = tests.get(test_id, [])
        if not cases or any(any(case.find(tag) is not None for tag in ('skipped', 'failure', 'error')) for case in cases):
            raise ValueError(f"HOLD: required contract absent, skipped, or failed: {test_id}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report', required=True)
    parser.add_argument('--policy', default='release_policy.json')
    args = parser.parse_args()
    check_report(args.report, json.loads(Path(args.policy).read_text())['required_test_ids'])


if __name__ == '__main__':
    main()
