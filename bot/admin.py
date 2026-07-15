import logging
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes
from app import create_app
from app.core.models import VpnUser
from app.services.provisioning import get_setting
from app.services.admin_bot import (
    admin_bot_settings, admin_bot_admin_ids, admin_bot_report_text,
    online_users_text, users_summary_text, user_detail_text, create_admin_backup,
)

logging.basicConfig(level=logging.INFO, format='[%(asctime)s] %(levelname)s %(name)s: %(message)s')
log = logging.getLogger('ironpanel-admin-bot')
flask_app = create_app()


def _token():
    return (get_setting('telegram_bot_token', '') or get_setting('sales_bot_token', '') or '').strip()


def _is_admin(tg_id):
    return str(tg_id) in admin_bot_admin_ids()


def _kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton('👥 کاربران آنلاین', callback_data='ab:online'), InlineKeyboardButton('👤 اطلاعات کاربران', callback_data='ab:users:0')],
        [InlineKeyboardButton('🗄 درخواست بکاپ', callback_data='ab:backup'), InlineKeyboardButton('📊 گزارش پنل', callback_data='ab:report')],
        [InlineKeyboardButton('🔄 بروزرسانی', callback_data='ab:refresh')],
    ])


def _back():
    return InlineKeyboardMarkup([[InlineKeyboardButton('⬅️ بازگشت', callback_data='ab:home')]])


def _users_keyboard(page=0, per_page=10):
    users = VpnUser.query.order_by(VpnUser.id.desc()).offset(page * per_page).limit(per_page + 1).all()
    rows = []
    for u in users[:per_page]:
        rows.append([InlineKeyboardButton(f'#{u.id} {u.username}', callback_data=f'ab:user:{u.id}:{page}')])
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton('قبلی', callback_data=f'ab:users:{page-1}'))
    if len(users) > per_page:
        nav.append(InlineKeyboardButton('بعدی', callback_data=f'ab:users:{page+1}'))
    if nav:
        rows.append(nav)
    rows.append([InlineKeyboardButton('⬅️ بازگشت', callback_data='ab:home')])
    return InlineKeyboardMarkup(rows)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    with flask_app.app_context():
        if not _is_admin(update.effective_user.id):
            await update.message.reply_text('⛔ دسترسی مجاز نیست.')
            return
        await update.message.reply_text('ربات مدیریتی IronPanel', reply_markup=_kb())


async def callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    with flask_app.app_context():
        if not _is_admin(q.from_user.id):
            await q.edit_message_text('⛔ دسترسی مجاز نیست.')
            return
        data = q.data or ''
        if data in ('ab:home', 'ab:refresh'):
            await q.edit_message_text('ربات مدیریتی IronPanel', reply_markup=_kb())
            return
        if data == 'ab:online':
            await q.edit_message_text(online_users_text(), reply_markup=_back())
            return
        if data.startswith('ab:users:'):
            try:
                page = int(data.split(':')[-1])
            except Exception:
                page = 0
            await q.edit_message_text(users_summary_text(), reply_markup=_users_keyboard(page))
            return
        if data.startswith('ab:user:'):
            parts = data.split(':')
            uid = int(parts[2])
            page = int(parts[3]) if len(parts) > 3 and parts[3].isdigit() else 0
            await q.edit_message_text(user_detail_text(uid), reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('⬅️ کاربران', callback_data=f'ab:users:{page}')]]))
            return
        if data == 'ab:report':
            await q.edit_message_text(admin_bot_report_text(), reply_markup=_back())
            return
        if data == 'ab:backup':
            path = create_admin_backup()
            await q.edit_message_text('بکاپ ساخته شد و در حال ارسال است...', reply_markup=_back())
            try:
                with open(path, 'rb') as f:
                    await context.bot.send_document(chat_id=q.message.chat_id, document=f, filename=path.name, caption='🗄 بکاپ IronPanel')
            except Exception as exc:
                await context.bot.send_message(chat_id=q.message.chat_id, text=f'ارسال فایل بکاپ ناموفق بود: {exc}\nمسیر فایل: {path}')
            return


def main():
    with flask_app.app_context():
        s = admin_bot_settings()
        token = _token()
    if not token:
        log.warning('Admin bot token is empty.')
        return
    if not s.get('enabled'):
        log.warning('Admin bot is disabled.')
        return
    app = Application.builder().token(token).build()
    app.add_handler(CommandHandler('start', start))
    app.add_handler(CommandHandler('admin', start))
    app.add_handler(CallbackQueryHandler(callbacks, pattern=r'^ab:'))
    log.info('IronPanel Admin Bot started')
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == '__main__':
    main()
