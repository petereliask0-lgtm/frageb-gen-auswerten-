import streamlit as st
from google import genai
import pandas as pd
import plotly.express as px
from PIL import Image
import json
import random
import io
import time

st.set_page_config(page_title="Fragebogen Studio", layout="wide")

st.sidebar.title("Einstellungen")
api_key = st.sidebar.text_input("Gemini API Key:", type="password")

st.title("📋 KI-Fragebogen-Studio")

if not api_key:
    st.info("Bitte gib in der Seitenleiste deinen Gemini API Key ein.")
    st.stop()

# Neuer offizieller Google GenAI Client
client = genai.Client(api_key=api_key)

uploaded_files = st.file_uploader(
    "Fragebogen-Fotos hochladen:", 
    type=["png", "jpg", "jpeg"], 
    accept_multiple_files=True
)

EXTRACTION_PROMPT = """
Analysiere diesen Fragebogen genau.
Erkenne die handschriftliche Bogen-Nummer/Gruppe (oben/Ecke), Noten (1-5) und handschriftlichen Freitext.
Antworte NUR mit reinem JSON ohne Markdown-Ticks:
{
  "gruppe": "<handschriftliche Nummer oder 'Ohne'>",
  "gesamt": <1 bis 5 oder null>,
  "organisation": <1 bis 5 oder null>,
  "inhalte": <1 bis 5 oder null>,
  "empfehlung": <"Ja" oder "Nein">,
  "stimmung": <"Positiv", "Neutral" oder "Negativ">,
  "freitext": "<Text oder 'Keine Angabe'>"
}
"""

def parse_image(file):
    image_bytes = file.getvalue()
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=[
            EXTRACTION_PROMPT,
            genai.types.Part.from_bytes(data=image_bytes, mime_type=file.type)
        ]
    )
    txt = response.text.strip().replace("```json", "").replace("```", "").strip()
    d = json.loads(txt)
    d["dateiname"] = file.name
    d["gruppe"] = str(d.get("gruppe", "Ohne")).strip()
    return d

if uploaded_files:
    st.write(f"Ausgewählte Fotos: {len(uploaded_files)}")
    if st.button("🚀 Alle Fragebögen analysieren"):
        data_list = []
        img_dict = {}
        bar = st.progress(0)
        status = st.empty()
        
        for i, f in enumerate(uploaded_files):
            status.text(f"Analysiere ({i + 1}/{len(uploaded_files)}): {f.name}...")
            try:
                item = parse_image(f)
                data_list.append(item)
                img_dict[f.name] = f.getvalue()
            except Exception as err:
                st.error(f"Fehler bei {f.name}: {err}")
            
            bar.progress((i + 1) / len(uploaded_files))
            time.sleep(2)  # Kurze Pause, um das API-Ratenlimit zu schützen
            
        status.success("Verarbeitung fertig!")
        st.session_state["data"] = data_list
        st.session_state["imgs"] = img_dict

if "data" in st.session_state and st.session_state["data"]:
    df = pd.DataFrame(st.session_state["data"])
    
    st.divider()
    st.subheader("1. Filter nach Bogen-Nummer / Gruppe")
    gruppen = sorted([str(x) for x in df["gruppe"].unique()])
    sel_grp = st.multiselect("Bogen-Nummern auswählen:", options=gruppen, default=gruppen)
    
    f_df = df[df["gruppe"].isin(sel_grp)]
    
    c1, c2, c3 = st.columns(3)
    avg_note = f_df["gesamt"].dropna().mean()
    c1.metric("Ø Gesamtnote", f"{avg_note:.2f} / 5" if pd.notna(avg_note) else "-")
    c2.metric("Positiv-Quote", f"{(f_df['stimmung'] == 'Positiv').mean()*100:.0f}%")
    c3.metric("Erfasste Bögen", len(f_df))
    
    if len(gruppen) > 1:
        st.divider()
        st.subheader("2. Vergleich der Bogen-Nummern")
        grp_avg = f_df.groupby("gruppe")[["gesamt", "organisation", "inhalte"]].mean().reset_index()
        fig1 = px.bar(grp_avg, x="gruppe", y=["gesamt", "organisation", "inhalte"], barmode="group")
        st.plotly_chart(fig1, use_container_width=True)
        
    st.divider()
    st.subheader("3. Detail-Vergleich")
    x_opts = ["empfehlung", "stimmung", "gruppe"]
    y_opts = ["gesamt", "organisation", "inhalte"]
    
    if st.button("🎲 Zufälligen Vergleich vorschlagen"):
        st.session_state["rand_x"] = random.choice(x_opts)
        st.session_state["rand_y"] = random.choice(y_opts)
        
    x_val = st.selectbox("Gruppieren nach:", x_opts, index=x_opts.index(st.session_state.get("rand_x", "empfehlung")))
    y_val = st.selectbox("Note / Messwert:", y_opts, index=y_opts.index(st.session_state.get("rand_y", "gesamt")))
    
    sub = f_df.groupby(x_val)[y_val].mean().reset_index()
    fig2 = px.bar(sub, x=x_val, y=y_val, color=x_val)
    st.plotly_chart(fig2, use_container_width=True)
    
    st.divider()
    st.subheader("4. Einzelfall prüfen")
    sel_img = st.selectbox("Bogen auswählen:", f_df["dateiname"].tolist())
    if sel_img:
        row = f_df[f_df["dateiname"] == sel_img].iloc[0]
        st.image(st.session_state["imgs"][sel_img], caption=f"Nummer: {row['gruppe']}")
        st.write(f"**Noten:** Gesamt: {row['gesamt']} | Orga: {row['organisation']} | Inhalte: {row['inhalte']}")
        st.info(f"**Handschrift:** {row['freitext']}")
        
    st.divider()
    st.download_button("📥 CSV herunterladen", f_df.to_csv(index=False).encode("utf-8"), "daten.csv", "text/csv")
