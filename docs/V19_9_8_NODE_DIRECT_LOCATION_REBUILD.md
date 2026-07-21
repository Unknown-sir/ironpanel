# IronPanel 19.9.8 — Node Direct Location Rebuild

## 19.9.8 — Node Direct Location Rebuild + Panel Watchdog

- بخش Nodes از نو بازنویسی شد و مدل پیش‌فرض آن Direct Location Subscription شد.
- فرم جدید نود شامل نام سرور، نام نود، آدرس سرور نود، دامنه کانفیگ، پروتکل‌ها و پورت جداگانه هر پروتکل است.
- هنگام ثبت نود، اطلاعات SSH به‌صورت رمزنگاری‌شده ذخیره و نصب خودکار در صف Job قرار می‌گیرد؛ نصب دیگر داخل request وب اجرا نمی‌شود و باعث Down شدن پنل نمی‌شود.
- نصب خودکار از طریق SSH هسته‌ها را نصب/Repair می‌کند، Agent نود را وصل می‌کند، کانفیگ پروتکل‌ها و کاربران را Sync می‌کند و Health Check می‌سازد.
- کانفیگ‌های نود به Subscription اضافه می‌شوند ولی UUID/Password/Identity از پنل اصلی می‌آید؛ مصرف Main و همه نودها روی همان quota مشترک کاربر محاسبه می‌شود.
- Heartbeat نود گزارش مصرف را ارسال می‌کند و پنل اصلی delta مصرف را روی کاربر اعمال می‌کند.
- Watchdog جدید اضافه شد تا اگر ironpanel فعال نبود یا /healthz پاسخ نداد، سرویس را خودکار restart کند.
- systemd پنل harden شد: Restart سریع‌تر، KillMode mixed، TimeoutStopSec و watchdog timer.
