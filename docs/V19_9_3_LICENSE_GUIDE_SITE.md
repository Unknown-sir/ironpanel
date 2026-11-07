# V19.9.3 — LicensePanel IronPanel Guide Site

این نسخه یک سایت راهنمای کامل IronPanel را به پکیج LicensePanel اضافه می‌کند.

## تغییرات

- نصب سایت راهنمای IronPanel همزمان با نصب LicensePanel.
- دریافت دامنه سایت راهنما از مدیر هنگام نصب.
- راه‌اندازی Nginx روی پورت 443 برای دامنه راهنما.
- دریافت خودکار SSL با Let's Encrypt در صورت معتبر بودن DNS.
- fallback به self-signed SSL در صورت ناموفق بودن دریافت گواهی تا سایت روی 443 بالا بماند.
- تم مدرن و ریسپانسیو هماهنگ با صفحه لاگین Matrix.
- صفحه اصلی شامل معرفی کامل امکانات IronPanel، پروتکل‌ها، نود، Transparent Relay، نصب خودکار نود، SSL، Firewall، Update Manager، Health Doctor، Backup و دستورات کاربردی.
- نمایش آیدی پشتیبانی و لینک GitHub داخل سایت.

## نصب دستی یا اجرای دوباره

```bash
sudo bash /opt/license-panel/scripts/install_guide_site.sh --domain help.example.com --email admin@example.com --support-id @Ironpanel_support --github-url https://github.com/Unknown-sir/ironpanel
```

## متغیرهای نصب غیرتعاملی

```bash
LICENSE_SETUP_GUIDE_SITE=y
LICENSE_GUIDE_DOMAIN=help.example.com
LICENSE_GUIDE_EMAIL=admin@example.com
LICENSE_GUIDE_SUPPORT_ID=@Ironpanel_support
LICENSE_GUIDE_GITHUB_URL=https://github.com/Unknown-sir/ironpanel
```
