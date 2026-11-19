import { redirect } from "next/navigation";

/** 설정 화면은 없앴다 — AI 연결은 이름 짓기 화면에서 바로 고른다. 예전 주소로 오면 홈으로. */
export default function SettingsPage() {
  redirect("/dashboard");
}
