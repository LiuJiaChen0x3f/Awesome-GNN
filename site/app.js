/* Static-only client. Treat all research metadata as untrusted text. */
(() => {
  'use strict';
  const $ = id => document.getElementById(id);
  const labels = {ready:'方法卡片已生成',pending:'等待 LLM 总结',failed:'总结生成失败 · 将重试',missing_abstract:'来源未提供摘要',missing_fulltext:'方法正文未获取',insufficient:'原文信息不足'};
  let papers = [], keyword = '', limit = 30;
  const topicNames=['GNN','SSL','CL','OOD','TAG','GSL','HGT','TGN','KG','KGE','HGNN'];
  const paperDate=p=>p.display_date||p.published||'';
  const hasKeyword=(p,k)=>(p.topics||[]).includes(k)||p.keywords.includes(k);
  const venueLabel=p=>p.venue_label||(p.sources.some(s=>s.name==='arxiv')?'arXiv':(p.venue||'').match(/\b(NeurIPS|ICML|KDD|AAAI|IJCAI|ACL|CVPR|ICCV|SIGMOD|VLDB|SIGIR|WWW|ICDE|EMNLP)\b/i)?.[0]||'');
  const node = (tag, text, className) => {const e=document.createElement(tag);if(text!==undefined)e.textContent=text;if(className)e.className=className;return e;};
  const safeUrl = value => {try {const u = new URL(value);return ['http:','https:'].includes(u.protocol) ? u.href : null;}catch{return null;}};
  const readableTime = value => {const d=new Date(value);return Number.isNaN(d.getTime())?'未知':d.toLocaleString('zh-CN',{year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',hour12:false});};
  function selectKeyword(value) {keyword=keyword===value?'':value;limit=30;render();}
  function card(p) {
    const e=node('article',undefined,'card'), meta=node('div',undefined,'card-meta');
    const venue=venueLabel(p);
    if(venue) meta.append(node('span',venue,'venue-badge'));
    const rssOnly=p.sources.every(s=>s.date_basis==='rss_announcement');
    meta.append(node('time',(paperDate(p)||'日期未知')+(p.date_basis==='arxiv_first_submission'?' · 首次提交':p.date_basis==='conference_publication'?' · 正式发表':rssOnly?' · 公告日期':'')));
    meta.append(node('span',labels[p.status]||'待处理',`state-badge ${p.status==='ready'?'':'pending'}`));
    e.append(meta,node('h3',p.title),node('p',p.authors.slice(0,5).join(' · ')+(p.authors.length>5?' 等':''),'authors'));
    const method=node('div',undefined,`method ${p.status==='ready'?'':'pending'}`);
    if(p.status==='ready') {method.append(node('span','核心方法 / METHOD','method-label'),node('span',p.method));}
    else {method.textContent=p.status==='missing_abstract'?'该来源未提供摘要，暂不生成方法卡片。':p.status==='missing_fulltext'?'暂未取得可核验的方法章节。':p.status==='insufficient'?'原文不足以支持可靠的方法描述，暂不展示推测内容。':p.status==='failed'?'模型请求或输出校验未通过，下次运行会自动重试。':'论文已收录；取得正文后将生成五个关键词与方法总结。';}
    const bottom=node('div',undefined,'card-bottom'), tags=node('div',undefined,'card-tags');
    p.keywords.forEach(k=>{const b=node('button',k,'chip'+(keyword===k?' active':''));b.setAttribute('aria-pressed',String(keyword===k));b.onclick=()=>selectKeyword(k);tags.append(b);});
    bottom.append(tags);
    const pdf=safeUrl(p.pdf_url)||p.sources.map(s=>s.name==='arxiv'&&s.id?`https://arxiv.org/pdf/${encodeURIComponent(s.id)}.pdf`:null).map(s=>safeUrl(s)).find(Boolean);
    const url=pdf||p.sources.map(s=>safeUrl(s.url)).find(Boolean);
    if(url){const a=node('a',pdf?'下载 PDF ↗':'打开论文页面 ↗','paper-link');a.href=url;a.target='_blank';a.rel='noopener noreferrer';bottom.append(a);}
    e.append(method,bottom);return e;
  }
  function render() {
    const q=$('search').value.trim().toLocaleLowerCase(), source=$('source').value, days=Number($('period').value), status=$('status').value;
    const cutoff=new Date();cutoff.setUTCDate(cutoff.getUTCDate()-days+1);const since=cutoff.toISOString().slice(0,10);
    let filtered=papers.filter(p=>(!q||[p.title,p.method,venueLabel(p),...(p.topics||[]),...p.keywords,...p.authors].join(' ').toLocaleLowerCase().includes(q))&&(!source||p.sources.some(s=>s.name===source))&&(!days||paperDate(p)>=since)&&(!keyword||hasKeyword(p,keyword))&&(!status||(status==='ready'?p.status==='ready':p.status!=='ready')));
    filtered.sort((a,b)=>$('sort').value==='ccf'?((b.ccf_venue?1:0)-(a.ccf_venue?1:0))||paperDate(b).localeCompare(paperDate(a)):$('sort').value==='title'?a.title.localeCompare(b.title):$('sort').value==='oldest'?paperDate(a).localeCompare(paperDate(b)):paperDate(b).localeCompare(paperDate(a)));
    $('result-count').textContent=`${filtered.length} 篇`;
    $('papers').replaceChildren(...filtered.slice(0,limit).map(card));
    if(!filtered.length)$('papers').append(node('div','没有符合筛选条件的论文。试试其他关键词或重置筛选。','empty'));
    $('load-more').hidden=filtered.length<=limit;
    $('active-tags').replaceChildren();
    if(keyword){const b=node('button',`${keyword} ×`,'active-filter');b.onclick=()=>selectKeyword(keyword);$('active-tags').append(b);}
    document.querySelectorAll('.keyword-cloud button').forEach(b=>{const active=b.dataset.keyword===keyword;b.classList.toggle('active',active);b.setAttribute('aria-pressed',String(active));});
  }
  for(const id of ['search','source','period','status','sort'])$(id).addEventListener(id==='search'?'input':'change',()=>{limit=30;render();});
  $('reset').onclick=()=>{['search','source','period','status'].forEach(id=>$(id).value='');$('sort').value='newest';keyword='';limit=30;render();};
  $('load-more').onclick=()=>{limit+=30;render();};
  document.addEventListener('keydown',e=>{if(e.key==='/'&&!['INPUT','TEXTAREA','SELECT'].includes(document.activeElement.tagName)){e.preventDefault();$('search').focus();}});
  fetch('./data/papers.json',{cache:'no-cache'}).then(r=>{if(!r.ok)throw new Error('fetch');return r.json();}).then(data=>{
    if(data.schema_version!==1||!Array.isArray(data.papers))throw new Error('schema');
    papers=data.papers;
    const ccfOption=node('option','会议优先');ccfOption.value='ccf';$('sort').append(ccfOption);$('sort').value='newest';
    $('total').textContent=papers.length.toLocaleString();$('ready').textContent=papers.filter(p=>p.status==='ready').length.toLocaleString();
    const sources=[...new Set(papers.flatMap(p=>p.sources.map(s=>s.name)))].sort();$('source-count').textContent=sources.length;
    sources.forEach(s=>{const o=node('option',s);o.value=s;$('source').append(o);});
    $('updated').textContent=data.generated_at?`最近运行 ${readableTime(data.generated_at)} · 本地时间`:'尚未运行采集';
    const counts=new Map(topicNames.map(k=>[k,papers.filter(p=>hasKeyword(p,k)).length]));
    [...counts].forEach(([k,n])=>{const b=node('button',k);b.dataset.keyword=k;b.append(node('span',n,'count'));b.onclick=()=>selectKeyword(k);$('keyword-cloud').append(b);});
    if(!counts.size)$('keyword-cloud').append(node('span','方法卡片生成后，关键词将在这里出现。','about-note'));
    const report=data.report||{}, notices=[];
    if(!report.llm_enabled)notices.push('采集预览模式：尚未连接 LLM。当前展示真实论文元数据，关键词与方法总结等待生成。');
    if(report.error)notices.push('最近一次采集未成功，当前展示已保存的数据。');
    if(report.mode==='responses_web_search')notices.push(`本次联网搜索返回 ${report.returned||0}/${report.requested||0} 篇经核验的论文。页面保留历史归档；旧记录未按新规则重新核验。`);
    if(report.quota_progress){const q=report.quota_progress;notices.push(`本次来源配额：会议 ${q.conference.returned}/${q.conference.requested} 篇；arXiv ${q.arxiv.returned}/${q.arxiv.requested} 篇。每篇仅计入一组，缺额不跨组补齐。`);}
    const partial=Object.entries(report.sources||{}).filter(([,s])=>!s.ok||s.warning||s.truncated||s.failed_feeds);
    if(partial.length)notices.push('采集范围提示：'+partial.map(([name,s])=>`${name} ${!s.ok?'请求失败':s.mode==='responses'&&s.truncated?'预算内未补齐目标':s.mode==='rss_fallback'?'仅含最新 RSS 公告':s.truncated?'达到抓取上限':'部分来源不可用'}`).join('；')+'。本列表不代表全网完整收录。');
    notices.forEach(s=>$('notices').append(node('div',s,'notice')));
    render();
  }).catch(()=>{$('updated').textContent='索引读取失败';$('papers').replaceChildren(node('div','无法加载论文数据。请通过本地 HTTP 服务或 GitHub Pages 打开页面，并确认 data/papers.json 已生成。','empty'));});
})();
