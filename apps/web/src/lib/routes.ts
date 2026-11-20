/** 화면 IA (기획서 §15). phase = 실제 기능이 구현될 Phase. */
export type RouteDef = {
  path: string;
  title: string;
  summary: string;
  phase: number;
  group: "naming" | "decision" | "data" | "ai" | "system";
  nav?: boolean;
};

export const ROUTES: RouteDef[] = [
  { path: "/dashboard", title: "대시보드", summary: "최근 프로젝트·즐겨찾기·기록", phase: 8, group: "naming", nav: true },
  { path: "/projects/new", title: "새 작명 프로젝트", summary: "기본 3단계 입력·고급 입력", phase: 8, group: "naming", nav: true },
  { path: "/projects/[id]/recommendations", title: "추천 후보", summary: "카드 추천·필터·정렬·근거·AI 재생성", phase: 8, group: "naming" },
  { path: "/names/analyze", title: "이름 분석", summary: "직접 이름 입력 및 한자 역검색", phase: 8, group: "naming", nav: true },
  { path: "/names/[id]", title: "이름 상세", summary: "한자·사주·수리·발음·출처", phase: 8, group: "naming" },
  { path: "/compare", title: "후보 비교", summary: "2~10개 이상 후보 비교·레이더 차트", phase: 8, group: "decision", nav: true },
  { path: "/scenario", title: "시나리오", summary: "예정일/시간 분기 비교·안정성", phase: 9, group: "decision", nav: true },
  { path: "/tournament", title: "토너먼트", summary: "이름 1:1 선호 토너먼트", phase: 9, group: "decision" },
  { path: "/family", title: "가족 평가", summary: "부모 공동 평가·선호 교집합", phase: 9, group: "decision" },
  { path: "/finalize", title: "최종 결정", summary: "3~5개 결선·출생신고 점검", phase: 9, group: "decision" },
  { path: "/imports", title: "자료 가져오기", summary: "외부 작명소 자료 가져오기·교차검증", phase: 10, group: "data", nav: true },
  { path: "/reports", title: "보고서", summary: "PDF/CSV/JSON 내보내기", phase: 11, group: "data", nav: true },
  { path: "/ai/providers", title: "AI 연결", summary: "Ollama 연결 상태·지원 기능·모델", phase: 7, group: "ai", nav: true },
  { path: "/ai/usage", title: "AI 사용량", summary: "로컬 Ollama 요청 수·응답 시간·토큰", phase: 11, group: "ai", nav: true },
  { path: "/ai/sessions", title: "AI 요청 기록", summary: "추천에 사용한 모델과 처리 결과를 확인해요.", phase: 11, group: "ai", nav: true },
  { path: "/ai/analytics", title: "모델별 사용 분석", summary: "요청 추이와 응답 시간, 모델별 사용 비중을 확인해요.", phase: 11, group: "ai", nav: true },
  { path: "/ai/settings", title: "AI 설정", summary: "로컬 요청 기록과 보존 기간", phase: 11, group: "ai", nav: true },
  { path: "/settings", title: "설정", summary: "학파·가중치·AI·백업·개인정보", phase: 8, group: "system", nav: true },
  { path: "/admin/data", title: "데이터 관리", summary: "데이터 검증·출처·버전(관리자 전용)", phase: 2, group: "system", nav: true },
];

export const GROUP_LABELS: Record<RouteDef["group"], string> = {
  naming: "작명",
  decision: "결정",
  data: "자료",
  ai: "AI",
  system: "시스템",
};

export function routeByPath(path: string): RouteDef {
  const r = ROUTES.find((x) => x.path === path);
  if (!r) throw new Error(`unknown route ${path}`);
  return r;
}
