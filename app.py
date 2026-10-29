import streamlit as st
import google.generativeai as genai
import pandas as pd
import plotly.express as px
from PIL import Image
import json
import random
import io

st.set_page_config(page_title="Fragebogen Analytics Studio", layout="wide", page_icon="🔬")

# Sidebar
st.sidebar.title("⚙️ Einstellungen")
api_key = st.sidebar.text_input("Gemini API Key:", type="password")
st.sidebar.caption("Key erstellen: aistudio.google.com")

st.title("📋 KI-Fragebogen-Studio: Gruppen, Muster & Vergleiche")
st.write("Automatische Handschriften-, Noten- und Gruppennummer-Erkennung inklusive Kreuzvergleich.")

if not api_key:
    st.info("Bitte gib in der Seitenleiste deinen Gemini API Key ein.")
    st.stop()

# API-Konfiguration
genai.configure(api_key=api_key)

# Automatische Erkennung des funktionierenden Modells auf deinem Key
@st.cache_resource
def get_model():
    try:
        available_models = [m.name for m in genai.list_models() if "generateContent" in m.supported_generation_methods]
        # Bevorzuge 1.5 flash
        for m in available_models:
            if "gemini-1.5-flash" in m:
                return genai.GenerativeModel(m)
        # Fallback auf erstes verfügbares multimodales Modell
        if available_models:
            return genai.GenerativeModel(available_models[0])
    except Exception:
        pass
    return genai.GenerativeModel("models/gemini-1.5-flash")

model = get_model()

# Upload
uploaded_files = st.file_uploader(
    "Fragebogen-Fotos hochladen:", 
    type=["png", "jpg", "jpeg"], 
    accept_multiple_files=True
)

EXTRACTION_PROMPT = """
Analysiere diesen ausgefüllten Fragebogen extrem genau.
Achte besonders darauf, ob irgendwo eine GROSSE HANDSCHRIFTLICHE NUMMER oder Bogen-ID steht (oft oben in der Ecke oder als Kennung für zusammengehörige Bögen).

Antworte AUSSCHLIESSLICH im folgenden JSON-Format ohne Markdown-Codeblöcke (kein ```json ... ```):
{
  "bogen_gruppe": "<Große handschriftliche Nummer oder Zahl z.B. 1, 2, A, oder 'Ohne Nummer'>",
  "gesamtzufriedenheit": <Note 1-5 als Zahl oder null>,
  "organisation": <Note 1-5 als Zahl oder null>,
  "inhalte": <Note 1-5 als Zahl oder null>,
  "empfehlung": <"Ja" oder "Nein">,
  "zielgruppe": <z.B. "Einsteiger", "Fortgeschritten", "Student", "Berufstätig">,
  "stimmung": <"Positiv", "Neutral" oder "Negativ">,
  "top_thema": <Hauptthema in 1-2 Wörtern>,
  "freitext": "<Transkription des handschriftlichen Textes oder 'Keine Angabe'>"
}
"""

def analyze_image(file):
    image = Image.open(io.BytesIO(file.getvalue()))
    response = model.generate_content([EXTRACTION_PROMPT, image])
    text = response.text.strip()
    
    # Eventuelle Markdown-Codeblöcke säubern
    if text.startswith("```"):
        text = text.split("```")[1]
        
