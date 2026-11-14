"""docs/ 의 문서 00~13 을 하나의 최종 결과 보고서(docs/최종_결과_보고서.md)로 합친다.

실행 : .venv/bin/python scripts/build_report.py
"""
import re
from datetime import date
from pathlib import Path

DOCS = Path(__file__).resolve().parent.parent / "docs"
OUT = DOCS / "최종_결과_보고서.md"
ORDER = [
    "01_프로젝트_개요서.md", "02_업무_기능도.md", "03_단위_업무_기술서.md", "04_업무_흐름도.md",
    "05_업무_문서_리스트.md", "06_개념적_데이터_모델.md", "07_논리적_데이터_모델.md",
    "08_물리적_데이터_모델.md", "09_용어_사전.md", "10_도메인_정의서.md", "11_테이블_기술서.md",
    "12_회의록.md", "13_시연_시나리오_및_테스트.md", "00_설계_결정사항.md",
]


def main():
    parts, toc = [], []
    for name in ORDER:
        path = DOCS / name
        if not path.exists():
            raise SystemExit(f"문서가 없습니다: {name}")
        text = path.read_text(encoding="utf-8").strip()
        title = re.match(r"#\s+(.+)", text).group(1)
        if name.startswith("00_"):
            title = "부록. " + re.sub(r"^00\.\s*", "", title)
            text = re.sub(r"^#\s+.+", f"# {title}", text, count=1)
        toc.append(f"- {title}")
        parts.append(text)
    cover = "\n".join([
        "# 도서관 대출·반납·연체 관리 시스템 — 최종 결과 보고서",
        "",
        f"> 데이터베이스 팀 프로젝트 · Python Flask + MySQL · 취합일 {date.today():%Y-%m-%d}",
        "",
        "| 항목 | 내용 |",
        "|---|---|",
        "| 팀원 | 임채선, 함성준, 너세리투, 강권영, 윤준서 |",
        "| 기준 규정 | 숭실대학교 중앙도서관 대출 규정 |",
        "| 소스 코드 | library-system (sql/ · app/ · scripts/ · tests/) |",
        "",
        "## 목차",
        "",
        *toc,
    ])
    OUT.write_text(cover + "\n\n---\n\n" + "\n\n---\n\n".join(parts) + "\n", encoding="utf-8")
    print(f"{OUT.name} : {len(parts)}개 문서, {OUT.stat().st_size // 1024} KB")


if __name__ == "__main__":
    main()
