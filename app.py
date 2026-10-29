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
st.sidebar.title("Einstellungen")
api_key = st.sidebar.text_input("Gemini API Key:", type="password")
st.sidebar.caption("Key erstellen: aistudio.google.com")

st.title("KI-Fragebogen-Studio")
st.write("Automatische Handschriften-, Noten- und Gruppennummer-Erkennung inklusive Kreuzvergleich.")

if not api_key:
    st.info("Bitte gib in der Seitenleiste deinen Gemini API Key ein.")
    st.stop()

# API-Konfiguration
genai.configure(api_key=api_key)
model = genai.GenerativeModel("models/gemini-1.5-flash")

# Upload
uploaded_files = st.file_uploader(
    "Fragebogen-Fotos hochladen:", 
    type=["png", "jpg", "jpeg"], 
    accept_multiple_files=True
)

EXTRACTION_PROMPT = """
Analysiere diesen ausgefüllten Fragebogen extrem genau.
Achte besonders darauf, ob irgendwo eine GROSSE HANDSCHRIFTLICHE NUMMER oder Bogen-ID steht (oft oben in der Ecke oder als Kennung für zusammengehörige Bögen).

Antworte AUSSCHLIESSLICH im folgenden JSON-Format ohne Markdown-Codeblöcke:
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
    
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
    text = text.strip()
    
    data = json.loads(text)
    data["dateiname"] = file.name
    data["bogen_gruppe"] = str(data.get("bogen_gruppe", "Ohne Nummer")).strip()
    return data

if uploaded_files:
    st.write(f"Ausgewählte Fotos: **{len(uploaded_files)}**")
    if st.button("🚀 Alle Fragebögen analysieren"):
        results = []
        file_dict = {}
        progress = st.progress(0)
        status = st.empty()
        
        for idx, file in enumerate(uploaded_files):
            status.text(f"Analysiere Dokument {idx + 1}/{len(uploaded_files)}: {file.name}")
            try:
                data = analyze_image(file)
                results.append(data)
                file_dict[file.name] = file.getvalue()
            except Exception as e:
                st.error(f"Fehler bei {file.name}: {e}")
            progress.progress((idx + 1) / len(uploaded_files))
            
        status.success("Verarbeitung fertig!")
        st.session_state["data"] = results
        st.session_state["images"] = file_dict

# Haupt-Dashboard
if "data" in st.session_state and st.session_state["data"]:
    df = pd.DataFrame(st.session_state["data"])
    
    st.divider()
    st.subheader("1. Gruppenauswahl (Handschriftliche Nummern)")
    
    alle_gruppen = sorted([str(g) for g in df["bogen_gruppe"].unique()])
    col_grp1, col_grp2 = st.columns([2, 1])
    
    with col_grp1:
        gewaehlte_gruppen = st.multiselect(
            "Wähle Bögen-Nummern aus, die du auswerten willst:",
            options=alle_gruppen,
            default=alle_gruppen
        )
    
    with col_grp2:
        st.caption("Verteilung gefundener Nummern:")
        st.dataframe(df["bogen_gruppe"].value_counts().rename("Anzahl"), use_container_width=True)

    filtered_df = df[df["bogen_gruppe"].isin(gewaehlte_gruppen)]

    # KPIs
    st.divider()
    k1, k2, k3, k4 = st.columns(4)
    avg_total = filtered_df["gesamtzufriedenheit"].dropna().mean()
    k1.metric("Ø Gesamtnote", f"{avg_total:.2f} / 5" if pd
