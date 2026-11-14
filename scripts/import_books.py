"""국립중앙도서관 API 로 실제 도서 데이터를 가져와 data/books.csv 를 만든다.

인증키 : https://www.nl.go.kr 회원가입 → Open API 인증키 신청 → 승인 후 환경변수로 지정
    export NL_CERT_KEY=발급받은키

사용 예
  # 1) data/books.csv 의 ISBN 목록을 국립중앙도서관 서지정보로 갱신 (권장)
  .venv/bin/python scripts/import_books.py --refresh
  # 2) 키워드로 새로 수집 (서명 검색, 종이책만)
  .venv/bin/python scripts/import_books.py --title 데이터베이스 --count 20 --append
그다음
  .venv/bin/python scripts/build_seed.py && ./scripts/init_db.sh
"""
import argparse
import csv
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app import nl_api  # noqa: E402

CSV_PATH = ROOT / "data" / "books.csv"
FIELDS = ["isbn", "title", "authors", "publisher", "pub_year", "price", "kdc_no", "category_code", "source"]
SOURCE = "국립중앙도서관 ISBN 서지정보 API"


def to_row(book, fallback=None):
    fallback = fallback or {}
    authors = ";".join(f"{name}:{role}" for name, role in book["authors"]) or fallback.get("authors", "")
    return {
        "isbn": book["isbn"],
        "title": book["title"] or fallback.get("title", ""),
        "authors": authors,
        "publisher": book["publisher"] or fallback.get("publisher", ""),
        "pub_year": book["pub_year"] or fallback.get("pub_year", ""),
        "price": book["price"] or fallback.get("price", ""),
        "kdc_no": book["kdc_no"] or fallback.get("kdc_no", ""),
        "category_code": book["category_code"] or fallback.get("category_code", "000"),
        "source": SOURCE,
    }


def read_csv():
    if not CSV_PATH.exists():
        return []
    with CSV_PATH.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def write_csv(rows):
    with CSV_PATH.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)


def refresh():
    rows = read_csv()
    updated, missing = [], 0
    for i, row in enumerate(rows, 1):
        try:
            book = nl_api.fetch_by_isbn(row["isbn"])
        except nl_api.NLApiError as e:
            sys.exit(str(e))
        if book:
            updated.append(to_row(book, row))
        else:
            missing += 1
            updated.append(row)
            print(f"  [{i}] 국립중앙도서관에 없음 → 기존 값 유지: {row['isbn']} {row['title']}")
        time.sleep(1)                       # 공식 제한은 없지만 초당 1건으로 조절
    write_csv(updated)
    print(f"갱신 {len(rows) - missing}건 / 미확인 {missing}건 → {CSV_PATH}")


def search(title, count, append):
    rows = read_csv() if append else []
    seen = {r["isbn"] for r in rows}
    page, added = 1, 0
    while added < count:
        try:
            books, total = nl_api.search(page_no=page, page_size=50, title=title, ebook_yn="N")
        except nl_api.NLApiError as e:
            sys.exit(str(e))
        if not books:
            break
        for book in books:
            if book["isbn"] and book["isbn"] not in seen and book["title"] and book["authors"]:
                seen.add(book["isbn"])
                rows.append(to_row(book))
                added += 1
                if added >= count:
                    break
        page += 1
        time.sleep(1)
    write_csv(rows)
    print(f"추가 {added}건 (전체 {len(rows)}건) → {CSV_PATH}")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--refresh", action="store_true", help="CSV 의 ISBN 들을 API 로 갱신")
    parser.add_argument("--title", help="서명 키워드로 검색해 추가")
    parser.add_argument("--count", type=int, default=20)
    parser.add_argument("--append", action="store_true", help="기존 CSV 뒤에 추가")
    args = parser.parse_args()
    if not nl_api.cert_key():
        sys.exit("NL_CERT_KEY 환경변수에 국립중앙도서관 API 인증키를 넣어 주세요.")
    if args.refresh:
        refresh()
    elif args.title:
        search(args.title, args.count, args.append)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
