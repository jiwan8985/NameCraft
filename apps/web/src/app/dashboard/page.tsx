import { headers } from "next/headers";
import { Dashboard } from "@/components/naming/dashboard";
import { pairingCode } from "@/lib/mobile-access";

export default async function Page() {
  const host = (await headers()).get("host");
  const desktopQR = !!pairingCode() && (host === "127.0.0.1:3000" || host === "localhost:3000");
  return <Dashboard desktopQR={desktopQR} />;
}
