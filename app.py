import gradio as gr
import os
import requests
import time
import whisper
from deep_translator import GoogleTranslator
from twilio.rest import Client
import threading
from dotenv import load_dotenv

load_dotenv()

GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
MODEL_NAME = "llama-3.3-70b-versatile"

# Load Whisper model
try:
    model_whisper = whisper.load_model("base")
except:
    model_whisper = whisper.load_model("tiny")

# Bot personality settings
system_prompts = {
    "Hazard Alerts (INDIANA)": "You are a hazard alert assistant for Indiana...",
    "Adaptive Crisis Response (ARK)": "You are ARK...",
    "Emotional Support (RAY)": "You are RAY...",
    "Survival & Logistics (BOLT)": "You are BOLT...",
    "Disaster Preparedness (READYBOT)": "You are READYBOT..."
}

variant_intros = {
    "Hazard Alerts (INDIANA)": "Hello, I am your **Indiana Hazard Alert Bot**...",
    "Adaptive Crisis Response (ARK)": "Hello, I am **ARK**...",
    "Emotional Support (RAY)": "Hi, I am **RAY**...",
    "Survival & Logistics (BOLT)": "Hello, I am **BOLT**...",
    "Disaster Preparedness (READYBOT)": "Greetings, I am **READYBOT**..."
}

variant_colors = {
    "Hazard Alerts (INDIANA)": {"bg": "#b91c1c", "text": "#ffffff"},
    "Adaptive Crisis Response (ARK)": {"bg": "#1e3a8a", "text": "#ffffff"},
    "Emotional Support (RAY)": {"bg": "#9333ea", "text": "#ffffff"},
    "Survival & Logistics (BOLT)": {"bg": "#0f766e", "text": "#ffffff"},
    "Disaster Preparedness (READYBOT)": {"bg": "#ca8a04", "text": "#000000"}
}

def get_groq_api_key():
    return os.getenv("GROQ_API_KEY")

def translate_text(text, target_lang='en'):
    try:
        return GoogleTranslator(source='auto', target=target_lang).translate(text)
    except Exception as e:
        return f"[Translation Error]: {e}"

def query_groq(message, chat_history, variant):
    if variant == "Hazard Alerts (INDIANA)":
        try:
            nws = requests.get("https://api.weather.gov/alerts/active?area=IN", timeout=10).json()
            fema = requests.get("https://www.fema.gov/api/open/v2/DisasterDeclarationsSummaries?$filter=state eq 'IN'", timeout=10).json()
            alerts = nws.get("features", [])
            disasters = fema.get("DisasterDeclarationsSummaries", [])

            result = f"📡 NWS Alerts: {len(alerts)}\n"
            for a in alerts[:3]:
                result += f"- {a['properties']['event']}: {a['properties']['headline']}\n"

            result += f"\n📜 FEMA Disasters: {len(disasters)}\n"
            for d in disasters[:3]:
                result += f"- {d['incidentType']} on {d['declarationDate']} in {d['designatedArea']}\n"
            return result
        except Exception as e:
            return f"[Data Fetch Error]: {e}"

    headers = {
        "Authorization": f"Bearer {get_groq_api_key()}",
        "Content-Type": "application/json"
    }

    # Convert chat history to the format expected by the API
    messages = [{"role": "system", "content": system_prompts[variant]}]
    for msg in chat_history:
        if msg[0] is not None:  # User message
            messages.append({"role": "user", "content": msg[0]})
        if msg[1] is not None:  # Assistant message
            messages.append({"role": "assistant", "content": msg[1]})
    messages.append({"role": "user", "content": message})

    try:
        response = requests.post(GROQ_API_URL, headers=headers, json={
            "model": MODEL_NAME,
            "messages": messages,
            "temperature": 0.7
        })
        if response.status_code == 200:
            return response.json()["choices"][0]["message"]["content"]
        else:
            return f"[GROQ API Error {response.status_code}]: {response.text}"
    except Exception as e:
        return f"[Request Error]: {e}"

def respond(message, chat_history, variant, lang):
    translated_input = translate_text(message, 'en')
    bot_reply = query_groq(translated_input, chat_history, variant)
    translated_reply = translate_text(bot_reply, lang)

    # Append user message and empty assistant message
    chat_history.append((message, None))

    # Stream the response
    for i in range(1, len(translated_reply) + 1):
        chat_history[-1] = (message, translated_reply[:i])
        time.sleep(0.00001)
        yield "", chat_history

def transcribe_and_respond(audio_path, chat_history, variant, lang):
    try:
        result = model_whisper.transcribe(audio_path)
        text = result["text"]
    except Exception as e:
        text = f"[Speech Error]: {e}"
    return respond(text, chat_history, variant, lang)

def send_sms_alert(message):
    try:
        client = Client(os.getenv("TWILIO_ACCOUNT_SID"), os.getenv("TWILIO_AUTH_TOKEN"))
        client.messages.create(
            body=message,
            from_=os.getenv("TWILIO_PHONE_NUMBER"),
            to=os.getenv("TARGET_PHONE_NUMBER")
        )
        print("✅ SMS Sent")
    except Exception as e:
        print(f"[SMS Error]: {e}")

def hazard_alert_monitor():
    while True:
        try:
            nws = requests.get("https://api.weather.gov/alerts/active?area=IN", timeout=10).json()
            fema = requests.get("https://www.fema.gov/api/open/v2/DisasterDeclarationsSummaries?$filter=state eq 'IN'", timeout=10).json()
            alerts = nws.get("features", [])
            disasters = fema.get("DisasterDeclarationsSummaries", [])

            if alerts or disasters:
                msg = f"📡 NWS: {len(alerts)} active\n"
                msg += "".join(f"- {a['properties']['event']}\n" for a in alerts[:2])
                msg += f"📜 FEMA: {len(disasters)}\n"
                msg += "".join(f"- {d['incidentType']} in {d['designatedArea']}\n" for d in disasters[:2])
                send_sms_alert(msg)
        except Exception as e:
            print(f"[Monitor Error]: {e}")
        time.sleep(1800)

def hex_to_rgba(hex_color, alpha=0.4):
    hex_color = hex_color.lstrip("#")
    r, g, b = tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
    return f"rgba({r}, {g}, {b}, {alpha})"

def generate_css(variant):
    color = variant_colors[variant]
    bg = hex_to_rgba(color['bg'], 0.3)
    border = hex_to_rgba(color['bg'], 0.5)
    return f"""
    <style>
    body, .gradio-container {{
        background: linear-gradient(90deg, {bg}, black);
        color: {color['text']};
    }}
    .gr-button, .gr-textbox, .gr-dropdown {{
        border: 2px solid;
        border-image: linear-gradient(135deg, {border}, black) 1;
        background: linear-gradient(135deg, black, {bg});
        color: {color['text']};
        border-radius: 6px;
        font-weight: bold;
    }}
    </style>
    """

# Gradio UI
with gr.Blocks() as demo:
    css_box = gr.HTML()
    gr.Markdown("## 🛡️ Civic Tech Chatbot (Powered by GROQ)")

    with gr.Row():
        variant_selector = gr.Dropdown(label="Choose Chatbot Variant", choices=list(system_prompts.keys()), value="Hazard Alerts (INDIANA)")
        language_selector = gr.Dropdown(label="Choose Language", choices=[
            ("English", "en"), ("Spanish", "es"), ("Hindi", "hi"),
            ("French", "fr"), ("Chinese", "zh-cn"), ("Arabic", "ar"), ("Russian", "ru")
        ], value="en")

    chatbot = gr.Chatbot(label="Crisis Assistant", height=480)
    msg = gr.Textbox(label="Ask a question")
    voice_input = gr.Audio(type="filepath", label="🎙️ Speak your question")
    clear = gr.Button("Clear Chat")
    state = gr.State([])

    def show_initial(variant):
        intro = variant_intros[variant]
        css = generate_css(variant)
        return [(None, intro)], css

    variant_selector.change(fn=show_initial, inputs=variant_selector, outputs=[state, css_box])
    msg.submit(respond, inputs=[msg, state, variant_selector, language_selector], outputs=[msg, chatbot])
    voice_input.change(transcribe_and_respond, inputs=[voice_input, state, variant_selector, language_selector], outputs=[msg, chatbot])
    clear.click(lambda: ([], "", ""), outputs=[state, msg, chatbot])

    state.value, css_box.value = show_initial("Hazard Alerts (INDIANA)")

# Background hazard monitor
threading.Thread(target=hazard_alert_monitor, daemon=True).start()

# Launch app
demo.launch()