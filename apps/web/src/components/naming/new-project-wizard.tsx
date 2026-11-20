"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { Baby, Loader2, Sparkles } from "lucide-react";
import { AIPicker, AI_NAME, useLocalAI, type NamingMethod } from "@/components/ai-picker";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Chip, Details, Field, Input, Notice, Select, splitList } from "@/components/ui/form";
import { postJson } from "@/lib/api";
import type { Project } from "@/lib/types";

const STYLE_OPTIONS = [
  { key: "modern", label: "요즘 느낌" },
  { key: "soft", label: "부드러운" },
  { key: "bright", label: "밝은" },
  { key: "traditional", label: "단정한" },
] as const;
export function NewProjectWizard() {
  const router = useRouter();
  const [surname, setSurname] = useState("");
  const [surnameHanja, setSurnameHanja] = useState("");
  const [sex, setSex] = useState<"m" | "f" | "n">("n");
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
  const [birth, setBirth] = useState({ kind: "expected", calendar: "solar", date: "", time: "", is_leap_month: false });
  const updateBirth = (data: Partial<typeof birth>) => setBirth((current) => ({ ...current, ...data }));
  const [choice, setProvider] = useState<NamingMethod | null>(null);
  const localAvailable = useLocalAI();
  const who = choice ?? (localAvailable ? "ollama" : "none");
  const validSurname = /^[가-힣]{1,4}$/.test(surname.trim());
  const validFixed = !fixed.trim() || /^[가-힣]$/.test(fixed.trim());
  const needsBirthDate = !!birth.time && !birth.date;
  const canSubmit = validSurname && validFixed && !needsBirthDate && (choice !== null || localAvailable !== null);

  async function submit() {
    if (!canSubmit || busy) return;
    setBusy(true);
    setError(null);
    const constraints: Record<string, unknown> = { include_syllables: splitList(include), exclude_syllables: splitList(exclude) };
    if (fixed.trim()) constraints.fixed_syllable = { [fixedPos]: fixed.trim() };
    const created = await postJson<Project>("projects", {
      surname_hangul: surname.trim(), surname_hanja: surnameHanja.trim() || null, sex,
      preferences: { syllables, name_type: nameType, style_tags: styles, liked_examples: splitList(liked), count: 20, use_traditional: true },
      constraints,
      ...(birth.date ? { birth: { ...birth, time: birth.time || null, is_leap_month: birth.calendar === "lunar" && birth.is_leap_month } } : {}),
    });
    if (!created.ok) {
      setBusy(false);
      return setError(created.error.message);
    }
    const destination = `/projects/${created.data.id}/recommendations`;
    const query = new URLSearchParams();
    if (birth.date) query.set("sort", "saju");
    const result = await postJson<{ provider_used: string }>(`projects/${created.data.id}/candidates/generate`, {
      provider: who, ...(who === "ollama" ? { local_only: true, count: 5 } : {}),
    });
    if (!result.ok) query.set("note", "ai_error");
    else if (who === "ollama" && result.data.provider_used !== "ollama") query.set("note", "ai_fallback");
    router.push(query.size ? `${destination}?${query}` : destination);
  }

  if (busy) {
    return (
      <Card className="mx-auto flex max-w-md flex-col items-center gap-4 py-12 text-center" aria-live="polite">
        <span className="grid h-16 w-16 place-items-center rounded-full bg-primary-soft text-primary"><Loader2 className="h-7 w-7 animate-spin" /></span>
        <div>
          <p className="text-lg font-semibold">이름을 고르고 있어요</p>
          <p className="mt-1 text-sm text-muted-foreground">잠시만요</p>
        </div>
      </Card>
    );
  }

  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <Card className="space-y-7 p-6 sm:p-8">
        <div className="flex items-center gap-3">
          <span className="grid h-11 w-11 place-items-center rounded-2xl bg-primary-soft text-primary"><Baby className="h-5 w-5" /></span>
          <div>
            <h1 className="text-xl font-semibold">우리 아기 이름 짓기</h1>
            <p className="text-sm text-muted-foreground">성을 입력하고 이름을 받아보세요. 성별과 출생정보는 아는 만큼만 입력하면 돼요.</p>
          </div>
        </div>
        <Field label="성" htmlFor="surname">
          <Input id="surname" aria-invalid={!!surname && !validSurname} value={surname} onChange={(e) => setSurname(e.target.value)} maxLength={4} placeholder="예: 김" className="max-w-[10rem] text-lg" />
        </Field>
        {!!surname && !validSurname && <Notice tone="warn">성을 한글로 입력해 주세요.</Notice>}
        <fieldset className="space-y-2">
          <legend className="text-sm font-medium">아기 성별</legend>
          <div className="flex flex-wrap gap-2">
            {([["f", "여자 아기"], ["m", "남자 아기"], ["n", "아직 몰라요"]] as const).map(([value, label]) => (
              <label key={value} className="flex min-h-11 cursor-pointer items-center gap-2 rounded-full border border-border bg-card px-3.5 text-sm has-checked:border-primary has-checked:bg-primary-soft has-checked:text-primary">
                <input type="radio" name="baby-sex" value={value} checked={sex === value}
                       onChange={() => setSex(value)} className="size-4 accent-primary" />
                {label}
              </label>
            ))}
          </div>
        </fieldset>
        <Details summary="사주 반영하기 · 선택">
          <div className="space-y-3">
            <p className="text-sm text-muted-foreground">예정일이나 출생일을 입력하면 사주를 계산해 한자 이름 후보 평가에 참고해요. 시각은 모르면 비워 두세요.</p>
            <div className="grid gap-3 sm:grid-cols-2">
              <Field label="출생 구분" htmlFor="wizard-birth-kind">
                <Select id="wizard-birth-kind" value={birth.kind} onChange={(e) => updateBirth({ kind: e.target.value })}>
                  <option value="expected">출산 예정</option><option value="actual">출생 완료</option>
                </Select>
              </Field>
              <Field label="달력" htmlFor="wizard-birth-calendar">
                <Select id="wizard-birth-calendar" value={birth.calendar} onChange={(e) => updateBirth({ calendar: e.target.value })}>
                  <option value="solar">양력</option><option value="lunar">음력</option>
                </Select>
              </Field>
              <Field label={birth.kind === "expected" ? "출산 예정일" : "출생일"} htmlFor="wizard-birth-date">
                <Input id="wizard-birth-date" type="date" value={birth.date} onChange={(e) => updateBirth({ date: e.target.value })} />
              </Field>
              <Field label={birth.kind === "expected" ? "예상 출생 시각 (선택)" : "출생 시각 (선택)"} htmlFor="wizard-birth-time">
                <Input id="wizard-birth-time" type="time" value={birth.time} onChange={(e) => updateBirth({ time: e.target.value })} />
              </Field>
              {birth.calendar === "lunar" && <label className="flex items-center gap-2 text-sm">
                <input type="checkbox" checked={birth.is_leap_month} onChange={(e) => updateBirth({ is_leap_month: e.target.checked })} /> 윤달
              </label>}
            </div>
          </div>
        </Details>
        <Details summary="이름 조건 더 설정하기">
          <div className="space-y-5">
            <div className="space-y-2">
              <p className="text-sm font-medium">이름 글자 수 <span className="font-normal text-muted-foreground">(성 빼고)</span></p>
              <div className="flex flex-wrap gap-2">
                {[2, 1, 3].map((n) => <Chip key={n} active={syllables === n} onClick={() => { setSyllables(n); if (fixedPos >= n) setFixedPos(0); }}>{n === 1 ? "한 글자" : `${n}글자`}</Chip>)}
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
                  <div className="flex flex-wrap gap-2">
                    <Input id="fixed" aria-invalid={!validFixed} value={fixed} onChange={(e) => setFixed(e.target.value)} maxLength={1} className="w-20" />
                    {["첫 글자", "둘째 글자", "셋째 글자"].slice(0, syllables).map((label, index) => (
                      <Chip key={label} active={fixedPos === index} onClick={() => setFixedPos(index)}>{label}</Chip>
                    ))}
                  </div>
                </Field>
              </div>
            </Details>
          </div>
        </Details>
        {needsBirthDate && <Notice tone="warn">출생 시각을 반영하려면 날짜도 입력해 주세요.</Notice>}
        {!validFixed && <Notice tone="warn">돌림자는 한글 한 글자로 입력해 주세요.</Notice>}
        <Details summary={`추천 방식 · ${AI_NAME[who]}`}>
          <AIPicker value={who} onChange={setProvider} localAvailable={localAvailable} />
          <Link href="/ai/providers" className="mt-3 inline-block text-sm font-medium text-primary underline">PC에 맞는 Ollama 모델 보기</Link>
        </Details>
        {error && <Notice tone="danger" role="alert">{error}</Notice>}
        <Button size="lg" className="w-full sm:w-auto" onClick={submit} disabled={!canSubmit}>
          <Sparkles className="h-4 w-4" />
          {who === "ollama" ? "AI로 이름 받기" : "이름 받기"}
        </Button>
      </Card>
    </div>
  );
}
