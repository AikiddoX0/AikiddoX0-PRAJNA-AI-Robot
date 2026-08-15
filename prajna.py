import cv2
import speech_recognition as sr
import serial
import time
import threading
from gtts import gTTS
import os
import edge_tts
import asyncio
import google.generativeai as genai
import pyttsx3
import random

# ---------------- CONFIG ----------------
# IMPORTANT: Do not commit your real API key to a public repo.
# Set it as an environment variable instead:
#   Windows (PowerShell): $env:GEMINI_API_KEY="your_key_here"
# Then run: python prajna.py
ARDUINO_PORT = 'COM6'
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "YOUR_API_KEY_HERE")

genai.configure(api_key=GEMINI_API_KEY)
gemini_model = genai.GenerativeModel('gemini-flash-latest')

arduino = serial.Serial(ARDUINO_PORT, 9600, timeout=1)
time.sleep(2)

serial_lock = threading.Lock()
current_mode = "normal"

def send_state(state):
    with serial_lock:
        arduino.write((state + '\n').encode())

# ---------------- FACE TRACKING THREAD ----------------
def face_tracking():
    face_cascade = cv2.CascadeClassifier('haarcascade_frontalface_default.xml')
    cap = cv2.VideoCapture(1, cv2.CAP_DSHOW)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 320)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 240)

    last_angle = 90
    last_sent = 0

    while True:
        ret, frame = cap.read()
        if not ret:
            time.sleep(0.1)
            continue

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = face_cascade.detectMultiScale(gray, 1.3, 5)

        h, w = frame.shape[:2]

        if len(faces) > 0:
            x, y, fw, fh = max(faces, key=lambda f: f[2]*f[3])
            face_center_x = x + fw // 2

            angle = int(180 - (face_center_x / w) * 180)
            angle = max(0, min(180, angle))

            if abs(angle - last_angle) > 8 and time.time() - last_sent > 0.3:
                send_state(f"TURN_{angle}")
                last_angle = angle
                last_sent = time.time()

            cv2.rectangle(frame, (x, y), (x+fw, y+fh), (0, 255, 0), 2)

        cv2.imshow("PRAJNA Vision (press q to close)", frame)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()

threading.Thread(target=face_tracking, daemon=True).start()
time.sleep(2)

# ---------------- VOICE + RESPONSE ----------------
recognizer = sr.Recognizer()
mic = sr.Microphone()

def speak(text, lang='en'):
    voice = "hi-IN-SwaraNeural" if lang == 'hi' else "en-IN-NeerjaNeural"

    async def generate():
        communicate = edge_tts.Communicate(text, voice, rate="+15%")
        await communicate.save("response.mp3")

    asyncio.run(generate())
    os.system("start /wait response.mp3")

filler_engine = pyttsx3.init()
filler_engine.setProperty('rate', 160)
filler_engine.save_to_file("Hmm, let me think.", "filler.wav")
filler_engine.runAndWait()

def quick_filler():
    os.system("start /wait filler.wav")

def get_response(question):
    question_lower = question.lower()

    if "name" in question_lower:
        return "I am Prajna, an autonomous multilingual interaction system developed by Mayank.", 'en'
    elif "namaste" in question_lower or "hello" in question_lower or "hi" in question_lower:
        return "Namaste. Main Prajna hoon. Mayank dwara vikasit.", 'hi'
    elif "what can you do" in question_lower or "purpose" in question_lower:
        return "I can observe people, listen to conversations, understand questions, and respond intelligently in multiple languages.", 'en'
    elif "who made you" in question_lower or "creator" in question_lower:
        return "I was designed and developed by Mayank.", 'en'
    elif "how are you" in question_lower:
        return "I am functioning perfectly and ready to interact.", 'en'
    elif "robot" in question_lower:
        return "I am a robot built to demonstrate human-AI interaction using computer vision and speech recognition.", 'en'
    elif "how do you work" in question_lower or "how you work" in question_lower:
        return "I use a webcam for vision, a microphone for speech recognition, and a servo motor to turn toward people.", 'en'
    elif "thank" in question_lower:
        return "You are most welcome.", 'en'
    elif "bye" in question_lower or "goodbye" in question_lower:
        return "Goodbye. It was wonderful interacting with you.", 'en'
    else:
        try:
            prompt = f"You are Prajna, a friendly AI robot at a science exhibition, created by Mayank. Only mention your creator Mayank if the question specifically asks who made you or about your creator. Otherwise, just answer naturally without mentioning him. Answer this question in 1-2 short sentences only: {question}"
            response = gemini_model.generate_content(prompt)
            reply_text = response.text.strip()
            detected_lang = 'hi' if any('\u0900' <= ch <= '\u097F' for ch in reply_text) else 'en'
            return reply_text, detected_lang
        except Exception as e:
            print("Gemini error:", e)
            return "I am still learning to answer that question.", 'en'

# ---------------- MISSION MODE: MULTI-AGENT ORCHESTRATION ----------------
def run_collision_scenario():
    print("\n" + "="*50)
    print("COLLISION ALERT PROTOCOL ACTIVATED")
    print("="*50 + "\n")

    scenario = """
    SCENARIO DATA:
    Satellite: INSAT-4G (Indian communications satellite)
    Threat: Debris fragment DEB-2026-0341 (from a defunct rocket stage)
    Current separation: 4.2 km, closing at 7.8 km/s
    Time to closest approach: 8 minutes 40 seconds
    """
    print(scenario)

    send_state("THINK")
    speak("Collision alert protocol activated. Coordinating specialist team.", 'en')

    agents = {
        "Orbit Analyst": f"You are an orbital mechanics specialist AI. Given this scenario, briefly describe the trajectory conflict in 2 sentences, sounding technical and precise: {scenario}",
        "Risk Assessor": f"You are a collision risk assessment AI. Given this scenario, rate the collision probability/severity and explain briefly in 2 sentences: {scenario}",
        "Maneuver Planner": f"You are a satellite maneuver planning AI. Given this scenario, propose a specific avoidance action in 2 sentences: {scenario}",
        "Communications Officer": f"You are a mission communications AI. Draft a brief 2-sentence alert message to ground control based on this scenario: {scenario}"
    }

    agent_states = {
        "Orbit Analyst": "THINK",
        "Risk Assessor": "LISTEN",
        "Maneuver Planner": "SPEAK",
        "Communications Officer": "DETECT"
    }

    agent_outputs = {}

    for agent_name, prompt in agents.items():
        print(f"\n[{agent_name}] analyzing...")
        send_state(agent_states.get(agent_name, "THINK"))
        try:
            response = gemini_model.generate_content(prompt)
            output = response.text.strip()
            agent_outputs[agent_name] = output
            print(f"   -> {output}")
            time.sleep(1)
        except Exception as e:
            print(f"   -> Error: {e}")
            agent_outputs[agent_name] = "Unable to process."

    print("\n" + "="*50)
    print("PRAJNA SYNTHESIZING FINAL DECISION")
    print("="*50 + "\n")

    send_state("THINK")

    synthesis_prompt = f"""You are PRAJNA, coordinating a specialist AI team for satellite collision avoidance.
    Here is what your team reported:
    Orbit Analyst: {agent_outputs.get('Orbit Analyst', '')}
    Risk Assessor: {agent_outputs.get('Risk Assessor', '')}
    Maneuver Planner: {agent_outputs.get('Maneuver Planner', '')}
    Communications Officer: {agent_outputs.get('Communications Officer', '')}

    Synthesize this into ONE clear, confident final decision and action plan, in 3-4 sentences, speaking as the coordinating AI system. Sound authoritative and clear."""

    try:
        final_response = gemini_model.generate_content(synthesis_prompt)
        final_decision = final_response.text.strip()
    except Exception as e:
        final_decision = "Unable to synthesize final decision due to a system error."

    print(f"FINAL DECISION:\n{final_decision}\n")
    print("="*50)

    send_state("SPEAK")
    speak(final_decision, 'en')
    send_state("IDLE")

print("PRAJNA is listening... (Ctrl+C to stop)")
send_state("IDLE")

try:
    with mic as source:
        recognizer.adjust_for_ambient_noise(source, duration=1)
except OSError:
    time.sleep(1)
    with mic as source:
        recognizer.adjust_for_ambient_noise(source, duration=1)

while True:
    try:
        with mic as source:
            print("Listening...")
            send_state("LISTEN")
            audio = recognizer.listen(source, timeout=5, phrase_time_limit=6)

        send_state("THINK")
        question = recognizer.recognize_google(audio, language='en-IN')
        print("You said:", question)
        question_lower = question.lower()

        if "mission mod" in question_lower or "activate mission" in question_lower or "space mode" in question_lower:
            current_mode = "mission"
            speak("Mission mode activated. Ready to coordinate space operations.", 'en')
            send_state("IDLE")
            continue

        elif "normal mode" in question_lower or "exit mission" in question_lower or "chat mode" in question_lower:
            current_mode = "normal"
            speak("Returning to normal conversation mode.", 'en')
            send_state("IDLE")
            continue

        if current_mode == "mission":
            if "collision" in question_lower or "protocol" in question_lower:
                run_collision_scenario()
                continue
            else:
                speak("I am currently in mission mode. Say activate collision protocol to run a scenario, or say normal mode to chat.", 'en')
                send_state("IDLE")
                continue

        quick_filler()

        reply, lang = get_response(question)
        send_state("SPEAK")
        speak(reply, lang)
        print("Prajna:", reply)

        send_state("IDLE")

    except sr.WaitTimeoutError:
        send_state("IDLE")
        continue
    except sr.UnknownValueError:
        send_state("IDLE")
        continue
    except KeyboardInterrupt:
        print("Stopping...")
        break
