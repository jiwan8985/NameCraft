"""작명소 자료 가져오기 (기획서 §13, §20, REQ-IMP-001~003).

보안 원칙
- 형식은 파일 앞부분 바이트(시그니처)로 확인 — 확장자·브라우저가 보낸 타입을 믿지 않는다.
- 크기 제한, 무작위 저장 이름, 저장 폴더 밖 경로 차단, 실행하지 않음.
- 문서 내용은 '데이터'일 뿐 명령으로 쓰지 않는다(AI 로 보내지 않음). 지시문처럼 보이는 문장은 검토자에게 경고.
- 삭제 시 원본 파일·추출 텍스트·추출값을 모두 지운다.
"""

from __future__ import annotations

import csv
import hashlib
import io
import re
import secrets
import unicodedata
from datetime import UTC, datetime, timedelta
from pathlib import Path

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from namecraft.db.models import CrosscheckResult, ExtractedAssertion, ImportedDocument
from namecraft.domain.calendar.ganzhi import BRANCHES, BRANCHES_KO, STEMS, STEMS_KO
from namecraft.errors import AppError, NotFound

MAX_BYTES = 10 * 1024 * 1024
RETENTION_DAYS = 180
MAX_TEXT_CHARS = 200_000

_HANJA = r"[㐀-䶿一-鿿豈-﫿]"
_INJECTION = re.compile(r"(ignore (all |the )?(previous|above) instructions|system prompt|지시(를|사항을)? 무시|"
                        r"이전 지시|프롬프트를|you are (now )?an? )", re.I)


class UploadRejected(AppError):
    status_code = 415
    code = "upload_rejected"


class UploadTooLarge(AppError):
    status_code = 413
    code = "upload_too_large"


# ---------------------------------------------------------------- 형식 판별

def sniff(data: bytes) -> tuple[str, str]:
    """(kind, media_type). 지원하지 않으면 UploadRejected."""
    if data.startswith(b"%PDF-"):
        return "pdf", "application/pdf"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image", "image/png"
    if data[:3] == b"\xff\xd8\xff":
        return "image", "image/jpeg"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image", "image/webp"
    if b"\x00" in data[:4096]:
        raise UploadRejected("지원하지 않는 파일 형식입니다(PDF, PNG, JPEG, WEBP, 텍스트, CSV).")
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise UploadRejected("텍스트 파일은 UTF-8 이어야 합니다.") from None
    first = text.splitlines()[0] if text.strip() else ""
    if first.count(",") >= 1 and len(text.splitlines()) >= 2:
        return "csv", "text/csv"
    return "text", "text/plain"


def safe_filename(name: str) -> str:
    name = unicodedata.normalize("NFC", Path(name.replace("\\", "/")).name)
    name = re.sub(r"[^\w가-힣.\- ()]", "_", name).strip(" .") or "upload"
    return name[:120]


def upload_dir(var_dir: Path) -> Path:
    d = (var_dir / "uploads").resolve()
    d.mkdir(parents=True, exist_ok=True)
    return d


def file_path(var_dir: Path, doc: ImportedDocument) -> Path:
    base = upload_dir(var_dir)
    p = (base / doc.stored_name).resolve()
    if base not in p.parents:  # 경로 탈출 방지(방어적)
        raise NotFound("파일 없음")
    return p


# ---------------------------------------------------------------- 저장·추출

def store_upload(session: Session, var_dir: Path, *, filename: str, data: bytes,
                 project_id: str | None) -> ImportedDocument:
    if len(data) > MAX_BYTES:
        raise UploadTooLarge(f"파일은 {MAX_BYTES // (1024 * 1024)}MB 이하만 올릴 수 있습니다.")
    if not data:
        raise UploadRejected("빈 파일입니다.")
    kind, media = sniff(data)
    stored = secrets.token_hex(16) + {"pdf": ".pdf", "image": "." + media.split("/")[1], "text": ".txt",
                                      "csv": ".csv"}[kind]
    (upload_dir(var_dir) / stored).write_bytes(data)
    doc = ImportedDocument(project_id=project_id, original_filename=safe_filename(filename), stored_name=stored,
                           media_type=media, kind=kind, size_bytes=len(data),
                           sha256=hashlib.sha256(data).hexdigest(),
                           retention_until=datetime.now(UTC) + timedelta(days=RETENTION_DAYS))
    session.add(doc)
    session.flush()
    extract(session, doc, data)
    return doc


def _pdf_text(data: bytes) -> str:
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(data))
    return "\n".join((p.extract_text() or "") for p in reader.pages[:50])


def extract(session: Session, doc: ImportedDocument, data: bytes) -> None:
    warnings: list[str] = []
    if doc.kind == "image":
        doc.extraction_method, doc.extracted_text = "manual", None
        warnings.append("ocr_unavailable")  # OCR 도구 미설치 — 원본을 보며 값을 직접 입력
    else:
        if doc.kind == "pdf":
            try:
                text = _pdf_text(data)
            except Exception:
                text = ""
                warnings.append("pdf_read_error")
            doc.extraction_method = "pdf_text"
            if not text.strip():
                warnings.append("pdf_no_text_layer")  # 스캔 PDF — OCR 필요
        else:
            text = data.decode("utf-8-sig")
            doc.extraction_method = doc.kind
        if doc.kind == "csv":
            text = _csv_to_lines(text)
        text = text[:MAX_TEXT_CHARS]
        doc.extracted_text = text
        if _INJECTION.search(text):
            warnings.append("instruction_like_text")
        for a in parse_assertions(text):
            session.add(ExtractedAssertion(document_id=doc.id, source="parsed", **a))
    doc.warnings = warnings
    doc.status = "extracted"
    session.flush()


def _csv_to_lines(text: str) -> str:
    rows = list(csv.reader(io.StringIO(text)))
    return "\n".join(" ".join(c.strip() for c in r if c.strip()) for r in rows)


# ---------------------------------------------------------------- 규칙 기반 파서

_STEM_KO = {k: STEMS[i] for i, k in enumerate(STEMS_KO)}
_BRANCH_KO = {k: BRANCHES[i] for i, k in enumerate(BRANCHES_KO)}
_GZ = f"[{STEMS}][{BRANCHES}]"
_GZ_KO = f"[{STEMS_KO}][{BRANCHES_KO}]"
_GYEOK = {"원격": "won", "형격": "hyeong", "이격": "i", "정격": "jeong"}
_LUCK = {"대길": "good", "길": "good", "반길": "half", "평": "half", "흉": "bad", "대흉": "bad"}


def _span(text: str, m: re.Match, pad: int = 12) -> str:
    return text[max(0, m.start() - pad): m.end() + pad].replace("\n", " ").strip()


def parse_assertions(text: str) -> list[dict]:
    out: list[dict] = []
    seen: set[tuple[str, str]] = set()

    def add(field: str, value: str, m: re.Match):
        if (field, value) in seen:
            return
        seen.add((field, value))
        out.append({"field": field, "value": value, "raw_text": _span(text, m)})

    m = re.search(rf"(?:성명|이름|작명)\s*[:：]?\s*([가-힣]{{2,6}})\s*[\(（]?\s*({_HANJA}{{2,6}})\s*[\)）]?", text) or \
        re.search(rf"([가-힣]{{2,6}})\s*[\(（]\s*({_HANJA}{{2,6}})\s*[\)）]", text)
    if m and len(m.group(1)) == len(m.group(2)):
        add("name_hangul", m.group(1), m)
        add("name_hanja", m.group(2), m)
    for m in re.finditer(rf"({_HANJA})\s*[\(（]?\s*(\d{{1,2}})\s*획", text):
        add(f"strokes:{m.group(1)}", m.group(2), m)
    for m in re.finditer(r"(원격|형격|이격|정격)\s*[:：]?\s*(\d{1,3})\s*(?:수|획)?\s*[\(（]?\s*(대길|반길|대흉|길|흉|평)?", text):
        key = _GYEOK[m.group(1)]
        add(f"gyeok.{key}", m.group(2), m)
        if m.group(3):
            add(f"luck.{key}", _LUCK[m.group(3)], m)
    m = re.search(rf"({_GZ})\s*(?:년)?\s*({_GZ})\s*(?:월)?\s*({_GZ})\s*(?:일)?\s*({_GZ})", text)
    if m:
        add("saju_pillars", " ".join(m.groups()), m)
    else:
        m = re.search(rf"({_GZ_KO})\s*년?\s*({_GZ_KO})\s*월?\s*({_GZ_KO})\s*일?\s*({_GZ_KO})\s*시?", text)
        if m:
            add("saju_pillars", " ".join(_STEM_KO[g[0]] + _BRANCH_KO[g[1]] for g in m.groups()), m)
    m = re.search(r"(양력|음력)?\s*(\d{4})\s*[.\-/년]\s*(\d{1,2})\s*[.\-/월]\s*(\d{1,2})\s*일?"
                  r"(?:\s*(\d{1,2})\s*[:시]\s*(\d{1,2})?\s*분?)?", text)
    if m:
        add("birth_date", f"{int(m.group(2)):04d}-{int(m.group(3)):02d}-{int(m.group(4)):02d}", m)
        if m.group(1):
            add("birth_calendar", "lunar" if m.group(1) == "음력" else "solar", m)
        if m.group(5):
            add("birth_time", f"{int(m.group(5)):02d}:{int(m.group(6) or 0):02d}", m)
    m = re.search(r"(원획|강희|필획|현대\s*획)", text)
    if m:
        add("stroke_system", "original" if m.group(1) in ("원획", "강희") else "modern", m)
    return out


# ---------------------------------------------------------------- 검토·삭제

def doc_dict(doc: ImportedDocument, assertions: list[ExtractedAssertion]) -> dict:
    return {"id": doc.id, "project_id": doc.project_id, "filename": doc.original_filename, "kind": doc.kind,
            "media_type": doc.media_type, "size_bytes": doc.size_bytes, "sha256": doc.sha256, "status": doc.status,
            "extraction_method": doc.extraction_method, "extracted_text": doc.extracted_text, "warnings": doc.warnings,
            "retention_until": doc.retention_until.isoformat() if doc.retention_until else None,
            "created_at": doc.created_at.isoformat(),
            "assertions": [{"id": a.id, "field": a.field, "value": a.value, "raw_text": a.raw_text, "source": a.source,
                            "review_status": a.review_status, "corrected_value": a.corrected_value,
                            "effective_value": a.corrected_value if a.review_status == "corrected" else a.value}
                           for a in assertions]}


def get_doc(session: Session, doc_id: str) -> ImportedDocument:
    d = session.get(ImportedDocument, doc_id)
    if d is None or d.status == "deleted":
        raise NotFound("문서를 찾을 수 없습니다.")
    return d


def assertions_of(session: Session, doc_id: str) -> list[ExtractedAssertion]:
    return list(session.scalars(select(ExtractedAssertion).where(ExtractedAssertion.document_id == doc_id)
                                .order_by(ExtractedAssertion.created_at, ExtractedAssertion.field)))


ALLOWED_FIELDS = re.compile(r"^(name_hangul|name_hanja|strokes:.|gyeok\.(won|hyeong|i|jeong)|luck\.(won|hyeong|i|jeong)|"
                            r"saju_pillars|birth_date|birth_time|birth_calendar|stroke_system)$")


def add_manual(session: Session, doc_id: str, field: str, value: str) -> ExtractedAssertion:
    get_doc(session, doc_id)
    if not ALLOWED_FIELDS.match(field):
        raise AppError("지원하지 않는 항목입니다.", details={"field": field})
    a = ExtractedAssertion(document_id=doc_id, field=field, value=value.strip()[:200], source="manual",
                           confidence="manual", review_status="accepted")
    session.add(a)
    session.flush()
    return a


def review(session: Session, assertion_id: str, status: str, corrected: str | None) -> ExtractedAssertion:
    a = session.get(ExtractedAssertion, assertion_id)
    if a is None:
        raise NotFound("추출값을 찾을 수 없습니다.")
    if status not in ("accepted", "corrected", "rejected"):
        raise AppError("review_status 는 accepted | corrected | rejected 입니다.")
    if status == "corrected" and not (corrected or "").strip():
        raise AppError("수정값이 필요합니다.")
    a.review_status, a.corrected_value = status, (corrected or "").strip()[:200] or None
    doc = session.get(ImportedDocument, a.document_id)
    if doc and all(x.review_status != "pending" for x in assertions_of(session, doc.id)):
        doc.status = "reviewed"
    session.flush()
    return a


def delete_doc(session: Session, var_dir: Path, doc_id: str) -> None:
    doc = get_doc(session, doc_id)
    try:
        file_path(var_dir, doc).unlink(missing_ok=True)
    except NotFound:
        pass
    session.execute(delete(ExtractedAssertion).where(ExtractedAssertion.document_id == doc.id))
    session.execute(delete(CrosscheckResult).where(CrosscheckResult.document_id == doc.id))
    doc.extracted_text, doc.status, doc.deleted_at = None, "deleted", datetime.now(UTC)
    session.flush()
