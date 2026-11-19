"use client";

import { Button } from "@/components/ui/button";

export type ConsentPreview = {
  provider_id: string;
  external: boolean;
  fields: { key: string; label: string; value: unknown }[];
  not_sent: string[];
  prompt_version: string;
};

/** 외부 AI 전송 전 동의 (기획서 §29.2: 보내는 필드를 미리 보여주고 명시적 동의) */
export function ConsentDialog({ preview, onConfirm, onCancel }: { preview: ConsentPreview; onConfirm: () => void; onCancel: () => void }) {
  return (
    <div role="dialog" aria-modal="true" aria-labelledby="consent-title" className="fixed inset-0 z-50 grid place-items-center bg-black/40 p-4">
      <div className="w-full max-w-lg space-y-3 rounded-lg border border-border bg-card p-5 shadow-lg">
        <h2 id="consent-title" className="text-lg font-semibold">외부 AI로 보낼 내용 확인</h2>
        <p className="text-sm text-muted-foreground">
          <b>{preview.provider_id}</b> 에 아래 항목만 보냅니다. 보유한 구독 계정의 사용 한도가 소모될 수 있습니다.
        </p>
        <table className="w-full text-sm">
          <tbody>
            {preview.fields.map((f) => (
              <tr key={f.key} className="border-t border-border">
                <th scope="row" className="py-1 pr-2 text-left font-normal text-muted-foreground">{f.label}</th>
                <td className="py-1 break-all">{JSON.stringify(f.value)}</td>
              </tr>
            ))}
          </tbody>
        </table>
        <p className="text-xs text-muted-foreground">보내지 않는 정보: {preview.not_sent.join(", ")}</p>
        <div className="flex justify-end gap-2">
          <Button variant="outline" onClick={onCancel}>취소</Button>
          <Button onClick={onConfirm}>동의하고 보내기</Button>
        </div>
      </div>
    </div>
  );
}
