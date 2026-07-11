import telebot
from telebot import types
import soundfile as sf
import numpy as np
import os
import subprocess
import time
import asyncio
import edge_tts
from flask import Flask
from threading import Thread

# --- Nayi Premium Audio Library ---
from pedalboard import Pedalboard, PitchShift, Reverb, Delay, Chorus, Distortion, HighpassFilter, LowpassFilter
from pedalboard.io import AudioFile

# ==========================================
# 👇 CONFIGURATION 👇
# ==========================================
BOT_TOKEN = os.getenv('BOT_TOKEN') # Yahan apna token hardcode bhi kar sakte ho
try:
    ADMIN_ID = int(os.getenv('ADMIN_ID', 0)) 
except (TypeError, ValueError):
    print("⚠️ Warning: ADMIN_ID not set or invalid.")
    ADMIN_ID = 0

CHANNEL_USERNAME = '@errorkid_05' 
DB_FILE = "users_db.txt"
# ==========================================

# --- MEMORY ---
user_modes = {}       
user_files = {}       
user_processing = {}  
user_temp_text = {}   

# --- FAKE SERVER FOR RENDER ---
app = Flask('')

@app.route('/')
def home():
    return "Premium Voice Bot is alive!"

def run_http():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run_http)
    t.start()

# --- BOT SETUP ---
bot = telebot.TeleBot(BOT_TOKEN)
print("🔥 Premium Bot Online! Edge-TTS & Pedalboard Active...")

# --- DATABASE & SUBSCRIPTION (Same as before) ---
def get_users():
    if not os.path.exists(DB_FILE): return []
    with open(DB_FILE, "r") as f: return [line.strip() for line in f.readlines()]

def save_user(chat_id):
    users = get_users()
    if str(chat_id) not in users:
        with open(DB_FILE, "a") as f: f.write(f"{chat_id}\n")

def check_subscription(user_id):
    if user_id == ADMIN_ID: return True
    try:
        member = bot.get_chat_member(CHANNEL_USERNAME, user_id)
        if member.status in ['creator', 'administrator', 'member']: return True
        return False
    except:
        return True 

def ask_for_join(chat_id):
    markup = types.InlineKeyboardMarkup()
    btn_join = types.InlineKeyboardButton("📢 Join Channel", url=f"https://t.me/{CHANNEL_USERNAME.replace('@', '')}")
    btn_check = types.InlineKeyboardButton("✅ Joined", callback_data='check_join')
    markup.add(btn_join, btn_check)
    bot.send_message(chat_id, f"⚠️ **Access Denied!**\nPehle channel join karein:\n{CHANNEL_USERNAME}", reply_markup=markup, parse_mode="Markdown")


# --- START COMMAND ---
@bot.message_handler(commands=['start'])
def start_command(message):
    chat_id = message.chat.id
    save_user(chat_id)

    if chat_id in user_processing: del user_processing[chat_id]
    if not check_subscription(chat_id):
        ask_for_join(chat_id)
        return

    markup = types.InlineKeyboardMarkup(row_width=2)
    btn1 = types.InlineKeyboardButton("📝 Text to Audio (AI)", callback_data='mode_text')
    btn2 = types.InlineKeyboardButton("🎤 Voice Changer (Pro)", callback_data='mode_voice')
    markup.add(btn1, btn2)

    user_name = message.chat.first_name or "User"
    caption = f"🏆 <b>PREMIUM VOICE OSINT</b> 🏆\n\n👤 <b>User:</b> {user_name}\n👑 <b>Status:</b> Premium Access\n\nSelect a module below:"
    
    bot.send_message(chat_id, caption, parse_mode="HTML", reply_markup=markup)


# --- INPUT HANDLING ---
@bot.message_handler(content_types=['text'])
def handle_text_input(message):
    chat_id = message.chat.id
    if not check_subscription(chat_id): return ask_for_join(chat_id)
    
    if user_modes.get(chat_id) != 'text':
        return bot.reply_to(message, "⚠️ Pehle /start dabakar 'Text to Audio' mode select karein!")

    user_temp_text[chat_id] = message.text

    # Naye AI Voices ke buttons
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("👨🏽 Hindi Male", callback_data='hi-IN-MadhurNeural'),
        types.InlineKeyboardButton("👩🏽 Hindi Female", callback_data='hi-IN-SwaraNeural'),
        types.InlineKeyboardButton("👨🏻 English Male", callback_data='en-US-GuyNeural'),
        types.InlineKeyboardButton("👩🏻 English Female", callback_data='en-US-AriaNeural')
    )
    bot.reply_to(message, "🌟 **Premium AI Voice Select karo:**", reply_markup=markup, parse_mode="Markdown")


@bot.message_handler(content_types=['voice', 'audio'])
def handle_audio_input(message):
    chat_id = message.chat.id
    if not check_subscription(chat_id): return ask_for_join(chat_id)

    if user_modes.get(chat_id) != 'voice':
        return bot.reply_to(message, "⚠️ Pehle /start dabakar 'Voice Changer' mode select karein!")

    msg = bot.reply_to(message, "⬇️ Downloading & Processing... ⏳")
    try:
        file_id = message.voice.file_id if message.content_type == 'voice' else message.audio.file_id
        file_info = bot.get_file(file_id)
        downloaded = bot.download_file(file_info.file_path)

        temp = f"temp_{chat_id}"
        wav = f"user_{chat_id}.wav"

        with open(temp, 'wb') as f: f.write(downloaded)
        # Convert to standard WAV for Pedalboard
        subprocess.call(['ffmpeg', '-i', temp, '-ar', '44100', wav, '-y'], stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
        if os.path.exists(temp): os.remove(temp)
        
        user_files[chat_id] = wav
        show_effects(chat_id, msg.message_id)
    except Exception as e:
        bot.reply_to(message, f"❌ Error: {e}")

def show_effects(chat_id, msg_id):
    markup = types.InlineKeyboardMarkup(row_width=3)
    btns = [
        types.InlineKeyboardButton("👩 Girl", callback_data='girl'),
        types.InlineKeyboardButton("👩‍🦰 Woman", callback_data='woman'),
        types.InlineKeyboardButton("👶 Kid", callback_data='kid'),
        types.InlineKeyboardButton("👹 Monster", callback_data='monster'),
        types.InlineKeyboardButton("🦍 Giant", callback_data='giant'),
        types.InlineKeyboardButton("👽 Alien", callback_data='alien'),
        types.InlineKeyboardButton("📢 Echo Studio", callback_data='echo'),
        types.InlineKeyboardButton("📻 Walkie-Talkie", callback_data='radio'),
        types.InlineKeyboardButton("🎤 Concert", callback_data='concert')
    ]
    markup.add(*btns)
    markup.row(types.InlineKeyboardButton("🔙 Menu", callback_data='back'))

    bot.edit_message_text("✅ **Studio Ready!**\nAb Pro Effect Select karo:", chat_id, msg_id, reply_markup=markup, parse_mode="Markdown")


# ==========================================
# --- CALLBACK HANDLERS ---
# ==========================================

@bot.callback_query_handler(func=lambda call: call.data in ['mode_text', 'mode_voice'])
def set_mode_handler(call):
    chat_id = call.message.chat.id
    bot.answer_callback_query(call.id)
    user_modes[chat_id] = call.data.split('_')[1]
    
    msg = "📝 **Text to Audio:** Text bhejo!" if user_modes[chat_id] == 'text' else "🎤 **Voice Changer:** Audio/Voice bhejo!"
    bot.edit_message_text(msg, chat_id, call.message.message_id, parse_mode="Markdown")

# Edge-TTS Async Runner
async def generate_edge_tts(text, voice_model, output_file):
    communicate = edge_tts.Communicate(text, voice_model)
    await communicate.save(output_file)

@bot.callback_query_handler(func=lambda call: 'Neural' in call.data)
def process_ai_tts(call):
    chat_id = call.message.chat.id
    bot.answer_callback_query(call.id)
    
    if chat_id not in user_temp_text:
        return bot.answer_callback_query(call.id, "❌ Text expired!", show_alert=True)

    bot.edit_message_text("🗣️ Generating Studio Quality AI Voice... ⏳", chat_id, call.message.message_id)

    try:
        mp3 = f"temp_{chat_id}.mp3"
        wav = f"user_{chat_id}.wav"
        
        # Run async Edge-TTS
        asyncio.run(generate_edge_tts(user_temp_text[chat_id], call.data, mp3))
        
        # Convert to WAV
        subprocess.call(['ffmpeg', '-i', mp3, '-ar', '44100', wav, '-y'], stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)

        if os.path.exists(mp3): os.remove(mp3)
        user_files[chat_id] = wav
        del user_temp_text[chat_id] 
        show_effects(chat_id, call.message.message_id)

    except Exception as e:
        bot.edit_message_text(f"❌ Error: {e}", chat_id, call.message.message_id)

# Premium Effects (True Pitch Shifting)
@bot.callback_query_handler(func=lambda call: True)
def apply_effect(call):
    chat_id = call.message.chat.id
    if call.data == 'back':
        bot.delete_message(chat_id, call.message.message_id)
        start_command(call.message)
        return

    if user_processing.get(chat_id, False): return bot.answer_callback_query(call.id, "✋ Wait!", show_alert=True)
    if chat_id not in user_files: return bot.answer_callback_query(call.id, "❌ File expire!", show_alert=True)

    user_processing[chat_id] = True
    bot.answer_callback_query(call.id, "✨ Applying Studio Effects...")
    
    inp = user_files[chat_id]
    out = f"out_{chat_id}.wav"

    try:
        # Load audio with Pedalboard
        with AudioFile(inp) as f:
            audio = f.read(f.frames)
            samplerate = f.samplerate

        board = Pedalboard([])
        eff = call.data

        # 🎛️ TRUE PITCH SHIFTING (Speed remains constant!)
        if eff == 'girl': board.append(PitchShift(semitones=4))
        elif eff == 'woman': board.append(PitchShift(semitones=2))
        elif eff == 'kid': board.append(PitchShift(semitones=7))
        elif eff == 'monster': 
            board.append(PitchShift(semitones=-6))
            board.append(Distortion(drive_db=5))
        elif eff == 'giant': 
            board.append(PitchShift(semitones=-4))
            board.append(Reverb(room_size=0.8, damping=0.9))
        elif eff == 'alien':
            board.append(PitchShift(semitones=3))
            board.append(Chorus(rate_hz=2.0, depth=0.5))
        elif eff == 'echo': board.append(Delay(delay_seconds=0.3, feedback=0.4))
        elif eff == 'concert': board.append(Reverb(room_size=1.0, damping=0.1, wet_level=0.5))
        elif eff == 'radio':
            board.append(HighpassFilter(cutoff_frequency_hz=800))
            board.append(LowpassFilter(cutoff_frequency_hz=2500))
            board.append(Distortion(drive_db=8))

        # Apply magic!
        effected = board(audio, samplerate)

        with AudioFile(out, 'w', samplerate, effected.shape[0]) as f:
            f.write(effected)

        with open(out, 'rb') as final_audio:
            bot.send_voice(chat_id, final_audio, caption=f"✨ Studio Effect: {eff.upper()}")
        
        os.remove(out)
    except Exception as e:
        print(f"Effect Error: {e}")
        bot.answer_callback_query(call.id, "❌ Error creating effect!", show_alert=True)
    finally:
        user_processing[chat_id] = False

if __name__ == "__main__":
    keep_alive()
    bot.infinity_polling()
