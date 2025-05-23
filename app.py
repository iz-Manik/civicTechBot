import gradio as gr
import os
import requests
import time
import whisper
import folium
from folium.plugins import MarkerCluster
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

# Map functions
def default_map_html():
    map_obj = folium.Map(location=[39.7684, -86.1581], zoom_start=7)
    return map_obj._repr_html_()

def create_hazard_map(alerts):
    hazard_map = folium.Map(location=[39.7684, -86.1581], zoom_start=7)
    marker_cluster = MarkerCluster().add_to(hazard_map)

    for alert in alerts:
        properties = alert.get('properties', {})
        geometry = alert.get('geometry', {})

        if geometry and properties:
            coords = []
            if geometry['type'] == 'Point':
                coords = [geometry['coordinates'][1], geometry['coordinates'][0]]
            elif geometry['type'] == 'Polygon':
                coords = [geometry['coordinates'][0][0][1], geometry['coordinates'][0][0][0]]

            if coords:
                popup_content = f"""
                <b>{properties.get('event', 'Unknown')}</b><br>
                <i>{properties.get('headline', 'No details')}</i><br>
                <small>Effective: {properties.get('effective', 'Unknown')}<br>
                Expires: {properties.get('expires', 'Unknown')}</small>
                """
                folium.Marker(
                    location=coords,
                    popup=popup_content,
                    icon=folium.Icon(color='red', icon='exclamation-triangle')
                ).add_to(marker_cluster)

    return hazard_map._repr_html_()

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

            map_html = create_hazard_map(alerts) if alerts else default_map_html()
            return result, map_html
        except Exception as e:
            return f"[Data Fetch Error]: {e}", default_map_html()

    headers = {
        "Authorization": f"Bearer {get_groq_api_key()}",
        "Content-Type": "application/json"
    }

    messages = [{"role": "system", "content": system_prompts[variant]}]
    for msg in chat_history:
        if msg[0]: messages.append({"role": "user", "content": msg[0]})
        if msg[1]: messages.append({"role": "assistant", "content": msg[1]})
    messages.append({"role": "user", "content": message})

    try:
        response = requests.post(GROQ_API_URL, headers=headers, json={
            "model": MODEL_NAME,
            "messages": messages,
            "temperature": 0.7
        })
        if response.status_code == 200:
            return response.json()["choices"][0]["message"]["content"], default_map_html()
        else:
            return f"[GROQ API Error {response.status_code}]: {response.text}", default_map_html()
    except Exception as e:
        return f"[Request Error]: {e}", default_map_html()

def respond(message, chat_history, variant, lang):
    translated_input = translate_text(message, 'en')
    bot_reply, map_html = query_groq(translated_input, chat_history, variant)
    translated_reply = translate_text(bot_reply, lang)

    chat_history.append((message, None))

    for i in range(1, len(translated_reply) + 1):
        chat_history[-1] = (message, translated_reply[:i])
        time.sleep(0.00001)
        yield "", chat_history, map_html

def transcribe_and_respond(audio_path, chat_history, variant, lang):
    try:
        result = model_whisper.transcribe(audio_path)
        text = result["text"]
    except Exception as e:
        text = f"[Speech Error]: {e}"

    response_gen = respond(text, chat_history, variant, lang)
    final_msg, final_chat, final_map = None, None, None
    for msg, chat, map_html in response_gen:
        final_msg, final_chat, final_map = msg, chat, map_html
    return final_msg, final_chat, final_map

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
    #map {{
        height: 500px !important;
        margin-top: 20px;
        border-radius: 10px;
        border: 2px solid {border};
    }}
    </style>
    """

# Gradio UI
with gr.Blocks() as demo:
    css_box = gr.HTML()
    gr.Markdown("## 🛡️ Civic Tech Chatbot (Powered by GROQ)")

    with gr.Row():
        variant_selector = gr.Dropdown(
            label="Choose Chatbot Variant",
            choices=list(system_prompts.keys()),
            value="Hazard Alerts (INDIANA)"
        )
        language_selector = gr.Dropdown(
            label="Choose Language",
            choices=[
                ("English", "en"), ("Spanish", "es"), ("Hindi", "hi"),
                ("French", "fr"), ("Chinese(Simplified)", "zh-cn"), ("Arabic", "ar"), ("Russian", "ru")
            ],
            value="en"
        )

    chatbot = gr.Chatbot(label="Crisis Assistant", height=400)
    msg = gr.Textbox(label="Ask a question")
    voice_input = gr.Audio(type="filepath", label="🎙️ Speak your question")
    clear = gr.Button("Clear Chat")
    hazard_map = gr.HTML(
        label="Hazard Map",
        value=default_map_html(),
        elem_id="map"
    )

    state = gr.State([])

    def show_initial(variant):
        intro = variant_intros[variant]
        css = generate_css(variant)
        _, map_html = query_groq("", [], variant)
        return [(None, intro)], css, map_html, [(None, intro)]  # Added chat history for chatbot

    # Updated variant change handler
    variant_selector.change(
        fn=show_initial,
        inputs=variant_selector,
        outputs=[state, css_box, hazard_map, chatbot]  # Match all 4 outputs
    )

    # Initialize components properly
    initial_state, initial_css, initial_map, initial_chat = show_initial("Hazard Alerts (INDIANA)")
    state.value = initial_state
    css_box.value = initial_css
    hazard_map.value = initial_map
    chatbot.value = initial_chat  # Initialize chatbot with initial state

    msg.submit(
        respond,
        inputs=[msg, state, variant_selector, language_selector],
        outputs=[msg, chatbot, hazard_map]
    )
    voice_input.change(
        transcribe_and_respond,
        inputs=[voice_input, state, variant_selector, language_selector],
        outputs=[msg, chatbot, hazard_map]
    )
    clear.click(
        lambda: ([], "", "", default_map_html()),
        outputs=[state, msg, chatbot, hazard_map]
    )

# Background hazard monitor
threading.Thread(target=hazard_alert_monitor, daemon=True).start()

# Launch app
demo.launch()