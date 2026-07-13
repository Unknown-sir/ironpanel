
document.addEventListener('click',e=>{if(e.target.classList.contains('copy')){const id=e.target.dataset.copy; const el=document.getElementById(id); if(el){navigator.clipboard.writeText(el.innerText); e.target.innerText='کپی شد'; setTimeout(()=>e.target.innerText='کپی',1200)}}});
function setRing(name,val){const card=document.querySelector(`[data-metric="${name}"] .ring`); if(card){const v=Math.max(0,Math.min(100,Number(val)||0)); card.style.setProperty('--p', v+'%'); card.classList.toggle('warning', v>=70 && name!=='license');}}
function setText(id,value){const el=document.getElementById(id); if(el) el.innerText=value;}
async function refreshMetrics(){
  try{
    const r=await fetch('/api/system/metrics',{cache:'no-store'}); if(!r.ok)return;
    const m=await r.json();
    [['cpu',m.cpu_percent],['ram',m.ram_percent],['swap',m.swap_percent],['disk',m.disk_percent]].forEach(x=>{setText(x[0]+'_percent',Math.round(Number(x[1])||0)+'%'); setRing(x[0],x[1]);});
    setText('cpu_sub',(m.cpu_freq||0)+' GHz');
    setText('ram_sub',(m.ram_used_mb||0)+'MB / '+(m.ram_total_mb||0)+'MB');
    setText('swap_sub',(m.swap_used_mb||0)+'MB / '+(m.swap_total_mb||0)+'MB');
    setText('disk_sub',(m.disk_used_gb||0)+'GB / '+(m.disk_total_gb||0)+'GB');
    const ld=document.getElementById('license_days');
    if(ld){
      const d=m.license_days_remaining;
      const unknown=(d===null||d===undefined||d==='');
      if(m.license_free){
        ld.innerText='FREE';
        setText('license_sub','Beginner · بدون انقضا');
        setRing('license',100);
      }else{
        ld.innerText=unknown?'ACTIVE':d;
        setText('license_sub',unknown?(String(m.license_type||'paid').toUpperCase()):(d+' روز باقی‌مانده'));
        setRing('license',unknown?100:Math.min(100,Math.max(0,Number(d)||0)));
      }
      const lr=document.querySelector('[data-metric="license"] .ring');
      if(lr) lr.classList.toggle('warning',!m.license_free && !unknown && Number(d)<=7);
    }
  }catch(e){console.warn('metrics refresh failed',e);}
}
if(document.querySelector('.system-monitor') || document.querySelector('.vpnui-metrics')){refreshMetrics(); setInterval(refreshMetrics,3000)}

// v13.1 - Remember opened sidebar categories per browser
(function(){
  const sections=document.querySelectorAll('.menu-section[data-menu]');
  sections.forEach(s=>{
    const key='ironpanel.menu.'+s.dataset.menu;
    const saved=localStorage.getItem(key);
    if(saved==='1') s.open=true;
    if(saved==='0' && !s.querySelector('a.active')) s.open=false;
    s.addEventListener('toggle',()=>localStorage.setItem(key,s.open?'1':'0'));
  });
})();
