import telebot
from telebot import types
import os
import subprocess
import time
import asyncio
import edge_tts
import sqlite3
import requests
import uuid
from datetime import date
from flask import Flask
from threading import Thread
from dotenv import load_dotenv # 👈 Naya module import kiya

# ==========================================
# 👇 SECURE CONFIGURATION 👇
# ==========================================
# .env file ko load karo
load_dotenv()

BOT_TOKEN = os.getenv('BOT_TOKEN') 
BOT_USERNAME = os.getenv('BOT_USERNAME') 
SHORTLINK_API = os.getenv('SHORTLINK_API', "https://gplinks.in/api") 
SHORTLINK_KEY = os.getenv('SHORTLINK_KEY')

try:
    ADMIN_ID = int(os.getenv('ADMIN_ID', 0)) 
except:
    ADMIN_ID = 0

CHANNEL_USERNAME = '@errorkids' 
FREE_DAILY_LIMIT = 3
# ==========================================

# ==========================================

user_modes = {}       
user_files = {}       
user_processing = {}  
user_temp_text = {}   
pending_verifications = {}

app = Flask('')
@app.route('/')
def home(): return "Premium Voice Bot is alive!"
def run_http(): app.run(host='0.0.0.0', port=8080)
def keep_alive():
    t = Thread(target=run_http)
    t.start()

bot = telebot.TeleBot(BOT_TOKEN)
print("🔥 Colored Pro Engine Active...")

# ==========================================
# 🗄️ DATABASE SYSTEM 
# ==========================================
def init_db():
    conn = sqlite3.connect('bot_database.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (user_id INTEGER PRIMARY KEY, daily_usage INTEGER, total_processed INTEGER, last_used_date TEXT, premium_expiry REAL)''')
    conn.commit()
    conn.close()

def add_user(user_id):
    conn = sqlite3.connect('bot_database.db')
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE user_id=?", (user_id,))
    if c.fetchone() is None:
        c.execute("INSERT INTO users VALUES (?, 0, 0, ?, 0.0)", (user_id, str(date.today())))
        conn.commit()
    conn.close()

def get_user_status(user_id):
    if user_id == ADMIN_ID: return "ADMIN", 0
    conn = sqlite3.connect('bot_database.db')
    c = conn.cursor()
    c.execute("SELECT daily_usage, premium_expiry FROM users WHERE user_id=?", (user_id,))
    data = c.fetchone()
    conn.close()
    if not data: return "FREE", 0
    usage, expiry = data
    if time.time() < expiry: return "VIP_48H", usage
    return "FREE", usage

def check_and_update_limit(user_id):
    if user_id == ADMIN_ID: return True 
    conn = sqlite3.connect('bot_database.db')
    c = conn.cursor()
    c.execute("SELECT daily_usage, last_used_date, premium_expiry FROM users WHERE user_id=?", (user_id,))
    data = c.fetchone()
    if not data: return False
    daily_usage, last_used_date, premium_expiry = data
    today = str(date.today())
    
    if time.time() < premium_expiry:
        c.execute("UPDATE users SET total_processed = total_processed + 1 WHERE user_id=?", (user_id,))
        conn.commit()
        conn.close()
        return True

    if last_used_date != today:
        daily_usage = 0
        c.execute("UPDATE users SET daily_usage=0, last_used_date=? WHERE user_id=?", (today, user_id))
        conn.commit()
        
    if daily_usage >= FREE_DAILY_LIMIT:
        conn.close()
        return False 
        
    c.execute("UPDATE users SET daily_usage = daily_usage + 1, total_processed = total_processed + 1 WHERE user_id=?", (user_id,))
    conn.commit()
    conn.close()
    return True

def activate_48h_vip(user_id):
    expiry_time = time.time() + (48 * 3600)
    conn = sqlite3.connect('bot_database.db')
    c = conn.cursor()
    c.execute("UPDATE users SET premium_expiry=? WHERE user_id=?", (expiry_time, user_id))
    conn.commit()
    conn.close()

init_db()

def generate_shortlink(url):
    try:
        res = requests.get(f"{SHORTLINK_API}?api={SHORTLINK_KEY}&url={url}").json()
        if res.get("status") == "success": return res.get("shortenedUrl")
    except: pass
    return url 

def ask_to_watch_ad(chat_id):
    token = str(uuid.uuid4().hex)[:10]
    pending_verifications[chat_id] = token
    deep_link = f"https://t.me/{BOT_USERNAME}?start={token}"
    bot.send_message(chat_id, "<i>🔗 Generating your unlock link...</i>", parse_mode="HTML")
    ad_link = generate_shortlink(deep_link)
    
    markup = types.InlineKeyboardMarkup()
    # 🟢 GREEN Button for VIP Unlock
    markup.add(types.InlineKeyboardButton("🔓 Watch Ad to Unlock (48H)", url=ad_link, style="success"))
    
    bot.send_message(chat_id, "⚠️ **Limit Reached!**\nAd dekh kar 48H Unlimited access lein.", reply_markup=markup, parse_mode="Markdown")

def check_subscription(user_id):
    if user_id == ADMIN_ID: return True
    try:
        member = bot.get_chat_member(CHANNEL_USERNAME, user_id)
        if member.status in ['creator', 'administrator', 'member']: return True
        return False
    except: return True 

def ask_for_join(chat_id):
    markup = types.InlineKeyboardMarkup()
    # 🔵 BLUE Button for joining, 🟢 GREEN for check
    markup.add(types.InlineKeyboardButton("📢 Join Channel", url=f"https://t.me/{CHANNEL_USERNAME.replace('@', '')}", style="primary"))
    markup.add(types.InlineKeyboardButton("✅ Checked & Joined", callback_data='check_join', style="success"))
    bot.send_message(chat_id, f"⚠️ **Access Denied!**\nPehle channel join karein:\n{CHANNEL_USERNAME}", reply_markup=markup, parse_mode="Markdown")

# --- COMMANDS ---
@bot.message_handler(commands=['start'])
def start_command(message):
    chat_id = message.chat.id
    add_user(chat_id) 

    if len(message.text.split()) > 1:
        token = message.text.split()[1]
        if pending_verifications.get(chat_id) == token:
            activate_48h_vip(chat_id)
            del pending_verifications[chat_id]
            bot.send_message(chat_id, "🎉 **48-Hour VIP Activated!** 🚀", parse_mode="Markdown")
            time.sleep(1)

    if chat_id in user_processing: del user_processing[chat_id]
    if not check_subscription(chat_id): return ask_for_join(chat_id)

    reply_markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    reply_markup.add("👤 My Profile", "💎 Unlock VIP")
    
    # 🔥 TELEGRAM NAYA UPDATE COLORED BUTTONS 🔥
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        # 🔵 BLUE Buttons
        types.InlineKeyboardButton("🎤 Voice Changer", callback_data='mode_voice', style="primary"),
        types.InlineKeyboardButton("📝 AI Text to Audio", callback_data='mode_text', style="primary")
    )
    # 🟢 GREEN Button (Prominent)
    markup.row(types.InlineKeyboardButton("💎 Unlock Premium", callback_data='mode_premium', style="success"))

    status, usage = get_user_status(chat_id)
    status_text = "🟢 48H VIP ACTIVE" if status == "VIP_48H" else f"⚪ FREE ({FREE_DAILY_LIMIT - usage} left)"

    caption = (
        f"👋 Welcome to Dashboard, <b>{message.chat.first_name}</b>!\n\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"🛡️ <b>ID:</b> <code>{chat_id}</code>\n"
        f"👑 <b>Status:</b> {status_text}\n"
        f"━━━━━━━━━━━━━━━━━━━\n\n"
        f"👇 <i>Select a module below:</i>"
    )
    bot.send_message(chat_id, caption, parse_mode="HTML", reply_markup=reply_markup)
    bot.send_message(chat_id, "Choose action:", reply_markup=markup)

@bot.message_handler(content_types=['text'])
def handle_text_input(message):
    chat_id = message.chat.id
    text = message.text
    if not check_subscription(chat_id): return ask_for_join(chat_id)

    if text == "👤 My Profile":
        status, usage = get_user_status(chat_id)
        plan = "🌟 48-Hour VIP" if status == "VIP_48H" else "👑 Owner" if status == "ADMIN" else f"⚪ Free ({usage}/{FREE_DAILY_LIMIT})"
        return bot.reply_to(message, f"👤 **PROFILE**\n📛 {message.chat.first_name}\n💳 **Plan:** {plan}", parse_mode="Markdown")
    
    elif text == "💎 Unlock VIP":
        status, _ = get_user_status(chat_id)
        if status in ["VIP_48H", "ADMIN"]: return bot.reply_to(message, "✅ VIP already active!")
        return ask_to_watch_ad(chat_id)

    if user_modes.get(chat_id) == 'text':
        user_temp_text[chat_id] = text
        markup = types.InlineKeyboardMarkup(row_width=2)
        # 🔵 BLUE Buttons
        markup.add(
            types.InlineKeyboardButton("👨🏽 Hindi Male", callback_data='hi-IN-MadhurNeural', style="primary"),
            types.InlineKeyboardButton("👩🏽 Hindi Female", callback_data='hi-IN-SwaraNeural', style="primary"),
            types.InlineKeyboardButton("👨🏻 Eng Male", callback_data='en-US-GuyNeural', style="primary"),
            types.InlineKeyboardButton("👩🏻 Eng Female", callback_data='en-US-AriaNeural', style="primary")
        )
        bot.reply_to(message, "🌟 **AI Voice Select karo:**", reply_markup=markup, parse_mode="Markdown")

@bot.message_handler(content_types=['voice', 'audio'])
def handle_audio_input(message):
    chat_id = message.chat.id
    if not check_subscription(chat_id): return ask_for_join(chat_id)
    if user_modes.get(chat_id) != 'voice': return bot.reply_to(message, "⚠️ Pehle /start se Voice mode lo!")
    if not check_and_update_limit(chat_id): return ask_to_watch_ad(chat_id)

    msg = bot.reply_to(message, "⬇️ Downloading... ⏳")
    try:
        file_id = message.voice.file_id if message.content_type == 'voice' else message.audio.file_id
        file_info = bot.get_file(file_id)
        downloaded = bot.download_file(file_info.file_path)
        temp = f"temp_{chat_id}.ogg"
        wav = f"user_{chat_id}.wav"
        with open(temp, 'wb') as f: f.write(downloaded)
        subprocess.call(['ffmpeg', '-i', temp, '-ar', '44100', wav, '-y'], stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
        if os.path.exists(temp): os.remove(temp)
        user_files[chat_id] = wav
        show_effect_categories(chat_id, msg.message_id)
    except: bot.edit_message_text("❌ Error", chat_id, msg.message_id)

def show_effect_categories(chat_id, msg_id):
    markup = types.InlineKeyboardMarkup(row_width=2)
    # 🎨 MIXED COLORS FOR CATEGORIES 🎨
    markup.add(
        types.InlineKeyboardButton("🧍‍♂️ Gender Swap", callback_data='cat_gender', style="primary"), # BLUE
        types.InlineKeyboardButton("👻 Scary & Fun", callback_data='cat_fun', style="danger"), # RED
        types.InlineKeyboardButton("🎚️ Studio Effects", callback_data='cat_studio', style="success") # GREEN
    )
    bot.edit_message_text("✅ **Audio Ready!**\nCategory chunein:", chat_id, msg_id, reply_markup=markup, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data.startswith('cat_'))
def handle_categories(call):
    chat_id = call.message.chat.id
    markup = types.InlineKeyboardMarkup(row_width=2)
    
    # 🔵 GENDER (BLUE)
    if call.data == 'cat_gender':
        markup.add(
            types.InlineKeyboardButton("👩 Girl", callback_data='eff_girl', style="primary"),
            types.InlineKeyboardButton("👩‍🦰 Woman", callback_data='eff_woman', style="primary"),
            types.InlineKeyboardButton("👶 Kid", callback_data='eff_kid', style="primary")
        )
    # 🔴 SCARY (RED)
    elif call.data == 'cat_fun':
        markup.add(
            types.InlineKeyboardButton("👹 Monster", callback_data='eff_monster', style="danger"),
            types.InlineKeyboardButton("🦍 Giant", callback_data='eff_giant', style="danger"),
            types.InlineKeyboardButton("👽 Alien", callback_data='eff_alien', style="danger")
        )
    # 🟢 STUDIO (GREEN)
    elif call.data == 'cat_studio':
        markup.add(
            types.InlineKeyboardButton("📢 Echo", callback_data='eff_echo', style="success"),
            types.InlineKeyboardButton("📻 Radio", callback_data='eff_radio', style="success"),
            types.InlineKeyboardButton("🎤 Concert", callback_data='eff_concert', style="success")
        )
    
    # 🔴 BACK BUTTON (RED)
    markup.row(types.InlineKeyboardButton("🔙 Back", callback_data='back_cats', style="danger"))
    bot.edit_message_text(f"🎛️ **Choose Effect:**", chat_id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data in ['mode_text', 'mode_voice', 'check_join', 'back_cats', 'mode_premium'])
def main_menu_handler(call):
    chat_id = call.message.chat.id
    bot.answer_callback_query(call.id)
    if call.data == 'check_join': start_command(call.message)
    elif call.data == 'back_cats': show_effect_categories(chat_id, call.message.message_id)
    elif call.data == 'mode_premium': ask_to_watch_ad(chat_id)
    elif call.data.startswith('mode_'):
        user_modes[chat_id] = call.data.split('_')[1]
        if user_modes[chat_id] == 'text': bot.edit_message_text("📝 **Text bhejo:**", chat_id, call.message.message_id, parse_mode="Markdown")
        else: bot.edit_message_text("🎤 **Audio bhejo:**", chat_id, call.message.message_id, parse_mode="Markdown")

async def generate_edge_tts(text, voice_model, output_file):
    communicate = edge_tts.Communicate(text, voice_model)
    await communicate.save(output_file)

@bot.callback_query_handler(func=lambda call: 'Neural' in call.data)
def process_ai_tts(call):
    chat_id = call.message.chat.id
    if chat_id not in user_temp_text: return bot.answer_callback_query(call.id, "❌ Text expired!", show_alert=True)
    if not check_and_update_limit(chat_id): return ask_to_watch_ad(chat_id)
    bot.edit_message_text("🗣️ Initiating AI Engine... ⏳", chat_id, call.message.message_id)
    try:
        mp3 = f"temp_{chat_id}.mp3"
        wav = f"user_{chat_id}.wav"
        asyncio.run(generate_edge_tts(user_temp_text[chat_id], call.data, mp3))
        subprocess.call(['ffmpeg', '-i', mp3, '-ar', '44100', wav, '-y'], stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
        if os.path.exists(mp3): os.remove(mp3)
        user_files[chat_id] = wav
        del user_temp_text[chat_id] 
        show_effect_categories(chat_id, call.message.message_id)
    except: bot.edit_message_text("❌ Error", chat_id, call.message.message_id)

def get_pitch_filter(semitones):
    r = 2 ** (semitones / 12.0)
    new_rate = int(44100 * r)
    atempo = 1.0 / r
    return f"aresample=44100,asetrate={new_rate},atempo={atempo:.4f}"

@bot.callback_query_handler(func=lambda call: call.data.startswith('eff_'))
def apply_effect(call):
    chat_id = call.message.chat.id
    if user_processing.get(chat_id, False): return bot.answer_callback_query(call.id, "✋ Wait!", show_alert=True)
    if chat_id not in user_files: return bot.answer_callback_query(call.id, "❌ File expire!", show_alert=True)

    user_processing[chat_id] = True
    eff = call.data.split('_')[1]
    msg = bot.send_message(chat_id, "✨ Processing...")
    
    inp = user_files[chat_id]
    out = f"out_{chat_id}.wav"

    try:
        filters = ""
        if eff == 'girl': filters = get_pitch_filter(4)
        elif eff == 'woman': filters = get_pitch_filter(2)
        elif eff == 'kid': filters = get_pitch_filter(7)
        elif eff == 'monster': filters = get_pitch_filter(-6) + ",aecho=0.8:0.9:50:0.2"
        elif eff == 'giant': filters = get_pitch_filter(-4) + ",aecho=0.8:0.9:1000:0.3"
        elif eff == 'alien': filters = get_pitch_filter(3) + ",chorus=0.5:0.9:50|60:0.4|0.32:0.25|0.4:2|2.3"
        elif eff == 'echo': filters = "aecho=0.8:0.9:500:0.4"
        elif eff == 'concert': filters = "aecho=0.8:0.9:1000|1800:0.3|0.25"
        elif eff == 'radio': filters = "highpass=f=600,lowpass=f=3000,volume=1.5"

        if filters: cmd = ['ffmpeg', '-i', inp, '-filter:a', filters, '-y', out]
        else: cmd = ['ffmpeg', '-i', inp, '-y', out]
        
        subprocess.call(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
        with open(out, 'rb') as final_audio:
            bot.send_voice(chat_id, final_audio, caption=f"✨ **Effect:** {eff.upper()}\n🤖 **Bot:** {CHANNEL_USERNAME}", parse_mode="Markdown")
        
        bot.delete_message(chat_id, msg.message_id)
        os.remove(out)
    except: bot.edit_message_text("❌ Error!", chat_id, msg.message_id)
    finally: user_processing[chat_id] = False

if __name__ == "__main__":
    keep_alive()
    bot.infinity_polling()
