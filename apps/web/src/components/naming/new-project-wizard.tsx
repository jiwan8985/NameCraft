"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { Check } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Chip, Details, Field, Input, Notice, splitList } from "@/components/ui/form";
import { postJson } from "@/lib/api";
import type { Project } from "@/lib/types";

const STYLE_OPTIONS = [
  { key: "soft", label: "부드러운" },
  { key: "bright", label: "밝은" },
  { key: "modern", label: "요즘 느낌" },
  { key: "traditional", label: "전통적인" },
] as const;
const STEPS = ["아이 정보", "원하는 느낌", "시작"];

/** 기획서 §4: 기본 3단계 + 접을 수 있는 고급 옵션 */
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
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const step1Valid = /^[가-힣]{1,4}$/.test(surname.trim());

  async function submit() {
    setBusy(true);
    setError(null);
    const constraints: Record<string, unknown> = { include_syllables: splitList(include), exclude_syllables: splitList(exclude) };
    if (fixed.trim()) constraints.fixed_syllable = { [fixedPos]: fixed.trim() };
    const created = await postJson<Project>("projects", {
      surname_hangul: surname.trim(), surname_hanja: surnameHanja.trim() || null, sex,
      preferences: { syllables, name_type: nameType, style_tags: styles, liked_examples: splitList(liked), count: 20, use_traditional: true },
      constraints,
    });
    if (!created.ok) {
      setBusy(false);
      return setError(created.error.message);
    }
    await postJson(`projects/${created.data.id}/candidates/generate`, { provider: "none" });
    router.push(`/projects/${created.data.id}/recommendations`);
  }

  return (
    <div className="space-y-6">
      <ol className="flex items-center gap-2 text-sm" aria-label="입력 단계">
        {STEPS.map((t, i) => (
          <li key={t} aria-current={step === i + 1 ? "step" : undefined} className="flex items-center gap-2">
            <span className={`grid h-7 w-7 place-items-center rounded-full text-xs font-semibold ${step > i + 1 ? "bg-primary text-primary-foreground" : step === i + 1 ? "bg-primary-soft text-primary ring-2 ring-primary" : "bg-muted text-muted-foreground"}`}>
              {step > i + 1 ? <Check className="h-3.5 w-3.5" /> : i + 1}
            </span>
            <span className={step === i + 1 ? "font-medium" : "text-muted-foreground"}>{t}</span>
            {i < STEPS.length - 1 && <span className="mx-1 h-px w-6 bg-border" aria-hidden="true" />}
          </li>
        ))}
      </ol>

      {step === 1 && (
        <Card className="space-y-6 p-6">
          <Field label="성씨 (한글)" htmlFor="surname">
            <Input id="surname" value={surname} onChange={(e) => setSurname(e.target.value)} maxLength={4} placeholder="예: 심" className="max-w-xs text-lg" />
          </Field>
          <div className="space-y-2">
            <p className="text-sm font-medium">아이</p>
            <div className="flex flex-wrap gap-2">
              {([["f", "여아"], ["m", "남아"], ["n", "상관없음"]] as const).map(([v, l]) => <Chip key={v} active={sex === v} onClick={() => setSex(v)}>{l}</Chip>)}
            </div>
            <p className="text-xs text-muted-foreground">이름 느낌을 고를 때 참고만 하고, 후보를 제한하지 않습니다.</p>
          </div>
          <div className="space-y-2">
            <p className="text-sm font-medium">이름 글자 수</p>
            <div className="flex flex-wrap gap-2">
              {[1, 2, 3].map((n) => <Chip key={n} active={syllables === n} onClick={() => setSyllables(n)}>{n === 1 ? "외자" : `${n}글자`}</Chip>)}
            </div>
          </div>
          <Details summary="더 정하기 (성씨 한자 · 이름 유형)">
            <div className="grid gap-4 sm:grid-cols-2">
              <Field label="성씨 한자" htmlFor="surname-hanja" hint="넣으면 획수·수리 분석도 보여드려요. 예: 沈">
                <Input id="surname-hanja" value={surnameHanja} onChange={(e) => setSurnameHanja(e.target.value)} maxLength={4} />
              </Field>
              <div className="space-y-2">
                <p className="text-sm font-medium">이름 유형</p>
                <div className="flex flex-wrap gap-2">
                  {([["any", "상관없음"], ["hanja", "한자 이름"], ["hangul", "한글 이름"]] as const).map(([v, l]) => <Chip key={v} active={nameType === v} onClick={() => setNameType(v)}>{l}</Chip>)}
                </div>
              </div>
            </div>
          </Details>
          <div className="flex justify-end"><Button disabled={!step1Valid} onClick={() => setStep(2)}>다음</Button></div>
        </Card>
      )}

      {step === 2 && (
        <Card className="space-y-6 p-6">
          <fieldset className="space-y-2">
            <legend className="text-sm font-medium">원하는 느낌 (여러 개 선택)</legend>
            <div className="flex flex-wrap gap-2">
              {STYLE_OPTIONS.map((o) => <Chip key={o.key} active={!!styles[o.key]} onClick={() => setStyles((s) => ({ ...s, [o.key]: s[o.key] ? 0 : 1 }))}>{o.label}</Chip>)}
            </div>
          </fieldset>
          <Field label="마음에 드는 이름 예시 (선택)" htmlFor="liked" hint="쉼표로 구분. 비슷한 느낌의 다른 이름을 찾아 드려요.">
            <Input id="liked" value={liked} onChange={(e) => setLiked(e.target.value)} placeholder="예: 지아, 하은" />
          </Field>
          <Details summary="고급 옵션 (꼭 넣을 글자 · 뺄 글자 · 돌림자)">
            <div className="grid gap-4 sm:grid-cols-2">
              <Field label="꼭 들어갈 글자" htmlFor="include"><Input id="include" value={include} onChange={(e) => setInclude(e.target.value)} /></Field>
              <Field label="빼고 싶은 글자" htmlFor="exclude"><Input id="exclude" value={exclude} onChange={(e) => setExclude(e.target.value)} /></Field>
              <Field label="돌림자" htmlFor="fixed" hint="정해진 글자와 위치">
                <div className="flex gap-2">
                  <Input id="fixed" value={fixed} onChange={(e) => setFixed(e.target.value)} maxLength={1} className="w-20" />
                  <Chip active={fixedPos === 0} onClick={() => setFixedPos(0)}>첫 글자</Chip>
                  <Chip active={fixedPos === 1} onClick={() => setFixedPos(1)}>둘째 글자</Chip>
                </div>
              </Field>
            </div>
          </Details>
          <div className="flex justify-between">
            <Button variant="ghost" onClick={() => setStep(1)}>이전</Button>
            <Button onClick={() => setStep(3)}>다음</Button>
          </div>
        </Card>
      )}

      {step === 3 && (
        <Card className="space-y-5 p-6">
          <p className="text-lg font-semibold">이렇게 시작할게요</p>
          <dl className="grid grid-cols-[6rem_1fr] gap-y-2 text-sm">
            <dt className="text-muted-foreground">성씨</dt><dd>{surname} {surnameHanja && `(${surnameHanja})`}</dd>
            <dt className="text-muted-foreground">이름</dt><dd>{syllables === 1 ? "외자" : `${syllables}글자`} · {{ any: "한자·한글 상관없음", hanja: "한자 이름", hangul: "한글 이름" }[nameType]}</dd>
            <dt className="text-muted-foreground">느낌</dt><dd>{STYLE_OPTIONS.filter((o) => styles[o.key]).map((o) => o.label).join(", ") || "따로 없음"}</dd>
            <dt className="text-muted-foreground">예시</dt><dd>{splitList(liked).join(", ") || "없음"}</dd>
          </dl>
          {error && <Notice tone="danger" role="alert">{error}</Notice>}
          <div className="flex justify-between">
            <Button variant="ghost" onClick={() => setStep(2)}>이전</Button>
            <Button size="lg" disabled={busy} onClick={submit}>{busy ? "후보를 만드는 중…" : "이름 후보 받기"}</Button>
          </div>
        </Card>
      )}
    </div>
  );
}
