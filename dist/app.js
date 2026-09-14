const el=id=>document.getElementById(id);
const fmt=n=>new Intl.NumberFormat('ko-KR').format(Number(n||0));
async function load(){
  try{
    const r=await fetch(`data/results.json?t=${Date.now()}`,{cache:'no-store'}); if(!r.ok)throw new Error(`HTTP ${r.status}`);
    const d=await r.json(), ok=d.status==='ok';
    el('status').textContent=ok?'정상 업데이트':d.message||'확인 필요'; el('status').className=ok?'ok':'warn';
    el('updated').textContent=d.generated_at?new Date(d.generated_at).toLocaleString('ko-KR'):'초기 설정 전';
    const stocks=Array.isArray(d.stocks)?d.stocks:[]; el('count').textContent=`${stocks.length}종목`;
    el('cards').innerHTML=stocks.length?stocks.map((s,i)=>`<article class="card"><small>#${i+1} ${s.code}</small><h3>${s.name||s.code}</h3><div class="score">${s.score}점</div><div class="row"><span>예상 등락</span><b>${s.change_pct}%</b></div><div class="row"><span>예상 체결량</span><b>${fmt(s.expected_volume)}</b></div><div class="row"><span>매수/매도 잔량</span><b>${s.bid_ask_ratio}</b></div><div class="row"><span>체결강도</span><b>${s.execution_strength}</b></div></article>`).join(''):`<div class="empty">${d.message||'조건 통과 종목이 없습니다.'}</div>`;
  }catch(e){el('status').textContent=`데이터 로드 실패: ${e.message}`;el('status').className='warn'}
}
el('refresh').addEventListener('click',load);load();setInterval(load,60000);

