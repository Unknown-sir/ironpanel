// IronPanel v19.10.3 stable UI runtime: single menu controller, responsive helpers, safe copy/metrics.
(function(){
  'use strict';
  function qs(sel, root){ return (root || document).querySelector(sel); }
  function qsa(sel, root){ return Array.prototype.slice.call((root || document).querySelectorAll(sel)); }
  function lang(){ return (document.documentElement.getAttribute('lang') || 'en').toLowerCase(); }
  function uiText(en, fa, ar, ru){ var l=lang(); if(l.indexOf('fa')===0) return fa || en; if(l.indexOf('ar')===0) return ar || en; if(l.indexOf('ru')===0) return ru || en; return en; }
  function isMobile(){ return window.matchMedia('(max-width: 1120px)').matches; }

  function setMenu(open){
    document.body.classList.toggle('menu-open', !!open);
    var btn = qs('.mobile-menu-toggle');
    if(btn) btn.setAttribute('aria-expanded', open ? 'true' : 'false');
  }
  function closeMenu(){ setMenu(false); }
  function toggleMenu(){ setMenu(!document.body.classList.contains('menu-open')); }

  function initMenu(){
    var btn = qs('.mobile-menu-toggle');
    if(btn && !btn.dataset.ipStableBound){
      btn.dataset.ipStableBound = '1';
      btn.addEventListener('click', function(e){
        e.preventDefault();
        e.stopImmediatePropagation();
        toggleMenu();
      }, true);
    }
    var backdrop = qs('.sidebar-backdrop');
    if(backdrop && !backdrop.dataset.ipStableBound){
      backdrop.dataset.ipStableBound = '1';
      backdrop.addEventListener('click', function(e){ e.preventDefault(); closeMenu(); });
    }
    qsa('.nav-group').forEach(function(details){
      var active = details.querySelector('a.active');
      var key = 'ironpanel.v19103.nav.' + (details.dataset.menu || 'group');
      if(active) details.open = true;
      else if(localStorage.getItem(key) === '1') details.open = true;
      else if(localStorage.getItem(key) === '0') details.open = false;
      if(details.dataset.ipStableBound) return;
      details.dataset.ipStableBound = '1';
      details.addEventListener('toggle', function(){
        localStorage.setItem(key, details.open ? '1' : '0');
        if(details.open){
          qsa('.nav-group', details.closest('.app-sidebar') || document).forEach(function(other){
            if(other !== details && !other.querySelector('a.active')){
              other.open = false;
              localStorage.setItem('ironpanel.v19103.nav.' + (other.dataset.menu || 'group'), '0');
            }
          });
        }
      });
    });
    qsa('.app-sidebar a').forEach(function(a){
      if(a.dataset.ipStableLinkBound) return;
      a.dataset.ipStableLinkBound = '1';
      a.addEventListener('click', function(){ if(isMobile()) closeMenu(); });
    });
    document.addEventListener('keydown', function(e){ if(e.key === 'Escape') closeMenu(); }, {passive:true});
    document.addEventListener('click', function(e){
      if(!document.body.classList.contains('menu-open')) return;
      if(e.target.closest('.app-sidebar') || e.target.closest('.mobile-menu-toggle')) return;
      closeMenu();
    });
    window.addEventListener('resize', function(){ if(!isMobile()) closeMenu(); }, {passive:true});
  }

  function normalizeControls(){
    qsa('label').forEach(function(label){
      var choice = label.querySelector(':scope > input[type="checkbox"], :scope > input[type="radio"]');
      if(choice) label.classList.add('ip-choice-line');
    });
    qsa('input[type="checkbox"], input[type="radio"]').forEach(function(input){
      input.classList.add('ip-choice-input');
      input.removeAttribute('style');
    });
    qsa('.page-content table, section table, main table').forEach(function(table){
      if(table.closest('.table-scroll')) return;
      var wrap = document.createElement('div');
      wrap.className = 'table-scroll';
      table.parentNode.insertBefore(wrap, table);
      wrap.appendChild(table);
    });
  }

  function setText(id, value){ var el = document.getElementById(id); if(el) el.innerText = value; }
  function setRing(name, val){
    var card = qs('[data-metric="'+name+'"] .ring');
    if(card){ var v = Math.max(0, Math.min(100, Number(val) || 0)); card.style.setProperty('--p', v + '%'); card.classList.toggle('warning', v >= 70 && name !== 'license'); }
  }
  window.refreshMetrics = async function(){
    try{
      var r = await fetch('/api/system/metrics', {cache:'no-store'});
      if(!r.ok) return;
      var m = await r.json();
      [['cpu',m.cpu_percent],['ram',m.ram_percent],['swap',m.swap_percent],['disk',m.disk_percent]].forEach(function(x){ setText(x[0]+'_percent', Math.round(Number(x[1])||0)+'%'); setRing(x[0], x[1]); });
      setText('cpu_sub', (m.cpu_freq||0)+' GHz');
      setText('ram_sub', (m.ram_used_mb||0)+'MB / '+(m.ram_total_mb||0)+'MB');
      setText('swap_sub', (m.swap_used_mb||0)+'MB / '+(m.swap_total_mb||0)+'MB');
      setText('disk_sub', (m.disk_used_gb||0)+'GB / '+(m.disk_total_gb||0)+'GB');
      var ld = document.getElementById('license_days');
      if(ld){
        var d=m.license_days_remaining, unknown=(d===null||d===undefined||d==='');
        if(m.license_free){ ld.innerText='FREE'; setText('license_sub', uiText('Beginner · no expiration','Beginner · بدون انقضا','Beginner · بلا انتهاء','Beginner · без срока')); setRing('license',100); }
        else { ld.innerText=unknown?'ACTIVE':d; setText('license_sub', unknown ? String(m.license_type||'paid').toUpperCase() : (d+' '+uiText('days remaining','روز باقی‌مانده','أيام متبقية','дней осталось'))); setRing('license', unknown?100:Math.min(100,Math.max(0,Number(d)||0))); }
      }
    }catch(err){}
  };

  function initCopy(){
    document.addEventListener('click', function(e){
      var target = e.target.closest('.copy,[data-copy],[data-copy-text],[data-copy-target]');
      if(!target) return;
      var id = target.dataset.copy || target.dataset.copyTarget;
      var el = id ? document.getElementById(id) : null;
      var text = el ? (el.innerText || el.textContent || '') : (target.dataset.copyText || '');
      if(!text || !navigator.clipboard) return;
      navigator.clipboard.writeText(text).then(function(){
        var old = target.innerText;
        target.innerText = uiText('Copied','کپی شد','تم النسخ','Скопировано');
        setTimeout(function(){ target.innerText = old || uiText('Copy','کپی','نسخ','Копировать'); }, 1200);
      });
    });
  }

  var en = {'داشبورد':'Dashboard','ساخت سریع':'Quick create','ساخت کاربر':'Create user','کاربران':'Users','کاربران و کانفیگ‌ها':'Users & configs','مصرف':'Usage','مصرف و گزارش‌ها':'Usage & reports','کاربران آنلاین':'Online users','نمایندگان':'Resellers','تنظیمات':'Settings','ذخیره':'Save','حذف':'Delete','ویرایش':'Edit','دانلود':'Download','کپی':'Copy','جستجو':'Search','وضعیت':'Status','فعال':'Enabled','غیرفعال':'Disabled','نام کاربری':'Username','رمز عبور':'Password','سابسکریپشن':'Subscription','ریست حجم':'Reset usage'};
  var ar = Object.assign({}, en, {'داشبورد':'لوحة التحكم','ساخت کاربر':'إنشاء مستخدم','کاربران':'المستخدمون','تنظیمات':'الإعدادات','ذخیره':'حفظ','حذف':'حذف','ویرایش':'تعديل','دانلود':'تنزيل','کپی':'نسخ','جستجو':'بحث','وضعیت':'الحالة','فعال':'مفعل','غیرفعال':'معطل','نام کاربری':'اسم المستخدم','رمز عبور':'كلمة المرور'});
  var ru = Object.assign({}, en, {'داشبورد':'Панель управления','ساخت کاربر':'Создать пользователя','کاربران':'Пользователи','تنظیمات':'Настройки','ذخیره':'Сохранить','حذف':'Удалить','ویرایش':'Изменить','دانلود':'Скачать','کپی':'Копировать','جستجو':'Поиск','وضعیت':'Статус','فعال':'Включено','غیرفعال':'Отключено','نام کاربری':'Имя пользователя','رمز عبور':'Пароль'});
  function localMap(){ var l=lang(); return l.indexOf('ar')===0 ? ar : (l.indexOf('ru')===0 ? ru : en); }
  function localizeClientFallback(){
    if(lang().indexOf('fa')===0) return;
    var map = localMap();
    var keys = Object.keys(map).sort(function(a,b){ return b.length-a.length; });
    var walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT, {acceptNode:function(node){
      if(!/[\u0600-\u06FF]/.test(node.nodeValue || '')) return NodeFilter.FILTER_REJECT;
      var p=node.parentElement;
      if(!p || ['SCRIPT','STYLE','CODE','PRE','TEXTAREA'].indexOf(p.tagName)>=0) return NodeFilter.FILTER_REJECT;
      return NodeFilter.FILTER_ACCEPT;
    }});
    var nodes=[]; while(walker.nextNode()) nodes.push(walker.currentNode);
    nodes.forEach(function(n){ var out=n.nodeValue || ''; keys.forEach(function(k){ if(k && out.indexOf(k)>=0) out=out.split(k).join(map[k]); }); n.nodeValue=out; });
    qsa('input,textarea,button').forEach(function(el){ ['placeholder','title','aria-label','value'].forEach(function(attr){ var v=el.getAttribute(attr); if(!v) return; var out=v; keys.forEach(function(k){ if(k && out.indexOf(k)>=0) out=out.split(k).join(map[k]); }); if(out!==v) el.setAttribute(attr,out); }); });
  }

  document.addEventListener('DOMContentLoaded', function(){
    initMenu();
    normalizeControls();
    initCopy();
    localizeClientFallback();
    if(qs('.system-monitor') || qs('.vpnui-metrics') || qs('.resource-grid') || qs('[data-metric]')){ window.refreshMetrics(); setInterval(window.refreshMetrics, 5000); }
  });
})();
