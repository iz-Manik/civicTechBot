import gradio as gr
import os
import requests
import time
import whisper
from deep_translator import GoogleTranslator
from gradio.components import Audio
from dotenv import load_dotenv
load_dotenv()

GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
MODEL_NAME = "llama-3.3-70b-versatile"
model_whisper = whisper.load_model("base")

system_prompts = {
    "Hazard Alerts (INDIANA)": """You are a hazard alert assistant for Indiana, providing users with real-time updates about weather warnings and disaster declarations from official sources like NWS and FEMA.""",

    "Adaptive Crisis Response (ARK)": """You are ARK, the Adaptive Response Keeper, a versatile AI assistant trained to support individuals during crises, disasters, and uncertain situations. Depending on the user’s needs, you provide a range of support:
    - **General Crisis Support:** Offering clear, compassionate, and actionable guidance to help people navigate crises with empathy and calm.
    - **Emotional Support:** Providing emotional first aid, comfort, and reassurance to individuals dealing with stress, trauma, or fear in uncertain times.
    - **Survival & Logistics:** Delivering practical, tactical advice for survival, crisis management, and resource allocation during natural disasters or emergencies.
    - **Disaster Preparedness:** Helping users prepare for potential disasters with detailed plans, readiness tips, and emergency preparedness strategies.
    No matter the challenge, you adapt to the situation and provide support in a way that keeps the user calm, informed, and empowered. If a situation exceeds your capabilities, you gently advise seeking professional or emergency help.""",

    "Emotional Support (RAY)": """You are RAY, Resilient Assisstant for You an emotionally intelligent AI assistant. Your goal is to help users cope with stress, fear, and trauma during uncertain times. Offer emotional support, calming language, and reassurance. Be kind, patient, and understanding.""",

    "Survival & Logistics (BOLT)": """You are BOLT, Brave Outreach for Logistics & Tactics, a crisis logistics bot trained in survival tactics and emergency response. Provide users with clear, prioritized action steps for surviving natural disasters, outages, or dangerous scenarios. Focus on calm, tactical instructions.""",

    "Disaster Preparedness (READYBOT)": """You are READYBOT, Readiness Engine for Assisting Disaster Yield and Backup Outreach Tasks, an AI guide for disaster preparedness. Help users understand how to prepare before crises occur: creating go-bags, making emergency plans, and staying informed. Be practical, helpful, and informative."""
}

variant_intros = {
    "Hazard Alerts (INDIANA)": "Hello, I am your **Indiana Hazard Alert Bot** — providing live updates on severe weather and disasters in Indiana.",
    "Adaptive Crisis Response (ARK)": "Hello, I am **ARK** — the *Adaptive Response Keeper*. I'm here to help you through crises and uncertainty with calm, clarity, and care. I combine emotional support, tactical guidance, and preparedness strategies to adapt to your needs.",
    "Emotional Support (RAY)": "Hi, I am **RAY** — *Resilient Assistant for You*. I'm here to provide emotional support, helping you feel heard, comforted, and calm during stressful or overwhelming situations.",
    "Survival & Logistics (BOLT)": "Hello, I am **BOLT** — *Brave Outreach for Logistics & Tactics*. I specialize in giving you clear, practical steps to stay safe and manage survival tasks in emergencies.",
    "Disaster Preparedness (READYBOT)": "Greetings, I am **READYBOT** — *Readiness Engine for Assisting Disaster Yield and Backup Outreach Tasks*. I help you prepare for disasters with detailed plans, go-bag tips, and readiness checklists."
}

variant_colors = {
    "Hazard Alerts (INDIANA)": {"bg": "#b91c1c", "text": "#ffffff"},
    "Adaptive Crisis Response (ARK)": {"bg": "#1e3a8a", "text": "#ffffff"},
    "Emotional Support (RAY)": {"bg": "#9333ea", "text": "#ffffff"},
    "Survival & Logistics (BOLT)": {"bg": "#0f766e", "text": "#ffffff"},
    "Disaster Preparedness (READYBOT)": {"bg": "#ca8a04", "text": "#000000"}
}

def get_groq_api_key():
    return os.environ.get("GROQ_API_KEY")

def translate_text(text, target_lang='en'):
    try:
        return GoogleTranslator(source='auto', target=target_lang).translate(text)
    except Exception as e:
        return f"[Translation Error]: {e}"

def transcribe_and_respond(audio_path, chat_history, variant, lang):
    try:
        result = model_whisper.transcribe(audio_path)
        transcribed_text = result["text"]
    except Exception as e:
        transcribed_text = f"[Speech Recognition Error]: {e}"

    return respond(transcribed_text, chat_history, variant, lang)

def query_groq(message, chat_history, variant):
    if variant == "Hazard Alerts (INDIANA)":
        nws_url = "https://api.weather.gov/alerts/active?area=IN"
        fema_url = "https://www.fema.gov/api/open/v2/DisasterDeclarationsSummaries?$filter=state eq 'IN'"
        try:
            nws_response = requests.get(nws_url, timeout=10).json()
            fema_response = requests.get(fema_url, timeout=10).json()
            alerts = nws_response.get("features", [])
            disasters = fema_response.get("DisasterDeclarationsSummaries", [])
            alert_msg = f"📡 NWS Alerts: {len(alerts)} active alerts.\n"
            for alert in alerts[:3]:
                props = alert.get("properties", {})
                alert_msg += f"- {props.get('event')}: {props.get('headline')}\n"

            disaster_msg = f"\n📜 FEMA Disasters: {len(disasters)} records.\n"
            recent = disasters[:3]
            for d in recent:
                disaster_msg += f"- {d.get('incidentType')} on {d.get('declarationDate')} in {d.get('designatedArea')}.\n"

            return alert_msg + disaster_msg
        except Exception as e:
            return f"⚠️ Error fetching hazard data: {e}"

    # original Groq API logic
    GROQ_API_KEY = get_groq_api_key()
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }
    messages = [{"role": "system", "content": system_prompts[variant]}]
    for msg in chat_history:
        messages.append(msg)
    messages.append({"role": "user", "content": message})

    response = requests.post(GROQ_API_URL, headers=headers, json={
        "model": MODEL_NAME,
        "messages": messages,
        "temperature": 0.7
    })

    if response.status_code == 200:
        return response.json()["choices"][0]["message"]["content"]
    else:
        return f"Error {response.status_code}: {response.text}"

def query_groq(message, chat_history, variant):
    GROQ_API_KEY = get_groq_api_key()
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }

    messages = [{"role": "system", "content": system_prompts[variant]}]
    for msg in chat_history:
        messages.append(msg)
    messages.append({"role": "user", "content": message})

    response = requests.post(GROQ_API_URL, headers=headers, json={
        "model": MODEL_NAME,
        "messages": messages,
        "temperature": 0.7
    })

    if response.status_code == 200:
        return response.json()["choices"][0]["message"]["content"]
    else:
        return f"Error {response.status_code}: {response.text}"

def respond(message, chat_history, variant, lang):
    translated_input = translate_text(message, target_lang='en')
    bot_reply = query_groq(translated_input, chat_history, variant)
    translated_reply = translate_text(bot_reply, target_lang=lang)

    chat_history.append({"role": "user", "content": message})
    chat_history.append({"role": "assistant", "content": ""})

    for i in range(1, len(translated_reply) + 1):
        chat_history[-1]["content"] = translated_reply[:i]
        time.sleep(0.00001)
        yield "", chat_history

def hex_to_rgba(hex_color, alpha=0.4):
    hex_color = hex_color.lstrip('#')
    r, g, b = tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
    return f"rgba({r}, {g}, {b}, {alpha})"

def generate_css(variant):
    colors = variant_colors[variant]
    bg, text = colors['bg'], colors['text']
    rgba_bg = hex_to_rgba(bg, 0.3)
    rgba_border = hex_to_rgba(bg, 0.5)

    return f"""
    <style>
    body, .gradio-container {{
        background: linear-gradient(80deg, {rgba_bg}, black);
        color: {text} !important;
    }}
    .gr-button, .gr-textbox, .gr-dropdown {{
        border: 2px solid;
        border-image: linear-gradient(135deg, {rgba_border}, black) 1;
        background: linear-gradient(135deg, black, {rgba_bg});
        color: {text} !important;
        border-radius: 6px;
        font-weight: bold;
    }}
    .gr-button:hover {{
        background: linear-gradient(135deg, {bg}, black);
        color: #ffffff !important;
    }}
    .message.bot, .message.user {{
        border: 2px solid {rgba_border} !important;
        background: linear-gradient(135deg, {rgba_bg}, black);
        color: {text} !important;
    }}
    </style>
    """

with gr.Blocks() as demo:
    css_box = gr.HTML()  # For dynamic CSS injection

    gr.Markdown("## 🛡️ Civic Tech Chatbot (Powered by GROQ)")

    with gr.Row():
        variant_selector = gr.Dropdown(
            choices=list(system_prompts.keys()),
            value="Hazard Alerts (INDIANA)",
            label="Choose Chatbot Variant"
        )
        language_selector = gr.Dropdown(
            choices=[
                ("English", "en"),
                ("Spanish", "es"),
                ("Hindi", "hi"),
                ("French", "fr"),
                ("Chinese (Simplified)", "zh-cn"),
                ("Arabic", "ar"),
                ("Russian", "ru")
            ],
            value="en",
            label="Choose Language"
        )

    chatbot = gr.Chatbot(label="Crisis Assistant", height=480, type="messages")
    with gr.Row():
        msg = gr.Textbox(label="Ask a question", lines=1)
        voice_input = gr.Audio(type="filepath", label="🎙️ Speak", interactive=True)
    clear = gr.Button("Clear Chat")
    state = gr.State([])

    def show_initial_message(variant):
        intro = variant_intros[variant]
        css = generate_css(variant)
        return [{"role": "assistant", "content": intro}], [], css

    demo.load(fn=show_initial_message, inputs=variant_selector, outputs=[chatbot, state, css_box])
    variant_selector.change(show_initial_message, inputs=variant_selector, outputs=[chatbot, state, css_box])
    msg.submit(respond, [msg, state, variant_selector, language_selector], [msg, chatbot])
    voice_input.change(transcribe_and_respond, [voice_input, state, variant_selector, language_selector], [msg, chatbot])
    clear.click(lambda: ([], []), None, [chatbot, state])

demo.launch(share=True)

