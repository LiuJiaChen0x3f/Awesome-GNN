/* Static-only client. Treat all research metadata as untrusted text. */
(() => {
  'use strict';
  const $ = id => document.getElementById(id);
  const labels = {pending:'等待 LLM 总结',failed:'总结生成失败 · 将重试',missing_abstract:'全文未获取',missing_fulltext:'全文未获取',insufficient:'原文信息不足'};
  let papers = [], keyword = '', limit = 30;
  const topicNames=['TAG','OOD'];
  const paperTopics=p=>(p.topics||[]).filter(t=>topicNames.includes(t));
  const paperDate=p=>p.display_date||p.published||'';
  const hasKeyword=(p,k)=>paperTopics(p).includes(k);
  const venueLabel=p=>p.venue_label||(p.sources.some(s=>s.name==='arxiv')?'arXiv':(p.venue||'').match(/\b(NeurIPS|ICML|KDD|AAAI|IJCAI|ACL|CVPR|ICCV|SIGMOD|VLDB|SIGIR|WWW|ICDE|EMNLP)\b/i)?.[0]||'');
  const node = (tag, text, className) => {const e=document.createElement(tag);if(text!==undefined)e.textContent=text;if(className)e.className=className;return e;};
  const safeUrl = value => {try {const u = new URL(value);return ['http:','https:'].includes(u.protocol) ? u.href : null;}catch{return null;}};
  const readableTime = value => {const d=new Date(value);return Number.isNaN(d.getTime())?'未知':d.toLocaleString('zh-CN',{year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',hour12:false});};
  function selectKeyword(value) {keyword=keyword===value?'':value;limit=30;render();}
  function card(p) {
    const e=node('article',undefined,'card'), meta=node('div',undefined,'card-meta');
    const venue=venueLabel(p);
    const isConference=p.sources.some(s=>s.name==='conference');
    if(isConference) {
      const year=p.conference_year||paperDate(p).match(/^\d{4}/)?.[0];
      meta.append(node('span',[year,venue].filter(Boolean).join(' '),'venue-badge'));
    } else {
      if(venue) meta.append(node('span',venue,'venue-badge'));
      meta.append(node('time',paperDate(p)||'日期未知'));
    }
    if(p.status!=='ready') meta.append(node('span',labels[p.status]||'待处理','state-badge pending'));
    e.append(meta,node('h3',p.title),node('p',p.authors.slice(0,5).join(' · ')+(p.authors.length>5?' 等':''),'authors'));
    const method=node('div',undefined,`method ${p.status==='ready'?'':'pending'}`);
    if(p.status==='ready') {method.append(node('span','核心方法 / METHOD','method-label'),MethodMarkdown.render(document,p.method));}
    else {method.textContent=(p.status==='missing_abstract'||p.status==='missing_fulltext')?'暂未取得可核验的论文全文。':p.status==='insufficient'?'全文不足以支持可靠的方法描述，暂不展示推测内容。':p.status==='failed'?'模型请求或输出校验未通过，下次运行会自动重试。':'论文已收录；取得全文后将生成关键词与方法总结。';}
    const bottom=node('div',undefined,'card-bottom'), tags=node('div',undefined,'card-tags');
    paperTopics(p).forEach(k=>{const b=node('button',k,'chip'+(keyword===k?' active':''));b.setAttribute('aria-pressed',String(keyword===k));b.onclick=()=>selectKeyword(k);tags.append(b);});
    bottom.append(tags);
    const pdf=safeUrl(p.pdf_url)||p.sources.map(s=>s.name==='arxiv'&&s.id?`https://arxiv.org/pdf/${encodeURIComponent(s.id)}.pdf`:null).map(s=>safeUrl(s)).find(Boolean);
    const url=pdf||p.sources.map(s=>safeUrl(s.url)).find(Boolean);
    if(url){const a=node('a',pdf?'下载 PDF ↗':'打开论文页面 ↗','paper-link');a.href=url;a.target='_blank';a.rel='noopener noreferrer';bottom.append(a);}
    e.append(method,bottom);return e;
  }
  function render() {
    const q=$('search').value.trim().toLocaleLowerCase(), source=$('source').value, days=Number($('period').value);
    const cutoff=new Date();cutoff.setUTCDate(cutoff.getUTCDate()-days+1);const since=cutoff.toISOString().slice(0,10);
    let filtered=papers.filter(p=>(!q||[p.title,p.method,venueLabel(p),String(p.conference_year||''),...(p.topics||[]),...p.keywords,...p.authors].join(' ').toLocaleLowerCase().includes(q))&&(!source||p.sources.some(s=>s.name===source))&&(!days||paperDate(p)>=since)&&(!keyword||hasKeyword(p,keyword)));
    filtered.sort((a,b)=>$('sort').value==='ccf'?((b.ccf_venue?1:0)-(a.ccf_venue?1:0))||paperDate(b).localeCompare(paperDate(a)):$('sort').value==='title'?a.title.localeCompare(b.title):$('sort').value==='oldest'?paperDate(a).localeCompare(paperDate(b)):paperDate(b).localeCompare(paperDate(a)));
    $('result-count').textContent=`${filtered.length} 篇`;
    $('papers').replaceChildren(...filtered.slice(0,limit).map(card));
    if(!filtered.length)$('papers').append(node('div','没有符合筛选条件的论文。试试其他关键词或重置筛选。','empty'));
    $('load-more').hidden=filtered.length<=limit;
    $('active-tags').replaceChildren();
    if(keyword){const b=node('button',`${keyword} ×`,'active-filter');b.onclick=()=>selectKeyword(keyword);$('active-tags').append(b);}
    document.querySelectorAll('.keyword-cloud button').forEach(b=>{const active=b.dataset.keyword===keyword;b.classList.toggle('active',active);b.setAttribute('aria-pressed',String(active));});
  }
  for(const id of ['search','source','period','sort'])$(id).addEventListener(id==='search'?'input':'change',()=>{limit=30;render();});
  $('reset').onclick=()=>{['search','source','period'].forEach(id=>$(id).value='');$('sort').value='newest';keyword='';limit=30;render();};
  $('load-more').onclick=()=>{limit+=30;render();};
  document.addEventListener('keydown',e=>{if(e.key==='/'&&!['INPUT','TEXTAREA','SELECT'].includes(document.activeElement.tagName)){e.preventDefault();$('search').focus();}});
  fetch('./data/papers.json',{cache:'no-cache'}).then(r=>{if(!r.ok)throw new Error('fetch');return r.json();}).then(data=>{
    if(data.schema_version!==1||!Array.isArray(data.papers))throw new Error('schema');
    papers=data.papers.filter(p=>paperTopics(p).length);
    const ccfOption=node('option','会议优先');ccfOption.value='ccf';$('sort').append(ccfOption);$('sort').value='newest';
    $('total').textContent=papers.length.toLocaleString();
    const sources=[...new Set(papers.flatMap(p=>p.sources.map(s=>s.name)))].sort();
    sources.forEach(s=>{const o=node('option',s);o.value=s;$('source').append(o);});
    $('updated').textContent=data.generated_at?`最新更新时间：${readableTime(data.generated_at)}`:'尚未运行采集';
    const counts=new Map(topicNames.map(k=>[k,papers.filter(p=>hasKeyword(p,k)).length]));
    [...counts].forEach(([k,n])=>{const b=node('button',k);b.dataset.keyword=k;b.append(node('span',n,'count'));b.onclick=()=>selectKeyword(k);$('keyword-cloud').append(b);});
    const report=data.report||{}, notices=[];
    if(!report.llm_enabled)notices.push('采集预览模式：尚未连接 LLM。当前展示真实论文元数据，关键词与方法总结等待生成。');
    if(report.error)notices.push('最近一次采集未成功，当前展示已保存的数据。');
    const partial=report.in_progress?[]:Object.entries(report.sources||{}).filter(([,s])=>!s.ok||s.warning||s.truncated||s.failed_feeds);
    if(partial.length)notices.push('采集范围提示：'+partial.map(([name,s])=>`${name} ${!s.ok?'请求失败':['responses','responses_web_search','function_tool','venue_year_sweep'].includes(s.mode)&&s.truncated?'本轮未补齐目标':s.mode==='rss_fallback'?'仅含最新 RSS 公告':s.truncated?'达到抓取上限':'部分来源不可用'}`).join('；')+'。本列表不代表全网完整收录。');
    notices.forEach(s=>$('notices').append(node('div',s,'notice')));
    render();
  }).catch(()=>{$('updated').textContent='索引读取失败';$('papers').replaceChildren(node('div','无法加载论文数据。请通过本地 HTTP 服务或 GitHub Pages 打开页面，并确认 data/papers.json 已生成。','empty'));});
})();
