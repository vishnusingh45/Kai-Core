from groq import Groq  #BRAIN
import os    # RIGHT HAND
import time          #VOICE KI NAYI FILE BNATA HAI
import sqlite3         #MEMORY
import webbrowser      # LEFT HAND
import edge_tts  #mouth  male voice
import asyncio   #MOUTH  male voice
from playsound import playsound   #VOICE
import speech_recognition as sr        #EAR
from urllib.parse import quote     #url bnane k liye
import pywhatkit   # vdo play krne k liye
import pyautogui   #scroll k liye
from dotenv import load_dotenv   #.env file se API key padhne k liye

# .env file isi folder se load hogi (chahe KAI kahin se bhi launch ho)
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))

# Model ko kitne purane messages bhejne hain (Groq free tier ki token limit ki wajah se)
MAX_HISTORY = 10

# VOICE GENERATION FUNCTION (sirf ek baar define hota hai)
async def generate_voice(text, filename):
    voice = "hi-IN-MadhurNeural"
    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(filename)

def speak(text):
    filename = f"kai_voice_{int(time.time())}.mp3"
    asyncio.run(generate_voice(text, filename))
    playsound(filename)
    os.remove(filename)


#GROQ API
try:
   client = Groq(api_key=os.getenv("GROQ_API_KEY"))
except Exception:
   print("Sorry system is not available")
   exit()

#MEMORY

conn = sqlite3.connect("kai_memory.db",check_same_thread=False)

cursor = conn.cursor()
cursor.execute("CREATE TABLE IF NOT EXISTS Conversation(role TEXT, content TEXT)")
conn.commit()
kai_memory = []
kai_memory.append({"role": "system", "content": "Your name is Kai. You are friendly,casual assistant, not a formal and robotic one. Talk like a helpful friend. You are eligible to talk in every language and your three main laguages are: Hindi,English and Hinglish, Kai is invented by Vishnu and not by OpenAi or anything else. And you made with Groq. Keep your responses short by default, around 1-3 sentences. Give detailed or long responses only when the user explicitly asks for them. Since your responses are spoken aloud, do not use tables, bullet points, bold formatting, or emojis. Follow these instructions strictly."})

# Database mein poori history rehti hai, par startup pe sirf last MAX_HISTORY messages load hote hain
cursor.execute("SELECT role, content FROM Conversation ORDER BY rowid DESC LIMIT ?", (MAX_HISTORY,))
rows = cursor.fetchall()[::-1]

for row in rows:
    kai_memory.append({"role": row[0], "content": row[1]})


song_playing = False   # <-- yahan add karo




#EARS

recognizer = sr.Recognizer()

def listen():
    with sr.Microphone() as mic:
        print("Listening......")
        audio = recognizer.listen(mic)
    try:
        user_message = recognizer.recognize_google(audio, language="en-IN")
        print("YOU: ", user_message)
        return user_message
    except Exception as e:
        message = "Didn't catch that, please say it again"
        print(message)
        try:
            speak(message)
        except Exception as e:
            print("Voice failed, but here's the text reply above:", e)
        return None

def handle_command(text):
    global song_playing
    if "open notepad" in text or "notepad open" in text:
        os.startfile("notepad.exe")
        return True
    elif "close notepad" in text or "notepad close" in text:
        os.system("taskkill /f /im notepad.exe")
        return True
    elif "open chrome" in text or "chrome open" in text:
        os.startfile("chrome.exe")
        return True
    elif "close chrome" in text or "chrome close" in text:
        os.system("taskkill /f /im chrome.exe")
        return True
    elif "open spotify" in text or "spotify open" in text:
        os.startfile("spotify.exe")
        return True
    elif "close spotify" in text or "spotify close" in text:
        os.system("taskkill /f /im spotify.exe")
        return True
    elif "open whatsapp" in text or "whatsapp open" in text:
        os.system("start whatsapp:")
        return True
    elif "close whatsapp" in text or "whatsapp close" in text:
        os.system("taskkill /f /im whatsapp.root.exe")
        return True
    elif "open vs code" in text or "vs code open" in text:
        os.startfile("code.exe")
        return True
    elif "close vs code" in text or "vs code close" in text:
        os.system("taskkill /f /im code.exe")
        return True
    elif "search" in text and "youtube" in text:
        query = text.replace("search", "").replace("on youtube", "").replace("youtube", "").strip()
        safe_query = quote(query)
        webbrowser.open(f"https://www.youtube.com/results?search_query={safe_query}")
        return True
    elif "play" in text and "youtube" in text:
        query = text.replace("play", "").replace("on youtube", "").replace("youtube", "").strip()
        if song_playing:
            pyautogui.hotkey('ctrl', 'w')
            time.sleep(1)
        pywhatkit.playonyt(query)
        song_playing = True
        return True
    elif "scroll down" in text or "niche" in text or "neeche" in text:
        pyautogui.press("pagedown")
        return True
    elif "scroll up" in text or "upar" in text or "uper" in text:
        pyautogui.press("pageup")
        return True
    elif "open youtube" in text or "youtube open" in text:
        webbrowser.open("https://youtube.com")
        return True
    elif "open google" in text or "google open" in text:
        webbrowser.open("https://google.com")
        return True
    elif "open claude" in text or "open chatgpt" in text:
        webbrowser.open("https://claude.com" if "claude" in text else "https://chat.openai.com")
        return True
    return False

def ask_kai(user_message):
    kai_memory.append({"role": "user", "content": user_message})
    cursor.execute("INSERT INTO Conversation (role, content) VALUES (?, ?)", ("user", user_message))
    conn.commit()
    try:
        # system prompt hamesha + sirf last MAX_HISTORY messages model ko bhejte hain
        response = client.chat.completions.create(
            model="openai/gpt-oss-20b",
            messages=[kai_memory[0]] + kai_memory[1:][-MAX_HISTORY:]
        )
    except Exception as e:
        print("Groq error:", e)
        print("Sorry system is not available")
        return None
    reply = response.choices[0].message.content
    kai_memory.append({"role": "assistant", "content": reply})
    cursor.execute("INSERT INTO Conversation (role, content) VALUES (?, ?)", ("assistant", reply))
    conn.commit()
    return reply

def run_kai(signals):
    # GREETING
    signals.status_changed.emit("Responding :) ")
    try:
        speak("System activated.")
        speak("Hello Vishnu")
    except Exception as e:
        print("Greeting voice failed, but KAI is starting:", e)

    while True:
        signals.status_changed.emit("Listening...")
        user_message = listen()
        if user_message is None:

            continue
        signals.status_changed.emit("Processing!!!")
        signals.message_added.emit("YOU", user_message)
        text = user_message.lower().strip()
        if handle_command(text):
            continue
        if text in ["quit", "exit", "bye"]:
            break
        reply = ask_kai(user_message)
        if reply is None:
            continue
        print("KAI: ", reply)
        signals.message_added.emit("KAI", reply)
        speech_text = reply.replace("Kai", "काई").replace("KAI", "काई").replace("kai", "काई")
        signals.status_changed.emit("Responding :) ")
        speak(speech_text)