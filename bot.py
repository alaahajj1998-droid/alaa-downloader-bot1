import os
import tempfile
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
import yt_dlp

BOT_TOKEN = os.environ.get("BOT_TOKEN")

# تخزين مؤقت للروابط
user_urls = {}

# ==================== /start ====================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 أهلاً! أنا بوت *علاء للتحميل* 🚀\n\n"
        "📌 المنصات المدعومة:\n"
        "▪️ يوتيوب 🎥\n"
        "▪️ تيك توك 🎵\n"
        "▪️ إنستغرام 📸\n"
        "▪️ تويتر/X 🐦\n"
        "▪️ فيسبوك 👍\n"
        "▪️ وأكثر من 1000 موقع!\n\n"
        "✅ فقط أرسل الرابط وأنا أتكفل بالباقي!",
        parse_mode="Markdown"
    )

# ==================== استقبال الرابط ====================
async def handle_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.strip()
    user_id = update.message.from_user.id

    if not url.startswith("http"):
        await update.message.reply_text("❌ الرجاء إرسال رابط صحيح يبدأ بـ http")
        return

    msg = await update.message.reply_text("🔍 جاري تحليل الرابط...")

    try:
        ydl_opts = {'quiet': True, 'no_warnings': True}
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)

        title = info.get('title', 'المحتوى')[:50]
        formats = info.get('formats', [])

        # جمع الدقات المتاحة
        qualities = {}
        for f in formats:
            height = f.get('height')
            ext = f.get('ext', '')
            vcodec = f.get('vcodec', 'none')
            if height and vcodec != 'none' and ext in ['mp4', 'webm', '']:
                label = f"{height}p"
                if label not in qualities:
                    qualities[label] = f.get('format_id')

        # حفظ الرابط والعنوان
        user_urls[user_id] = {'url': url, 'title': title}

        # بناء الأزرار
        keyboard = []
        quality_order = ['1080p', '720p', '480p', '360p', '240p', '144p']
        available = [q for q in quality_order if q in qualities]

        if available:
            row = []
            for q in available:
                row.append(InlineKeyboardButton(f"🎥 {q}", callback_data=f"quality_{q}_{qualities[q]}"))
                if len(row) == 3:
                    keyboard.append(row)
                    row = []
            if row:
                keyboard.append(row)

        keyboard.append([
            InlineKeyboardButton("⭐ أفضل جودة", callback_data="quality_best"),
            InlineKeyboardButton("🎵 صوت فقط MP3", callback_data="quality_audio")
        ])

        reply_markup = InlineKeyboardMarkup(keyboard)
        await msg.edit_text(
            f"✅ تم تحليل الرابط!\n\n"
            f"📹 *{title}*\n\n"
            f"اختر الجودة:",
            parse_mode="Markdown",
            reply_markup=reply_markup
        )

    except Exception as e:
        await msg.edit_text(
            "❌ فشل تحليل الرابط\n"
            "تأكد من:\n"
            "• صحة الرابط\n"
            "• أن المحتوى عام وغير محمي"
        )

# ==================== تنفيذ التحميل ====================
async def download_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    if user_id not in user_urls:
        await query.edit_message_text("❌ انتهت الجلسة، أرسل الرابط مجدداً")
        return

    url = user_urls[user_id]['url']
    title = user_urls[user_id]['title']
    data = query.data

    await query.edit_message_text("⏳ جاري التحميل... قد يستغرق بعض الوقت")

    try:
        with tempfile.TemporaryDirectory() as tmp:
            if data == "quality_audio":
                ydl_opts = {
                    'outtmpl': f'{tmp}/audio.%(ext)s',
                    'format': 'bestaudio/best',
                    'postprocessors': [{
                        'key': 'FFmpegExtractAudio',
                        'preferredcodec': 'mp3',
                        'preferredquality': '192',
                    }],
                    'quiet': True,
                }
            elif data == "quality_best":
                ydl_opts = {
                    'outtmpl': f'{tmp}/video.%(ext)s',
                    'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
                    'merge_output_format': 'mp4',
                    'quiet': True,
                }
            else:
                parts = data.split('_')
                format_id = parts[-1]
                ydl_opts = {
                    'outtmpl': f'{tmp}/video.%(ext)s',
                    'format': f'{format_id}+bestaudio/best',
                    'merge_output_format': 'mp4',
                    'quiet': True,
                }

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.extract_info(url, download=True)

            files = os.listdir(tmp)
            if not files:
                await query.edit_message_text("❌ فشل التحميل")
                return

            fname = os.path.join(tmp, files[0])
            size = os.path.getsize(fname)

            if size > 50 * 1024 * 1024:
                await query.edit_message_text(
                    "❌ حجم الملف أكبر من 50MB\n"
                    "جرب جودة أقل"
                )
                return

            await query.edit_message_text("📤 جاري الإرسال...")

            ext = fname.split('.')[-1].lower()
            caption = f"✅ *{title}*\n🤖 @Alaa_Downloader_bot"

            with open(fname, 'rb') as f:
                if ext == 'mp3' or data == "quality_audio":
                    await query.message.reply_audio(audio=f, caption=caption, parse_mode="Markdown")
                elif ext in ['jpg', 'jpeg', 'png', 'webp']:
                    await query.message.reply_photo(photo=f, caption=caption, parse_mode="Markdown")
                else:
                    await query.message.reply_video(video=f, caption=caption, parse_mode="Markdown", supports_streaming=True)

            await query.delete_message()

    except Exception as e:
        err = str(e)
        if "ffmpeg" in err.lower():
            msg = "❌ خطأ في معالجة الفيديو، جرب جودة أخرى"
        elif "private" in err.lower():
            msg = "🔒 هذا المحتوى خاص"
        else:
            msg = "❌ فشل التحميل، جرب جودة أخرى أو رابطاً مختلفاً"
        await query.edit_message_text(msg)

# ==================== تشغيل البوت ====================
def main():
    print("✅ بوت علاء يعمل...")
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_url))
    app.add_handler(CallbackQueryHandler(download_video))
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
