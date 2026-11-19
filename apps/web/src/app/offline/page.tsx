export default function Offline() {
  return (
    <div className="mx-auto max-w-md space-y-2 py-10 text-center">
      <h1 className="text-xl font-semibold">오프라인 상태입니다</h1>
      <p className="text-sm text-muted-foreground">
        NameCraft AI 는 이 기기의 로컬 서버(127.0.0.1)와 연결되어야 데이터를 볼 수 있습니다. 서버를 실행한 뒤 다시 열어 주세요.
        개인정보 보호를 위해 이름·출생정보 데이터는 브라우저에 저장해 두지 않습니다.
      </p>
    </div>
  );
}
