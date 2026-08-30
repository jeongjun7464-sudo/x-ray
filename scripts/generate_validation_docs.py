"""Generate a transparent Markdown validation summary from pytest JUnit XML."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
from pathlib import Path
import xml.etree.ElementTree as ET

def main():
    parser=argparse.ArgumentParser();parser.add_argument("junit");parser.add_argument("output");args=parser.parse_args()
    root=ET.parse(args.junit).getroot();suite=root if root.tag=="testsuite" else root.find("testsuite")
    tests=int(suite.attrib.get("tests",0));failures=int(suite.attrib.get("failures",0));errors=int(suite.attrib.get("errors",0));skipped=int(suite.attrib.get("skipped",0))
    failed=[]
    for case in suite.iter("testcase"):
        issue=case.find("failure") or case.find("error")
        if issue is not None: failed.append((f'{case.attrib.get("classname")}::{case.attrib.get("name")}',(issue.text or issue.attrib.get("message","")).strip()))
    lines=["# 자동 검증 요약",f"- 생성 시각: {datetime.now(timezone.utc).isoformat()}",f"- 전체: {tests}",f"- 실패: {failures}",f"- 오류: {errors}",f"- 건너뜀: {skipped}",f"- 결과: {'PASS' if failures+errors==0 else 'FAIL'}","","## 실패 및 미해결 항목"]
    lines += ["없음"] if not failed else [f"### {name}\n\n```text\n{detail[:4000]}\n```" for name,detail in failed]
    Path(args.output).write_text("\n".join(lines)+"\n",encoding="utf-8")
if __name__=="__main__": main()
