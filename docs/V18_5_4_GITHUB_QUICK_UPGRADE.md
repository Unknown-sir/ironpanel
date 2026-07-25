# IronPanel v18.5.4 — GitHub Update Alert & Quick Upgrade

این نسخه یک سیستم بررسی نسخه از GitHub و آپگرید سریع داخل داشبورد اضافه می‌کند.

## رفتار جدید

- پنل نسخه نصب‌شده را از `VERSION` می‌خواند.
- آخرین نسخه GitHub از فایل `VERSION` روی branch تنظیم‌شده خوانده می‌شود.
- مقایسه نسخه‌ها عددی است؛ مثلا `18.5.10` از `18.5.4` جدیدتر تشخیص داده می‌شود.
- بررسی نسخه کش می‌شود تا داشبورد در هر بار باز شدن کند نشود.
- اگر نسخه GitHub جدیدتر باشد، در داشبورد main admin اعلان نمایش داده می‌شود.
- دکمه «آپگرید سریع» job آپگرید را در پس‌زمینه اجرا می‌کند تا restart پنل باعث قطع شدن request نشود.

## تنظیمات

در دیتابیس / Settings:

- `github_version_url`: آدرس raw فایل VERSION
- `github_repo_url`: آدرس repo برای clone/fetch
- `github_branch`: branch پیش‌فرض، معمولا `main`
- `github_update_check_interval_minutes`: فاصله بررسی نسخه، پیش‌فرض 60 دقیقه

## لاگ آپگرید

```bash
sudo tail -f /var/log/ironpanel-github-upgrade.log
```

## اجرای دستی آپگرید از سرور

```bash
sudo bash /opt/ironpanel/scripts/update_from_github.sh
```

برای repo یا branch سفارشی:

```bash
sudo IRONPANEL_GITHUB_REPO="https://github.com/USER/REPO.git" \
     IRONPANEL_GITHUB_BRANCH="main" \
     bash /opt/ironpanel/scripts/update_from_github.sh
```
