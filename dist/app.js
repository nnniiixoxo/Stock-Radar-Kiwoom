const el = (id) => document.getElementById(id);

const WORKFLOW_URL =
  "https://github.com/nnniiixoxo/Stock-Radar-Kiwoom/actions/workflows/market-screen.yml";

const fmt = (number) =>
  new Intl.NumberFormat("ko-KR").format(Number(number || 0));

function getStockCode(code) {
  const matched = String(code || "").match(/\d{6}/);
  return matched ? matched[0] : "";
}

function getNaverFinanceUrl(code) {
  const stockCode = getStockCode(code);

  if (!stockCode) {
    return "https://finance.naver.com/";
  }

  return `https://finance.naver.com/item/main.naver?code=${stockCode}`;
}

function safeValue(value, fallback = "0") {
  if (
    value === undefined ||
    value === null ||
    value === ""
  ) {
    return fallback;
  }

  return value;
}

async function load() {
  try {
    el("status").textContent = "최신 결과 확인 중";

    const response = await fetch(
      `data/results.json?t=${Date.now()}`,
      {
        cache: "no-store",
      }
    );

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }

    const data = await response.json();
    const ok = data.status === "ok";

    el("status").textContent = ok
      ? "정상 업데이트"
      : data.message || "확인 필요";

    el("status").className = ok
      ? "ok"
      : "warn";

    el("updated").textContent = data.generated_at
      ? new Date(data.generated_at).toLocaleString("ko-KR")
      : "초기 설정 전";

    const stocks = Array.isArray(data.stocks)
      ? data.stocks
      : [];

    el("count").textContent = `${stocks.length}종목`;

    if (!stocks.length) {
      el("cards").innerHTML = `
        <div class="empty">
          ${data.message || "조건 통과 종목이 없습니다."}
        </div>
      `;

      return;
    }

    el("cards").innerHTML = stocks
      .map((stock, index) => {
        const stockCode = getStockCode(stock.code);
        const stockName = stock.name || stockCode;
        const naverUrl = getNaverFinanceUrl(stock.code);

        return `
          <a
            class="card"
            href="${naverUrl}"
            target="_blank"
            rel="noopener noreferrer"
            aria-label="${stockName} 네이버 증권에서 보기"
          >
            <div class="card-top">
              <small>#${index + 1}</small>
              <span class="stock-code">${stockCode}</span>
            </div>

            <h3>${stockName}</h3>

            <div class="score">
              ${safeValue(stock.score)}점
            </div>

            <div class="row">
              <span>등락</span>
              <b>${safeValue(stock.change_pct)}%</b>
            </div>

            <div class="row">
              <span>체결량</span>
              <b>${fmt(stock.expected_volume)}</b>
            </div>

            <div class="row">
              <span>잔량비</span>
              <b>${safeValue(stock.bid_ask_ratio)}</b>
            </div>

            <div class="row">
              <span>체결강도</span>
              <b>${safeValue(stock.execution_strength)}</b>
            </div>

            <div class="naver-link">
              네이버 증권 ↗
            </div>
          </a>
        `;
      })
      .join("");
}

function openWorkflow() {
  const newWindow = window.open(
    WORKFLOW_URL,
    "_blank",
    "noopener,noreferrer"
  );

  if (!newWindow) {
    window.location.href = WORKFLOW_URL;
  }
}

el("refresh").textContent = "현재 기준 다시 계산";
el("refresh").addEventListener("click", openWorkflow);

/* 계산 화면에서 홈페이지로 돌아오면 최신 결과 확인 */
window.addEventListener("focus", () => {
  setTimeout(load, 1000);
});

/* 홈페이지를 열어둔 동안 30초마다 새 결과 확인 */
setInterval(load, 30000);

load();
