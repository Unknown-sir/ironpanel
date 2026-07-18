from __future__ import annotations

from flask import request
from .provisioning import get_setting, set_setting

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
        'light': 'روشن', 'dark': 'تاریک', 'auto': 'خودکار', 'logs': 'لاگ‌ها', 'jobs': 'Jobها',
    },
    'en': {
        'dashboard': 'Dashboard', 'quick_create': 'Quick Create', 'users': 'Users & Configs',
        'usage': 'Usage & Reports', 'online_users': 'Online Users', 'resellers': 'Resellers',
        'auto_ssl': 'Auto SSL', 'health': 'Health & Repair', 'settings': 'Core Settings',
        'license': 'License', 'more_settings': 'More Settings', 'appearance': 'Language & Theme',
        'logout': 'Logout', 'active_version': 'Active edition', 'active_host': 'Active host',
        'quick': 'Quick Create', 'language': 'Language', 'theme': 'Theme', 'save': 'Save',
        'light': 'Light', 'dark': 'Dark', 'auto': 'Auto', 'logs': 'Logs', 'jobs': 'Jobs',
    },
    'ar': {
        'dashboard': 'لوحة التحكم', 'quick_create': 'إنشاء سريع', 'users': 'المستخدمون والملفات',
        'usage': 'الاستهلاك والتقارير', 'online_users': 'المتصلون الآن', 'resellers': 'الوكلاء',
        'auto_ssl': 'SSL تلقائي', 'health': 'الصحة والإصلاح', 'settings': 'الإعدادات الأساسية',
        'license': 'الترخيص', 'more_settings': 'إعدادات إضافية', 'appearance': 'اللغة والمظهر',
        'logout': 'خروج', 'active_version': 'الإصدار النشط', 'active_host': 'المضيف النشط',
        'quick': 'إنشاء سريع', 'language': 'اللغة', 'theme': 'السمة', 'save': 'حفظ',
        'light': 'فاتح', 'dark': 'داكن', 'auto': 'تلقائي', 'logs': 'السجلات', 'jobs': 'المهام',
    },
    'ru': {
        'dashboard': 'Панель', 'quick_create': 'Быстро создать', 'users': 'Пользователи и конфиги',
        'usage': 'Трафик и отчёты', 'online_users': 'Онлайн пользователи', 'resellers': 'Реселлеры',
        'auto_ssl': 'Auto SSL', 'health': 'Диагностика', 'settings': 'Основные настройки',
        'license': 'Лицензия', 'more_settings': 'Дополнительно', 'appearance': 'Язык и тема',
        'logout': 'Выход', 'active_version': 'Активная редакция', 'active_host': 'Активный хост',
        'quick': 'Быстро', 'language': 'Язык', 'theme': 'Тема', 'save': 'Сохранить',
        'light': 'Светлая', 'dark': 'Тёмная', 'auto': 'Авто', 'logs': 'Логи', 'jobs': 'Задачи',
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
