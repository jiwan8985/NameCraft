"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardTitle } from "@/components/ui/card";
import { Field, Input, Notice, Select, splitList } from "@/components/ui/form";
import { postJson } from "@/lib/api";
import type { Project } from "@/lib/types";

const STYLE_OPTIONS = [
  { key: "soft", label: "부드러움" },
  { key: "bright", label: "밝음" },
  { key: "modern", label: "현대적" },
  { key: "traditional", label: "전통적" },
] as const;

/** 기획서 §4 입력 UX: 기본 3단계(아이 정보 → 선호 → 추천 시작) + 접을 수 있는 고급 옵션 */
export function NewProjectWizard() {
  const router = useRouter();
  const [step, setStep] = useState(1);
  const [surname, setSurname] = useState("");
  const [surnameHanja, setSurnameHanja] = useState("");
  const [sex, setSex] = useState<"m" | "f" | "n">("n");
  const [syllables, setSyllables] = useState(2);
  const [nameType, setNameType] = useState<"hanja" | "hangul" | "any">("any");
  const [styles, setStyles] = useState<Record<string, number>>({});
  const [liked, setLiked] = useState("");
  const [include, setInclude] = useState("");
  const [exclude, setExclude] = useState("");
  const [fixed, setFixed] = useState("");
  const [fixedPos, setFixedPos] = useState(0);
  const [count, setCount] = useState(20);
  const [useTraditional, setUseTraditional] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const step1Valid = /^[가-힣]{1,4}$/.test(surname.trim());

  async function submit() {
    setBusy(true);
    setError(null);
    const constraints: Record<string, unknown> = {
      include_syllables: splitList(include),
      exclude_syllables: splitList(exclude),
    };
    if (fixed.trim()) constraints.fixed_syllable = { [fixedPos]: fixed.trim() };
    const created = await postJson<Project>("projects", {
      surname_hangul: surname.trim(),
      surname_hanja: surnameHanja.trim() || null,
      sex,
      preferences: { syllables, name_type: nameType, style_tags: styles, liked_examples: splitList(liked), count,
                     use_traditional: useTraditional },
      constraints,
    });
    if (!created.ok) {
      setBusy(false);
      setError(created.error.message);
      return;
    }
    // AI 없이 규칙 기반으로 첫 후보 생성 (AI 사용은 추천 화면에서 선택)
    await postJson(`projects/${created.data.id}/candidates/generate`, { provider: "none" });
    router.push(`/projects/${created.data.id}/recommendations`);
  }

  return (
    <div className="space-y-4">
      <ol className="flex gap-2 text-sm" aria-label="입력 단계">
        {["아이 정보", "선호", "추천 시작"].map((t, i) => (
          <li key={t} aria-current={step === i + 1 ? "step" : undefined}
              className={`rounded-full border px-3 py-1 ${step === i + 1 ? "border-primary text-primary" : "border-border text-muted-foreground"}`}>
            {i + 1}. {t}
          </li>
        ))}
      </ol>

      {step === 1 && (
        <Card className="space-y-4">
          <CardTitle>아이 정보</CardTitle>
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="성씨 (한글)" htmlFor="surname" hint="예: 심, 남궁">
              <Input id="surname" value={surname} onChange={(e) => setSurname(e.target.value)} maxLength={4} />
            </Field>
            <Field label="성씨 한자 (선택)" htmlFor="surname-hanja" hint="수리 분석에 쓰입니다. 예: 沈">
              <Input id="surname-hanja" value={surnameHanja} onChange={(e) => setSurnameHanja(e.target.value)} maxLength={4} />
            </Field>
            <Field label="성별 선호" htmlFor="sex" hint="이름 느낌의 선호일 뿐, 후보를 제한하지 않습니다.">
              <Select id="sex" value={sex} onChange={(e) => setSex(e.target.value as "m" | "f" | "n")}>
                <option value="n">상관없음·중립</option>
                <option value="f">여아</option>
                <option value="m">남아</option>
              </Select>
            </Field>
            <Field label="이름 글자 수" htmlFor="syllables">
              <Select id="syllables" value={syllables} onChange={(e) => setSyllables(Number(e.target.value))}>
                <option value={1}>1자(외자)</option>
                <option value={2}>2자</option>
                <option value={3}>3자</option>
              </Select>
            </Field>
            <Field label="이름 유형" htmlFor="name-type">
              <Select id="name-type" value={nameType} onChange={(e) => setNameType(e.target.value as typeof nameType)}>
                <option value="any">한자·한글 모두</option>
                <option value="hanja">한자 이름</option>
                <option value="hangul">한글 이름</option>
              </Select>
            </Field>
          </div>
          <p className="text-xs text-muted-foreground">출생 예정일·시간은 시나리오 화면(Phase 9)에서 입력합니다.</p>
          <div className="flex justify-end">
            <Button disabled={!step1Valid} onClick={() => setStep(2)}>다음</Button>
          </div>
        </Card>
      )}

      {step === 2 && (
        <Card className="space-y-4">
          <CardTitle>선호</CardTitle>
          <fieldset className="space-y-2">
            <legend className="text-sm font-medium">원하는 느낌 (여러 개 선택)</legend>
            <div className="flex flex-wrap gap-2">
              {STYLE_OPTIONS.map((o) => (
                <label key={o.key} className="inline-flex items-center gap-2 rounded-md border border-border px-3 py-1.5 text-sm">
                  <input type="checkbox" checked={!!styles[o.key]}
                         onChange={(e) => setStyles((s) => ({ ...s, [o.key]: e.target.checked ? 1 : 0 }))} />
                  {o.label}
                </label>
              ))}
            </div>
          </fieldset>
          <Field label="좋아하는 이름 예시" htmlFor="liked" hint="쉼표로 구분. 비슷한 느낌의 '다른' 이름을 찾습니다. 예: 심지아, 심하은">
            <Input id="liked" value={liked} onChange={(e) => setLiked(e.target.value)} />
          </Field>
          <details className="rounded-md border border-border p-3">
            <summary className="cursor-pointer text-sm font-medium">고급 옵션</summary>
            <div className="mt-3 grid gap-4 sm:grid-cols-2">
              <Field label="꼭 들어갈 음절 (하나 이상)" htmlFor="include"><Input id="include" value={include} onChange={(e) => setInclude(e.target.value)} /></Field>
              <Field label="제외할 음절" htmlFor="exclude"><Input id="exclude" value={exclude} onChange={(e) => setExclude(e.target.value)} /></Field>
              <Field label="돌림자" htmlFor="fixed" hint="정해진 음절과 위치">
                <div className="flex gap-2">
                  <Input id="fixed" value={fixed} onChange={(e) => setFixed(e.target.value)} maxLength={1} className="w-20" />
                  <Select aria-label="돌림자 위치" value={fixedPos} onChange={(e) => setFixedPos(Number(e.target.value))}>
                    <option value={0}>첫 글자</option>
                    <option value={1}>둘째 글자</option>
                  </Select>
                </div>
              </Field>
              <Field label="후보 개수" htmlFor="count">
                <Select id="count" value={count} onChange={(e) => setCount(Number(e.target.value))}>
                  {[20, 30, 50].map((n) => <option key={n} value={n}>{n}</option>)}
                </Select>
              </Field>
              <label className="inline-flex items-center gap-2 text-sm sm:col-span-2">
                <input type="checkbox" checked={useTraditional} onChange={(e) => setUseTraditional(e.target.checked)} />
                한자 조합 정렬에 전통 수리(81수리·음양) 반영 — 전통 해석 · 출처 대조 전
              </label>
            </div>
          </details>
          <div className="flex justify-between">
            <Button variant="outline" onClick={() => setStep(1)}>이전</Button>
            <Button onClick={() => setStep(3)}>다음</Button>
          </div>
        </Card>
      )}

      {step === 3 && (
        <Card className="space-y-4">
          <CardTitle>추천 시작</CardTitle>
          <dl className="grid grid-cols-[7rem_1fr] gap-y-1 text-sm">
            <dt className="text-muted-foreground">성씨</dt><dd>{surname} {surnameHanja && `(${surnameHanja})`}</dd>
            <dt className="text-muted-foreground">글자 수·유형</dt><dd>{syllables}자 · {{ any: "한자·한글", hanja: "한자", hangul: "한글" }[nameType]}</dd>
            <dt className="text-muted-foreground">좋아하는 예시</dt><dd>{splitList(liked).join(", ") || "없음"}</dd>
          </dl>
          <Notice>첫 후보는 AI 없이 규칙 기반 엔진으로 만듭니다. AI 사용은 추천 화면에서 선택할 수 있습니다.</Notice>
          {error && <Notice tone="danger" role="alert">{error}</Notice>}
          <div className="flex justify-between">
            <Button variant="outline" onClick={() => setStep(2)}>이전</Button>
            <Button disabled={busy} onClick={submit}>{busy ? "만드는 중…" : "프로젝트 만들고 추천 받기"}</Button>
          </div>
        </Card>
      )}
    </div>
  );
}
