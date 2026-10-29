import streamlit as st
import google.generativeai as genai
import pandas as pd
import plotly.express as px
from PIL import Image
import json
import random

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

genai.configure(api_key=api_key)
model = genai.GenerativeModel("gemini-1.5-flash")

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
    image_bytes = file.getvalue()
    image_part = {"mime_type": file.type, "data": image_bytes}
    response = model.generate_content([EXTRACTION_PROMPT, image_part])
    text = response.text.strip().replace("```json", "").replace("```", "").strip()
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
    
    # 1. Gruppenfilter
    st.subheader("📁 1. Gruppenauswahl (Handschriftliche Nummern)")
    
    alle_gruppen = sorted([str(g) for g in df["bogen_gruppe"].unique()])
    col_grp1, col_grp2 = st.columns([2, 1])
    
    with col_grp1:
        gewaehlte_gruppen = st.multiselect(
            "Wähle Bögen-Nummern aus, die du auswerten willst (oder lass alle aktiv):",
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
    k1.metric("Ø Gesamtnote", f"{avg_total:.2f} / 5" if pd.notna(avg_total) else "-")
    rec_rate = (filtered_df["empfehlung"] == "Ja").mean() * 100 if len(filtered_df) > 0 else 0
    k2.metric("Weiterempfehlung", f"{rec_rate:.0f}%")
    pos_rate = (filtered_df["stimmung"] == "Positiv").mean() * 100 if len(filtered_df) > 0 else 0
    k3.metric("Positiv-Quote", f"{pos_rate:.0f}%")
    k4.metric("Ausgewählte Bögen", f"{len(filtered_df)} / {len(df)}")

    # 2. Gruppenvergleich
    if len(alle_gruppen) > 1:
        st.divider()
        st.subheader("⚖️ 2. Direkter Vergleich der handschriftlichen Nummern")
        st.write("Wie schneiden die verschiedenen Bogen-Gruppen gegeneinander ab?")
        
        grp_summary = filtered_df.groupby("bogen_gruppe")[["gesamtzufriedenheit", "organisation", "inhalte"]].mean().reset_index()
        grp_melted = grp_summary.melt(id_vars="bogen_gruppe", var_name="Kriterium", value_name="Schnitt")
        
        fig_grp = px.bar(
            grp_melted, 
            x="bogen_gruppe", 
            y="Schnitt", 
            color="Kriterium", 
            barmode="group",
            text_auto=".2f",
            labels={"bogen_gruppe": "Bogen-Nummer", "Schnitt": "Durchschnittsnote"}
        )
        fig_grp.update_yaxes(range=[1, 5])
        st.plotly_chart(fig_grp, use_container_width=True)

    # 3. Detail-Vergleich & Kreuztabelle
    st.divider()
    st.subheader("🔀 3. Detail-Vergleich: Wie unterscheiden sich Antworten?")
    st.caption("Vergleiche z.B.: 'Unterscheidet sich die Gesamtnote, je nachdem ob Empfehlung Ja oder Nein war?'")

    merkmale_x = ["empfehlung", "zielgruppe", "stimmung", "bogen_gruppe"]
    merkmale_y = ["gesamtzufriedenheit", "organisation", "inhalte"]

    if st.button("🎲 Zufälligen Vergleich vorschlagen"):
        st.session_state["zufall_x"] = random.choice(merkmale_x)
        st.session_state["zufall_y"] = random.choice(merkmale_y)

    sel_x = st.selectbox(
        "Kriterium 1 (Gruppierung nach):", 
        merkmale_x, 
        index=merkmale_x.index(st.session_state.get("zufall_x", "empfehlung"))
    )
    sel_y = st.selectbox(
        "Kriterium 2 (Messwert / Notenvergleich):", 
        merkmale_y, 
        index=merkmale_y.index(st.session_state.get("zufall_y", "gesamtzufriedenheit"))
    )

    cv1, cv2 = st.columns(2)
    with cv1:
        st.write(f"##### Notendurchschnitt von **{sel_y}** aufgeteilt nach **{sel_x}**")
        cross_df = filtered_df.groupby(sel_x)[sel_y].agg(["mean", "count"]).reset_index()
        cross_df.columns = [sel_x, "Durchschnitt", "Anzahl Antworten"]
        
        fig_cross = px.bar(
            cross_df, 
            x=sel_x, 
            y="Durchschnitt", 
            color=sel_x, 
            text_auto=".2f",
            hover_data=["Anzahl Antworten"]
        )
        fig_cross.update_yaxes(range=[1, 5])
        st.plotly_chart(fig_cross, use_container_width=True)

    with cv2:
        st.write("##### Verteilung als Boxplot (Streuung)")
        fig_box = px.box(
            filtered_df, 
            x=sel_x, 
            y=sel_y, 
            color=sel_x, 
            points="all",
            labels={sel_y: "Note", sel_x: "Kategorie"}
        )
        st.plotly_chart(fig_box, use_container_width=True)

    # 4. KI-Bericht
    st.divider()
    st.subheader("🤖 4. KI-Bericht & Detailinterpretation")
    if st.button("📝 Tiefenanalyse für ausgewählte Gruppen generieren"):
        with st.spinner("KI vergleicht Muster und Gruppen..."):
            prompt_deep = f"""
            Analysiere diese Umfrage-Daten:
            Verwendete Bogen-Nummern: {gewaehlte_gruppen}
            Durchschnittsnote Gesamt: {avg_total:.2f}
            Noten pro Gruppe: {filtered_df.groupby('bogen_gruppe')[['gesamtzufriedenheit', 'organisation', 'inhalte']].mean().to_dict()}
            Stimmungen: {filtered_df['stimmung'].value_counts().to_dict()}
            Handschriftliche Kommentare: {filtered_df['freitext'].tolist()}

            Gib einen übersichtlichen Bericht:
            1. Auffällige Unterschiede zwischen den Bogen-Nummern (falls vorhanden).
            2. Welche Muster gibt es zwischen unzufriedenen und zufriedenen Teilnehmern?
            3. Die 3 wichtigsten Erkenntnisse aus dem Handschriften-Feedback.
            """
            deep_res = model.generate_content(prompt_deep)
            st.markdown(deep_res.text)

    # 5. Bildkontrolle & Download
    st.divider()
    st.subheader("🔍 5. Einzelfallprüfung mit Originalbild")
    selected_doc = st.selectbox("Bogen auswählen:", options=filtered_df["dateiname"].tolist())
    if selected_doc:
        doc = filtered_df[filtered_df["dateiname"] == selected_doc].iloc[0]
        c1, c2 = st.columns(2)
        with c1:
            st.image(st.session_state["images"][selected_doc], caption=f"{selected_doc} (Erkannte Gruppe: {doc['bogen_gruppe']})", use_container_width=True)
        with c2:
            st.write(f"**Erkannte Nummer / Gruppe:** `{doc['bogen_gruppe']}`")
            st.write(f"**Gesamtzufriedenheit:** {doc['gesamtzufriedenheit']} / 5")
            st.write(f"**Organisation:** {doc['organisation']} / 5")
            st.write(f"**Inhalte:** {doc['inhalte']} / 5")
            st.write(f"**Weiterempfehlung:** {doc['empfehlung']}")
            st.info(f"**Handschriftlicher Freitext:**\n\n{doc['freitext']}")

    st.divider()
    st.download_button(
        "📥 Daten inkl. Gruppennummern als CSV herunterladen", 
        data=filtered_df.to_csv(index=False).encode("utf-8"), 
        file_name="umfrage_mit_gruppen.csv", 
        mime="text/csv"
    )
