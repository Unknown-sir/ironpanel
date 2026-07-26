// IronPanel v19.9.29 UI runtime: stable drawer, accordion menu, metrics and tables.
(function(){
  function qs(s,root){return (root||document).querySelector(s)}
  function qsa(s,root){return Array.prototype.slice.call((root||document).querySelectorAll(s))}

  document.addEventListener('click',function(e){
    if(e.target.classList && e.target.classList.contains('copy')){
      var id=e.target.dataset.copy, el=document.getElementById(id);
      if(el && navigator.clipboard){
        navigator.clipboard.writeText(el.innerText || el.textContent || '');
        var old=e.target.innerText; e.target.innerText=document.documentElement.dir==='rtl'?'کپی شد':'Copied';
        setTimeout(function(){e.target.innerText=old || (document.documentElement.dir==='rtl'?'کپی':'Copy')},1200);
      }
    }
  });

  function setText(id,value){var el=document.getElementById(id); if(el) el.innerText=value;}
  function setRing(name,val){
    var card=document.querySelector('[data-metric="'+name+'"] .ring');
    if(card){var v=Math.max(0,Math.min(100,Number(val)||0)); card.style.setProperty('--p',v+'%'); card.classList.toggle('warning',v>=70&&name!=='license');}
  }
  window.refreshMetrics=async function(){
    try{
      var r=await fetch('/api/system/metrics',{cache:'no-store'}); if(!r.ok) return;
      var m=await r.json();
      [['cpu',m.cpu_percent],['ram',m.ram_percent],['swap',m.swap_percent],['disk',m.disk_percent]].forEach(function(x){setText(x[0]+'_percent',Math.round(Number(x[1])||0)+'%');setRing(x[0],x[1]);});
      setText('cpu_sub',(m.cpu_freq||0)+' GHz');
      setText('ram_sub',(m.ram_used_mb||0)+'MB / '+(m.ram_total_mb||0)+'MB');
      setText('swap_sub',(m.swap_used_mb||0)+'MB / '+(m.swap_total_mb||0)+'MB');
      setText('disk_sub',(m.disk_used_gb||0)+'GB / '+(m.disk_total_gb||0)+'GB');
      var ld=document.getElementById('license_days');
      if(ld){
        var d=m.license_days_remaining, unknown=(d===null||d===undefined||d==='');
        if(m.license_free){ld.innerText='FREE';setText('license_sub','Beginner · بدون انقضا');setRing('license',100)}
        else{ld.innerText=unknown?'ACTIVE':d;setText('license_sub',unknown?(String(m.license_type||'paid').toUpperCase()):(d+' روز باقی‌مانده'));setRing('license',unknown?100:Math.min(100,Math.max(0,Number(d)||0)))}
        var lr=document.querySelector('[data-metric="license"] .ring'); if(lr) lr.classList.toggle('warning',!m.license_free&&!unknown&&Number(d)<=7);
      }
    }catch(err){/* keep UI quiet */}
  };
  if(qs('.system-monitor')||qs('.vpnui-metrics')||qs('.resource-grid')){window.refreshMetrics();setInterval(window.refreshMetrics,4000)}

  function closeMenu(){document.body.classList.remove('menu-open');var btn=qs('.mobile-menu-toggle');if(btn)btn.setAttribute('aria-expanded','false')}
  function openMenu(){document.body.classList.add('menu-open');var btn=qs('.mobile-menu-toggle');if(btn)btn.setAttribute('aria-expanded','true')}
  var btn=qs('.mobile-menu-toggle');
  if(btn){btn.addEventListener('click',function(e){e.preventDefault();e.stopPropagation();document.body.classList.contains('menu-open')?closeMenu():openMenu();});}
  var backdrop=qs('.sidebar-backdrop'); if(backdrop) backdrop.addEventListener('click',closeMenu);
  document.addEventListener('keydown',function(e){if(e.key==='Escape') closeMenu();});
  qsa('.app-sidebar a').forEach(function(a){a.addEventListener('click',function(){if(window.matchMedia('(max-width:1180px)').matches) closeMenu();});});
  document.addEventListener('click',function(e){if(!document.body.classList.contains('menu-open')) return; if(e.target.closest('.app-sidebar')||e.target.closest('.mobile-menu-toggle')) return; closeMenu();});

  qsa('.nav-group').forEach(function(details){
    var active=details.querySelector('a.active');
    var key='ironpanel.v19929.nav.'+(details.dataset.menu||'group');
    if(active) details.open=true;
    else if(localStorage.getItem(key)==='1') details.open=true;
    else if(localStorage.getItem(key)==='0') details.open=false;
    details.addEventListener('toggle',function(){
      localStorage.setItem(key,details.open?'1':'0');
      if(details.open){
        qsa('.nav-group').forEach(function(other){
          if(other!==details && other.closest('.app-sidebar')===details.closest('.app-sidebar') && !other.querySelector('a.active')){other.open=false; localStorage.setItem('ironpanel.v19929.nav.'+(other.dataset.menu||'group'),'0');}
        });
      }
    });
  });

  qsa('.page-content table').forEach(function(table){
    if(table.closest('.table-scroll')) return;
    var wrap=document.createElement('div');wrap.className='table-scroll';table.parentNode.insertBefore(wrap,table);wrap.appendChild(table);
  });
})();
