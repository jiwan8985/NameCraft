"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { Baby, Check, Loader2, Sparkles } from "lucide-react";
import { AIPicker, AI_NAME, SendNote, defaultChoice, useProviders } from "@/components/ai-picker";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Chip, Details, Field, Input, Notice, splitList } from "@/components/ui/form";
import { postJson } from "@/lib/api";
import type { Project } from "@/lib/types";

const STYLE_OPTIONS = [
  { key: "modern", label: "요즘 느낌" },
  { key: "soft", label: "부드러운" },
  { key: "bright", label: "밝은" },
  { key: "traditional", label: "단정한" },
] as const;
const STEPS = ["아기 정보", "누구와 지을까요"];

/** 2단계: 아기 정보·원하는 느낌 → 함께 지을 AI 고르고 바로 이름 받기 */
export function NewProjectWizard() {
  const router = useRouter();
  const [step, setStep] = useState(1);
  const [surname, setSurname] = useState("");
  const [surnameHanja, setSurnameHanja] = useState("");
  const [sex, setSex] = useState<"m" | "f" | "n" | null>(null);
  const [syllables, setSyllables] = useState(2);
  const [nameType, setNameType] = useState<"hanja" | "hangul" | "any">("any");
  const [styles, setStyles] = useState<Record<string, number>>({ modern: 1 });
  const [liked, setLiked] = useState("");
  const [include, setInclude] = useState("");
  const [exclude, setExclude] = useState("");
  const [fixed, setFixed] = useState("");
  const [fixedPos, setFixedPos] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const { list, reload } = useProviders();
  const [provider, setProvider] = useState<string | null>(null);
  useEffect(() => { if (list && provider === null) setProvider(defaultChoice(list)); }, [list, provider]);
  const step1Valid = /^[가-힣]{1,4}$/.test(surname.trim()) && sex !== null;
  const who = provider ?? "none";

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
    // AI 를 고른 경우: 버튼에 보낼 내용을 보여 줬으므로 그 클릭이 동의
    const g = await postJson<{ provider_used: string; fallback_reason: string | null }>(
      `projects/${created.data.id}/candidates/generate`, { provider: who, consent: who !== "none" });
    const note = g.ok && g.data.fallback_reason ? "?note=ai_fallback" : !g.ok ? "?note=ai_error" : "";
    router.push(`/projects/${created.data.id}/recommendations${note}`);
  }

  if (busy) {
    return (
      <Card className="mx-auto flex max-w-md flex-col items-center gap-4 py-12 text-center" aria-live="polite">
        <span className="grid h-16 w-16 place-items-center rounded-full bg-primary-soft text-primary"><Loader2 className="h-7 w-7 animate-spin" /></span>
        <div>
          <p className="text-lg font-semibold">{who === "none" ? "이름을 고르고 있어요" : `${AI_NAME[who]}가 아기 이름을 고르고 있어요`}</p>
          <p className="mt-1 text-sm text-muted-foreground">{who === "none" ? "잠시만요" : "보통 20~40초 걸려요. 한자 뜻과 발음도 함께 확인하고 있어요."}</p>
        </div>
      </Card>
    );
  }

  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <ol className="flex items-center gap-2 text-sm" aria-label="입력 단계">
        {STEPS.map((t, i) => (
          <li key={t} aria-current={step === i + 1 ? "step" : undefined} className="flex items-center gap-2">
            <span className={`grid h-7 w-7 place-items-center rounded-full text-xs font-semibold ${step > i + 1 ? "bg-primary text-primary-foreground" : step === i + 1 ? "bg-primary-soft text-primary ring-2 ring-primary" : "bg-muted text-muted-foreground"}`}>
              {step > i + 1 ? <Check className="h-3.5 w-3.5" /> : i + 1}
            </span>
            <span className={step === i + 1 ? "font-medium" : "text-muted-foreground"}>{t}</span>
            {i < STEPS.length - 1 && <span className="mx-1 h-px w-8 bg-border" aria-hidden="true" />}
          </li>
        ))}
      </ol>

      {step === 1 && (
        <Card className="space-y-7 p-6 sm:p-8">
          <div className="flex items-center gap-3">
            <span className="grid h-11 w-11 place-items-center rounded-2xl bg-primary-soft text-primary"><Baby className="h-5 w-5" /></span>
            <div>
              <p className="text-lg font-semibold">우리 아기 이름 짓기</p>
              <p className="text-sm text-muted-foreground">몇 가지만 알려 주세요.</p>
            </div>
          </div>
          <Field label="성" htmlFor="surname">
            <Input id="surname" value={surname} onChange={(e) => setSurname(e.target.value)} maxLength={4} placeholder="예: 심" className="max-w-[10rem] text-lg" />
          </Field>
          <div className="space-y-2">
            <p className="text-sm font-medium">아기는</p>
            <div className="flex flex-wrap gap-2">
              {([["f", "여자 아기"], ["m", "남자 아기"], ["n", "아직 몰라요"]] as const).map(([v, l]) => <Chip key={v} active={sex === v} onClick={() => setSex(v)}>{l}</Chip>)}
            </div>
          </div>
          <div className="space-y-2">
            <p className="text-sm font-medium">이름 글자 수 <span className="font-normal text-muted-foreground">(성 빼고)</span></p>
            <div className="flex flex-wrap gap-2">
              {[2, 1, 3].map((n) => <Chip key={n} active={syllables === n} onClick={() => setSyllables(n)}>{n === 1 ? "한 글자" : `${n}글자`}</Chip>)}
            </div>
          </div>
          <fieldset className="space-y-2">
            <legend className="text-sm font-medium">원하는 느낌 <span className="font-normal text-muted-foreground">(여러 개)</span></legend>
            <div className="flex flex-wrap gap-2">
              {STYLE_OPTIONS.map((o) => <Chip key={o.key} active={!!styles[o.key]} onClick={() => setStyles((s) => ({ ...s, [o.key]: s[o.key] ? 0 : 1 }))}>{o.label}</Chip>)}
            </div>
          </fieldset>
          <div className="space-y-2">
            <p className="text-sm font-medium">이름 종류</p>
            <div className="flex flex-wrap gap-2">
              {([["any", "상관없음"], ["hanja", "한자 이름"], ["hangul", "순우리말 이름"]] as const).map(([v, l]) => <Chip key={v} active={nameType === v} onClick={() => setNameType(v)}>{l}</Chip>)}
            </div>
          </div>
          <Details summary="더 자세히 (좋아하는 이름 · 돌림자 · 성 한자)">
            <div className="grid gap-4 sm:grid-cols-2">
              <Field label="마음에 드는 이름" htmlFor="liked" hint="쉼표로 구분 — 비슷한 느낌으로 찾아 드려요">
                <Input id="liked" value={liked} onChange={(e) => setLiked(e.target.value)} placeholder="예: 서아, 하준" />
              </Field>
              <Field label="성 한자" htmlFor="surname-hanja" hint="넣으면 획수·수리 분석도 해 드려요. 예: 沈">
                <Input id="surname-hanja" value={surnameHanja} onChange={(e) => setSurnameHanja(e.target.value)} maxLength={4} />
              </Field>
              <Field label="꼭 들어갈 글자" htmlFor="include"><Input id="include" value={include} onChange={(e) => setInclude(e.target.value)} /></Field>
              <Field label="빼고 싶은 글자" htmlFor="exclude"><Input id="exclude" value={exclude} onChange={(e) => setExclude(e.target.value)} /></Field>
              <Field label="돌림자" htmlFor="fixed" hint="집안에서 정해진 글자와 위치">
                <div className="flex gap-2">
                  <Input id="fixed" value={fixed} onChange={(e) => setFixed(e.target.value)} maxLength={1} className="w-20" />
                  <Chip active={fixedPos === 0} onClick={() => setFixedPos(0)}>첫 글자</Chip>
                  <Chip active={fixedPos === 1} onClick={() => setFixedPos(1)}>둘째 글자</Chip>
                </div>
              </Field>
            </div>
          </Details>
          <div className="flex justify-end"><Button size="lg" disabled={!step1Valid} onClick={() => setStep(2)}>다음</Button></div>
        </Card>
      )}

      {step === 2 && (
        <Card className="space-y-6 p-6 sm:p-8">
          <div>
            <p className="text-lg font-semibold">누구와 함께 지을까요?</p>
            <p className="text-sm text-muted-foreground">AI 가 요즘 이름 흐름과 한자 뜻까지 생각해서 골라 줘요. 나중에 다른 쪽으로 더 받을 수도 있어요.</p>
          </div>
          <AIPicker value={who} onChange={setProvider} list={list} reload={reload} />
          <SendNote provider={who} />
          {error && <Notice tone="danger" role="alert">{error}</Notice>}
          <div className="flex justify-between">
            <Button variant="ghost" onClick={() => setStep(1)}>이전</Button>
            <Button size="lg" onClick={submit}><Sparkles className="h-4 w-4" />{who === "none" ? "이름 받기" : `${AI_NAME[who]}에게 이름 받기`}</Button>
          </div>
        </Card>
      )}
    </div>
  );
}
