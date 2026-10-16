async function renderSagaMermaid(loader=()=>import('https://cdn.jsdelivr.net/npm/mermaid@11.12.0/dist/mermaid.esm.min.mjs')){
  const {default:mermaid}=await loader();
  mermaid.initialize({startOnLoad:false,securityLevel:'strict',theme:'neutral'});
  await mermaid.run({querySelector:'.mermaid'});
}
document.addEventListener('DOMContentLoaded',()=>{
  // Reuse the actual localized column headings for narrow-screen cards.
  // Native headers remain available to assistive technology, with explicit
  // roles preserving table semantics when CSS changes the display layout.
  document.querySelectorAll('.body table').forEach(table=>{
    const headers=[...table.querySelectorAll('thead tr:first-child th')];
    if(headers.length<3 || table.closest('.infobox'))return;
    table.classList.add('saga-responsive-table');table.setAttribute('role','table');
    table.tHead.setAttribute('role','rowgroup');
    table.querySelectorAll('tr').forEach(row=>row.setAttribute('role','row'));
    headers.forEach(header=>{header.setAttribute('scope','col');header.setAttribute('role','columnheader');});
    [...table.tBodies].forEach(body=>{
      body.setAttribute('role','rowgroup');
      [...body.rows].forEach(row=>[...row.cells].forEach((cell,index)=>{
        cell.setAttribute('role',cell.tagName==='TH'?(cell.scope==='col'?'columnheader':'rowheader'):'cell');const header=headers[index];if(!header)return;
        const label=document.createElement('span');label.className='saga-cell-label';label.setAttribute('aria-hidden','true');
        label.lang=header.querySelector('[lang]')?.lang || header.closest('[lang]')?.lang || document.documentElement.lang;
        label.textContent=header.textContent.trim();cell.prepend(label);
      }));
    });
  });
  document.querySelectorAll('.clickmap-wrap').forEach(wrap=>{
    const tip=wrap.querySelector('.clickmap-tip'); if(!tip)return;
    const hide=()=>{tip.hidden=true;};
    wrap.querySelectorAll('a').forEach(a=>{
      const show=()=>{tip.textContent='';const name=document.createElement('strong');name.textContent=a.dataset.name||'';tip.appendChild(name);tip.appendChild(document.createTextNode(a.dataset.tip||''));tip.hidden=false;const w=wrap.getBoundingClientRect(),r=a.getBoundingClientRect();tip.style.left=Math.max(4,Math.min(r.left-w.left, w.width-tip.offsetWidth-4))+'px';tip.style.top=Math.max(4,r.top-w.top-tip.offsetHeight-8)+'px';};
      a.addEventListener('mouseenter',show);a.addEventListener('focus',show);a.addEventListener('mouseleave',hide);a.addEventListener('blur',hide);
    });
  });
  if(document.querySelector('.mermaid')){
    renderSagaMermaid().catch(error=>console.error('Diagram rendering failed',error));
  }
});
