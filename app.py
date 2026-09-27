import streamlit as st
import simpy
import random
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
import google.generativeai as genai
import json
import re

# ==========================================
# 1. SETUP HALAMAN & CUSTOM CSS
# ==========================================
st.set_page_config(
    page_page_title="DSS Bottleneck Gudang & AI Scenario Generator",
    page_icon="🏭",
    layout="wide"
)

st.markdown("""
<style>
    .metric-card {
        background-color: #f8f9fa;
        border-radius: 8px;
        padding: 15px;
        border-left: 5px solid #0066cc;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    }
    .stButton>button {
        width: 100%;
        border-radius: 5px;
        font-weight: bold;
    }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 2. KONFIGURASI GEMINI API
# ==========================================
API_KEY = st.secrets.get("GEMINI_API_KEY", "")

if API_KEY:
    try:
        genai.configure(api_key=API_KEY)
    except Exception as e:
        st.error(f"Gagal memuat API Key: {e}")

def get_gemini_model():
    return genai.GenerativeModel('gemini-1.5-flash')

# ==========================================
# 3. HELPER AI PARSER & SCENARIO GENERATOR
# ==========================================
def extract_parameters_to_json(prompt_text):
    if not API_KEY:
        return None, "API Key belum dikonfigurasi di Streamlit Secrets."
    
    sys_instruction = """
    Kamu adalah pakar simulasi sistem logistik & gudang.
    Ekstrak data dari deskripsi teks berikut menjadi JSON murni tanpa Markdown/formatting lain.
    Format JSON yang WAJIB dihasilkan:
    {
        "arrival_rate": float (truk per jam),
        "unloading_time_mean": float (menit per truk),
        "num_bays": int (jumlah loading bay),
        "num_forklifts": int (jumlah forklift)
    }
    Jika ada parameter yang tidak disebutkan di teks, gunakan nilai default:
    arrival_rate: 5.0, unloading_time_mean: 30.0, num_bays: 2, num_forklifts: 3.
    """
    
    try:
        model = get_gemini_model()
        response = model.generate_content(f"{sys_instruction}\n\nTeks Deskripsi:\n{prompt_text}")
        text_resp = response.text.strip()
        
        # Cleaner untuk membuang backtick ```json ...
