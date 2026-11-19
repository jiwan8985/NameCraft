import { Suspense } from "react";
import { ReportPrint } from "@/components/reports/report-print";

export default function Page() {
  return <Suspense fallback={<p className="text-sm">불러오는 중…</p>}><ReportPrint /></Suspense>;
}
