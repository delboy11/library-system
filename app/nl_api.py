"""국립중앙도서관 ISBN 서지정보 API (seoji) 클라이언트.

인증키는 https://www.nl.go.kr/NL/contents/N31101030700.do 에서 발급받아
환경변수 NL_CERT_KEY 로 지정한다. 표준 라이브러리만 사용한다.
"""
import json
import os
import re
import urllib.parse
import urllib.request

ENDPOINT = "https://www.nl.go.kr/seoji/SearchApi.do"            # ISBN 서지정보 (seoji)
HOLDINGS_ENDPOINT = "https://www.nl.go.kr/NL/search/openApi/search.do"  # 소장자료 검색 (KDC 보강용)

ROLE_WORDS = [
    ("지은이", ("글·그림", "글/그림", "글, 그림")),        # 글과 그림을 모두 한 사람 → 지은이 (먼저 검사)
    ("옮긴이", ("옮김", "옮긴이", "번역", "공역", "역")),
    ("엮은이", ("엮음", "엮은이", "편저", "편")),
    ("그림", ("그림", "그린이")),
    ("지은이", ("지음", "지은이", "저자", "공저", "저", "글", "著")),
]
SKIP_ROLES = ("감수", "기획", "사진", "해제", "해설")   # 저자로 등록하지 않는 역할


class NLApiError(Exception):
    pass


def cert_key():
    return os.environ.get("NL_CERT_KEY", "").strip()


def call(**params):
    key = cert_key()
    if not key:
        raise NLApiError("국립중앙도서관 API 인증키(NL_CERT_KEY)가 설정되어 있지 않습니다.")
    query = {"cert_key": key, "result_style": "json", "page_no": 1, "page_size": 10}
    query.update({k: v for k, v in params.items() if v is not None})
    url = f"{ENDPOINT}?{urllib.parse.urlencode(query)}"
    try:
        with urllib.request.urlopen(url, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception as e:  # 네트워크·JSON 오류
        raise NLApiError(f"국립중앙도서관 API 호출 실패: {e}") from e
    if data.get("RESULT") == "ERROR":
        raise NLApiError(f"국립중앙도서관 API 오류 {data.get('ERR_CODE')}: {data.get('ERR_MESSAGE')}")
    return data


def parse_authors(text):
    """'유발 하라리 지음 ; 조현욱 옮김' → [('유발 하라리', '지은이'), ('조현욱', '옮긴이')]"""
    authors = []
    for part in re.split(r"\s*;\s*", text or ""):
        part = re.sub(r"\s*\[?공\]?\s*(?=(지음|옮김|엮음|저|역)\s*$)", " ", part.strip())
        part = re.sub(r"\s+외\s*(\d+\s*인|\d+\s*명)?(?=\s|$)", " ", part).strip()   # '홍길동 외 지음' → '홍길동 지음'
        if not part or any(re.search(r"(?:^|\s)" + w + r"\s*$", part) for w in SKIP_ROLES):
            continue
        role = "지은이"
        for role_name, words in ROLE_WORDS:
            # '김역' 같은 이름 끝 글자를 역할로 오인하지 않도록 공백 또는 ']' 뒤에서만 인식
            m = re.search(r"(?:^|\s+|(?<=\]))(" + "|".join(map(re.escape, words)) + r")\s*$", part)
            if m:
                role, part = role_name, part[: m.start()].strip()
                break
        for name in re.split(r"\s*,\s*", part):
            name = re.sub(r"\[.*?\]|\(.*?\)", "", name).strip()
            if name and (name, role) not in authors:
                authors.append((name, role))
    return authors


def kdc_main(kdc_no, add_code="", subject=""):
    """KDC 주류(800)를 구한다. 우선순위: KDC 기호(813.7) → SUBJECT(한 자리) → ISBN 부가기호(03810)의 3번째 자리"""
    m = re.match(r"\s*(\d)", kdc_no or "")
    if m:
        return f"{m.group(1)}00"
    if re.fullmatch(r"\d", (subject or "").strip()):
        return f"{subject.strip()}00"
    if add_code and len(add_code) == 5 and add_code.isdigit():
        return f"{add_code[2]}00"
    return None


def parse_doc(doc):
    isbn = re.sub(r"[^0-9]", "", doc.get("EA_ISBN") or "")
    # 실제 발행일(REAL_PUBLISH_DATE)이 있으면 출판예정일(PUBLISH_PREDATE)보다 우선
    year = re.match(r"(\d{4})", doc.get("REAL_PUBLISH_DATE") or doc.get("PUBLISH_PREDATE") or "")
    price_match = re.search(r"\d+", (doc.get("PRE_PRICE") or "").replace(",", ""))   # '12,500' / '비매품' / '15000원(세트)'
    price = price_match.group(0) if price_match else ""
    kdc_no = (doc.get("KDC") or "").strip() or None
    return {
        "isbn": isbn,
        "title": (doc.get("TITLE") or "").strip(),
        "authors": parse_authors(doc.get("AUTHOR")),
        "publisher": (doc.get("PUBLISHER") or "").strip(),
        "pub_year": int(year.group(1)) if year else None,
        "price": int(price) if price else None,
        "kdc_no": kdc_no,
        "category_code": kdc_main(kdc_no, doc.get("EA_ADD_CODE") or "", doc.get("SUBJECT") or ""),
    }


def fetch_by_isbn(isbn):
    isbn = re.sub(r"[^0-9]", "", isbn)
    data = call(isbn=isbn, ebook_yn="N", page_size=10)
    # isbn 은 우절단 검색이라 정확히 일치하는 레코드를 고른다 (세트 레코드는 EA_ISBN 이 비어 있음)
    docs = [d for d in data.get("docs") or [] if re.sub(r"[^0-9]", "", d.get("EA_ISBN") or "") == isbn]
    if not docs:
        return None
    book = parse_doc(docs[0])
    if not book["kdc_no"]:
        book["kdc_no"] = fetch_kdc(isbn)
        book["category_code"] = kdc_main(book["kdc_no"]) or book["category_code"]
    return book


def _norm(key):
    return re.sub(r"[_\s]", "", key).lower()


def _find_records(obj):
    """응답 JSON 에서 레코드 목록을 찾는다 (목록 키 이름이 문서화되어 있지 않음)."""
    if isinstance(obj, list):
        return [x for x in obj if isinstance(x, dict)]
    if isinstance(obj, dict):
        for value in obj.values():
            if isinstance(value, list) and value and isinstance(value[0], dict):
                return value
    return []


def fetch_kdc(isbn):
    """소장자료 검색 API 로 KDC 분류기호를 보강한다. 실패하면 None (서지 등록은 계속 진행)."""
    key = cert_key()
    if not key:
        return None
    query = {"key": key, "apiType": "json", "detailSearch": "true", "isbnOp": "isbn",
             "isbnCode": isbn, "pageNum": 1, "pageSize": 10}
    try:
        with urllib.request.urlopen(f"{HOLDINGS_ENDPOINT}?{urllib.parse.urlencode(query)}", timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception:
        return None
    for rec in _find_records(data):
        fields = {_norm(k): v for k, v in rec.items()}
        class_no = str(fields.get("classno") or "").strip()
        if not class_no:
            m = re.match(r"\s*(\d{3}(?:\.\d+)?)", str(fields.get("callno") or ""))
            class_no = m.group(1) if m else ""
        if class_no:
            return class_no
    return None


def search(page_no=1, page_size=100, **filters):
    """키워드·분류 등으로 검색 (예: search(title='데이터베이스'))."""
    data = call(page_no=page_no, page_size=page_size, **filters)
    return [parse_doc(d) for d in data.get("docs") or []], int(data.get("TOTAL_COUNT") or 0)
