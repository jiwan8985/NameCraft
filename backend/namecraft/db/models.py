"""Phase 1 기반 테이블.

도메인 테이블(성씨·한자·이름·사주 등)은 각 Phase에서 마이그레이션으로 추가한다 (기획서 §16, §21.1).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import JSON, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    pass


Base.metadata.naming_convention = NAMING_CONVENTION


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    display_name: Mapped[str] = mapped_column(String(100))  # 표시용 별칭(실명 불필요)
    role: Mapped[str] = mapped_column(String(20), default="owner")  # owner | member | admin
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class AuditLog(Base):
    """감사 로그 — 개인정보 원문 저장 금지. target은 ID만."""

    __tablename__ = "audit_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    action: Mapped[str] = mapped_column(String(100))
    target_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    target_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    meta: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, index=True)


class ReferenceSource(Base):
    """datasets/source-manifests 와 1:1 (DATA_SOURCES.md)."""

    __tablename__ = "reference_sources"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)  # 예: SRC-SCOURT-HANJA
    name: Mapped[str] = mapped_column(String(200))
    url: Mapped[str | None] = mapped_column(Text, nullable=True)
    authority: Mapped[str] = mapped_column(String(50))
    license: Mapped[str | None] = mapped_column(String(200), nullable=True)
    license_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(30))
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class DataReleaseVersion(Base):
    """데이터 스냅샷 버전 — 이전 보고서 재현용 (기획서 §16.2)."""

    __tablename__ = "data_release_versions"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)  # 예: 2026.11.0
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    checksums: Mapped[dict] = mapped_column(JSON, default=dict)
    is_sample: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


# ---------------------------------------------------------------------------
# Phase 2: 성씨·한자·어휘 데이터 레이어 (기획서 §5, §16)
#
# 원칙
# - 출처(source_id)·검증상태(status)는 레코드/필드 단위로 분리 저장한다.
# - 법적 허용(official_name_character_rules)은 공식 출처만 기록한다. Unihan 등 비공식 힌트는
#   hanja_characters.unihan_korean_name 같은 별도 필드에만 둔다.
# - 현대 필획과 성명학 원획은 hanja_stroke_counts.system 으로 분리한다.
# ---------------------------------------------------------------------------

RECORD_STATUSES = ("verified", "unverified", "conflict", "deprecated")


class HanjaCharacter(Base):
    __tablename__ = "hanja_characters"

    codepoint: Mapped[str] = mapped_column(String(12), primary_key=True)  # "U+6C88"
    char: Mapped[str] = mapped_column(String(2))
    canonical_codepoint: Mapped[str] = mapped_column(String(12), index=True)  # 호환한자 → 통합한자
    is_compatibility: Mapped[bool] = mapped_column(default=False)
    radical_stroke: Mapped[str | None] = mapped_column(String(20), nullable=True)  # kRSUnicode
    definition_en: Mapped[str | None] = mapped_column(Text, nullable=True)  # kDefinition (참고용)
    unihan_korean_name: Mapped[str | None] = mapped_column(String(10), nullable=True)  # kKoreanName 판(비공식 힌트)
    unihan_korean_education: Mapped[str | None] = mapped_column(String(10), nullable=True)
    record_status: Mapped[str] = mapped_column(String(20), default="unverified")
    source_id: Mapped[str] = mapped_column(ForeignKey("reference_sources.id"))
    data_release_id: Mapped[str | None] = mapped_column(ForeignKey("data_release_versions.id"), nullable=True)


class HanjaReading(Base):
    __tablename__ = "hanja_readings"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    codepoint: Mapped[str] = mapped_column(ForeignKey("hanja_characters.codepoint", ondelete="CASCADE"), index=True)
    reading: Mapped[str] = mapped_column(String(10), index=True)  # 한글 독음
    is_name_reading: Mapped[bool | None] = mapped_column(nullable=True)  # 출처가 말하는 인명용 여부 (None=정보 없음)
    flags: Mapped[str | None] = mapped_column(String(20), nullable=True)  # 출처 원본 플래그(예: Unihan "0N")
    source_id: Mapped[str] = mapped_column(ForeignKey("reference_sources.id"))
    status: Mapped[str] = mapped_column(String(20), default="unverified")
    data_release_id: Mapped[str | None] = mapped_column(ForeignKey("data_release_versions.id"), nullable=True)


class HanjaVariant(Base):
    __tablename__ = "hanja_variants"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    codepoint: Mapped[str] = mapped_column(ForeignKey("hanja_characters.codepoint", ondelete="CASCADE"), index=True)
    variant_codepoint: Mapped[str] = mapped_column(String(12))
    variant_type: Mapped[str] = mapped_column(String(30))  # compatibility|traditional|simplified|semantic|z
    source_id: Mapped[str] = mapped_column(ForeignKey("reference_sources.id"))


class HanjaStrokeCount(Base):
    __tablename__ = "hanja_stroke_counts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    codepoint: Mapped[str] = mapped_column(ForeignKey("hanja_characters.codepoint", ondelete="CASCADE"), index=True)
    system: Mapped[str] = mapped_column(String(20))  # modern | original
    strokes: Mapped[int]
    rule_id: Mapped[str | None] = mapped_column(String(50), nullable=True)  # original 산출 규칙 (Phase 4)
    profile_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    source_id: Mapped[str] = mapped_column(ForeignKey("reference_sources.id"))
    status: Mapped[str] = mapped_column(String(20), default="unverified")


class HanjaElementMapping(Base):
    """자원오행 — 학파(profile)별, 출처 필수 (Phase 4에서 데이터 투입)."""

    __tablename__ = "hanja_element_mappings"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    codepoint: Mapped[str] = mapped_column(ForeignKey("hanja_characters.codepoint", ondelete="CASCADE"), index=True)
    profile_id: Mapped[str] = mapped_column(String(50))
    element: Mapped[str] = mapped_column(String(2))  # 木火土金水
    source_id: Mapped[str] = mapped_column(ForeignKey("reference_sources.id"))
    status: Mapped[str] = mapped_column(String(20), default="unverified")


class OfficialNameCharacterRule(Base):
    """인명용 한자 법적 허용 — 공식 출처(SRC-SCOURT-HANJA 등) 레코드만."""

    __tablename__ = "official_name_character_rules"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    codepoint: Mapped[str] = mapped_column(String(12), index=True)
    reading: Mapped[str] = mapped_column(String(10))  # 허용 독음
    allowed: Mapped[bool] = mapped_column(default=True)
    legal_basis: Mapped[str | None] = mapped_column(String(200), nullable=True)
    effective_date: Mapped[str | None] = mapped_column(String(10), nullable=True)  # 고시·시행일 YYYY-MM-DD
    checked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    source_id: Mapped[str] = mapped_column(ForeignKey("reference_sources.id"))
    data_release_id: Mapped[str | None] = mapped_column(ForeignKey("data_release_versions.id"), nullable=True)
    is_sample: Mapped[bool] = mapped_column(default=False)


class Surname(Base):
    __tablename__ = "surnames"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    hangul: Mapped[str] = mapped_column(String(10), index=True)
    hanja: Mapped[str | None] = mapped_column(String(10), nullable=True)
    hanja_codepoints: Mapped[list] = mapped_column(JSON, default=list)
    is_compound: Mapped[bool] = mapped_column(default=False)
    record_status: Mapped[str] = mapped_column(String(20), default="unverified")
    is_provisional: Mapped[bool] = mapped_column(default=False)  # 사용자 입력 임시 레코드 (확정 보류)
    source_id: Mapped[str] = mapped_column(ForeignKey("reference_sources.id"))
    note: Mapped[str | None] = mapped_column(Text, nullable=True)


class SurnameVariant(Base):
    """두음법칙 등 대체 한글 표기 (예: 李 이/리, 柳 류/유)."""

    __tablename__ = "surname_variants"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    surname_id: Mapped[str] = mapped_column(ForeignKey("surnames.id", ondelete="CASCADE"), index=True)
    hangul: Mapped[str] = mapped_column(String(10), index=True)
    variant_type: Mapped[str] = mapped_column(String(30), default="initial_sound_law")


class DictionaryTerm(Base):
    """어휘 의미·발음 (국립국어원 등, 라이선스 확인 후 투입 — Phase 5)."""

    __tablename__ = "dictionary_terms"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    term: Mapped[str] = mapped_column(String(50), index=True)
    pos: Mapped[str | None] = mapped_column(String(20), nullable=True)
    meaning: Mapped[str | None] = mapped_column(Text, nullable=True)
    pronunciation: Mapped[str | None] = mapped_column(String(50), nullable=True)
    hanja: Mapped[str | None] = mapped_column(String(20), nullable=True)
    tags: Mapped[list] = mapped_column(JSON, default=list)  # 예: ["negative_association_candidate"]
    source_id: Mapped[str] = mapped_column(ForeignKey("reference_sources.id"))
    status: Mapped[str] = mapped_column(String(20), default="unverified")


class NamePopularityDataset(Base):
    __tablename__ = "name_popularity_datasets"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    source_id: Mapped[str] = mapped_column(ForeignKey("reference_sources.id"))
    year: Mapped[int]
    sex: Mapped[str | None] = mapped_column(String(10), nullable=True)
    region: Mapped[str | None] = mapped_column(String(50), nullable=True)
    aggregation_basis: Mapped[str] = mapped_column(Text)  # 집계 기준
    coverage: Mapped[str] = mapped_column(String(100))  # 예: "top 10 only"
    checked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class NamePopularityRow(Base):
    __tablename__ = "name_popularity_rows"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    dataset_id: Mapped[str] = mapped_column(ForeignKey("name_popularity_datasets.id", ondelete="CASCADE"), index=True)
    name_hangul: Mapped[str] = mapped_column(String(20), index=True)
    rank: Mapped[int | None] = mapped_column(nullable=True)
    count: Mapped[int | None] = mapped_column(nullable=True)


# ---------------------------------------------------------------------------
# Phase 7: 프로젝트·후보·반응·AI 기록 (기획서 §9, §16, §29, §33.4)
# 사용량 기록에는 프롬프트 원문·출생정보·인증정보를 저장하지 않는다.
# ---------------------------------------------------------------------------

from sqlalchemy import UniqueConstraint  # noqa: E402


class NamingProject(Base):
    __tablename__ = "naming_projects"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    title: Mapped[str] = mapped_column(String(100))
    surname_hangul: Mapped[str] = mapped_column(String(10))
    surname_hanja: Mapped[str | None] = mapped_column(String(10), nullable=True)
    sex: Mapped[str] = mapped_column(String(1), default="n")
    preferences: Mapped[dict] = mapped_column(JSON, default=dict)  # style_tags, liked_examples, syllables, name_type
    constraints: Mapped[dict] = mapped_column(JSON, default=dict)  # include/exclude, fixed 등 하드 조건
    analysis_options: Mapped[dict] = mapped_column(JSON, default=dict)  # 학파·가중치
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)


class NameCandidate(Base):
    __tablename__ = "name_candidates"
    __table_args__ = (UniqueConstraint("project_id", "given_hangul", "given_hanja", name="uq_candidate_name"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    project_id: Mapped[str] = mapped_column(ForeignKey("naming_projects.id", ondelete="CASCADE"), index=True)
    given_hangul: Mapped[str] = mapped_column(String(10))
    given_hanja: Mapped[str] = mapped_column(String(10), default="")  # 한자 없음 = "" (유니크 제약 위해)
    source: Mapped[str] = mapped_column(String(20))  # rule_based | data_based | ai_based | user
    status: Mapped[str] = mapped_column(String(20), default="active")  # active | excluded | favorite
    provider_id: Mapped[str | None] = mapped_column(String(30), nullable=True)
    generation_record_id: Mapped[str | None] = mapped_column(ForeignKey("ai_generation_records.id"), nullable=True)
    ai_reason: Mapped[str | None] = mapped_column(Text, nullable=True)  # 검증 통과한 AI 설명(subjective)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class NameReaction(Base):
    __tablename__ = "name_reactions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    candidate_id: Mapped[str] = mapped_column(ForeignKey("name_candidates.id", ondelete="CASCADE"), index=True)
    member: Mapped[str] = mapped_column(String(50), default="owner")
    reaction: Mapped[str] = mapped_column(String(10))  # like | dislike | hold
    reasons: Mapped[list] = mapped_column(JSON, default=list)
    memo: Mapped[str | None] = mapped_column(Text, nullable=True)
    rank: Mapped[int | None] = mapped_column(nullable=True)  # 가족 평가 순위(1=가장 선호)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class AIGenerationRecord(Base):
    """AI/규칙 생성 배치 기록 — 재현성(모델·프롬프트 버전·시드·검증 상태), 보낸 필드 '이름'만 저장."""

    __tablename__ = "ai_generation_records"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    project_id: Mapped[str | None] = mapped_column(ForeignKey("naming_projects.id", ondelete="SET NULL"), nullable=True)
    task: Mapped[str] = mapped_column(String(30))
    provider_id: Mapped[str] = mapped_column(String(30))  # rule_based 포함
    model_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    execution_mode: Mapped[str] = mapped_column(String(30))
    prompt_version: Mapped[str | None] = mapped_column(String(30), nullable=True)
    seed: Mapped[int | None] = mapped_column(nullable=True)
    sent_fields: Mapped[list] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(String(20))  # ok | partial | invalid | fallback | error
    validation: Mapped[dict] = mapped_column(JSON, default=dict)
    fallback_reason: Mapped[str | None] = mapped_column(String(50), nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class AIProviderSetting(Base):
    __tablename__ = "ai_provider_settings"

    provider_id: Mapped[str] = mapped_column(String(30), primary_key=True)
    enabled: Mapped[bool] = mapped_column(default=False)
    command: Mapped[list | None] = mapped_column(JSON, nullable=True)
    model_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    timeout_s: Mapped[int] = mapped_column(default=120)
    fallback_rank: Mapped[int] = mapped_column(default=99)  # 자동 대체 순서 (낮을수록 먼저)
    allow_auto_fallback: Mapped[bool] = mapped_column(default=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)


class AIInvocation(Base):
    """NameCraft 내부 AI 호출 1건 = 1행 (§33.4: provider, mode, model_if_known, source_type, observed_at, quota_data_status)."""

    __tablename__ = "ai_invocations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    provider_id: Mapped[str] = mapped_column(String(30), index=True)
    execution_mode: Mapped[str] = mapped_column(String(30))
    model_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    task: Mapped[str] = mapped_column(String(30))
    project_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    status: Mapped[str] = mapped_column(String(20))  # success | error | timeout | rate_limited | invalid_output
    duration_ms: Mapped[int | None] = mapped_column(nullable=True)
    tokens_in: Mapped[int | None] = mapped_column(nullable=True)
    tokens_out: Mapped[int | None] = mapped_column(nullable=True)
    source_type: Mapped[str] = mapped_column(String(20), default="local_observed")
    quota_data_status: Mapped[str] = mapped_column(String(20), default="unknown")
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, index=True)
    is_demo: Mapped[bool] = mapped_column(default=False)




# ---------------------------------------------------------------------------
# Phase 9: 출생정보 버전·시나리오 스냅샷·가족·토너먼트·결선/결정 (기획서 §11, §12)
# 출생정보는 민감 정보 — 로그 금지, 사용량/AI 기록과 분리.
# ---------------------------------------------------------------------------


class BirthProfile(Base):
    __tablename__ = "birth_profiles"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    project_id: Mapped[str] = mapped_column(ForeignKey("naming_projects.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(10))  # expected | actual
    calendar: Mapped[str] = mapped_column(String(10), default="solar")
    date: Mapped[str] = mapped_column(String(10))  # YYYY-MM-DD (입력 달력 기준)
    is_leap_month: Mapped[bool] = mapped_column(default=False)
    time: Mapped[str | None] = mapped_column(String(5), nullable=True)
    time_range: Mapped[list | None] = mapped_column(JSON, nullable=True)
    tz: Mapped[str] = mapped_column(String(64), default="Asia/Seoul")
    longitude: Mapped[float | None] = mapped_column(nullable=True)
    true_solar_time: Mapped[str] = mapped_column(String(30), default="off")
    zi_convention: Mapped[str] = mapped_column(String(30), default="jojasi_next_day")
    day_window: Mapped[int] = mapped_column(default=0)  # 예정일 ±N일
    extra_dates: Mapped[list] = mapped_column(JSON, default=list)  # 다른 후보 예정일(양력)
    is_current: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    superseded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ScenarioResult(Base):
    """시나리오 평가 스냅샷 — 출생정보 버전별로 보존(이전 평가 재현)."""

    __tablename__ = "scenario_results"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    project_id: Mapped[str] = mapped_column(ForeignKey("naming_projects.id", ondelete="CASCADE"), index=True)
    birth_profile_id: Mapped[str] = mapped_column(ForeignKey("birth_profiles.id", ondelete="CASCADE"), index=True)
    engine_version: Mapped[str] = mapped_column(String(20))
    rule_version: Mapped[str] = mapped_column(String(20))
    interpretation_profile: Mapped[str | None] = mapped_column(String(50), nullable=True)
    summary: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class FamilyMember(Base):
    __tablename__ = "family_members"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    project_id: Mapped[str] = mapped_column(ForeignKey("naming_projects.id", ondelete="CASCADE"), index=True)
    alias: Mapped[str] = mapped_column(String(30))  # 표시용 별칭(예: 엄마, 아빠) — 실명 불필요
    role: Mapped[str] = mapped_column(String(20), default="parent")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class Tournament(Base):
    __tablename__ = "tournaments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    project_id: Mapped[str] = mapped_column(ForeignKey("naming_projects.id", ondelete="CASCADE"), index=True)
    member: Mapped[str] = mapped_column(String(50), default="owner")
    status: Mapped[str] = mapped_column(String(10), default="active")  # active | done
    rounds: Mapped[list] = mapped_column(JSON, default=list)  # [[{a, b, choice}]]
    result: Mapped[dict] = mapped_column(JSON, default=dict)  # {winner, finalists, tied}
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class FinalNameDecision(Base):
    """결선 보드·최종 결정 기록 — 선택 근거·선택일·비교 스냅샷 보존, 이전 기록 유지."""

    __tablename__ = "final_name_decisions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    project_id: Mapped[str] = mapped_column(ForeignKey("naming_projects.id", ondelete="CASCADE"), index=True)
    finalists: Mapped[list] = mapped_column(JSON, default=list)
    chosen_candidate_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    snapshot: Mapped[dict] = mapped_column(JSON, default=dict)
    birth_profile_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    is_current: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


# ---------------------------------------------------------------------------
# Phase 10: 작명소 자료 가져오기·교차검증 (기획서 §13)
# 업로드 원본은 var/uploads 에 무작위 이름으로 저장, 실행·AI 전송하지 않는다.
# ---------------------------------------------------------------------------


class ImportedDocument(Base):
    __tablename__ = "imported_documents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    project_id: Mapped[str | None] = mapped_column(ForeignKey("naming_projects.id", ondelete="SET NULL"),
                                                   nullable=True, index=True)
    original_filename: Mapped[str] = mapped_column(String(200))  # 표시용(정리된 이름)
    stored_name: Mapped[str] = mapped_column(String(80))  # 무작위 저장 이름
    media_type: Mapped[str] = mapped_column(String(50))
    kind: Mapped[str] = mapped_column(String(10))  # pdf | image | text | csv
    size_bytes: Mapped[int]
    sha256: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(20), default="uploaded")  # uploaded | extracted | reviewed | deleted
    extraction_method: Mapped[str | None] = mapped_column(String(30), nullable=True)  # text | csv | pdf_text | manual
    extracted_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    warnings: Mapped[list] = mapped_column(JSON, default=list)
    retention_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ExtractedAssertion(Base):
    """문서에서 추출(또는 사람이 입력)한 주장 — 원문 위치와 함께 저장, 사람 검토 후에만 교차검증에 사용."""

    __tablename__ = "extracted_assertions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    document_id: Mapped[str] = mapped_column(ForeignKey("imported_documents.id", ondelete="CASCADE"), index=True)
    field: Mapped[str] = mapped_column(String(40))  # name_hangul | name_hanja | strokes | gyeok.won | luck.won | saju_pillars | stroke_system | ...
    value: Mapped[str] = mapped_column(String(200))
    raw_text: Mapped[str | None] = mapped_column(Text, nullable=True)  # 원문 조각
    source: Mapped[str] = mapped_column(String(20))  # parsed | manual
    confidence: Mapped[str] = mapped_column(String(20), default="parsed_unreviewed")
    review_status: Mapped[str] = mapped_column(String(20), default="pending")  # pending | accepted | corrected | rejected
    corrected_value: Mapped[str | None] = mapped_column(String(200), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class CrosscheckResult(Base):
    __tablename__ = "crosscheck_results"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    document_id: Mapped[str] = mapped_column(ForeignKey("imported_documents.id", ondelete="CASCADE"), index=True)
    summary: Mapped[dict] = mapped_column(JSON, default=dict)
    items: Mapped[list] = mapped_column(JSON, default=list)
    engine_versions: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
