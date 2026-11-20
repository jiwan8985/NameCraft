import { CSRF_HEADER } from "@/lib/proxy-guard";

// Load the pairing logic directly, without waiting for Next.js client bundles.
export function GET() {
  return new Response(`<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>NameCraft 연결</title>
  <style>
    body { margin: 0; background: #f8faf7; color: #193629; font: 1rem/1.6 system-ui, sans-serif; }
    main { max-width: 26rem; margin: 12vh auto 0; padding: 1.75rem; background: white; border: 1px solid #dbe6dd; border-radius: 1.25rem; }
    @media (max-width: 480px) { main { margin: 9vh 1rem 0; } }
    h1 { margin: 0; font-size: 1.4rem; }
    button { background: #24634c; color: white; border: 0; border-radius: .75rem; padding: .65rem 1rem; font: inherit; cursor: pointer; }
  </style>
</head>
<body>
  <main>
    <h1>NameCraft 연결</h1>
    <p id="status" role="status">휴대폰 연결을 준비하고 있어요.</p>
    <button id="retry" type="button" hidden>다시 연결</button>
    <noscript>이 링크를 Safari나 Chrome에서 열고 JavaScript를 허용해 주세요.</noscript>
  </main>
  <script>
    const statusLine = document.getElementById("status");
    const retry = document.getElementById("retry");
    const code = location.hash.slice(1);

    async function connect() {
      retry.hidden = true;
      if (!code) {
        statusLine.textContent = "연결 정보가 없어요. PC 화면의 QR을 카메라로 다시 찍어 주세요.";
        return;
      }

      statusLine.textContent = "작명 프로젝트에 연결하고 있어요.";
      const controller = new AbortController();
      const timer = setTimeout(() => controller.abort(), 8000);
      try {
        const response = await fetch("/api/mobile", {
          method: "POST",
          headers: { "Content-Type": "application/json", "${CSRF_HEADER}": "1" },
          body: JSON.stringify({ code }),
          signal: controller.signal,
        });
        if (response.status === 403) {
          statusLine.textContent = "이 QR은 만료됐거나 사용할 수 없어요. PC 화면에서 현재 QR을 다시 찍어 주세요.";
          return;
        }
        if (!response.ok) throw new Error("Connection failed");
        location.replace("/dashboard");
      } catch {
        statusLine.textContent = "응답이 없어요. PC와 같은 Wi-Fi에 연결되어 있는지 확인하고 다시 연결해 주세요.";
        retry.hidden = false;
      } finally {
        clearTimeout(timer);
      }
    }

    retry.addEventListener("click", connect);
    connect();
  </script>
</body>
</html>`, {
    headers: { "Content-Type": "text/html; charset=utf-8", "Cache-Control": "no-store" },
  });
}
