import telebot
from telebot import types
from gtts import gTTS
import soundfile as sf
import numpy as np
import os
import subprocess
import time
from flask import Flask
from threading import Thread

# ==========================================
# 👇 CONFIGURATION 👇
# ==========================================
BOT_TOKEN = os.getenv('BOT_TOKEN')
ADMIN_ID = os.getenv('ADMIN_ID')    # <--- Apna Chat ID dalo
CHANNEL_USERNAME = '@errorkid_05' 
# ==========================================


# --- FAKE SERVER FOR RENDER ---
app = Flask('')

@app.route('/')
def home():
    return "I am alive"

def run_http():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run_http)
    t.start()

# --- BOT SETUP ---
bot = telebot.TeleBot(BOT_TOKEN)

user_modes = {}
user_files = {}
user_processing = {}
DB_FILE = "users_db.txt"


bot = telebot.TeleBot(BOT_TOKEN)

# --- MEMORY ---
user_modes = {}       # User kis mode me hai (Text/Voice)
user_files = {}       # User ki original file
user_processing = {}  # 🔒 LOCK SYSTEM: Kaun abhi wait kar raha hai
DB_FILE = "users_db.txt"

print("🔥 Master Bot Online! Anti-Spam & Auto-Reconnect Active...")

# --- DATABASE FUNCTIONS ---
def get_users():
    if not os.path.exists(DB_FILE):
        return []
    with open(DB_FILE, "r") as f:
        return [line.strip() for line in f.readlines()]

def save_user(chat_id):
    users = get_users()
    if str(chat_id) not in users:
        with open(DB_FILE, "a") as f:
            f.write(f"{chat_id}\n")

# --- HELPER: CHECK SUBSCRIPTION ---
def check_subscription(user_id):
    try:
        member = bot.get_chat_member(CHANNEL_USERNAME, user_id)
        if member.status in ['creator', 'administrator', 'member']:
            return True
        return False
    except Exception as e:
        print(f"Verification Error: {e}") 
        return False 

def ask_for_join(chat_id):
    markup = types.InlineKeyboardMarkup()
    btn_join = types.InlineKeyboardButton("📢 Join Channel", url=f"https://t.me/{CHANNEL_USERNAME.replace('@', '')}")
    btn_check = types.InlineKeyboardButton("✅ Joined", callback_data='check_join')
    markup.add(btn_join)
    markup.add(btn_check)
    bot.send_message(chat_id, f"⚠️ **Access Denied!**\n\nIs Bot ko use karne ke liye hamara channel join karein:\n{CHANNEL_USERNAME}", reply_markup=markup, parse_mode="Markdown")

# --- 1. ADMIN COMMANDS (Broadcast) ---
@bot.message_handler(commands=['broadcast'])
def broadcast_msg(message):
    if message.chat.id != ADMIN_ID:
        bot.reply_to(message, "❌ Aap Admin nahi ho!")
        return

    msg = message.text.replace("/broadcast", "").strip()
    if not msg:
        bot.reply_to(message, "Message likho! Ex: `/broadcast Hello`")
        return

    users = get_users()
    sent = 0
    status = bot.reply_to(message, f"📢 Sending to {len(users)} users...")

    for uid in users:
        try:
            bot.send_message(uid, f"📢 **Announcement:**\n\n{msg}", parse_mode="Markdown")
            sent += 1
        except:
            pass

    bot.edit_message_text(f"✅ Broadcast Sent to {sent} users.", message.chat.id, status.message_id)

# --- 2. MAIN MENU (/start) ---
@bot.message_handler(commands=['start'])
def start_command(message):
    chat_id = message.chat.id
    save_user(chat_id)

    # Reset Processing Lock
    if chat_id in user_processing:
        del user_processing[chat_id]

    if not check_subscription(chat_id):
        ask_for_join(chat_id)
        return

    markup = types.InlineKeyboardMarkup(row_width=2)
    btn1 = types.InlineKeyboardButton("📝 Text to Audio", callback_data='mode_text')
    btn2 = types.InlineKeyboardButton("🎤 Voice Changer", callback_data='mode_voice')
    btn_dev = types.InlineKeyboardButton("👨‍💻 Developer", url='https://t.me/errorkid_05')

    markup.add(btn1, btn2)
    markup.row(btn_dev)

    welcome = (
        "👋 **Welcome to Voice Bot!**\n\n"
        "Kya karna chahte ho?\n"
        "🔹 **Text:** Likh ke audio banao.\n"
        "🔹 **Voice:** Apni awaaz badlo."
    )
    bot.send_message(chat_id, welcome, reply_markup=markup, parse_mode="Markdown")

# --- 3. CALLBACK HANDLERS ---
@bot.callback_query_handler(func=lambda call: call.data in ['mode_text', 'mode_voice', 'check_join'])
def set_mode_handler(call):
    chat_id = call.message.chat.id

    if call.data == 'check_join':
        if check_subscription(chat_id):
            bot.delete_message(chat_id, call.message.message_id)
            start_command(call.message)
        else:
            bot.answer_callback_query(call.id, "❌ Aapne abhi tak join nahi kiya!", show_alert=True)
        return

    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🔙 Back to Main Menu", callback_data='back'))

    if call.data == 'mode_text':
        user_modes[chat_id] = 'text'
        msg = "📝 **Mode Selected: Text to Audio**\n\nAb apna **TEXT** likh kar bhejo.\n(Voice mat bhejna!)"
    else:
        user_modes[chat_id] = 'voice'
        msg = "🎤 **Mode Selected: Voice Changer**\n\nAb apni **VOICE** record karke ya audio file bhejo.\n(Text mat likhna!)"
    
    bot.edit_message_text(msg, chat_id, call.message.message_id, parse_mode="Markdown", reply_markup=markup)

# --- 4. INPUT HANDLING ---
@bot.message_handler(content_types=['text'])
def handle_text_input(message):
    chat_id = message.chat.id

    if not check_subscription(chat_id):
        ask_for_join(chat_id)
        return
    
    current_mode = user_modes.get(chat_id)

    if current_mode == 'voice':
        bot.reply_to(message, "❌ **Wrong Input!**\nVoice Changer mode hai. Audio bhejo.")
        return
    elif current_mode != 'text':
        bot.reply_to(message, "⚠️ Pehle /start dabakar mode select karein!")
        return

    msg = bot.reply_to(message, "🗣️ Generating Audio... ⏳")
    try:
        tts = gTTS(text=message.text, lang='hi')
        mp3 = f"temp_{chat_id}.mp3"
        wav = f"user_{chat_id}.wav"

        tts.save(mp3)
        subprocess.call(['ffmpeg', '-i', mp3, wav, '-y'], stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)

        if os.path.exists(mp3): os.remove(mp3)
        user_files[chat_id] = wav
        show_effects(chat_id, msg.message_id)

    except Exception as e:
        bot.reply_to(message, f"❌ Error: {e}")

@bot.message_handler(content_types=['voice', 'audio'])
def handle_audio_input(message):
    chat_id = message.chat.id

    if not check_subscription(chat_id):
        ask_for_join(chat_id)
        return

    current_mode = user_modes.get(chat_id)

    if current_mode == 'text':
        bot.reply_to(message, "❌ **Wrong Input!**\nText Mode hai. Text likho.")
        return
    elif current_mode != 'voice':
        bot.reply_to(message, "⚠️ Pehle /start dabakar mode select karein!")
        return

    msg = bot.reply_to(message, "⬇️ Downloading... ⏳")
    try:
        if message.content_type == 'voice':
            file_id = message.voice.file_id
        else:
            file_id = message.audio.file_id

        file_info = bot.get_file(file_id)
        downloaded = bot.download_file(file_info.file_path)

        temp = f"temp_{chat_id}"
        wav = f"user_{chat_id}.wav"

        with open(temp, 'wb') as f: f.write(downloaded)
        subprocess.call(['ffmpeg', '-i', temp, wav, '-y'], stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)

        if os.path.exists(temp): os.remove(temp)
        user_files[chat_id] = wav
        show_effects(chat_id, msg.message_id)

    except Exception as e:
        bot.reply_to(message, f"❌ Error: {e}")

# --- HELPER: SHOW ALL 12 EFFECTS ---
def show_effects(chat_id, msg_id):
    markup = types.InlineKeyboardMarkup(row_width=3)
    btns = [
        types.InlineKeyboardButton("👩 Girl", callback_data='girl'),
        types.InlineKeyboardButton("👩‍🦰 Woman", callback_data='woman'),
        types.InlineKeyboardButton("👶 Kid", callback_data='kid'),
        types.InlineKeyboardButton("🐿️ Chipmunk", callback_data='chipmunk'),
        types.InlineKeyboardButton("👹 Monster", callback_data='monster'),
        types.InlineKeyboardButton("🦍 Giant", callback_data='giant'),
        types.InlineKeyboardButton("👻 Ghost", callback_data='ghost'),
        types.InlineKeyboardButton("👽 Alien", callback_data='alien'),
        types.InlineKeyboardButton("🤖 Robot", callback_data='robot'),
        types.InlineKeyboardButton("📢 Echo", callback_data='echo'),
        types.InlineKeyboardButton("📻 Radio", callback_data='radio'),
        types.InlineKeyboardButton("🔄 Reverse", callback_data='reverse')
    ]
    markup.add(*btns)
    markup.row(types.InlineKeyboardButton("🔙 Back to Main Menu", callback_data='back'))

    try:
        bot.edit_message_text("✅ **Audio Ready!**\nAb Effect Select karo:", chat_id, msg_id, reply_markup=markup, parse_mode="Markdown")
    except:
        bot.send_message(chat_id, "✅ **Audio Ready!**\nAb Effect Select karo:", reply_markup=markup)

# --- 5. APPLY EFFECTS (LOGIC) ---
@bot.callback_query_handler(func=lambda call: call.data not in ['mode_text', 'mode_voice', 'check_join'])
def apply_effect(call):
    chat_id = call.message.chat.id

    # Handle Back Button
    if call.data == 'back':
        if chat_id in user_files and os.path.exists(user_files[chat_id]):
            os.remove(user_files[chat_id])
            del user_files[chat_id]
        if chat_id in user_processing: 
            del user_processing[chat_id] # Lock bhi hata do
        
        user_modes[chat_id] = None
        bot.delete_message(chat_id, call.message.message_id)
        start_command(call.message) 
        return

    # 🔒 ANTI-SPAM LOCK CHECK 🔒
    # Agar user pehle se koi process kar raha hai, to roko
    if user_processing.get(chat_id, False) == True:
        bot.answer_callback_query(call.id, "✋ Ruko! Pehle wala complete hone do!", show_alert=True)
        return

    # Check Validity
    if chat_id not in user_files or not os.path.exists(user_files[chat_id]):
        bot.answer_callback_query(call.id, "❌ File expire ho gayi! /start dabao.")
        return

    # 🔒 LOCK LAGAO
    user_processing[chat_id] = True
    
    bot.answer_callback_query(call.id, "✨ Applying Magic...")
    bot.send_chat_action(chat_id, 'record_audio')

    inp = user_files[chat_id]
    out = f"out_{chat_id}.wav"

    try:
        data, rate = sf.read(inp)
        eff = call.data

        # --- EFFECTS LOGIC ---
        if eff == 'girl': sf.write(out, data, int(rate * 1.3))
        elif eff == 'woman': sf.write(out, data, int(rate * 1.15))
        elif eff == 'kid': sf.write(out, data, int(rate * 1.25))
        elif eff == 'chipmunk': sf.write(out, data, int(rate * 1.5))
        elif eff == 'monster': sf.write(out, data, int(rate * 0.6))
        elif eff == 'giant': sf.write(out, data, int(rate * 0.4))
        elif eff == 'ghost': sf.write(out, data[::-1], rate)
        elif eff == 'reverse': sf.write(out, data[::-1], int(rate * 1.2))
        elif eff == 'robot':
            if len(data.shape) > 1: sf.write(out, data[::2].repeat(2, axis=0), rate)
            else: sf.write(out, data[::2].repeat(2), rate)
        elif eff == 'radio':
            noise = np.random.normal(0, 0.01, data.shape)
            sf.write(out, data + noise, rate)
        elif eff == 'alien': sf.write(out, data, int(rate * 1.8))
        elif eff == 'echo':
            delay = int(rate * 0.3)
            padding = np.zeros((delay, data.shape[1])) if len(data.shape) > 1 else np.zeros(delay)
            delayed = np.concatenate((padding, data))[:-delay]
            sf.write(out, data + 0.6 * delayed, rate)

        with open(out, 'rb') as audio:
            bot.send_voice(chat_id, audio, caption=f"✨ Effect: {eff.upper()}")
        os.remove(out)

    except Exception as e:
        print(f"Effect Error: {e}")
        bot.answer_callback_query(call.id, "❌ Error creating effect!")

    finally:
        # 🔓 LOCK HATAO (Chahe error aaye ya success ho)
        user_processing[chat_id] = False

#  --- AUTO RESTART & KEEP ALIVE ---
if __name__ == "__main__":
    keep_alive()  # <--- YEH LINE ZAROORI HAI RENDER KE LIYE
    while True:
        try:
            print("🚀 Bot Started on Render...")
            bot.infinity_polling(timeout=10, long_polling_timeout=5)
        except Exception as e:
            print(f"⚠️ Connection Lost: {e}")
            time.sleep(5)
