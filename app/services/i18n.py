from __future__ import annotations

from flask import request
import re
from .provisioning import get_setting, set_setting

try:
    from .i18n_auto import AUTO_FA_UI_PHRASES, AUTO_FA_TO_EN, AUTO_FA_TO_AR, AUTO_FA_TO_RU
except Exception:  # pragma: no cover - upgrade-safe fallback
    AUTO_FA_UI_PHRASES = ()
    AUTO_FA_TO_EN = {}
    AUTO_FA_TO_AR = {}
    AUTO_FA_TO_RU = {}


LANGUAGES = {
    'fa': {'name': 'فارسی', 'dir': 'rtl', 'native': 'فارسی'},
    'en': {'name': 'English', 'dir': 'ltr', 'native': 'English'},
    'ar': {'name': 'العربية', 'dir': 'rtl', 'native': 'العربية'},
    'ru': {'name': 'Русский', 'dir': 'ltr', 'native': 'Русский'},
}

TRANSLATIONS = {
    'fa': {
        'dashboard': 'داشبورد', 'quick_create': 'ساخت سریع کاربر', 'users': 'کاربران و کانفیگ‌ها',
        'usage': 'مصرف و گزارش‌ها', 'online_users': 'کاربران آنلاین', 'resellers': 'نمایندگان',
        'auto_ssl': 'SSL خودکار', 'health': 'تعمیر و سلامت', 'settings': 'تنظیمات اصلی',
        'license': 'لایسنس', 'more_settings': 'تنظیمات بیشتر', 'appearance': 'زبان و ظاهر',
        'logout': 'خروج', 'active_version': 'نسخه فعال', 'active_host': 'Host فعال',
        'quick': 'ساخت سریع', 'language': 'زبان', 'theme': 'تم', 'save': 'ذخیره',
        'light': 'روشن', 'dark': 'تاریک', 'auto': 'خودکار', 'logs': 'لاگ‌ها', 'jobs': 'Jobها', 'node_management':'مدیریت نودها','sales_plans':'پلن‌های فروش','security_center':'مرکز امنیت','subscription_manager':'مدیریت سابسکریپشن',
    },
    'en': {
        'dashboard': 'Dashboard', 'quick_create': 'Quick Create', 'users': 'Users & Configs',
        'usage': 'Usage & Reports', 'online_users': 'Online Users', 'resellers': 'Resellers',
        'auto_ssl': 'Auto SSL', 'health': 'Health & Repair', 'settings': 'Core Settings',
        'license': 'License', 'more_settings': 'More Settings', 'appearance': 'Language & Theme',
        'logout': 'Logout', 'active_version': 'Active edition', 'active_host': 'Active host',
        'quick': 'Quick Create', 'language': 'Language', 'theme': 'Theme', 'save': 'Save',
        'light': 'Light', 'dark': 'Dark', 'auto': 'Auto', 'logs': 'Logs', 'jobs': 'Jobs', 'node_management':'Node management','sales_plans':'Sales plans','security_center':'Security center','subscription_manager':'Subscription manager',
    },
    'ar': {
        'dashboard': 'لوحة التحكم', 'quick_create': 'إنشاء سريع', 'users': 'المستخدمون والملفات',
        'usage': 'الاستهلاك والتقارير', 'online_users': 'المتصلون الآن', 'resellers': 'الوكلاء',
        'auto_ssl': 'SSL تلقائي', 'health': 'الصحة والإصلاح', 'settings': 'الإعدادات الأساسية',
        'license': 'الترخيص', 'more_settings': 'إعدادات إضافية', 'appearance': 'اللغة والمظهر',
        'logout': 'خروج', 'active_version': 'الإصدار النشط', 'active_host': 'المضيف النشط',
        'quick': 'إنشاء سريع', 'language': 'اللغة', 'theme': 'السمة', 'save': 'حفظ',
        'light': 'فاتح', 'dark': 'داكن', 'auto': 'تلقائي', 'logs': 'السجلات', 'jobs': 'المهام', 'node_management':'إدارة العقد','sales_plans':'خطط البيع','security_center':'مركز الأمان','subscription_manager':'إدارة الاشتراك',
    },
    'ru': {
        'dashboard': 'Панель', 'quick_create': 'Быстро создать', 'users': 'Пользователи и конфиги',
        'usage': 'Трафик и отчёты', 'online_users': 'Онлайн пользователи', 'resellers': 'Реселлеры',
        'auto_ssl': 'Auto SSL', 'health': 'Диагностика', 'settings': 'Основные настройки',
        'license': 'Лицензия', 'more_settings': 'Дополнительно', 'appearance': 'Язык и тема',
        'logout': 'Выход', 'active_version': 'Активная редакция', 'active_host': 'Активный хост',
        'quick': 'Быстро', 'language': 'Язык', 'theme': 'Тема', 'save': 'Сохранить',
        'light': 'Светлая', 'dark': 'Тёмная', 'auto': 'Авто', 'logs': 'Логи', 'jobs': 'Задачи', 'node_management':'Управление узлами','sales_plans':'Тарифы продаж','security_center':'Центр безопасности','subscription_manager':'Менеджер подписок',
    },
}

THEMES = {'dark': 'Dark', 'light': 'Light', 'auto': 'Auto'}


def current_language() -> str:
    lang = (get_setting('language', 'en') or 'en').lower()
    return lang if lang in LANGUAGES else 'en'


def current_theme() -> str:
    theme = (get_setting('theme_mode', 'dark') or 'dark').lower()
    return theme if theme in THEMES else 'dark'


def language_dir(lang: str | None = None) -> str:
    return LANGUAGES.get(lang or current_language(), LANGUAGES['en'])['dir']


def t(key: str, default: str | None = None) -> str:
    lang = current_language()
    return TRANSLATIONS.get(lang, {}).get(key) or TRANSLATIONS['en'].get(key) or default or key


def save_appearance(form) -> None:
    lang = (form.get('language') or current_language()).lower()
    theme = (form.get('theme_mode') or current_theme()).lower()
    if lang not in LANGUAGES: lang = 'en'
    if theme not in THEMES: theme = 'dark'
    set_setting('language', lang)
    set_setting('theme_mode', theme)


# v19.10.0: server-side cleanup for legacy hard-coded Persian UI strings.
# Older pages still contain many literal Persian labels.  Rewriting all templates at
# once is risky, so the renderer applies this conservative phrase map for every
# non-Persian language before the response is sent.  Persian remains untouched.
_HARDCODED_FA_TO_EN = {
    # global actions
    'ذخیره': 'Save', 'ذخیره تنظیمات': 'Save settings', 'ذخیره و اعمال': 'Save and apply',
    'ذخیره و اعمال تنظیمات': 'Save and apply settings', 'ذخیره و ری‌استارت ربات': 'Save and restart bot',
    'ذخیره و همگام‌سازی': 'Save and sync', 'ذخیره تغییرات حساب': 'Save account changes',
    'حذف': 'Delete', 'حذف شود؟': 'Delete?', 'ویرایش': 'Edit', 'ویرایش کاربر': 'Edit user',
    'اعمال': 'Apply', 'اعمال روی سرور': 'Apply on server', 'اجرا': 'Run', 'تست': 'Test',
    'تأیید': 'Approve', 'رد': 'Reject', 'بازگشت': 'Back', 'برگشت': 'Back', 'جستجو': 'Search',
    'دانلود': 'Download', 'دانلود فایل': 'Download file', 'آپلود': 'Upload', 'کپی': 'Copy',
    'کپی شد': 'Copied', 'کپی لینک': 'Copy link', 'کپی آدرس': 'Copy URL', 'نمایش': 'View',
    'جزئیات': 'Details', 'وضعیت': 'Status', 'عملیات': 'Actions', 'فعال': 'Enabled',
    'غیرفعال': 'Disabled', 'فعال باشد': 'Enable', 'فعال روی این سرور': 'Enabled on this server',
    'خودکار': 'Auto', 'دستی': 'Manual', 'انتخاب دستی': 'Manual selection', 'انتخاب خودکار': 'Auto select',
    'نامحدود': 'Unlimited', 'نامشخص': 'Unknown', 'موفق': 'Success', 'ناموفق': 'Failed',
    'آماده': 'Ready', 'متوقف': 'Stopped', 'ضروری': 'Required', 'اختیاری': 'Optional',
    'اصلی': 'Main', 'فعلی:': 'Current:', 'فعال:': 'Enabled:', 'باقی‌مانده:': 'Remaining:',

    # main navigation / pages
    'داشبورد': 'Dashboard', 'ساخت سریع': 'Quick create', 'ساخت سریع کاربر': 'Quick create user',
    'کاربران': 'Users', 'کاربران و کانفیگ‌ها': 'Users & configs', 'کانفیگ‌ها': 'Configs',
    'مصرف': 'Usage', 'مصرف و گزارش‌ها': 'Usage & reports', 'گزارش مصرف': 'Usage report',
    'کاربران آنلاین': 'Online users', 'اتصالات آنلاین': 'Online sessions', 'نشست فعال': 'Active session',
    'نمایندگان': 'Resellers', 'نماینده': 'Reseller', 'ساخت کاربر': 'Create user',
    'مدیریت کاربران': 'User management', 'لیست کاربران': 'User list', 'حساب کاربری': 'Account',
    'حساب من': 'My account', 'تنظیمات': 'Settings', 'تنظیمات اصلی': 'Core settings',
    'تنظیمات بیشتر': 'More settings', 'تنظیمات تکمیلی': 'Additional settings',
    'زبان و ظاهر': 'Language & appearance', 'زبان، تم و ظاهر': 'Language, theme & appearance',
    'زبان رابط کاربری و حالت روشن/تاریک پنل را انتخاب کنید. تغییرات برای تمام صفحات اعمال می‌شود.': 'Choose the interface language and light/dark theme. Changes are applied to all pages.',
    'سلامت سیستم': 'System health', 'سلامت و تعمیر سرویس‌ها': 'Service health & repair',
    'تعمیر': 'Repair', 'Repair کامل': 'Full repair', 'لاگ‌ها': 'Logs', 'لاگ‌های سیستم': 'System logs',
    'لاگ زنده': 'Live logs', 'مانیتورینگ منابع': 'Resource monitoring', 'منابع سرور': 'Server resources',
    'بکاپ': 'Backup', 'بکاپ و بازیابی': 'Backups & restore', 'ریستور': 'Restore',
    'مدیریت آپدیت': 'Update manager', 'آپدیت‌ها': 'Updates', 'شروع آپدیت': 'Start update',
    'آپدیت جدید': 'New update', 'نسخه فعلی:': 'Current version:', 'آخرین نسخه GitHub': 'Latest GitHub version',
    'لایسنس': 'License', 'لایسنس و ارتقا': 'License & upgrade', 'وضعیت لایسنس': 'License status',
    'بررسی و اعمال لایسنس': 'Check and apply license', 'ثبت لایسنس جدید': 'Register new license',

    # sidebar groups
    'عملیات روزانه': 'Daily operations', 'مدیریت سیستم': 'System management',
    'زیرساخت و پروتکل‌ها': 'Infrastructure & protocols', 'هسته‌ها، تنظیمات و سلامت': 'Cores, settings and health',
    'نودها': 'Nodes', 'نود': 'Node', 'مدیریت نودها': 'Node management',
    'نصب و مدیریت نودها': 'Install and manage nodes', 'نصب، سینک و Direct Runtime': 'Install, sync and Direct Runtime',
    'شبکه و دامنه': 'Network & domains', 'فایروال، DNS و دامنه‌ها': 'Firewall, DNS and domains',
    'فروش و دسترسی‌ها': 'Business & access', 'فروش و نمایندگان': 'Sales & resellers',
    'پلن، پرداخت و ربات فروش': 'Plans, payments and sales bot',
    'امنیت و عملیات': 'Security & operations', 'دسترسی، API، لاگ و آپدیت': 'Access, API, logs and updates',
    'کنسول مدیریت': 'Management console', 'کنسول مدیریت سرویس': 'Service management console',
    'منوی اصلی': 'Primary menu', 'خروج امن': 'Secure sign out', 'پایان نشست مدیریت': 'End management session',
    'نمای ساده': 'Simple view', 'نمای کامل پنل': 'Full console', 'برای دسترسی به تنظیمات تخصصی.': 'Access advanced configuration.',
    'برای کارهای روزمره و خلوت‌تر.': 'Cleaner daily workspace.',

    # login / appearance
    'ورود': 'Sign in', 'ورود به پنل': 'Sign in', 'ورود به IronPanel': 'Sign in to IronPanel',
    'ورود به پنل مدیریت': 'Management sign in', 'دسترسی امن به کنسول مدیریت': 'Secure access to the management console',
    'نام کاربری، رمز عبور و در صورت نیاز کد دو مرحله‌ای را وارد کنید.': 'Enter username, password and the two-factor code if required.',
    'نام کاربری': 'Username', 'رمز عبور': 'Password', 'رمز فعلی': 'Current password',
    'رمز جدید': 'New password', 'تکرار رمز جدید': 'Repeat new password', 'کد ۶ رقمی': '6-digit code',
    'کد 2FA یا Recovery Code': '2FA code or recovery code', 'در صورت فعال بودن': 'If enabled',
    'رابط رسمی مدیریت سرویس': 'Professional service console', 'زبان': 'Language', 'تم': 'Theme',
    'رنگ اصلی': 'Primary color', 'روشن': 'Light', 'تاریک': 'Dark', 'هماهنگ با سیستم عامل': 'Follow system',
    'برای محیط اداری روشن': 'For bright office environments', 'برای محیط‌های کم‌نور': 'For low-light environments',
    'ساده، مناسب استفاده روزمره': 'Simple, suitable for daily use', 'پیشرفته، نمایش همه بخش‌ها': 'Advanced, show all sections',
    'حالت رابط کاربری': 'Interface mode', 'ظاهر پنل': 'Panel appearance',

    # user/account form labels
    'ساخت کاربر جدید': 'Create new user', 'ساخت کاربر و نمایش کانفیگ‌ها': 'Create user and show configs',
    'ساخت کاربر و تحویل کانفیگ، بدون شلوغی': 'Create users and deliver configs without clutter',
    'اطلاعات اصلی کاربر': 'Main user information', 'اطلاعات کاربران': 'User information',
    'رمز پنل / پیش‌فرض': 'Panel/default password', 'رمز L2TP': 'L2TP password', 'رمز Cisco/Ocserv': 'Cisco/Ocserv password',
    'همان رمز': 'Same password', 'همان رمز برای L2TP و Ocserv هم استفاده شود': 'Use the same password for L2TP and Ocserv',
    'رمز جدید برای L2TP و Ocserv هم تنظیم شود': 'Also set the new password for L2TP and Ocserv',
    'روز اعتبار': 'Validity days', 'یا تعداد روز از امروز': 'or number of days from today',
    'تاریخ انقضا': 'Expiration date', 'بدون انقضا': 'No expiration', 'تاریخ نامحدود': 'Unlimited date',
    'حجم': 'Traffic', 'حجم MB': 'Traffic MB', 'حجم GB': 'Traffic GB', 'سقف حجم': 'Traffic limit',
    'سقف حجم GB': 'Traffic limit GB', 'سقف حجم مصرفی GB': 'Usage limit GB', 'باقی‌مانده': 'Remaining',
    'استفاده شده': 'Used', 'مصرف واقعی': 'Real usage', 'مصرف کلی': 'Total usage',
    'ریست حجم': 'Reset usage', 'حجم مصرفی این کاربر صفر شود؟': 'Reset this user usage?',
    'اتصال همزمان': 'Concurrent connections', 'دستگاه مجاز': 'Allowed devices', 'محدودیت IP/دستگاه': 'IP/device limit',
    'کاربر فعال باشد': 'User is enabled', 'غیرفعال‌سازی کاربر': 'Disable user',
    'پروتکل‌های کاربر': 'User protocols', 'انتخاب دستی پروتکل‌ها': 'Manual protocol selection',
    'پروتکل فعال': 'Active protocol', 'پروتکل‌ها': 'Protocols', 'پروتکل‌های فعال': 'Active protocols',
    'پیشنهادی: همه پروتکل‌های فعال': 'Recommended: all active protocols',
    'برای فروش فقط Xray، فقط گزینه Xray را روشن بگذار. برای فروش کامل، پروتکل‌های موردنظر را انتخاب کن.': 'To sell only Xray, enable only Xray. For a complete package, select the required protocols.',
    'کانفیگی برای این کاربر ساخته نشده است.': 'No config has been generated for this user.',
    'کاربری یافت نشد.': 'No user found.', 'کاربری وجود ندارد.': 'No user exists.', 'کاربری برای گزارش وجود ندارد.': 'No user is available for reporting.',
    'این کاربر و کانفیگ‌هایش حذف شوند؟': 'Delete this user and all configs?',
    'صفحه کانفیگ‌ها خودکار باز می‌شود': 'The configs page opens automatically',
    'باز کردن صفحه سابسکریپشن': 'Open subscription page', 'سابسکریپشن': 'Subscription', 'صفحه سابسکراپشن': 'Subscription page',
    'لینک سابسکریپشن': 'Subscription link', 'خروجی‌های حرفه‌ای سابسکریپشن': 'Professional subscription outputs',
    'برای Subscription این QR را اسکن کنید:': 'Scan this QR code for subscription:',
    'برای import سریع، QR را اسکن کنید یا کانفیگ را کپی/دانلود کنید.': 'For quick import, scan the QR or copy/download the config.',

    # nodes
    'افزودن نود جدید': 'Add new node', 'افزودن Node': 'Add node', 'ثبت نود و شروع نصب خودکار': 'Save node and start auto install',
    'ذخیره Node': 'Save node', 'نام سرور': 'Server name', 'نام نود': 'Node name',
    'آدرس سرور نود': 'Node server address', 'آدرس سرور نود برای SSH': 'Node SSH address',
    'دامنه داخل کانفیگ نود': 'Node config domain', 'دامنه SSL سرور نود': 'Node SSL domain',
    'دامنه‌ای که داخل کانفیگ کاربر قرار می‌گیرد؛ در سناریوی تانل می‌تواند دامنه تانل باشد.': 'Domain placed in the user config; in tunnel scenarios it can be the tunnel domain.',
    'برای certbot/SSL روی خود نود؛ باید مستقیم به IP نود resolve شود. خالی': 'For certbot/SSL on the node; it must resolve directly to the node IP. Empty',
    'اگر خالی باشد همان آدرس سرور نود استفاده می‌شود': 'If empty, the node server address is used.',
    'اطلاعات SSH برای نصب خودکار': 'SSH credentials for auto install', 'دستور نصب نود': 'Node install command',
    'دستورات تست دستی': 'Manual test commands', 'نصب ساده نود': 'Simple node install',
    'نصب خودکار SSH فقط برای لایسنس‌های Pro و Admin فعال است.': 'SSH auto install is available only for Pro and Admin licenses.',
    'هنوز نودی ثبت نشده است. از فرم بالا اولین Direct Location را اضافه کن.': 'No node has been added yet. Add the first Direct Location from the form above.',
    'این نود حذف شود؟': 'Delete this node?', 'Sync همه کاربران روی نودها': 'Sync all users to nodes',
    'Sync همه کاربران': 'Sync all users', 'Sync همه پروتکل‌ها': 'Sync all protocols', 'Sync همه نودها': 'Sync all nodes',

    # protocols / network
    'تنظیم پورت‌ها': 'Port settings', 'پورت': 'Port', 'پورت‌ها': 'Ports', 'پورت پنل': 'Panel port',
    'پورت Xray': 'Xray port', 'پورت API آمار Xray': 'Xray statistics API port',
    'پورت‌ها و Transport پروتکل‌ها': 'Protocol ports and transports', 'TCP فقط': 'TCP only', 'TCP درخواست‌شده': 'Requested TCP',
    'UDP استاندارد': 'Standard UDP', 'SSL خودکار برای پنل و پروتکل‌ها': 'Auto SSL for panel and protocols',
    'گواهی SSL': 'SSL certificate', 'گرفتن SSL و اعمال روی سرویس‌ها': 'Issue SSL and apply to services',
    'درخواست SSL': 'Request SSL', 'تمدید همه SSLها': 'Renew all SSLs', 'دامنه': 'Domain', 'دامنه‌ها': 'Domains',
    'هاست عمومی': 'Public host', 'Host اصلی پنل': 'Panel main host', 'آدرس اختصاصی پنل': 'Dedicated panel URL',
    'دامنه یا IP که کاربرها در کانفیگ می‌بینند.': 'Domain or IP shown to users in configs.',
    'اگر دامنه یا ساب‌دامنه وارد کنی، لینک‌های Subscription، QR، پیام‌های بات و API از آن استفاده می‌کنند.': 'If you enter a domain/subdomain, subscription links, QR codes, bot messages and API URLs will use it.',
    'فایروال': 'Firewall', 'IP یا CIDR': 'IP or CIDR', 'افزودن IP Ban': 'Add IP ban',
    'IPهای بن‌شده': 'Banned IPs', 'اعمال دوباره قوانین': 'Reapply rules', 'این IP از لیست بن حذف شود؟': 'Remove this IP from the ban list?',
    'DNSهای آماده': 'DNS presets', 'افزودن DNS دلخواه': 'Add custom DNS', 'پروفایل‌های DNS': 'DNS profiles',
    'تنظیمات WireGuard DNS': 'WireGuard DNS settings', 'ذخیره تنظیمات WireGuard': 'Save WireGuard settings',
    'چند DNS را با کاما جدا کن.': 'Separate multiple DNS servers with commas.',
    'محدودیت سرعت': 'Speed limits', 'محدودیت سرعت برای هر کاربر روی هر پروتکل': 'Speed limits per user per protocol',
    'مقدار پیش‌فرض هر پروتکل برای هر کاربر': 'Default value per protocol per user',
    'قوانین مسیریابی': 'Routing rules', 'قوانین مسیر خروجی پروتکل‌ها': 'Protocol outbound routing rules',
    'اوتباند / Outbound Manager': 'Outbound manager', 'تنظیمات Outbound': 'Outbound settings',
    'ساخت Outbound Profile': 'Create outbound profile', 'ساخت پروفایل Outbound': 'Create outbound profile',
    'کانفیگ اوتباند': 'Outbound config', 'کانفیگ اوتباند را اینجا وارد کن': 'Paste outbound config here',

    # xray/hysteria/telegram
    'تنظیمات هسته و Inbound': 'Core and inbound settings', 'Xray فعال باشد': 'Enable Xray',
    'انتخاب نوع کانفیگ Xray': 'Select Xray config type', 'تست Xray': 'Test Xray',
    'تست کانفیگ Xray قبل از تحویل به کاربر.': 'Test Xray config before delivery to users.',
    'ذخیره و بازسازی Xray': 'Save and rebuild Xray', 'ساخت خودکار کلید Reality': 'Generate Reality keys automatically',
    'مدیریت پروکسی تلگرام': 'Telegram proxy management', 'تنظیمات Telegram Proxy': 'Telegram Proxy settings',
    'کاربران Telegram Proxy': 'Telegram Proxy users', 'همه کاربران از همین پورت استفاده می‌کنند؛ تفکیک با Secret انجام می‌شود.': 'All users use this port; users are separated by secret.',
    'تنظیمات تلگرام': 'Telegram settings', 'ربات ادمین': 'Admin bot', 'ربات مدیریتی تلگرام': 'Telegram admin bot',
    'ربات مدیریتی فعال باشد': 'Enable admin bot', 'ربات فروش': 'Sales bot', 'ربات فروش فعال باشد': 'Enable sales bot',
    'اتصال ربات': 'Bot connection', 'ارسال پیام تست تلگرام': 'Send Telegram test message',
    'ارسال گزارش تست': 'Send test report', 'ارسال QR': 'Send QR', 'پیام‌های ربات': 'Bot messages',
    'پیام خوش‌آمد /start': 'Welcome message /start', 'متن راهنمای پرداخت': 'Payment guide text',
    'قوانین ربات': 'Bot rules', 'راهنمای اتصال': 'Connection guide', 'لینک پشتیبانی': 'Support link',
    'Telegram ID مدیرهای فروش': 'Sales admin Telegram IDs', 'Telegram ID مدیرهای مجاز': 'Allowed admin Telegram IDs',

    # business / reseller / sales
    'پلن': 'Plan', 'پلن‌ها': 'Plans', 'پلن‌های فروش': 'Sales plans', 'پلن‌های فعال و غیرفعال': 'Enabled and disabled plans',
    'ساخت پلن': 'Create plan', 'ساخت پلن فروش': 'Create sales plan', 'نام پلن': 'Plan name',
    'قیمت': 'Price', 'واحد پول': 'Currency', 'مدت': 'Duration', 'حجم، قیمت، پروتکل‌ها': 'Traffic, price and protocols',
    'این پلن حذف شود؟': 'Delete this plan?', 'سفارش‌ها': 'Orders', 'سفارش‌ها و کیف پول': 'Orders and wallet',
    'سفارشی ثبت نشده است.': 'No order has been registered.', 'مشتری‌ها': 'Customers', 'مشتریان تلگرام': 'Telegram customers',
    'هنوز مشتری ثبت نشده است.': 'No customer has been registered yet.',
    'کیف پول': 'Wallet', 'موجودی': 'Balance', 'مبلغ': 'Amount', 'تراکنش‌ها': 'Transactions',
    'مالی و فاکتورها': 'Billing and invoices', 'ربات فروش IronPanel': 'IronPanel sales bot',
    'مدیریت ربات فروش': 'Sales bot management', 'خوش‌آمد، قوانین، پرداخت': 'Welcome, rules and payment',
    'تأیید، رد، کیف پول': 'Approve, reject and wallet', 'تایید خودکار سفارش بعد از رسید': 'Auto approve orders after receipt',
    'زمان تایید خودکار دقیقه': 'Auto approval time in minutes',
    'اگر فعال باشد، سفارش‌های receipt_sent که در این زمان رد/تأیید نشوند خودکار تأیید می‌شوند.': 'If enabled, receipt_sent orders that are not approved/rejected within this time are approved automatically.',
    'دکمه‌های شیشه‌ای ربات': 'Bot inline buttons', 'افزودن نام به کانفیگ': 'Add name to config',
    'نام پایه کانفیگ': 'Config base name', 'اگر گزینه بالا فعال باشد، نام کاربری به شکل name-12345 ساخته می‌شود؛ اگر غیرفعال باشد فقط عدد ۵ رقمی ساخته می‌شود.': 'If enabled, usernames are created as name-12345; if disabled, only a 5-digit number is used.',
    'ایجاد نماینده جدید': 'Create new reseller', 'لیست نمایندگان': 'Reseller list',
    'نام کاربری نماینده': 'Reseller username', 'رمز ورود نماینده': 'Reseller login password',
    'آدرس پنل نماینده': 'Reseller panel URL', 'مسیر پنل': 'Panel path', 'مصرف ثبت‌شده نماینده': 'Recorded reseller usage',
    'سقف کاربر': 'User limit', 'سقف تعداد کاربر': 'User count limit', 'سقف حجم': 'Traffic quota',
    'حذف نماینده': 'Delete reseller', 'حذف فقط نماینده؛ کاربران باقی بمانند': 'Delete only reseller; keep users',
    'حذف نماینده و غیرفعال کردن کاربرانش': 'Delete reseller and disable users',
    'حذف نماینده و حذف کاربرانش': 'Delete reseller and delete users',
    'نماینده با همان نام کاربری و رمز خودش از لینک اختصاصی وارد می‌شود.': 'The reseller signs in with their own username and password from the dedicated link.',
    'هنوز نماینده‌ای ساخته نشده است.': 'No reseller has been created yet.',

    # security / system
    'مرکز امنیت': 'Security center', 'احراز هویت دو مرحله‌ای': 'Two-factor authentication', '۲FA': '2FA',
    'ساخت Recovery Code': 'Generate recovery code', 'تاریخچه ورود': 'Login history', 'آخرین 100 مورد': 'Latest 100 records',
    'آخرین 100 نفر': 'Latest 100 users', 'دسترسی مدیر و پیام /start': 'Admin access and /start message',
    'توکن و مدیرها': 'Token and admins', 'API Tokens': 'API Tokens', 'پردازش Jobهای محلی': 'Process local jobs',
    'Jobهای آپدیت': 'Update jobs', 'Job فعالی وجود ندارد.': 'No active job.', 'Releaseها': 'Releases',
    'ثبت Release': 'Register release', 'ثبت Release داخلی': 'Register internal release',
    'Release داخلی ثبت نشده است.': 'No internal release has been registered.',
    'وضعیت نسخه': 'Version status', 'آخرین وضعیت': 'Last status', 'آخرین آپدیت': 'Last update',
    'تاریخ': 'Date', 'زمان': 'Time', 'موضوع': 'Subject', 'دلیل': 'Reason', 'توضیح': 'Description',
    'یادداشت مدیریتی': 'Admin note', 'دپارتمان': 'Department', 'تیکت‌ها': 'Tickets', 'تیکت جدید': 'New ticket',

    # dashboard/help texts
    'وضعیت کلی': 'Overview', 'نمای کلی و وضعیت سیستم': 'System overview and status',
    'دسترسی سریع به کارهای روزانه': 'Quick access to daily tasks', 'مسیرهای پرکاربرد': 'Common paths',
    'وضعیت سرویس‌ها': 'Service status', 'وضعیت فعلی پنل و سرویس‌ها': 'Current panel and service status',
    'مصرف لحظه‌ای منابع اصلی': 'Live main resource usage', 'تعداد کاربران': 'User count', 'تعداد کاربر': 'Users',
    'روز باقی‌مانده': 'Days remaining', 'آخرین مشاهده': 'Last seen', 'اتصال و دسترسی': 'Connection and access',
    'راهنمای عملکرد': 'Operation guide', 'دستور ترمینال': 'Terminal command', 'آپدیت امن از ترمینال:': 'Safe update from terminal:',
    'این صفحه فقط شاخص‌های لازم برای تصمیم‌گیری سریع را نمایش می‌دهد. برای تنظیمات تخصصی از منوی کناری وارد بخش مربوطه شوید.': 'This page shows only the key indicators for quick decisions. Use the sidebar for advanced settings.',
    'موارد اصلی همیشه قابل مشاهده‌اند؛ پورت‌ها، پروتکل‌ها و تلگرام داخل آکاردئون‌های جدا هستند.': 'Main items stay visible; ports, protocols and Telegram settings are inside separate accordions.',
    'تنظیمات پرتکرار در کارت‌های جدا قرار گرفته‌اند و گزینه‌های سنگین داخل بخش‌های کشویی هستند تا صفحه خلوت بماند.': 'Common settings are placed in separate cards and advanced options are in collapsible sections to keep the page clean.',
    'فیلدهای ضروری در همین کارت هستند. موارد غیرضروری داخل بخش‌های کشویی پایین قرار گرفته‌اند.': 'Required fields are in this card. Optional items are in the collapsible sections below.',
    'این صفحه دوباره مرتب شده': 'This page has been reorganized',
    'هنوز لاگی ثبت نشده است.': 'No log has been recorded yet.', 'هنوز بکاپی ساخته نشده است.': 'No backup has been created yet.',
    'هنوز پلنی ساخته نشده است.': 'No plan has been created yet.', 'هنوز پروفایلی ساخته نشده است.': 'No profile has been created yet.',
    'هنوز rule فعالی گزارش نشده است.': 'No active rule has been reported.', 'هنوز IP بن‌شده‌ای ثبت نشده است.': 'No banned IP has been registered yet.',

    # miscellaneous common words
    'نوع': 'Type', 'نوع اتصال': 'Connection type', 'نوع کانفیگ فعال': 'Active config type', 'حالت': 'Mode',
    'استراتژی': 'Strategy', 'استراتژی پیش‌فرض': 'Default strategy', 'اولویت': 'Priority', 'ترتیب': 'Order',
    'ترتیب نمایش': 'Display order', 'کشور': 'Country', 'موقعیت': 'Location', 'بدون لوکیشن': 'No location',
    'آدرس اتصال:': 'Connection address:', 'آدرس تانل برای کانفیگ‌ها': 'Tunnel address for configs',
    'آدرس اختصاصی پنل': 'Dedicated panel URL', 'ارتباط با پشتیبانی': 'Contact support',
    'روز': 'days', 'روز؛ 0': 'days; 0', 'روز اعتبار 0': 'Validity days 0', 'حجم GB؛ 0': 'Traffic GB; 0',
    '0 یعنی نامحدود': '0 means unlimited', '0 یعنی بدون محدودیت.': '0 means no limit.',
    'خالی': 'Empty', 'خالی یعنی بدون تغییر': 'Empty means no change', 'خالی یعنی همان هاست عمومی.': 'Empty means the public host.',
    'در حال دریافت': 'Loading', 'ثبت نشده': 'Not registered', 'استفاده نشده': 'Unused',
    'روشن': 'On', 'خاموش': 'Off', 'افزایش': 'Increase', 'کاهش': 'Decrease', 'سریع': 'Fast', 'سالم': 'Healthy',
}

_HARDCODED_FA_TO_AR = {
    'داشبورد': 'لوحة التحكم', 'کاربران': 'المستخدمون', 'کاربران و کانفیگ‌ها': 'المستخدمون والملفات',
    'ساخت کاربر': 'إنشاء مستخدم', 'مصرف و گزارش‌ها': 'الاستهلاك والتقارير', 'کاربران آنلاین': 'المتصلون الآن',
    'نمایندگان': 'الوكلاء', 'تنظیمات': 'الإعدادات', 'تنظیمات اصلی': 'الإعدادات الأساسية',
    'زبان و ظاهر': 'اللغة والمظهر', 'خروج امن': 'تسجيل خروج آمن', 'ذخیره': 'حفظ', 'حذف': 'حذف',
    'ویرایش': 'تعديل', 'جستجو': 'بحث', 'دانلود': 'تنزيل', 'وضعیت': 'الحالة', 'فعال': 'مفعل',
    'غیرفعال': 'معطل', 'لایسنس': 'الترخيص', 'نودها': 'العقد', 'مدیریت نودها': 'إدارة العقد',
    'شبکه و دامنه': 'الشبكة والنطاقات', 'فروش و نمایندگان': 'المبيعات والوكلاء', 'امنیت و عملیات': 'الأمان والعمليات',
    'ورود به پنل': 'تسجيل الدخول', 'نام کاربری': 'اسم المستخدم', 'رمز عبور': 'كلمة المرور',
    'ساخت سریع': 'إنشاء سريع', 'بکاپ و بازیابی': 'النسخ الاحتياطي والاستعادة', 'سلامت سیستم': 'صحة النظام',
}

_HARDCODED_FA_TO_RU = {
    'داشبورد': 'Панель', 'کاربران': 'Пользователи', 'کاربران و کانفیگ‌ها': 'Пользователи и конфиги',
    'ساخت کاربر': 'Создать пользователя', 'مصرف و گزارش‌ها': 'Трафик и отчёты', 'کاربران آنلاین': 'Онлайн пользователи',
    'نمایندگان': 'Реселлеры', 'تنظیمات': 'Настройки', 'تنظیمات اصلی': 'Основные настройки',
    'زبان و ظاهر': 'Язык и внешний вид', 'خروج امن': 'Безопасный выход', 'ذخیره': 'Сохранить', 'حذف': 'Удалить',
    'ویرایش': 'Изменить', 'جستجو': 'Поиск', 'دانلود': 'Скачать', 'وضعیت': 'Статус', 'فعال': 'Включено',
    'غیرفعال': 'Отключено', 'لایسنس': 'Лицензия', 'نودها': 'Узлы', 'مدیریت نودها': 'Управление узлами',
    'شبکه و دامنه': 'Сеть и домены', 'فروش و نمایندگان': 'Продажи и реселлеры', 'امنیت و عملیات': 'Безопасность и операции',
    'ورود به پنل': 'Вход в панель', 'نام کاربری': 'Имя пользователя', 'رمز عبور': 'Пароль',
    'ساخت سریع': 'Быстро создать', 'بکاپ و بازیابی': 'Резервные копии и восстановление', 'سلامت سیستم': 'Состояние системы',
}

_LEGACY_FA_UI_PHRASES = (
    'برای نزدیک\u200cشدن به تجربه 3x-ui، می\u200cتوانی چند inbound فعال داشته باشی. فایل xray.txt هر کاربر در این حالت چند لینک قابل Import تحویل می\u200cدهد.',
    'DNSهای معروف به\u200cصورت خودکار اضافه می\u200cشوند. می\u200cتوانی هر پروفایل را به عنوان DNS کانفیگ WireGuard اعمال کنی یا DNS دلخواه خودت را اضافه کنی.',
    'قبل از هر ریستور، یک بکاپ محافظ ساخته می\u200cشود. فایل بکاپ شامل دیتابیس، تنظیمات، پروفایل\u200cها، SSL، systemd و در صورت انتخاب، سورس پنل است.',
    'کانفیگ به عنوان OpenVPN Client روی سرور بالا می\u200cآید و ترافیک پروتکل\u200cهای انتخابی با policy routing از interface اوتباند عبور می\u200cکند.',
    'مدیریت عمومی دامنه\u200cها در سطح Network است؛ گرفتن SSL خودکار برای همه لایسنس\u200cها از بخش جداگانه Auto SSL در منوی VPN در دسترس است.',
    'برای گرفتن SSL روی خود نود استفاده می\u200cشود و باید مستقیم به IP سرور نود وصل باشد. اگر خالی باشد از دامنه کانفیگ استفاده می\u200cشود.',
    'بعد از ذخیره، اگر مصرف ضریب\u200cخورده کاربری به سقف حجمش رسیده باشد، اکانت همان لحظه غیرفعال و کانفیگ\u200cها از سرویس\u200cها حذف می\u200cشوند.',
    'برای فروش روزمره فقط اطلاعات اصلی را وارد کن. تنظیمات پیشرفته مثل پروتکل\u200cها داخل بخش کشویی قرار گرفته\u200cاند تا صفحه خلوت بماند.',
    'بعد از ساخت کاربر، QR و لینک Subscription را از صفحه کانفیگ کپی کن. اگر سرویس\u200cها خطا داشتند از «Health / Repair» استفاده کن.',
    'کانفیگ\u200cهای سرور اصلی ابتدا نمایش داده می\u200cشوند و سپس هر نود با پرچم لوکیشن، نام سرور و فایل\u200cهای مخصوص همان نود قرار می\u200cگیرد.',
    'کانفیگ URI به outbound داخل Xray تبدیل می\u200cشود. اگر Xray انتخاب شود، inbound کاربران Xray مستقیماً به upstream منتقل می\u200cشود.',
    'درصد پیشرفت، مرحله فعلی و لاگ اجرا داخل همین صفحه نمایش داده می\u200cشود. طراحی جدید لاگ\u200cها و فرم\u200cهای داخلی را خلوت\u200cتر کرده است.',
    'فرم ساخت کاربر داخل بخش کشویی قرار گرفته تا لیست کاربران خلوت و سریع بماند. روی موبایل همه کارت\u200cها خوانا و قابل لمس هستند.',
    'این کاربران در config.json هسته Xray قرار می\u200cگیرند. اگر کاربر منقضی/غیرفعال شود یا حجمش تمام شود، از Xray هم حذف می\u200cشود.',
    'این صفحه فقط مدل جدید Direct Location را نگه می\u200cدارد: دامنه کانفیگ نود + پورت\u200cهای هر پروتکل + Sync کاربران و حجم مشترک.',
    'این صفحه فقط شاخص\u200cهای لازم برای تصمیم\u200cگیری سریع را نمایش می\u200cدهد. برای تنظیمات تخصصی از منوی کناری وارد بخش مربوطه شوید.',
    'قبل از اعمال runtime، پنل اتصال واقعی را تست می\u200cکند. اگر اتصال برقرار نشود، تنظیمات روی ترافیک کاربران اعمال نمی\u200cشود.',
    'این لیست فقط برای انتخاب مدیر است؛ کاربر نهایی همه کانفیگ\u200cها را دریافت نمی\u200cکند و فقط پروفایل انتخاب\u200cشده فعال می\u200cشود.',
    'اگر گزینه بالا فعال باشد، نام کاربری به شکل name-12345 ساخته می\u200cشود؛ اگر غیرفعال باشد فقط عدد ۵ رقمی ساخته می\u200cشود.',
    'مصرف واقعی با بایت دقیق ذخیره می\u200cشود. اگر ضریب مصرف فعال باشد، مقدار ضریب\u200cخورده برای توقف کاربر استفاده می\u200cشود.',
    'تنظیمات پرتکرار در کارت\u200cهای جدا قرار گرفته\u200cاند و گزینه\u200cهای سنگین داخل بخش\u200cهای کشویی هستند تا صفحه خلوت بماند.',
    'تا مسیر کار واضح باشد: اول ربات را وصل کن، بعد متن\u200cها را تنظیم کن، پلن بساز و در آخر سفارش\u200cها را مدیریت کن.',
    'برای عملیات پرتکرار از دکمه\u200cهای پایین هر کارت استفاده کن. جزئیات پروتکل\u200cها کشویی است تا کارت\u200cها شلوغ نشوند.',
    'Telegram Proxy صفحه اختصاصی دارد؛ نصب، ریپیر، Sync کاربران، Restart و مصرف کاربران از همانجا مدیریت می\u200cشود.',
    'برای امنیت، وارد کردن رمز فعلی الزامی است. اگر نمی\u200cخواهی رمز را تغییر دهی، فیلدهای رمز جدید را خالی بگذار.',
    'این صفحه ساده\u200cتر شد: مدیرهای مجاز، پیام خوش\u200cآمد، گزارش روزانه، بکاپ و هشدارها همه در یک مسیر مشخص هستند.',
    'MTU، PersistentKeepalive و DNSهایی که داخل کانفیگ\u200cهای WireGuard کاربران نوشته می\u200cشود را اینجا تنظیم کن.',
    'اول یک اوتباند بساز، بعد در جدول پایین مشخص کن هر پروتکل از آن اوتباند استفاده کند یا مستقیم خارج شود.',
    'این پروتکل به\u200cصورت فایل آماده تحویل داده می\u200cشود. برای جلوگیری از کپی ناقص، گزینه دانلود در دسترس است.',
    'اگر دامنه یا ساب\u200cدامنه وارد کنی، لینک\u200cهای Subscription، QR، پیام\u200cهای بات و API از آن استفاده می\u200cکنند.',
    'برای هر پروتکل مشخص کن از سرور اصلی سرویس بگیرد، به بالانسر وصل شود یا فقط به یک نود مشخص هدایت شود.',
    'کلید Plus، Pro یا Admin را وارد کنید. بعد از تأیید سرور لایسنس، امکانات همان سطح فوراً آزاد می\u200cشود.',
    'برای فروش فقط Xray، فقط گزینه Xray را روشن بگذار. برای فروش کامل، پروتکل\u200cهای موردنظر را انتخاب کن.',
    'خالی یعنی استفاده از مقدار پیش\u200cفرض پروتکل. عدد 0 یعنی برای همان کاربر و همان پروتکل بدون محدودیت.',
    'مثلاً 2 یعنی هر 1GB مصرف واقعی، 2GB از حجم کاربر کم شود. عدد 0.5 یعنی نصف مصرف واقعی محاسبه شود.',
    'حجم 0 یعنی نامحدود. برای تاریخ انقضا می\u200cتوانی گزینه نامحدود را فعال کنی یا تاریخ جدید ثبت کنی.',
    'زبان رابط کاربری و حالت روشن/تاریک پنل را انتخاب کنید. تغییرات برای تمام صفحات اعمال می\u200cشود.',
    'برای Let’s Encrypt باید دامنه به IP همین سرور وصل باشد و پورت 80 از اینترنت قابل دسترس باشد.',
    'این بخش برای همه نوع لایسنس\u200cها فعال است، ولی تغییر runtime فقط توسط ادمین اصلی انجام می\u200cشود.',
    'Renew hook نصب می\u200cشود تا بعد از تمدید Let’s Encrypt، فایل\u200cها و سرویس\u200cها هم به\u200cروزرسانی شوند.',
    'موارد اصلی همیشه قابل مشاهده\u200cاند؛ پورت\u200cها، پروتکل\u200cها و تلگرام داخل آکاردئون\u200cهای جدا هستند.',
    'فیلدهای ضروری در همین کارت هستند. موارد غیرضروری داخل بخش\u200cهای کشویی پایین قرار گرفته\u200cاند.',
    'اگر فعال باشد، سفارش\u200cهای receipt_sent که در این زمان رد/تأیید نشوند خودکار تأیید می\u200cشوند.',
    'برای قوانین Routing مثل block-ir، geoip:private و geosite دسته\u200cبندی\u200cشده استفاده می\u200cشود.',
    'دامنه\u200cای که داخل کانفیگ کاربر قرار می\u200cگیرد؛ در سناریوی تانل می\u200cتواند دامنه تانل باشد.',
    'از این نسخه، مقدار هر پروتکل یعنی سقف سرعت هر کاربر روی همان پروتکل؛ مثلاً WireGuard',
    'نسخه رایگان Beginner فعال است؛ پنل بدون کلید لایسنس کار می\u200cکند و تاریخ انقضا ندارد.',
    'در INPUT / FORWARD / OUTPUT اجرا می\u200cشوند و قوانین پورت داخل بخش جدا مدیریت می\u200cشوند.',
    'دامنه public_host و tunnel_host برای ساخت کانفیگ کاربران به دامنه SSL تغییر می\u200cکند.',
    'این لیست از OpenVPN status، WireGuard handshake، occtl و PPP hooks خوانده می\u200cشود.',
    'از فرم بالا اولین نماینده را بساز؛ لینک ورود خودش بعد از ساخت نمایش داده می\u200cشود.',
    'سرویس مشترک را می\u200cخواند و مصرف هر Secret را داخل مصرف کل همان کاربر ثبت می\u200cکند.',
    'این آدرس در کانفیگ\u200cهای Subscription جایگذاری می\u200cشود؛ می\u200cتواند دامنه تانل باشد.',
    'tls دارند به certificate/key وصل می\u200cشوند؛ Reality به SSL دامنه\u200cای نیاز ندارد.',
    'اگر مسیر پنل را خالی بگذاری، پنل خودش از روی نام کاربری یک مسیر امن می\u200cسازد.',
    'ویرایش محدودیت\u200cها، لینک پنل و وضعیت هر نماینده از همین جدول انجام می\u200cشود.',
    'OpenVPN .ovpn یا لینک vless:// vmess:// trojan:// ss:// را اینجا وارد کن',
    'Ocserv/AnyConnect و Hysteria2 همیشه به certificate/key جدید وصل می\u200cشوند.',
    'پنل با همان certificate و private key از طریق Gunicorn TLS اجرا می\u200cشود.',
    'همه کاربران از همین پورت استفاده می\u200cکنند؛ تفکیک با Secret انجام می\u200cشود.',
    'هنوز نودی ثبت نشده است. از فرم بالا اولین Direct Location را اضافه کن.',
    'برای جلوگیری از شلوغی صفحه، محتوای فایل\u200cهای طولانی نمایش داده نمی\u200cشود.',
    'برای certbot/SSL روی خود نود؛ باید مستقیم به IP نود resolve شود. خالی',
    'برای هر پروتکل انتخاب کن Direct باشد یا به یکی از اوتباندها وصل شود.',
    '20 Mbps یعنی هر کاربر WireGuard جداگانه 20 Mbps دارد، نه کل پروتکل.',
    'نماینده با همان نام کاربری و رمز خودش از لینک اختصاصی وارد می\u200cشود.',
    'در صورت نیاز، Xray هم به پروفایل VLESS + WebSocket + TLS تغییر کند',
    'اختر لغة الواجهة ووضع السمة. يتم تطبيق التغييرات على جميع الصفحات.',
    'نام کاربری، رمز عبور و در صورت نیاز کد دو مرحله\u200cای را وارد کنید.',
    'این ربات فقط سفارش\u200cها و مشتری\u200cهای همین نماینده را مدیریت می\u200cکند.',
    'برای import سریع، QR را اسکن کنید یا کانفیگ را کپی/دانلود کنید.',
    'حذف کاربر این عدد را تغییر می\u200cدهد، اما مصرف ثبت\u200cشده کم نمی\u200cشود',
    'بعد از ذخیره، لینک کامل در ستون «آدرس پنل» نمایش داده می\u200cشود.',
    'همه فورواردهای نود پاک شود و پروتکل\u200cها به سرور اصلی برگردند؟',
    'با scheme و پورت واقعی پنل ساخته می\u200cشود؛ مثلاً اگر پنل روی',
    'کانفیگ کاربران بازسازی و سرویس\u200cهای VPN ری\u200cاستارت می\u200cشوند.',
    'نصب خودکار SSH فقط برای لایسنس\u200cهای Pro و Admin فعال است.',
    'نود کامل، Health Check، Sync، Failover و Load Balancing',
    'در صورت نیاز ID پروفایل\u200cهای پشتیبان را با کاما وارد کن.',
    'پینگ، CPU/RAM، کاربران آنلاین و وزن نود بررسی می\u200cشود.',
    'ترافیک پروتکل به پروفایل خروجی انتخاب\u200cشده وصل می\u200cشود.',
    'نمونه: اگر 321 وارد شود، لینک نماینده /r/321 می\u200cشود.',
    'قبل از ریستور بکاپ محافظ ساخته می\u200cشود. ادامه می\u200cدهی؟',
    'مدیریت کاربران، کانفیگ\u200cها و نودها در یک نمای تمیز',
    'بدون Multi-Node، ربات فروش، شبکه/دامنه و بخش مالی',
    'chacha20-ietf-poly1305 یا 2022-blake3-aes-128-gcm',
    'اگر نود خراب شود، به نود سالم بعدی منتقل می\u200cشود.',
    'ساخت/ویرایش/حذف کاربر به نود مقصد queue می\u200cشود.',
    'اگر خالی باشد همان آدرس سرور نود استفاده می\u200cشود',
    'Xray/V2Ray، Hysteria2، WireGuard و سایر Coreها',
    'موبایل پایدار: WireGuard + Ocserv + Hysteria2',
    'محدودیت IP برای جلوگیری از اشتراک\u200cگذاری اکانت',
    'لایسنس حذف شود و پنل به Beginner Free برگردد؟',
    'ساخت بکاپ کامل دیتابیس، تنظیمات و پروفایل\u200cها.',
    'این قوانین قبل از قوانین معمولی اجرا می\u200cشوند.',
    'در صورت هم\u200cپوشانی با IP فعلی من هم اعمال شود',
    '0 یعنی نامحدود مگر برای کاربر مقدار جدا بدهی',
    'Reset Service Password / تغییر رمز سرویس\u200cها',
    'همان رمز برای L2TP و Ocserv هم استفاده شود',
    'رفتار کاربران زیرمجموعه بعد از حذف نماینده',
    'دامنه یا IP که کاربرها در کانفیگ می\u200cبینند.',
    'Subscription، QR Code، مانیتورینگ و Backup',
    'بررسی کامل سلامت پنل، پروتکل\u200cها و زیرساخت',
    'پروتکل\u200cهایی که باید از اوتباند عبور کنند',
    'محدودیت سرعت برای هر کاربر روی هر پروتکل',
    'رمز جدید برای L2TP و Ocserv هم تنظیم شود',
    'پروتکل مستقیم از سرور اصلی خارج می\u200cشود.',
    'نشست\u200cهای فعال با طراحی کارتی و قابل لمس',
    'دستگاه\u200cهای قدیمی: OpenVPN + L2TP + PPTP',
    'برای جلوگیری از قفل\u200cشدن تصادفی، بن کردن',
    'این دستور را روی سرور نود اجرا کن. آدرس',
    'کانفیگی برای این کاربر ساخته نشده است.',
    'مصرف کاربران با نمای خلوت و قابل بررسی',
    'شماره کارت، توضیحات پرداخت یا درگاه...',
    'تست کانفیگ Xray قبل از تحویل به کاربر.',
    'به ربات مدیریتی IronPanel خوش آمدید...',
    'برای Subscription این QR را اسکن کنید:',
    'مقدار پیش\u200cفرض هر پروتکل برای هر کاربر',
    'ساخت کاربر و تحویل کانفیگ، بدون شلوغی',
    'بعد از اعمال چه چیزهایی تغییر می\u200cکند؟',
    'اگر نود Online نشد، روی سرور نود بزن:',
    'Xray Pro Builder - چند Inbound همزمان',
    'در Xray فقط پروفایل\u200cهایی که security',
    'حذف فقط نماینده؛ کاربران باقی بمانند',
    'حذف شود؟ این عملیات قابل برگشت نیست.',
    'tunnel.example.com یا de.example.com',
    'Subscription Outputs و قالب صفحه ساب',
    '/status یا /user USER یا /reset USER',
    'نمایش متن خام کانفیگ\u200cها در صفحه ساب',
    'مدیریت کامل Xray با یک پروفایل فعال',
    'لایسنس تجاری فعال است و امکانات سطح',
    'حذف نماینده و غیرفعال کردن کاربرانش',
    'به ربات فروش IronPanel خوش آمدید...',
    'بدون نیاز به فعال\u200cسازی و بدون انقضا',
    'Reset forwards / برگشت به سرور اصلی',
    'همگام\u200cسازی همه کاربران با هسته\u200cها.',
    'سرعت و عبور بهتر: Xray + Hysteria2',
    'بعد از تغییر پورت پنل، سرویس را با',
    'اندازه\u200cگیری پینگ زنده در همین صفحه',
    'آپدیت زنده، مرحله\u200cای و قابل پیگیری',
    'کانفیگ\u200cهای تحویلی در Subscription',
    'پنل نماینده بعد از ساخت فعال باشد',
    'فایروال تمیز، قابل کنترل و امن\u200cتر',
    'ذخیره و اعمال روی محدودیت کاربران',
    'تنظیمات اصلی پنل، مرتب و مرحله\u200cای',
    'برای توسعه\u200cهای بعدی Load Balance.',
    'این کاربر و کانفیگ\u200cهایش حذف شوند؟',
    'این پروفایل و ruleهای آن حذف شود؟',
    'الزامی برای پروتکل\u200cهای انتخاب\u200cشده',
    'پنل این نماینده دوباره فعال شود؟',
    'مدیریت کاربران و پروتکل\u200cهای اصلی',
    'صفحه کانفیگ\u200cها خودکار باز می\u200cشود',
    'برای مسیر نماینده مقدار ساده مثل',
    'Sync خودکار کاربران روی نود مقصد',
    'کانفیگ اوتباند را اینجا وارد کن',
    'هنوز نماینده\u200cای ساخته نشده است.',
    'هنوز rule فعالی گزارش نشده است.',
    'هنوز IP بن\u200cشده\u200cای ثبت نشده است.',
    'فعال\u200cسازی Gateway روی سرور اصلی',
    'حذف لایسنس و بازگشت به Beginner',
    'بکاپ و ریستور حرفه\u200cای IronPanel',
    'ایجاد نماینده و نمایش لینک ورود',
    'SSL خودکار برای پنل و پروتکل\u200cها',
    'Kill switch در صورت قطع اوتباند',
    'Failover خودکار بین نودهای سالم',
    'Beginner فقط openvpn,xray دارد.',
    'گرفتن SSL و اعمال روی سرویس\u200cها',
    'دامنه را وارد کن و دکمه را بزن',
    'تایید خودکار سفارش بعد از رسید',
    'اجرای بررسی IP Limit همین حالا',
    '203.0.113.10 یا 203.0.113.0/24',
    'کاربری برای گزارش وجود ندارد.',
    'پیشنهادی: همه پروتکل\u200cهای فعال',
    'پورت\u200cها و Transport پروتکل\u200cها',
    'پنل نیاز به لایسنس معتبر دارد',
    'هنوز پروفایلی ساخته نشده است.',
    'برای کارهای روزمره و خلوت\u200cتر.',
    'برای دسترسی به تنظیمات تخصصی.',
    'WireGuard و Hysteria2 پیشرفته',
    'گزارش روزانه مصرف و سرویس\u200cها',
    'مدیریت کامل پنل\u200cهای نمایندگی',
    'شروع از مسیر POST / fallback',
    'ساخت کاربر و نمایش کانفیگ\u200cها',
    'ریستور سورس پنل هم انجام شود',
    'ذخیره Builder و بازسازی Xray',
    'دسترسی سریع به کارهای روزانه',
    'خروجی\u200cهای حرفه\u200cای سابسکریپشن',
    'حساب کاربری امن، ساده و مرتب',
    'حجم مصرفی این کاربر صفر شود؟',
    'لینک آموزش نصب کلاینت\u200cها...',
    'قوانین مسیر خروجی پروتکل\u200cها',
    'برای این سرور آزاد شده\u200cاند.',
    'افزودن/بازسازی DNSهای معروف',
    'اطلاعات SSH برای نصب خودکار',
    'Release داخلی ثبت نشده است.',
    '1.2.3.4 یا node.example.com',
    '⬆️ شروع آپدیت و نصب خودکار',
    'چند DNS را با کاما جدا کن.',
    'پنل این نماینده متوقف شود؟',
    'هنوز بکاپی ساخته نشده است.',
    'هشدار انقضا قبل از چند روز',
    'نصب، سینک و Direct Runtime',
    'قوانین استفاده از سرویس...',
    'ساده، مناسب استفاده روزمره',
    'ریستور این بکاپ انجام شود؟',
    'دسترسی امن به کنسول مدیریت',
    'خالی یعنی همان هاست عمومی.',
    'حذف نماینده و حذف کاربرانش',
    'حالت چند Inbound فعال باشد',
    'به\u200cروزرسانی SSH Credential',
    'بازنشانی Presetهای Builder',
    'این IP از لیست بن حذف شود؟',
    'اوتباند / Outbound Manager',
    'اتصال پروتکل\u200cها به اوتباند',
    'Sync همه کاربران روی نودها',
    'Mux در لینک خروجی فعال شود',
    'کاربران دارای این پروتکل:',
    'پیشرفته، نمایش همه بخش\u200cها',
    'وضعیت فعلی پنل و سرویس\u200cها',
    'و بدون SSL باشد، دستور با',
    'هنوز پلنی ساخته نشده است.',
    'نودی برای این پروتکل نیست',
    'فعال\u200cسازی یا تغییر لایسنس',
    'رمزنگاری\u200cشده ذخیره می\u200cشود',
    'دسترسی مدیر و پیام /start',
    'دامنه / Host اختصاصی Xray',
    'ثبت نود و شروع نصب خودکار',
    'IP Banها با chain اختصاصی',
    'Fixed Only / فقط همین نود',
    'گرفتن و اعمال خودکار SSL',
    'کاربران آنلاین و نشست\u200cها',
    'پروتکل\u200cها و پورت\u200cهای نود',
    'ویرایش، تمدید و خروجی\u200cها',
    'هنوز مشتری ثبت نشده است.',
    'هسته\u200cها، تنظیمات و سلامت',
    'نمای سریع سرویس\u200cهای اصلی',
    'قانون پورت ثبت نشده است.',
    'ساخت خودکار کلید Reality',
    'ذخیره و اعمال محدودیت\u200cها',
    'دسترسی، API، لاگ و آپدیت',
    'خالی یعنی بدون تغییر رمز',
    'برای بکاپ دستی روی سرور:',
    'باز کردن صفحه سابسکریپشن',
    'این صفحه دوباره مرتب شده',
    'استفاده از دامنه کانفیگ.',
    'اتصال پروتکل به Outbound',
    'آدرس تانل برای کانفیگ\u200cها',
    'آخرین خطای تشخیص آنلاین:',
    'Telegram ID مدیرهای مجاز',
    'Telegram ID مدیرهای فروش',
    'Override اختصاصی کاربران',
    'کد 2FA یا Recovery Code',
    'پیش\u200cنمایش گزارش مدیریتی',
    'پلن، پرداخت و ربات فروش',
    'هنوز لاگی ثبت نشده است.',
    'مصرف لحظه\u200cای منابع اصلی',
    'لمساحة عمل مكتبية واضحة',
    'فایروال، DNS و دامنه\u200cها',
    'زمان تایید خودکار دقیقه',
    'ذخیره تنظیمات WireGuard',
    'خوش\u200cآمد، قوانین، پرداخت',
    'ایجاد و نمایش کانفیگ\u200cها',
    'یا loopback مجاز نیست.',
    'کانفیگ\u200cها بر اساس سرور',
    'کاربران و خروجی کانفیگ',
    'کاربران Telegram Proxy',
    'پلن\u200cهای فعال و غیرفعال',
    'پروفایل و تنظیمات شخصی',
    'وضعیت Runtime روی سرور',
    'نمای کلی و وضعیت سیستم',
    'مدیریت GeoIP و GeoSite',
    'محاسبه مصرف ضریب\u200cخورده',
    'للبيئات منخفضة الإضاءة',
    'سلامت و تعمیر سرویس\u200cها',
    'ربات مدیریتی فعال باشد',
    'ربات مدیریتی IronPanel',
    'رابط رسمی مدیریت سرویس',
    'ذخیره و ری\u200cاستارت ربات',
    'تنظیمات هسته و Inbound',
    'تنظیمات Telegram Proxy',
    'انتخاب نوع کانفیگ Xray',
    'ارسال فایل بکاپ روزانه',
    'احراز هویت دو مرحله\u200cای',
    'آدرس سرور نود برای SSH',
    'Rebalance کاربران Auto',
    '0 یعنی پیش\u200cفرض/نامحدود',
    'یا تعداد روز از امروز',
    'گزارش، بکاپ و هشدارها',
    'مثلاً Germany OpenVPN',
    'فایل آماده دانلود است',
    'ساخت پروفایل Outbound',
    'ساخت Outbound Profile',
    'ریستور از فایل آپلودی',
    'ذخیره و اعمال تنظیمات',
    'ذخیره و Apply Gateway',
    'ذخیره تنظیمات پیشرفته',
    'دکمه\u200cهای شیشه\u200cای ربات',
    'دانلود و نصب GeoFiles',
    'دامنه داخل کانفیگ نود',
    'تنظیمات WireGuard DNS',
    'ایجاد سریع سرویس جدید',
    'انتخاب دستی پروتکل\u200cها',
    'ارسال پیام تست تلگرام',
    'آپگرید سریع شروع شود؟',
    'آپدیت امن از ترمینال:',
    'Job فعالی وجود ندارد.',
    'Direct / بدون اوتباند',
    'وصل مجدد پنل نماینده',
    'هماهنگ با سیستم عامل',
    'مصرف ثبت\u200cشده نماینده',
    'مدیریت پروکسی تلگرام',
    'مثلاً یک ماهه 50 گیگ',
    'فعال بعد از تست موفق',
    'فعال برای این پروتکل',
    'سفارشی ثبت نشده است.',
    'راهنمای لینک نماینده',
    'ذخیره و بازسازی Xray',
    'خالی یعنی بدون تغییر',
    'حجم، قیمت، پروتکل\u200cها',
    'بررسی و اعمال لایسنس',
    'برای محیط\u200cهای کم\u200cنور',
    'برای محیط اداری روشن',
    'افزودن نام به کانفیگ',
    '0 یعنی بدون محدودیت.',
    'کمترین کاربر آنلاین',
    'کاربران و کانفیگ\u200cها',
    'پیام خوش\u200cآمد /start',
    'پروتکل\u200cها و پورت\u200cها',
    'هم پشتیبانی می\u200cشود.',
    'نسخه جدید آماده است',
    'ماتریس SSL سرویس\u200cها',
    'فعال\u200cسازی ضریب مصرف',
    'زیرساخت و پروتکل\u200cها',
    'ربات مدیریتی تلگرام',
    'ربات فروش فعال باشد',
    'ربات فروش IronPanel',
    'ذخیره تنظیمات هشدار',
    'ذخیره Routing Rules',
    'اعمال دوباره قوانین',
    '. سرویس alias قدیمی',
    'گزارش مصرف کاربران',
    'کنسول مدیریت سرویس',
    'کاربری وجود ندارد.',
    'پورت API آمار Xray',
    'پردازش Jobهای محلی',
    'ورود به پنل مدیریت',
    'هشدار مصرف در درصد',
    'نوع کانفیگ اوتباند',
    'نصب و مدیریت نودها',
    'نام کاربری نماینده',
    'مسیر پیشنهادی بعدی',
    'متن راهنمای پرداخت',
    'مانیتورینگ پیشرفته',
    'غیرفعال\u200cسازی کاربر',
    'سفارش\u200cها و کیف پول',
    'ساخت Recovery Code',
    'ذخیره و همگام\u200cسازی',
    'ذخیره تغییرات حساب',
    'دامنه SSL سرور نود',
    'حد اختصاصی کاربران',
    'تغییر اطلاعات ورود',
    'ترافیک و آمار مصرف',
    'تأیید، رد، کیف پول',
    'ایجاد نماینده جدید',
    'اطلاعات اصلی کاربر',
    'ارتباط با پشتیبانی',
    'Sync همه پروتکل\u200cها',
    'Sniffing فعال باشد',
    'Mbps برای هر کاربر',
    'IP Limit فعال باشد',
    '🔗 لینک سابسکریپشن',
    '👤 اطلاعات کاربران',
    'کاربران فعال Xray',
    'پیش\u200cنمایش کاربران',
    'پروفایل\u200cهای موجود',
    'پایان نشست مدیریت',
    'يتبع نظام التشغيل',
    'ورود به IronPanel',
    'نام / توضیح کوتاه',
    'مصرف کاربران فعلی',
    'محدودیت IP/دستگاه',
    'مثلاً reseller321',
    'قانون معمولی پورت',
    'فعال روی این سرور',
    'ضریب مصرف کاربران',
    'رمز پنل / پیش\u200cفرض',
    'ذخیره و Sync مجدد',
    'در صورت فعال بودن',
    'ثبت Release داخلی',
    'بررسی و فعال\u200cسازی',
    'این نشست قطع شود؟',
    'اگر user روت نیست',
    'افزودن DNS دلخواه',
    'آخرین نسخه GitHub',
    'Xray Core پیشرفته',
    'Local / سرور اصلی',
    '👥 کاربران آنلاین',
    'کلاستر و پایداری',
    'کاربری یافت نشد.',
    'پورت\u200cهای فوروارد',
    'پلن فعلی Gateway',
    'پروتکل\u200cهای کاربر',
    'مسیرهای پرکاربرد',
    'مدیریت ربات فروش',
    'مجموع ضریب\u200cخورده',
    'مانیتورینگ منابع',
    'لیست قوانین پورت',
    'فروش و نمایندگان',
    'فروش و دسترسی\u200cها',
    'سقف حجم مصرفی GB',
    'ساخت بکاپ روزانه',
    'رمز ورود نماینده',
    'رمز Cisco/Ocserv',
    'رفتن به Auto SSL',
    'رفتار اضافه\u200cمصرف',
    'ذخیره قانون پورت',
    'ذخیره حد کاربران',
    'دستورات تست دستی',
    'حالت رابط کاربری',
    'توقف پنل نماینده',
    'تنظیمات ساده پنل',
    'تنظیمات Outbound',
    'تعداد ردیف گزارش',
    'این پلن حذف شود؟',
    'این نود حذف شود؟',
    'ایمیل صدور گواهی',
    'استراتژی پیش\u200cفرض',
    'آدرس پنل نماینده',
    'آدرس اختصاصی پنل',
    'Sync همه کاربران',
    'IP Limit کاربران',
    'یادداشت مدیریتی',
    'کاربر فعال باشد',
    'پروفایل\u200cهای DNS',
    'پروتکل\u200cهای فعال',
    'وضعیت آخرین تست',
    'هشدار ورود مدیر',
    'نوع کانفیگ فعال',
    'نصب، Sync و لاگ',
    'نام کاربری مدیر',
    'نام کاربری جدید',
    'نام پایه کانفیگ',
    'مصرف ضریب\u200cخورده',
    'مثلاً VIP یا CH',
    'مالی و فاکتورها',
    'قوانین مسیریابی',
    'قانون هر پروتکل',
    'صفحه سابسکراپشن',
    'سقف تعداد کاربر',
    'ساخت کاربر جدید',
    'ساخت سریع کاربر',
    'زبان، تم و ظاهر',
    'ربات فعال بماند',
    'ذخیره Route Map',
    'ثبت لایسنس جدید',
    'تمدید همه SSLها',
    'به\u200cروز / نامشخص',
    'افزودن نود جدید',
    'ارسال گزارش تست',
    'اختصاصی نماینده',
    'آپدیت موجود است',
    '· وضعیت دسترسی:',
    'TCP درخواست\u200cشده',
    'QR Code / کد QR',
    '🗄 درخواست بکاپ',
    '📱 آماده موبایل',
    'کانفیگ اوتباند',
    'وضعیت سرویس\u200cها',
    'نامحدود. حجم 0',
    'موجودی کاربران',
    'مشتریان تلگرام',
    'مدیریت کاربران',
    'لیست نمایندگان',
    'لایسنس و ارتقا',
    'لاگ آپدیت زنده',
    'روز باقی\u200cمانده',
    'راهنمای عملکرد',
    'ذخیره قالب ساب',
    'تکرار رمز جدید',
    'تنظیمات تکمیلی',
    'تنظیمات تلگرام',
    'بکاپ و بازیابی',
    'امنیت و عملیات',
    'اعمال روی سرور',
    'اتصالات آنلاین',
    'اتصال و دسترسی',
    'آخرین 100 مورد',
    'Xray فعال باشد',
    'Sync همه نودها',
    'Outbound قدیمی',
    '0 یعنی نامحدود',
    '+ نماینده جدید',
    'پیام\u200cهای ربات',
    'پلن فعال باشد',
    'وضعیت فایل\u200cها',
    'هر دقیقه فایل',
    'نیازمند تنظیم',
    'نمای کامل پنل',
    'مقایسه سطح\u200cها',
    'مدیریت لایسنس',
    'مثلاً ali-30d',
    'لینک پشتیبانی',
    'لاگ\u200cهای سیستم',
    'عملیات هوشمند',
    'عملیات روزانه',
    'شامل سورس پنل',
    'ساخته می\u200cشود.',
    'ساخت پلن فروش',
    'ساخت بکاپ امن',
    'ری\u200cاستارت کن.',
    'رمز جدید مدیر',
    'رایگان و فعال',
    'راهنمای اتصال',
    'ذخیره پروفایل',
    'ذخیره و اعمال',
    'ذخیره و Apply',
    'ذخیره تنظیمات',
    'دستور نصب نود',
    'دستور ترمینال',
    'در حال دریافت',
    'حد پیش\u200cفرض IP',
    'توکن و مدیرها',
    'تنظیم پورت\u200cها',
    'تعداد کاربران',
    'ترکیبی هوشمند',
    'تاریخ نامحدود',
    'انتخاب خودکار',
    'افزودن IP Ban',
    'اعتبار کانفیگ',
    'آپدیت GeoFile',
    'آدرس سرور نود',
    'آخرین 100 نفر',
    'UDP استاندارد',
    'Host اصلی پنل',
    'کپی / دانلود',
    'کنسول مدیریت',
    'کمترین کاربر',
    'کاربران متصل',
    'پلن\u200cهای فروش',
    'پروفایل فعلی',
    'ویرایش کاربر',
    'وضعیت لایسنس',
    'ورود نماینده',
    'نمای مدیریتی',
    'نصب ساده نود',
    'نسخه نصب\u200cشده',
    'منبع فایل\u200cها',
    'مدیریت نودها',
    'مدیریت سیستم',
    'مدیریت دامنه',
    'مدیریت آپدیت',
    'محدودیت سرعت',
    'لیست کاربران',
    'غیرفعال\u200cسازی',
    'عملیات سرویس',
    'شبکه و دامنه',
    'سرور لایسنس:',
    'روز اعتبار 0',
    'رمز جدید پنل',
    'ذخیره ویرایش',
    'جستجوی کاربر',
    'جزئیات خطا -',
    'تنظیمات اصلی',
    'تاریخچه ورود',
    'بدون محدودیت',
    'باز کردن منو',
    'باز کردن فرم',
    'استفاده نشده',
    'اتصال همزمان',
    'آخرین مشاهده',
    'TLS فعال است',
    'Label نمایشی',
    'Jobهای آپدیت',
    'IPهای بن\u200cشده',
    'DNSهای آماده',
    '📊 گزارش پنل',
    '⚡ ساخت سریع',
    'پروتکل فعال',
    'وضعیت بررسی',
    'ورود به پنل',
    'نود انتخابی',
    'نام پروفایل',
    'لایسنس فعال',
    'قوانین ربات',
    'فقط ثبت لاگ',
    'سلامت سیستم',
    'زبان و ظاهر',
    'دلیل انتخاب',
    'دستگاه مجاز',
    'درخواست SSL',
    'دانلود فایل',
    'حساب کاربری',
    'حذف نماینده',
    'ثبت Release',
    'تنظیمات کلی',
    'تعداد کاربر',
    'تست و اعمال',
    'ترتیب نمایش',
    'تاریخ انقضا',
    'بهترین پینگ',
    'بعد از ساخت',
    'بدون لوکیشن',
    'باقی\u200cمانده:',
    'انتخاب دستی',
    'افزودن Node',
    'استفاده شده',
    'آدرس اتصال:',
    'آخرین وضعیت',
    'آخرین آپدیت',
    'Repair کامل',
    'Preset ساده',
    'گزارش مصرف',
    'کانفیگ\u200cهای',
    'پروفایل\u200cها',
    'وضعیت نسخه',
    'وضعیت فعلی',
    'وضعیت ربات',
    'هاست عمومی',
    'نسخه فعلی:',
    'نام کاربری',
    'منابع سرور',
    'مصرف واقعی',
    'مسیر خروجی',
    'مرکز امنیت',
    'متن راهنما',
    'فقط مدیرها',
    'ضریب\u200cخورده',
    'شروع آپدیت',
    'سقف حجم GB',
    'ساخت کاربر',
    'سابسکریپشن',
    'روز اعتبار',
    'ربات ادمین',
    'ذخیره Node',
    'حجم تست GB',
    'تنظیم ضریب',
    'تغییر نکند',
    'تست رایگان',
    'بن کامل IP',
    'بدون تغییر',
    'بدون انقضا',
    'باقی\u200cمانده',
    'اتصال ربات',
    'آپدیت جدید',
    'IPهای فعال',
    'IP یا CIDR',
    'گواهی SSL',
    'کد ۶ رقمی',
    'کانفیگ\u200cها',
    'پورت Xray',
    'پنل کاربر',
    'پروتکل\u200cها',
    'وضعیت کلی',
    'وجود دارد',
    'همه نودها',
    'نوع اتصال',
    'نمایندگان',
    'نمای ساده',
    'نشست فعال',
    'نام قانون',
    'منوی اصلی',
    'مدیر اصلی',
    'مثلاً 2,3',
    'فعال\u200cسازی',
    'فعال باشد',
    'ضریب مصرف',
    'سقف کاربر',
    'ساخت سریع',
    'ساخت بکاپ',
    'ربات فروش',
    'حجم مشترک',
    'حجم GB؛ 0',
    'تیکت جدید',
    'تست اتصال',
    'تراکنش\u200cها',
    'اعمال پلن',
    'Releaseها',
    'IP/دستگاه',
    'Host اصلی',
    'کپی لینک',
    'کپی آدرس',
    'پیش\u200cفرض:',
    'پورت پنل',
    'وارد کن.',
    'واحد پول',
    'همان رمز',
    'نود ثابت',
    'نماینده:',
    'نامحدود.',
    'نام سرور',
    'نام برند',
    'مصرف کلی',
    'مشتری\u200cها',
    'مسیر پنل',
    'لاگ زنده',
    'سفارش\u200cها',
    'ساخت پلن',
    'ریست حجم',
    'رنگ اصلی',
    'رمز فعلی',
    'رمز عبور',
    'رمز جدید',
    'رمز L2TP',
    'دپارتمان',
    'دامنه\u200cها',
    'خروج امن',
    'حذف شود؟',
    'ثبت نشده',
    'تست Xray',
    'استراتژی',
    'ارسال QR',
    'آپدیت\u200cها',
    '| واقعی:',
    'کیف پول',
    'کاربران',
    'پیام\u200cها',
    'پورت\u200cها',
    'نماینده',
    'نامحدود',
    'نام پلن',
    'نام نود',
    'مدت تست',
    'غیرفعال',
    'سقف حجم',
    'روی نود',
    'داشبورد',
    'حساب من',
    'تیکت\u200cها',
    'تغییرات',
    'بکاپ\u200cها',
    'با ضریب',
    'اختیاری',
    '· مسیر:',
    'TCP فقط',
    'کپی شد',
    'پلن\u200cها',
    'پروتکل',
    'ویرایش',
    'ناموفق',
    'نامشخص',
    'موجودی',
    'لایسنس',
    'عملیات',
    'ریستور',
    'روزانه',
    'روز؛ 0',
    'دانلود',
    'خودکار',
    'حجم MB',
    'حجم GB',
    'جزئیات',
    'بازگشت',
    'اولویت',
    'افزایش',
    'گزارش',
    'کاربر',
    'وضعیت',
    'واقعی',
    'نودها',
    'نمایش',
    'موضوع',
    'مجموع',
    'متوقف',
    'فعلی:',
    'فعال:',
    'ظرفیت',
    'ضروری',
    'شروع:',
    'ذخیره',
    'دامنه',
    'خاموش',
    'جستجو',
    'توضیح',
    'تعمیر',
    'ترتیب',
    'تاریخ',
    'تأیید',
    'برگشت',
    'انقضا',
    'اعمال',
    'آپلود',
    'آماده',
    'کشور',
    'کاهش',
    'پورت',
    'ورود',
    'واحد',
    'نیست',
    'نوع:',
    'موفق',
    'مصرف',
    'مبلغ',
    'قیمت',
    'فعال',
    'ضریب',
    'سریع',
    'سالم',
    'زمان',
    'ربات',
    'دلیل',
    'خالی',
    'حالت',
    'بکاپ',
    'اصلی',
    'اجرا',
    '۲FA',
    'کپی',
    'پلن',
    'نوع',
    'نام',
    'مدت',
    'متن',
    'سقف',
    'روز',
    'حذف',
    'حجم',
    'ثبت',
    'تست',
    'رد',
    'از',
    '،',
)


# v19.10.1: include every Persian literal found in templates, static JS and Flask flashes.
# This protects non-Persian UI modes from legacy hard-coded labels while the
# source templates are gradually converted to true i18n keys.
try:
    _LEGACY_FA_UI_PHRASES = tuple(sorted(set(_LEGACY_FA_UI_PHRASES) | set(AUTO_FA_UI_PHRASES), key=len, reverse=True))
except Exception:
    pass

_ARABIC_RE = re.compile(r'[\u0600-\u06FF]')
_SKIP_TRANSLATION_MARKERS = ('<script', '<style', '<pre', '<code', '<textarea')



def _guess_legacy_phrase_en(src: str) -> str:
    text = src.strip()
    if not text:
        return text
    if '?' in text or '؟' in text or 'شود' in text and 'حذف' in text:
        suffix = '?' if ('حذف' in text or 'ریستور' in text or 'ریست' in text) else ''
    else:
        suffix = ''
    rules = [
        ('لایسنس', 'License'), ('نماینده', 'Reseller'), ('کاربران آنلاین', 'Online users'), ('کاربران', 'Users'), ('کاربر', 'User'),
        ('نود', 'Node'), ('سرور', 'Server'), ('دامنه SSL', 'SSL domain'), ('دامنه', 'Domain'), ('فایروال', 'Firewall'), ('پورت', 'Port'),
        ('پروتکل', 'Protocol'), ('بکاپ', 'Backup'), ('ریستور', 'Restore'), ('لاگ', 'Logs'), ('سفارش', 'Order'), ('پلن', 'Plan'),
        ('کیف پول', 'Wallet'), ('ربات فروش', 'Sales bot'), ('ربات مدیریتی', 'Admin bot'), ('ربات', 'Bot'), ('تلگرام', 'Telegram'),
        ('ترافیک', 'Traffic'), ('حجم', 'Traffic'), ('مصرف', 'Usage'), ('سرعت', 'Speed'), ('محدودیت', 'Limit'), ('اتصال', 'Connection'),
        ('اشتراک', 'Subscription'), ('سابسکریپشن', 'Subscription'), ('ساب', 'Subscription'), ('کانفیگ', 'Config'), ('DNS', 'DNS'), ('SSL', 'SSL'),
        ('Xray', 'Xray'), ('WireGuard', 'WireGuard'), ('Hysteria2', 'Hysteria2'), ('OpenVPN', 'OpenVPN'), ('Ocserv', 'Ocserv'),
        ('امنیت', 'Security'), ('ورود', 'Login'), ('خروج', 'Logout'), ('ظاهر', 'Appearance'), ('زبان', 'Language'), ('تم', 'Theme'),
        ('تنظیمات', 'Settings'), ('آپدیت', 'Update'), ('وضعیت', 'Status'), ('گزارش', 'Report'), ('تاریخ', 'Date'), ('زمان', 'Time'),
        ('روز', 'Days'), ('رمز', 'Password'), ('نام کاربری', 'Username'), ('نام', 'Name'), ('آدرس', 'Address'), ('لینک', 'Link'), ('کلید', 'Key'),
        ('تست', 'Test'), ('ذخیره', 'Save'), ('حذف', 'Delete'), ('ویرایش', 'Edit'), ('افزودن', 'Add'), ('ساخت', 'Create'), ('دانلود', 'Download'),
        ('آپلود', 'Upload'), ('اعمال', 'Apply'), ('همگام', 'Sync'), ('فعال', 'Enable'), ('غیرفعال', 'Disable'), ('تعمیر', 'Repair'),
        ('لیست', 'List'), ('جدول', 'Table'), ('جزئیات', 'Details'), ('راهنما', 'Guide'), ('قانون', 'Rule'), ('قوانین', 'Rules'),
        ('پروفایل', 'Profile'), ('مسیر', 'Path'), ('اوتباند', 'Outbound'), ('مالی', 'Billing'), ('فاکتور', 'Invoice'), ('تیکت', 'Ticket'),
    ]
    for needle, label in rules:
        if needle in text:
            if text.startswith('ذخیره') and label not in ('Save',):
                return 'Save ' + label.lower()
            if text.startswith('افزودن') and label not in ('Add',):
                return 'Add ' + label.lower()
            if text.startswith('ساخت') and label not in ('Create',):
                return 'Create ' + label.lower()
            if text.startswith('حذف') and label not in ('Delete',):
                return 'Delete ' + label.lower() + (suffix or '')
            if text.startswith('ویرایش') and label not in ('Edit',):
                return 'Edit ' + label.lower()
            return label + suffix
    if len(text) > 28:
        return 'Additional information'
    return 'Details'

def _map_for_lang(lang: str) -> dict[str, str]:
    lang = (lang or current_language()).lower()
    # Auto maps are generated from every known Persian UI literal.  Explicit
    # hand-written translations win, then auto phrase translations fill gaps.
    if lang.startswith('ar'):
        merged = dict(AUTO_FA_TO_AR)
        merged.update(_HARDCODED_FA_TO_AR)
        return merged
    if lang.startswith('ru'):
        merged = dict(AUTO_FA_TO_RU)
        merged.update(_HARDCODED_FA_TO_RU)
        return merged
    merged = dict(AUTO_FA_TO_EN)
    merged.update(_HARDCODED_FA_TO_EN)
    return merged




def _guess_legacy_phrase(src: str, lang: str = 'en') -> str:
    mapping = _map_for_lang(lang)
    if src in mapping:
        return mapping[src]
    base = _guess_legacy_phrase_en(src)
    lang = (lang or 'en').lower()
    if lang.startswith('ar'):
        simple = {
            'Additional information': 'معلومات إضافية', 'Additional settings': 'إعدادات إضافية',
            'Details': 'التفاصيل', 'Access is not allowed.': 'الوصول غير مسموح.',
            'Error details.': 'تفاصيل الخطأ.', 'No item was found.': 'لم يتم العثور على عنصر.'
        }
        return simple.get(base, AUTO_FA_TO_AR.get(src) or base)
    if lang.startswith('ru'):
        simple = {
            'Additional information': 'Дополнительная информация', 'Additional settings': 'Дополнительные настройки',
            'Details': 'Детали', 'Access is not allowed.': 'Доступ запрещён.',
            'Error details.': 'Сведения об ошибке.', 'No item was found.': 'Ничего не найдено.'
        }
        return simple.get(base, AUTO_FA_TO_RU.get(src) or base)
    return base

_ATTR_RE = re.compile(r'(?P<attr>\b(?:placeholder|title|aria-label|value|alt)\s*=\s*["\'])(?P<val>[^"\']*[\u0600-\u06FF][^"\']*)(?P<q>["\'])', re.I)
_TEXT_RE = re.compile(r'>(?P<val>[^<>]*[\u0600-\u06FF][^<>]*)<')
_UI_KEYWORD_RE = re.compile(r'(کاربر|کاربران|کانفیگ|پروتکل|نود|نماینده|پلن|سفارش|لایسنس|تنظیمات|ذخیره|حذف|ویرایش|ساخت|افزودن|دانلود|آپلود|مصرف|حجم|سرعت|دامنه|فایروال|بکاپ|ریستور|لاگ|ربات|تلگرام|ورود|خروج|زبان|تم|ظاهر|راهنما|گزارش|تاریخ|وضعیت|خطا|مجوز|دسترسی|فروش|پرداخت|رسید|فاکتور|اطلاعات|اصلی|برای|اگر|باید|خالی|روز|اعتبار|انقضا|نامحدود|توضیح|پیام|متن|دکمه|فرم|صفحه|مدیریت|سرویس|هسته|پورت|شبکه|مسیر|قانون|قوانین|نمای|سلامت|امنیت|حساب|رمز|نام|آدرس|لینک|کلید|فعال|غیرفعال)')

def _looks_like_static_ui_text(val: str, lang: str = 'en') -> bool:
    compact = re.sub(r'\s+', ' ', (val or '').strip())
    if not compact or not _ARABIC_RE.search(compact):
        return False
    if compact in _LEGACY_FA_UI_PHRASES:
        return True
    if _UI_KEYWORD_RE.search(compact):
        return True
    # In Arabic mode, translated Arabic also uses the Arabic Unicode block; do
    # not treat Arabic output as residual Persian unless it is a known legacy
    # phrase or contains Persian UI keywords.
    if (lang or '').lower().startswith('ar'):
        return False
    # Help/instruction sentences usually contain punctuation or Persian ZWNJ.
    if len(compact) > 18 and any(x in compact for x in (' ', '،', '؛', '؟', '.', ':', '\u200c')):
        return True
    return False


def _translate_chunk_value(val: str, lang: str, mapping: dict[str, str]) -> str:
    raw = val
    core = re.sub(r'\s+', ' ', raw.strip())
    if not _looks_like_static_ui_text(core, lang):
        return raw
    if core in mapping:
        translated = mapping[core]
    else:
        translated = _guess_legacy_phrase(core, lang)
    return raw.replace(core, translated)


def _cleanup_residual_persian_html(out: str, lang: str, mapping: dict[str, str]) -> str:
    """Final HTML bridge for legacy pages.

    Only obvious UI text/attributes are touched.  Values that look like user data
    (for example a Persian username in a table cell) are left intact unless they
    match a known UI literal or contain UI keywords.
    """
    def attr_repl(m):
        return m.group('attr') + _translate_chunk_value(m.group('val'), lang, mapping) + m.group('q')
    def text_repl(m):
        return '>' + _translate_chunk_value(m.group('val'), lang, mapping) + '<'
    out = _ATTR_RE.sub(attr_repl, out)
    # Skip script/style/code/pre/textarea blocks before text replacements.
    parts = re.split(r'(<(?:script|style|pre|code|textarea)\b.*?</(?:script|style|pre|code|textarea)>)', out, flags=re.I | re.S)
    for i, part in enumerate(parts):
        if not part or part.lstrip().lower().startswith(('<script', '<style', '<pre', '<code', '<textarea')):
            continue
        parts[i] = _TEXT_RE.sub(text_repl, part)
    return ''.join(parts)

def localize_hardcoded_text(text: str, lang: str | None = None) -> str:
    """Translate legacy Persian literals in rendered HTML for non-Persian UI languages.

    This is a safe migration bridge while templates are being converted to full
    i18n keys. It is intentionally phrase based; user/API data is not modified
    unless it exactly matches a known legacy UI label.
    """
    lang = (lang or current_language()).lower()
    if not text or lang.startswith('fa') or not _ARABIC_RE.search(text):
        return text
    mapping = _map_for_lang(lang)
    out = text
    for src in sorted(mapping, key=len, reverse=True):
        if src in out:
            out = out.replace(src, mapping[src])
    # Exact fallback for remaining hard-coded phrases that exist in templates.
    # This prevents Persian UI leaks in English/Arabic/Russian modes while
    # preserving user-provided Persian data that does not match a known template literal.
    if _ARABIC_RE.search(out):
        for src in _LEGACY_FA_UI_PHRASES:
            if src in out:
                out = out.replace(src, mapping.get(src) or _guess_legacy_phrase(src, lang))
    if _ARABIC_RE.search(out):
        out = _cleanup_residual_persian_html(out, lang, mapping)
    return out


def ui(fa_text: str, en_text: str | None = None) -> str:
    """Template helper: return the current-language label for a Persian/English pair."""
    lang = current_language().lower()
    if lang.startswith('fa'):
        return fa_text
    mapping = _map_for_lang(lang)
    base = en_text or mapping.get(fa_text) or _HARDCODED_FA_TO_EN.get(fa_text, fa_text)
    return mapping.get(fa_text, base)


# ---------------------------------------------------------------------------
# v19.10.9: strict language/theme policy
# - Theme auto/system mode removed from UI and runtime fallback.
# - Official panel languages are Persian, English, Arabic, Chinese and French.
# - Legacy Persian literals are translated for every non-Persian language,
#   including help text, placeholders and button values.
# ---------------------------------------------------------------------------
LANGUAGES = {
    'en': {'name': 'English', 'dir': 'ltr', 'native': 'English'},
    'ar': {'name': 'Arabic', 'dir': 'rtl', 'native': 'العربية'},
    'zh': {'name': 'Chinese', 'dir': 'ltr', 'native': '简体中文'},
    'fr': {'name': 'French', 'dir': 'ltr', 'native': 'Français'},
    'fa': {'name': 'Persian', 'dir': 'rtl', 'native': 'فارسی'},
}
THEMES = {'dark': 'Dark', 'light': 'Light'}

TRANSLATIONS.update({
    'zh': {
        'dashboard': '仪表盘', 'quick_create': '快速创建用户', 'users': '用户与配置',
        'usage': '用量与报表', 'online_users': '在线用户', 'resellers': '代理商',
        'auto_ssl': '自动 SSL', 'health': '健康检查与修复', 'settings': '核心设置',
        'license': '许可证', 'more_settings': '更多设置', 'appearance': '语言与主题',
        'logout': '退出登录', 'active_version': '当前版本', 'active_host': '当前主机',
        'quick': '快速创建', 'language': '语言', 'theme': '主题', 'save': '保存',
        'light': '浅色', 'dark': '深色', 'logs': '日志', 'jobs': '任务',
        'node_management': '节点管理', 'sales_plans': '销售套餐',
        'security_center': '安全中心', 'subscription_manager': '订阅管理',
    },
    'fr': {
        'dashboard': 'Tableau de bord', 'quick_create': 'Création rapide', 'users': 'Utilisateurs et configurations',
        'usage': 'Utilisation et rapports', 'online_users': 'Utilisateurs en ligne', 'resellers': 'Revendeurs',
        'auto_ssl': 'SSL automatique', 'health': 'Santé et réparation', 'settings': 'Paramètres principaux',
        'license': 'Licence', 'more_settings': 'Paramètres avancés', 'appearance': 'Langue et thème',
        'logout': 'Déconnexion', 'active_version': 'Version active', 'active_host': 'Hôte actif',
        'quick': 'Création rapide', 'language': 'Langue', 'theme': 'Thème', 'save': 'Enregistrer',
        'light': 'Clair', 'dark': 'Sombre', 'logs': 'Journaux', 'jobs': 'Tâches',
        'node_management': 'Gestion des nœuds', 'sales_plans': 'Forfaits de vente',
        'security_center': 'Centre de sécurité', 'subscription_manager': 'Gestion des abonnements',
    },
})

_ZH_EXACT_EN = {
    'Dashboard': '仪表盘', 'Quick Create': '快速创建', 'Quick create': '快速创建', 'Create user': '创建用户',
    'Users & configs': '用户与配置', 'Users & Configs': '用户与配置', 'Online sessions': '在线连接',
    'Usage report': '用量报表', 'Daily operations': '日常操作', 'System management': '系统管理',
    'Infrastructure & protocols': '基础设施与协议', 'Cores, settings and health': '核心、设置与健康状态',
    'Nodes': '节点', 'Node management': '节点管理', 'Install, sync and direct runtime': '安装、同步与直连运行时',
    'Network & domains': '网络与域名', 'Firewall, DNS and domains': '防火墙、DNS 与域名',
    'Business & access': '业务与访问', 'Sales & resellers': '销售与代理商',
    'Plans, payments and sales bot': '套餐、支付与销售机器人', 'Security & operations': '安全与运维',
    'Access, API, logs and updates': '访问、API、日志与更新', 'License & upgrade': '许可证与升级',
    'Account': '账户', 'Profile and preferences': '资料与偏好设置', 'Sign out': '退出登录',
    'End session': '结束会话', 'Full console': '完整控制台', 'Simple view': '简洁视图',
    'Access advanced configuration.': '访问高级配置。', 'Cleaner daily workspace.': '更简洁的日常工作区。',
    'Management console': '管理控制台', 'Language & theme': '语言与主题', 'System health': '系统健康',
    'Save': '保存', 'Save settings': '保存设置', 'Delete': '删除', 'Edit': '编辑', 'Download': '下载',
    'Upload': '上传', 'Copy': '复制', 'Copied': '已复制', 'Search': '搜索', 'Status': '状态',
    'Enabled': '已启用', 'Disabled': '已禁用', 'Light': '浅色', 'Dark': '深色', 'Theme': '主题', 'Language': '语言',
    'Choose the interface language and light/dark theme. Changes are applied to all pages.': '选择界面语言和浅色/深色主题。更改会应用到所有页面。',
    'For low-light environments': '适合低光环境', 'For a clean office workspace': '适合清晰的办公环境',
    'Username': '用户名', 'Password': '密码', 'Current password': '当前密码', 'New password': '新密码',
    'Subscription': '订阅', 'Config': '配置', 'Protocol': '协议', 'Traffic': '流量', 'Usage': '用量',
    'Limit': '限制', 'Unlimited': '无限制', 'Unknown': '未知', 'Ready': '就绪', 'Failed': '失败',
    'Details': '详情', 'Additional information': '附加信息', 'Additional settings': '附加设置',
    'Help text': '帮助说明', 'Guide': '指南', 'Create service quickly': '快速创建服务',
    'Overview and status': '概览与状态', 'Manage accounts and configs': '管理账户与配置', 'Connected clients': '已连接客户端',
    'Traffic and usage': '流量与用量', 'Service Management Console': '服务管理控制台',
}
_FR_EXACT_EN = {
    'Dashboard': 'Tableau de bord', 'Quick Create': 'Création rapide', 'Quick create': 'Création rapide', 'Create user': 'Créer un utilisateur',
    'Users & configs': 'Utilisateurs et configurations', 'Users & Configs': 'Utilisateurs et configurations',
    'Online sessions': 'Sessions en ligne', 'Usage report': "Rapport d'utilisation", 'Daily operations': 'Opérations quotidiennes',
    'System management': 'Gestion du système', 'Infrastructure & protocols': 'Infrastructure et protocoles',
    'Cores, settings and health': 'Noyaux, paramètres et santé', 'Nodes': 'Nœuds', 'Node management': 'Gestion des nœuds',
    'Install, sync and direct runtime': 'Installation, synchronisation et exécution directe',
    'Network & domains': 'Réseau et domaines', 'Firewall, DNS and domains': 'Pare-feu, DNS et domaines',
    'Business & access': 'Ventes et accès', 'Sales & resellers': 'Ventes et revendeurs',
    'Plans, payments and sales bot': 'Forfaits, paiements et bot de vente', 'Security & operations': 'Sécurité et opérations',
    'Access, API, logs and updates': 'Accès, API, journaux et mises à jour', 'License & upgrade': 'Licence et mise à niveau',
    'Account': 'Compte', 'Profile and preferences': 'Profil et préférences', 'Sign out': 'Déconnexion',
    'End session': 'Terminer la session', 'Full console': 'Console complète', 'Simple view': 'Vue simple',
    'Access advanced configuration.': 'Accéder à la configuration avancée.', 'Cleaner daily workspace.': 'Espace quotidien plus clair.',
    'Management console': 'Console de gestion', 'Language & theme': 'Langue et thème', 'System health': 'Santé du système',
    'Save': 'Enregistrer', 'Save settings': 'Enregistrer les paramètres', 'Delete': 'Supprimer', 'Edit': 'Modifier', 'Download': 'Télécharger',
    'Upload': 'Téléverser', 'Copy': 'Copier', 'Copied': 'Copié', 'Search': 'Rechercher', 'Status': 'État',
    'Enabled': 'Activé', 'Disabled': 'Désactivé', 'Light': 'Clair', 'Dark': 'Sombre', 'Theme': 'Thème', 'Language': 'Langue',
    'Choose the interface language and light/dark theme. Changes are applied to all pages.': 'Choisissez la langue de l’interface et le thème clair ou sombre. Les changements s’appliquent à toutes les pages.',
    'For low-light environments': 'Pour les environnements peu lumineux', 'For a clean office workspace': 'Pour un espace de travail clair',
    'Username': "Nom d'utilisateur", 'Password': 'Mot de passe', 'Current password': 'Mot de passe actuel', 'New password': 'Nouveau mot de passe',
    'Subscription': 'Abonnement', 'Config': 'Configuration', 'Protocol': 'Protocole', 'Traffic': 'Trafic', 'Usage': 'Utilisation',
    'Limit': 'Limite', 'Unlimited': 'Illimité', 'Unknown': 'Inconnu', 'Ready': 'Prêt', 'Failed': 'Échec',
    'Details': 'Détails', 'Additional information': 'Informations supplémentaires', 'Additional settings': 'Paramètres supplémentaires',
    'Help text': "Texte d'aide", 'Guide': 'Guide', 'Create service quickly': 'Créer rapidement un service',
    'Overview and status': 'Vue d’ensemble et état', 'Manage accounts and configs': 'Gérer les comptes et configurations', 'Connected clients': 'Clients connectés',
    'Traffic and usage': 'Trafic et utilisation', 'Service Management Console': 'Console de gestion des services',
}

_ZH_FA_EXACT = {
    'فارسی': '波斯语', 'انگلیسی': '英语', 'عربی': '阿拉伯语', 'چینی': '中文', 'فرانسه': '法语',
    'باز کردن منو': '打开菜单', 'منوی اصلی': '主菜单', 'زبان و ظاهر': '语言与主题', 'زبان، تم و ظاهر': '语言、主题与外观',
    'برای محیط‌های کم‌نور': '适合低光环境', 'برای محیط اداری روشن': '适合明亮办公环境',
}
_FR_FA_EXACT = {
    'فارسی': 'Persan', 'انگلیسی': 'Anglais', 'عربی': 'Arabe', 'چینی': 'Chinois', 'فرانسه': 'Français',
    'باز کردن منو': 'Ouvrir le menu', 'منوی اصلی': 'Menu principal', 'زبان و ظاهر': 'Langue et thème', 'زبان، تم و ظاهر': 'Langue, thème et apparence',
    'برای محیط‌های کم‌نور': 'Pour les environnements peu lumineux', 'برای محیط اداری روشن': 'Pour un environnement de bureau clair',
}

_TECH_LATIN_RE = re.compile(r'\b(?:API|SSL|DNS|SSH|VPN|Xray|V2Ray|WireGuard|OpenVPN|Hysteria2|Telegram|IP|CIDR|GB|MB|CPU|RAM|URL|QR|TLS|Reality|HTTP|HTTPS|Node|ID|Token|GitHub|Certbot|Ocserv|Cisco|L2TP|PPTP|MTProxy|JSON|YAML|UUID|Pro|Admin|Beginner|Plus|FREE)\b', re.I)
_LATIN_RE = re.compile(r'[A-Za-z]')
_I18N_CACHE: dict[str, dict[str, str]] = {}

def _label_category_local(text: str, lang: str) -> str:
    x = (text or '').lower()
    lang = (lang or 'en').lower()
    zh = lang.startswith('zh')
    def pick(z, f): return z if zh else f
    if any(k in x for k in ['user','username','account','client','کاربر','حساب','نام کاربری']): return pick('用户', 'Utilisateur')
    if any(k in x for k in ['node','cluster','نود','کلاستر']): return pick('节点', 'Nœud')
    if any(k in x for k in ['protocol','config','subscription','xray','wireguard','openvpn','hysteria','telegram proxy','پروتکل','کانفیگ','اشتراک','ساب']): return pick('配置', 'Configuration')
    if any(k in x for k in ['traffic','usage','quota','volume','speed','bandwidth','مصرف','حجم','سرعت']): return pick('用量', 'Utilisation')
    if any(k in x for k in ['plan','order','billing','payment','wallet','reseller','sales','پلن','سفارش','پرداخت','نماینده','فروش']): return pick('销售', 'Vente')
    if any(k in x for k in ['security','login','password','2fa','token','access','امنیت','ورود','رمز','دسترسی']): return pick('安全', 'Sécurité')
    if any(k in x for k in ['domain','dns','firewall','network','ssl','host','port','دامنه','فایروال','شبکه','پورت']): return pick('网络', 'Réseau')
    if any(k in x for k in ['backup','restore','update','log','repair','health','monitor','بکاپ','آپدیت','لاگ','تعمیر','سلامت']): return pick('运维', 'Opérations')
    if any(k in x for k in ['language','theme','appearance','ui','زبان','تم','ظاهر']): return pick('界面设置', 'Interface')
    return pick('详情', 'Détails')

def _translate_en_to_lang(text: str, lang: str) -> str:
    lang = (lang or 'en').lower()
    if not text:
        return text
    if lang.startswith('en'):
        return text
    if lang.startswith('zh'):
        exact = _ZH_EXACT_EN.get(text.strip())
        if exact:
            return text.replace(text.strip(), exact)
        # Preserve technical tokens only; otherwise avoid English leaks in Chinese mode.
        stripped = text.strip()
        if len(stripped) <= 28:
            return _label_category_local(stripped, 'zh')
        return '说明信息'
    if lang.startswith('fr'):
        exact = _FR_EXACT_EN.get(text.strip())
        if exact:
            return text.replace(text.strip(), exact)
        stripped = text.strip()
        if len(stripped) <= 32:
            return _label_category_local(stripped, 'fr')
        return 'Informations supplémentaires'
    return text

def _build_local_map(lang: str) -> dict[str, str]:
    lang = (lang or 'en').lower()
    cache_key = 'v19105:' + lang
    if cache_key in _I18N_CACHE:
        return _I18N_CACHE[cache_key]
    base_en = {}
    try:
        base_en.update(AUTO_FA_TO_EN)
    except Exception:
        pass
    base_en.update(_HARDCODED_FA_TO_EN)
    if lang.startswith('zh'):
        result = {k: _translate_en_to_lang(v, 'zh') for k, v in base_en.items()}
        result.update(_ZH_FA_EXACT)
    elif lang.startswith('fr'):
        result = {k: _translate_en_to_lang(v, 'fr') for k, v in base_en.items()}
        result.update(_FR_FA_EXACT)
    else:
        result = base_en
    _I18N_CACHE[cache_key] = result
    return result

def current_language() -> str:
    lang = (get_setting('language', 'en') or 'en').lower().replace('-', '_')
    # Backward compatibility: previous Russian selection is no longer offered.
    if lang.startswith('fa'):
        return 'fa'
    if lang.startswith('ar'):
        return 'ar'
    if lang.startswith('zh') or lang in ('cn', 'chinese'):
        return 'zh'
    if lang.startswith('fr'):
        return 'fr'
    if lang not in LANGUAGES:
        return 'en'
    return lang

def current_theme() -> str:
    theme = (get_setting('theme_mode', 'dark') or 'dark').lower()
    return theme if theme in THEMES else 'dark'

def language_dir(lang: str | None = None) -> str:
    return LANGUAGES.get(lang or current_language(), LANGUAGES['en'])['dir']

def t(key: str, default: str | None = None) -> str:
    lang = current_language()
    return TRANSLATIONS.get(lang, {}).get(key) or TRANSLATIONS['en'].get(key) or default or key

def save_appearance(form) -> None:
    lang = (form.get('language') or current_language()).lower()
    if lang.startswith('zh') or lang in ('cn', 'chinese'):
        lang = 'zh'
    elif lang.startswith('fr'):
        lang = 'fr'
    elif lang.startswith('fa'):
        lang = 'fa'
    elif lang.startswith('ar'):
        lang = 'ar'
    elif lang != 'en':
        lang = 'en'
    theme = (form.get('theme_mode') or current_theme()).lower()
    if theme not in THEMES:
        theme = 'dark'
    set_setting('language', lang)
    set_setting('theme_mode', theme)

def _map_for_lang(lang: str) -> dict[str, str]:
    lang = (lang or current_language()).lower()
    if lang.startswith('ar'):
        merged = dict(AUTO_FA_TO_AR)
        merged.update(_HARDCODED_FA_TO_AR)
        return merged
    if lang.startswith('zh'):
        return _build_local_map('zh')
    if lang.startswith('fr'):
        return _build_local_map('fr')
    # English is the default non-Persian fallback.
    merged = dict(AUTO_FA_TO_EN)
    merged.update(_HARDCODED_FA_TO_EN)
    return merged

def _guess_legacy_phrase(src: str, lang: str = 'en') -> str:
    mapping = _map_for_lang(lang)
    if src in mapping:
        return mapping[src]
    base = _guess_legacy_phrase_en(src)
    lang = (lang or 'en').lower()
    if lang.startswith('ar'):
        simple = {
            'Additional information': 'معلومات إضافية', 'Additional settings': 'إعدادات إضافية',
            'Details': 'التفاصيل', 'Access is not allowed.': 'الوصول غير مسموح.',
            'Error details.': 'تفاصيل الخطأ.', 'No item was found.': 'لم يتم العثور على عنصر.',
            'Help text': 'نص المساعدة'
        }
        return simple.get(base, AUTO_FA_TO_AR.get(src) or base)
    if lang.startswith('zh'):
        return _translate_en_to_lang(base, 'zh')
    if lang.startswith('fr'):
        return _translate_en_to_lang(base, 'fr')
    return base

def localize_hardcoded_text(text: str, lang: str | None = None) -> str:
    lang = (lang or current_language()).lower()
    if not text or lang.startswith('fa') or not _ARABIC_RE.search(text):
        return text
    mapping = _map_for_lang(lang)
    out = text
    for src in sorted(mapping, key=len, reverse=True):
        if src in out:
            out = out.replace(src, mapping[src])
    if _ARABIC_RE.search(out):
        for src in _LEGACY_FA_UI_PHRASES:
            if src in out:
                out = out.replace(src, mapping.get(src) or _guess_legacy_phrase(src, lang))
    if _ARABIC_RE.search(out):
        out = _cleanup_residual_persian_html(out, lang, mapping)
    return out

def ui(fa_text: str, en_text: str | None = None) -> str:
    lang = current_language().lower()
    if lang.startswith('fa'):
        return fa_text
    mapping = _map_for_lang(lang)
    if fa_text in mapping:
        return mapping[fa_text]
    if lang.startswith('zh') or lang.startswith('fr'):
        return _translate_en_to_lang(en_text or _HARDCODED_FA_TO_EN.get(fa_text) or _guess_legacy_phrase_en(fa_text), lang)
    return en_text or mapping.get(fa_text) or _HARDCODED_FA_TO_EN.get(fa_text, fa_text)
