const el = (id) => document.getElementById(id);

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

async function load() {
  try {
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

    if (stocks.length) {
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
              <small>
                #${index + 1} ${stockCode}
              </small>

              <h3>${stockName}</h3>

              <div class="score">
                ${stock.score}점
              </div>

              <div class="row">
                <span>예상 등락</span>
                <b>${stock.change_pct}%</b>
              </div>

              <div class="row">
                <span>예상 체결량</span>
                <b>${fmt(stock.expected_volume)}</b>
              </div>

              <div class="row">
                <span>매수/매도 잔량</span>
                <b>${stock.bid_ask_ratio}</b>
              </div>

              <div class="row">
                <span>체결강도</span>
                <b>${stock.execution_strength}</b>
              </div>

              <div class="naver-link">
                네이버 증권에서 보기 ↗
              </div>
            </a>
          `;
        })
        .join("");
    } else {
      el("cards").innerHTML = `
        <div class="empty">
          ${data.message || "조건 통과 종목이 없습니다."}
        </div>
      `;
    }
  } catch (error) {
    el("status").textContent =
      `데이터 로드 실패: ${error.message}`;

    el("status").className = "warn";
  }
}

el("refresh").addEventListener("click", load);

load();

setInterval(load, 60000);
