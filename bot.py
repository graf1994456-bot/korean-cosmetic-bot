import os
import json
import logging
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, ConversationHandler, ContextTypes, filters
)

logging.basicConfig(level=logging.INFO)

# ─── SOZLAMALAR ───────────────────────────────────────────────
BOT_TOKEN = os.getenv("8776863634:AAEy86X6sGv9X1RKp0gbgEubXWFnOBiRCsY")
ADMIN_ID  = int(os.getenv("566209569"))
GROUP_ID  = int(os.getenv("-1003771968577"))
DATA_FILE   = "products.json"
ORDERS_FILE = "orders.json"

# ─── HOLATLAR ─────────────────────────────────────────────────
(
    ADD_NAME, ADD_PRICE, ADD_DESC, ADD_PHOTO,
    ORDER_NAME, ORDER_PHONE, ORDER_ADDRESS,
    CANCEL_REASON
) = range(8)

# ─── ZAKAZ HOLATLARI ──────────────────────────────────────────
STATUS_NEW       = "🆕 Yangi"
STATUS_CONFIRMED = "✅ Tasdiqlandi"
STATUS_ONWAY     = "🚚 Yo'lda"
STATUS_DELIVERED = "📦 Yetkazildi"
STATUS_CANCELLED = "❌ Bekor qilindi"


# ══════════════════════════════════════════════════════════════
#  YORDAMCHI FUNKSIYALAR
# ══════════════════════════════════════════════════════════════

def load_products():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_products(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def load_orders():
    if os.path.exists(ORDERS_FILE):
        with open(ORDERS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

def save_orders(data):
    with open(ORDERS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def get_order(order_id):
    for o in load_orders():
        if o["id"] == order_id:
            return o
    return None

def update_order_status(order_id, fields: dict):
    orders = load_orders()
    for o in orders:
        if o["id"] == order_id:
            o.update(fields)
    save_orders(orders)

def is_admin(user_id):
    return user_id == ADMIN_ID

def admin_keyboard(order_id):
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Tasdiqlash", callback_data=f"confirm_{order_id}"),
            InlineKeyboardButton("🚚 Yo'lda",     callback_data=f"onway_{order_id}"),
        ],
        [
            InlineKeyboardButton("📦 Yetkazildi",   callback_data=f"delivered_{order_id}"),
            InlineKeyboardButton("❌ Bekor qilish", callback_data=f"cancel_order_{order_id}"),
        ],
    ])


# ══════════════════════════════════════════════════════════════
#  /start — KATALOG
# ══════════════════════════════════════════════════════════════

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    user = update.effective_user
    products = load_products()

    if args:
        key = args[0]
        if key in products:
            p = products[key]
            kb = [[InlineKeyboardButton("🛒 Buyurtma berish", callback_data=f"order_{key}")]]
            text = f"🌿 *{p['name']}*\n\n💰 Narxi: *{p['price']}*\n📝 {p['desc']}"
            if p.get("photo"):
                await update.message.reply_photo(
                    photo=p["photo"], caption=text,
                    parse_mode="Markdown",
                    reply_markup=InlineKeyboardMarkup(kb)
                )
            else:
                await update.message.reply_text(text, parse_mode="Markdown",
                                                reply_markup=InlineKeyboardMarkup(kb))
            return

    if not products:
        await update.message.reply_text("Salom! Hozircha mahsulotlar yo'q. Tez orada qo'shiladi! 🌸")
        return

    kb = [[InlineKeyboardButton(f"🛍 {p['name']} — {p['price']}", callback_data=f"view_{k}")]
          for k, p in products.items()]
    await update.message.reply_text(
        f"Salom, {user.first_name}! 🌸\nQaysi mahsulot qiziqtiradi?",
        reply_markup=InlineKeyboardMarkup(kb)
    )


# ══════════════════════════════════════════════════════════════
#  TUGMALAR
# ══════════════════════════════════════════════════════════════

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    products = load_products()

    if data.startswith("view_"):
        key = data[5:]
        if key not in products:
            await query.edit_message_text("Mahsulot topilmadi.")
            return
        p = products[key]
        kb = [
            [InlineKeyboardButton("🛒 Buyurtma berish", callback_data=f"order_{key}")],
            [InlineKeyboardButton("🔙 Orqaga", callback_data="back_catalog")]
        ]
        text = f"🌿 *{p['name']}*\n\n💰 Narxi: *{p['price']}*\n📝 {p['desc']}"
        if p.get("photo"):
            await query.message.reply_photo(photo=p["photo"], caption=text,
                                            parse_mode="Markdown",
                                            reply_markup=InlineKeyboardMarkup(kb))
            await query.message.delete()
        else:
            await query.edit_message_text(text, parse_mode="Markdown",
                                          reply_markup=InlineKeyboardMarkup(kb))

    elif data == "back_catalog":
        kb = [[InlineKeyboardButton(f"🛍 {p['name']} — {p['price']}", callback_data=f"view_{k}")]
              for k, p in products.items()]
        await query.edit_message_text("Mahsulotlar ro'yxati:", reply_markup=InlineKeyboardMarkup(kb))

    elif data.startswith("order_"):
        key = data[6:]
        if key not in products:
            await query.edit_message_text("Mahsulot topilmadi.")
            return
        context.user_data["order_product"] = key
        context.user_data["order_product_name"] = products[key]["name"]
        context.user_data["order_product_price"] = products[key]["price"]
        await query.message.reply_text("✍️ Ismingizni yozing:")
        return ORDER_NAME

    # ── Admin holat tugmalari ──
    elif data.startswith("confirm_"):
        order_id = int(data[8:])
        await change_status(context, query, order_id, STATUS_CONFIRMED,
            "✅ Buyurtmangiz tasdiqlandi! Tez orada yetkazib beramiz. 🌸")

    elif data.startswith("onway_"):
        order_id = int(data[6:])
        await change_status(context, query, order_id, STATUS_ONWAY,
            "🚚 Buyurtmangiz yo'lda! Tez orada yetib boradi.")

    elif data.startswith("delivered_"):
        order_id = int(data[10:])
        await change_status(context, query, order_id, STATUS_DELIVERED,
            "📦 Buyurtmangiz yetkazildi!\n\nXaridingiz uchun rahmat! 🌸\nYana buyurtma: /start")

    elif data.startswith("cancel_order_"):
        order_id = int(data[13:])
        context.user_data["cancelling_order_id"] = order_id
        await query.message.reply_text(f"Zakaz #{order_id} bekor qilish sababini yozing:")
        return CANCEL_REASON


async def change_status(context, query, order_id, status, client_msg):
    order = get_order(order_id)
    if not order:
        await query.answer("Zakaz topilmadi!", show_alert=True)
        return

    update_order_status(order_id, {"status": status})

    # Mijozga xabar
    try:
        await context.bot.send_message(
            order["user_id"],
            f"🌸 *{order['name']}*, zakaz #{order_id} — *{order['product']}*\n\n{client_msg}",
            parse_mode="Markdown"
        )
    except Exception:
        pass

    # Admin xabarini yangilash
    old = query.message.text or ""
    new_text = old.split("\n📊")[0] + f"\n📊 Holat: *{status}*"
    try:
        await query.edit_message_text(new_text, parse_mode="Markdown",
                                      reply_markup=admin_keyboard(order_id))
    except Exception:
        await query.answer(f"{status} ✓")


async def cancel_reason(update: Update, context: ContextTypes.DEFAULT_TYPE):
    order_id = context.user_data.get("cancelling_order_id")
    reason = update.message.text
    order = get_order(order_id)
    if not order:
        await update.message.reply_text("Zakaz topilmadi.")
        return ConversationHandler.END

    update_order_status(order_id, {"status": STATUS_CANCELLED, "cancel_reason": reason})

    try:
        await context.bot.send_message(
            order["user_id"],
            f"❌ Zakaz #{order_id} bekor qilindi.\nSabab: {reason}\n\nSavollar uchun admin bilan bog'laning."
        )
    except Exception:
        pass

    await update.message.reply_text(f"✅ Zakaz #{order_id} bekor qilindi, mijozga xabar yuborildi.")
    return ConversationHandler.END


# ══════════════════════════════════════════════════════════════
#  BUYURTMA JARAYONI
# ══════════════════════════════════════════════════════════════

async def order_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["order_client_name"] = update.message.text
    await update.message.reply_text("📞 Telefon raqamingiz?")
    return ORDER_PHONE

async def order_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["order_phone"] = update.message.text
    await update.message.reply_text("📍 Manzilingiz? (shahar, tuman)")
    return ORDER_ADDRESS

async def order_address(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["order_address"] = update.message.text
    d = context.user_data
    user = update.effective_user
    now = datetime.now().strftime("%d.%m.%Y %H:%M")

    orders = load_orders()
    order_id = len(orders) + 1
    order = {
        "id": order_id,
        "product": d["order_product_name"],
        "price": d["order_product_price"],
        "name": d["order_client_name"],
        "phone": d["order_phone"],
        "address": d["order_address"],
        "username": user.username or "—",
        "user_id": user.id,
        "status": STATUS_NEW,
        "date": now
    }
    orders.append(order)
    save_orders(orders)

    # Mijozga
    await update.message.reply_text(
        f"✅ *Buyurtmangiz qabul qilindi!*\n\n"
        f"📋 Zakaz #{order_id}\n"
        f"🛍 {d['order_product_name']}\n"
        f"💰 {d['order_product_price']}\n"
        f"👤 {d['order_client_name']}\n"
        f"📞 {d['order_phone']}\n"
        f"📍 {d['order_address']}\n\n"
        f"Holat: {STATUS_NEW}\n"
        f"Tez orada siz bilan bog'lanamiz! 🌸",
        parse_mode="Markdown"
    )

    # Adminга
    admin_text = (
        f"🔔 *YANGI ZAKAZ #{order_id}*\n\n"
        f"🛍 {d['order_product_name']}\n"
        f"💰 {d['order_product_price']}\n"
        f"👤 {d['order_client_name']}\n"
        f"📞 {d['order_phone']}\n"
        f"📍 {d['order_address']}\n"
        f"🕐 {now}\n"
        f"🆔 @{user.username or '—'}\n"
        f"📊 Holat: {STATUS_NEW}"
    )
    await context.bot.send_message(
        ADMIN_ID, admin_text,
        parse_mode="Markdown",
        reply_markup=admin_keyboard(order_id)
    )
    return ConversationHandler.END


# ══════════════════════════════════════════════════════════════
#  ADMIN BUYRUQLARI
# ══════════════════════════════════════════════════════════════

async def add_product(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("⛔ Faqat admin uchun.")
        return ConversationHandler.END
    await update.message.reply_text("🏷 Mahsulot nomini yozing:")
    return ADD_NAME

async def add_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["new_name"] = update.message.text
    await update.message.reply_text("💰 Narxini yozing:")
    return ADD_PRICE

async def add_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["new_price"] = update.message.text
    await update.message.reply_text("📝 Tavsif yozing:")
    return ADD_DESC

async def add_desc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["new_desc"] = update.message.text
    await update.message.reply_text("🖼 Rasmini yuboring (yoki /skip):")
    return ADD_PHOTO

async def add_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    photo_id = None
    if update.message.photo:
        photo_id = update.message.photo[-1].file_id

    name  = context.user_data["new_name"]
    price = context.user_data["new_price"]
    desc  = context.user_data["new_desc"]
    key   = name.upper().replace(" ", "_")[:20]

    products = load_products()
    products[key] = {"name": name, "price": price, "desc": desc, "photo": photo_id}
    save_products(products)

    bot_username = (await context.bot.get_me()).username
    deep_link = f"https://t.me/{bot_username}?start={key}"
    text = f"🌿 *{name}*\n\n💰 Narxi: *{price}*\n📝 {desc}\n\n🛒 [Buyurtma berish]({deep_link})"

    try:
        if photo_id:
            await context.bot.send_photo(GROUP_ID, photo=photo_id, caption=text, parse_mode="Markdown")
        else:
            await context.bot.send_message(GROUP_ID, text, parse_mode="Markdown")
        await update.message.reply_text(f"✅ '{name}' guruhga yuborildi!")
    except Exception as e:
        await update.message.reply_text(f"Saqlandi, lekin guruhga yuborishda xato: {e}")
    return ConversationHandler.END

async def skip_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    update.message.photo = []
    return await add_photo(update, context)

async def orders_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    orders = load_orders()
    if not orders:
        await update.message.reply_text("Hozircha zakaz yo'q.")
        return
    text = "📋 *Oxirgi zakazlar:*\n\n"
    for o in orders[-20:]:
        text += f"#{o['id']} {o['status']} | {o['product']} | {o['name']} | {o['phone']}\n"
    await update.message.reply_text(text, parse_mode="Markdown")

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    orders = load_orders()
    total     = len(orders)
    new       = sum(1 for o in orders if o["status"] == STATUS_NEW)
    confirmed = sum(1 for o in orders if o["status"] == STATUS_CONFIRMED)
    onway     = sum(1 for o in orders if o["status"] == STATUS_ONWAY)
    delivered = sum(1 for o in orders if o["status"] == STATUS_DELIVERED)
    cancelled = sum(1 for o in orders if o["status"] == STATUS_CANCELLED)
    await update.message.reply_text(
        f"📊 *Statistika*\n\n"
        f"Jami: *{total}* ta zakaz\n\n"
        f"{STATUS_NEW}: {new}\n"
        f"{STATUS_CONFIRMED}: {confirmed}\n"
        f"{STATUS_ONWAY}: {onway}\n"
        f"{STATUS_DELIVERED}: {delivered}\n"
        f"{STATUS_CANCELLED}: {cancelled}",
        parse_mode="Markdown"
    )

async def products_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    products = load_products()
    if not products:
        await update.message.reply_text("Mahsulotlar yo'q.")
        return
    text = "📦 *Mahsulotlar:*\n\n"
    for k, p in products.items():
        text += f"• {p['name']} — {p['price']}\n"
    await update.message.reply_text(text, parse_mode="Markdown")

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    await update.message.reply_text(
        "🤖 *Admin buyruqlari:*\n\n"
        "/add — yangi mahsulot qo'shish\n"
        "/products — mahsulotlar ro'yxati\n"
        "/orders — zakazlar ro'yxati\n"
        "/stats — statistika\n"
        "/help — yordam",
        parse_mode="Markdown"
    )

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Bekor qilindi.")
    return ConversationHandler.END


# ══════════════════════════════════════════════════════════════
#  MAIN
# ══════════════════════════════════════════════════════════════

def main():
    app = Application.builder().token(BOT_TOKEN).build()

    add_conv = ConversationHandler(
        entry_points=[CommandHandler("add", add_product)],
        states={
            ADD_NAME:  [MessageHandler(filters.TEXT & ~filters.COMMAND, add_name)],
            ADD_PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_price)],
            ADD_DESC:  [MessageHandler(filters.TEXT & ~filters.COMMAND, add_desc)],
            ADD_PHOTO: [
                MessageHandler(filters.PHOTO, add_photo),
                CommandHandler("skip", skip_photo)
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    order_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(button_handler, pattern="^order_")],
        states={
            ORDER_NAME:    [MessageHandler(filters.TEXT & ~filters.COMMAND, order_name)],
            ORDER_PHONE:   [MessageHandler(filters.TEXT & ~filters.COMMAND, order_phone)],
            ORDER_ADDRESS: [MessageHandler(filters.TEXT & ~filters.COMMAND, order_address)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    cancel_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(button_handler, pattern="^cancel_order_")],
        states={
            CANCEL_REASON: [MessageHandler(filters.TEXT & ~filters.COMMAND, cancel_reason)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("orders", orders_list))
    app.add_handler(CommandHandler("products", products_list))
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(add_conv)
    app.add_handler(order_conv)
    app.add_handler(cancel_conv)
    app.add_handler(CallbackQueryHandler(button_handler))

    print("✅ Bot ishga tushdi!")
    app.run_polling()

if __name__ == "__main__":
    main()
