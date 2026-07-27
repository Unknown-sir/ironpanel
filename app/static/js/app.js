// IronPanel v19.9.29 UI runtime: stable drawer, accordion menu, metrics and tables.
(function(){
  function qs(s,root){return (root||document).querySelector(s)}
  function qsa(s,root){return Array.prototype.slice.call((root||document).querySelectorAll(s))}
  function uiText(en,fa,ar,ru){var l=(document.documentElement.getAttribute('lang')||'en').toLowerCase(); if(l.indexOf('fa')===0)return fa; if(l.indexOf('ar')===0)return ar||en; if(l.indexOf('ru')===0)return ru||en; return en;}

  document.addEventListener('click',function(e){
    if(e.target.classList && e.target.classList.contains('copy')){
      var id=e.target.dataset.copy, el=document.getElementById(id);
      if(el && navigator.clipboard){
        navigator.clipboard.writeText(el.innerText || el.textContent || '');
        var old=e.target.innerText; e.target.innerText=uiText('Copied','کپی شد','تم النسخ','Скопировано');
        setTimeout(function(){e.target.innerText=old || uiText('Copy','کپی','نسخ','Копировать')},1200);
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
        if(m.license_free){ld.innerText='FREE';setText('license_sub',uiText('Beginner · no expiration','Beginner · بدون انقضا','Beginner · بلا انتهاء','Beginner · без срока'));setRing('license',100)}
        else{ld.innerText=unknown?'ACTIVE':d;setText('license_sub',unknown?(String(m.license_type||'paid').toUpperCase()):(d+' '+uiText('days remaining','روز باقی‌مانده','أيام متبقية','дней осталось')));setRing('license',unknown?100:Math.min(100,Math.max(0,Number(d)||0)))}
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

// v19.9.31 final UI/i18n stabilizer: robust menu, normalized controls, non-Persian fallback labels.
(function(){
  function qsa(s, root){ return Array.prototype.slice.call((root || document).querySelectorAll(s)); }
  function qs(s, root){ return (root || document).querySelector(s); }
  function lang(){ return (document.documentElement.getAttribute('lang') || 'en').toLowerCase(); }
  function isFa(){ return lang().indexOf('fa') === 0; }
  function closeMenu(){ document.body.classList.remove('menu-open'); var b=qs('.mobile-menu-toggle'); if(b) b.setAttribute('aria-expanded','false'); }
  function openMenu(){ document.body.classList.add('menu-open'); var b=qs('.mobile-menu-toggle'); if(b) b.setAttribute('aria-expanded','true'); }

  function stabilizeMenu(){
    var btn = qs('.mobile-menu-toggle');
    if(btn && !btn.dataset.v19931){
      btn.dataset.v19931='1';
      btn.addEventListener('click', function(e){ e.preventDefault(); e.stopPropagation(); document.body.classList.contains('menu-open') ? closeMenu() : openMenu(); }, true);
    }
    var backdrop = qs('.sidebar-backdrop');
    if(backdrop && !backdrop.dataset.v19931){ backdrop.dataset.v19931='1'; backdrop.addEventListener('click', closeMenu); }
    qsa('.nav-group').forEach(function(details){
      var active = details.querySelector('a.active');
      if(active) details.open = true;
      if(details.dataset.v19931) return;
      details.dataset.v19931='1';
      details.addEventListener('toggle', function(){
        if(!details.open) return;
        qsa('.nav-group', details.closest('.app-sidebar') || document).forEach(function(other){
          if(other !== details && !other.querySelector('a.active')) other.open = false;
        });
      });
    });
    qsa('.app-sidebar a').forEach(function(a){ if(!a.dataset.v19931){ a.dataset.v19931='1'; a.addEventListener('click', function(){ if(window.matchMedia('(max-width:1180px)').matches) closeMenu(); }); }});
  }

  function normalizeControls(){
    qsa('label').forEach(function(label){
      var cb = label.querySelector(':scope > input[type="checkbox"], :scope > input[type="radio"]');
      if(cb) label.classList.add('normalized-checkline');
    });
    qsa('input[type="checkbox"],input[type="radio"]').forEach(function(input){
      input.classList.add('normalized-choice');
      input.removeAttribute('style');
    });
    qsa('table').forEach(function(table){
      if(table.closest('.table-scroll')) return;
      var wrap=document.createElement('div'); wrap.className='table-scroll';
      table.parentNode.insertBefore(wrap, table); wrap.appendChild(table);
    });
  }

  var en = {
    'داشبورد':'Dashboard','ساخت سریع':'Quick create','ساخت سریع کاربر':'Quick create user','کاربران و کانفیگ‌ها':'Users & configs','کاربران':'Users','مصرف':'Usage','مصرف و گزارش‌ها':'Usage & reports','کاربران آنلاین':'Online users','نمایندگان':'Resellers','تنظیمات':'Settings','تنظیمات اصلی':'Core settings','تنظیمات بیشتر':'More settings','زبان و ظاهر':'Language & appearance','زبان، تم و ظاهر':'Language, theme & appearance','خروج':'Logout','سلامت و تعمیر سرویس‌ها':'Service health & repair','مدیریت نودها':'Node management','نصب و مدیریت نودها':'Install and manage nodes','کلاستر و پایداری':'Cluster & availability','شبکه و دامنه':'Network & domains','مدیریت دامنه':'Domain manager','فروش و نمایندگان':'Sales & resellers','پلن‌های فروش':'Sales plans','ربات فروش':'Sales bot','کیف پول':'Wallet','تیکت‌ها':'Tickets','مرکز امنیت':'Security center','احراز هویت دو مرحله‌ای':'Two-factor authentication','تاریخچه ورود':'Login history','لاگ‌های سیستم':'System logs','ربات مدیریتی':'Admin bot','آپدیت پنل':'Panel updates','ظاهر پنل':'Panel appearance','مانیتورینگ منابع':'Resource monitoring','لاگ زنده':'Live logs','بکاپ و بازیابی':'Backups & restore','گواهی SSL':'SSL certificates','محدودیت سرعت':'Speed limits','قوانین مسیریابی':'Routing rules','مالی و فاکتورها':'Billing & invoices','وضعیت':'Status','فعال':'Enabled','غیرفعال':'Disabled','ذخیره':'Save','حذف':'Delete','ویرایش':'Edit','دانلود':'Download','کپی':'Copy','ایجاد':'Create','ایجاد و نمایش کانفیگ‌ها':'Create and show configs','جستجو':'Search','جستجوی کاربر':'Search user','کانفیگ‌ها':'Configs','سابسکریپشن':'Subscription','ریست حجم':'Reset usage','حجم مصرفی این کاربر صفر شود؟':'Reset this user usage?','نام کاربری':'Username','رمز عبور':'Password','رمز پنل / پیش‌فرض':'Panel/default password','روز اعتبار':'Validity days','حجم MB':'Traffic MB','اتصال همزمان':'Concurrent connections','دستگاه مجاز':'Allowed devices','پروتکل‌های کاربر':'User protocols','انتخاب دستی':'Manual selection','نام سرور':'Server name','نام نود':'Node name','آدرس سرور نود برای SSH':'Node SSH address','دامنه داخل کانفیگ نود':'Config domain for node','دامنه SSL سرور نود':'Node SSL domain','اطلاعات SSH برای نصب خودکار':'SSH credentials for auto install','ثبت نود و شروع نصب خودکار':'Save node and start auto install','وضعیت کلی':'Overview','هنوز نودی ثبت نشده است. از فرم بالا اولین Direct Location را اضافه کن.':'No node has been added yet. Add the first direct location from the form above.','لیست کاربران':'User list','کاربری یافت نشد.':'No users found.','نامحدود':'Unlimited','باقی‌مانده':'Remaining','انقضا':'Expires','فعال:':'Active:','پروتکل فعال':'active protocols','جزئیات':'Details','باز کردن فرم':'Open form','مدیریت کاربران، کانفیگ‌ها و نودها در یک نمای تمیز':'Manage users, configs and nodes in one clean view','تعداد کاربران':'Users count','عملیات روزانه':'Daily operations','مدیریت سیستم':'System management','فروش و دسترسی‌ها':'Business & access','زیرساخت و پروتکل‌ها':'Infrastructure & protocols','امنیت و عملیات':'Security & operations','نمای کلی و وضعیت سیستم':'Overview and status','ایجاد سریع سرویس جدید':'Create a new service quickly','ویرایش، تمدید و خروجی‌ها':'Manage, renew and export','کاربران متصل':'Connected users','ترافیک و آمار مصرف':'Traffic and usage','هسته‌ها، تنظیمات و سلامت':'Cores, settings and health','نصب، سینک و Direct Runtime':'Install, sync and Direct Runtime','فایروال، DNS و دامنه‌ها':'Firewall, DNS and domains','پلن، پرداخت و ربات فروش':'Plans, payments and sales bot','دسترسی، API، لاگ و آپدیت':'Access, API, logs and updates','ورود به پنل':'Sign in','ورود به پنل مدیریت':'Management sign in','دسترسی امن به کنسول مدیریت':'Secure access to the management console','نام کاربری، رمز عبور و در صورت نیاز کد دو مرحله‌ای را وارد کنید.':'Enter username, password and two-factor code if required.','در صورت فعال بودن':'If enabled','رابط رسمی مدیریت سرویس':'Professional service console'
  };
  var ar = Object.assign({}, en, {'داشبورد':'لوحة التحكم','ساخت سریع':'إنشاء سريع','ساخت کاربر':'إنشاء مستخدم','کاربران':'المستخدمون','کاربران و کانفیگ‌ها':'المستخدمون والملفات','مصرف':'الاستهلاك','مصرف و گزارش‌ها':'الاستهلاك والتقارير','کاربران آنلاین':'المستخدمون المتصلون','نمایندگان':'الوكلاء','تنظیمات':'الإعدادات','تنظیمات اصلی':'الإعدادات الأساسية','زبان و ظاهر':'اللغة والمظهر','ذخیره':'حفظ','حذف':'حذف','ویرایش':'تعديل','دانلود':'تنزيل','کپی':'نسخ','جستجو':'بحث','وضعیت':'الحالة','فعال':'مفعل','غیرفعال':'معطل','نام کاربری':'اسم المستخدم','رمز عبور':'كلمة المرور','سابسکریپشن':'الاشتراك','ریست حجم':'تصفير الاستهلاك','حجم مصرفی این کاربر صفر شود؟':'تصفير استهلاك هذا المستخدم؟'});
  var ru = Object.assign({}, en, {'داشبورد':'Панель управления','ساخت سریع':'Быстро создать','ساخت کاربر':'Создать пользователя','کاربران':'Пользователи','کاربران و کانفیگ‌ها':'Пользователи и конфиги','مصرف':'Трафик','مصرف و گزارش‌ها':'Трафик и отчёты','کاربران آنلاین':'Пользователи онлайн','نمایندگان':'Реселлеры','تنظیمات':'Настройки','تنظیمات اصلی':'Основные настройки','زبان و ظاهر':'Язык и внешний вид','ذخیره':'Сохранить','حذف':'Удалить','ویرایش':'Изменить','دانلود':'Скачать','کپی':'Копировать','جستجو':'Поиск','وضعیت':'Статус','فعال':'Включено','غیرفعال':'Отключено','نام کاربری':'Имя пользователя','رمز عبور':'Пароль','سابسکریپشن':'Подписка','ریست حجم':'Сброс трафика','حجم مصرفی این کاربر صفر شود؟':'Сбросить трафик этого пользователя?'});
  function localizedMap(){ var l=lang(); if(l.indexOf('ar')===0) return ar; if(l.indexOf('ru')===0) return ru; return en; }
  function replaceTextNode(node, map){
    var raw=node.nodeValue || ''; var out=raw; var keys=Object.keys(map).sort(function(a,b){return b.length-a.length});
    keys.forEach(function(k){ if(k && out.indexOf(k)>=0) out=out.split(k).join(map[k]); });
    node.nodeValue = out;
  }
  function localizeFallback(){
    if(isFa()) return;
    var map=localizedMap();
    var walker=document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT, {acceptNode:function(node){
      if(!/[\u0600-\u06FF]/.test(node.nodeValue || '')) return NodeFilter.FILTER_REJECT;
      var p=node.parentElement; if(!p || ['SCRIPT','STYLE','CODE','PRE','TEXTAREA'].indexOf(p.tagName)>=0) return NodeFilter.FILTER_REJECT;
      return NodeFilter.FILTER_ACCEPT;
    }});
    var nodes=[]; while(walker.nextNode()) nodes.push(walker.currentNode); nodes.forEach(function(n){ replaceTextNode(n,map); });
    qsa('input,textarea,button').forEach(function(el){ ['placeholder','title','aria-label','value'].forEach(function(attr){ var v=el.getAttribute(attr); if(v && map[v.trim()]) el.setAttribute(attr, v.replace(v.trim(), map[v.trim()])); }); });
  }

  document.addEventListener('DOMContentLoaded', function(){ stabilizeMenu(); normalizeControls(); localizeFallback(); });
  document.addEventListener('keydown', function(e){ if(e.key==='Escape') closeMenu(); });
  window.addEventListener('resize', function(){ if(window.innerWidth>1180) closeMenu(); });
})();
