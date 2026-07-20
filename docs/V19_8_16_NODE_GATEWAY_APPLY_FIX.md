# IronPanel v19.8.16 - Node Gateway Apply Fix


## نسخه 19.8.16 — Node Gateway Apply Fix
- رفع خطای `Node Gateway apply error` زمانی که chainهای قبلی MASQUERADE وجود نداشتند و اسکریپت به خاطر `pipefail` قبل از ساخت قانون‌ها خارج می‌شد.
- دستور نصب نود حالا scheme واقعی پنل را حفظ می‌کند؛ اگر پنل روی `https://IP:8001` اجرا شده باشد، دیگر به اشتباه `http://IP:8001` تولید نمی‌شود.
- لاگ Node Gateway دقیق‌تر شد و اگر هیچ قانونی اعمال نشود یا host نود resolve نشود، خطای قابل بررسی داخل `/var/log/ironpanel-node-gateway.log` ثبت می‌شود.

