async function renderSagaMermaid(loader=()=>import('https://cdn.jsdelivr.net/npm/mermaid@11.12.0/dist/mermaid.esm.min.mjs')){
  const {default:mermaid}=await loader();
  mermaid.initialize({startOnLoad:false,securityLevel:'strict',theme:'neutral'});
  await mermaid.run({querySelector:'.mermaid'});
}
document.addEventListener('DOMContentLoaded',()=>{
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
