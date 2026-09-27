import streamlit as st
import simpy
import random
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import google.generativeai as genai
import json
import re

# ==========================================
# 1. SETUP HALAMAN & MODERN CUSTOM CSS
# ==========================================
st.set_page_config(
    page_title="Warehouse Bottleneck DSS",
    page_icon="🏭",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom Styling untuk Tampilan SaaS Modern
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
    }
    
    .header-box {
        background: linear-gradient(135deg, #1E293B 0%, #0F172A 100%);
        padding: 24px 32px;
        border-radius: 12px;
        color: white;
        margin-bottom: 24px;
        box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1);
    }
    .header-box h1 {
        color: #F8FAFC !important;
        font-weight: 700;
        font-size: 28px;
        margin: 0;
    }
    .header-box p {
        color: #94A3B8;
        font-size: 14px;
        margin-top: 6px;
        margin-bottom: 0;
    }
    
    .custom-card {
        background-color: #FFFFFF;
        border: 1px solid #E2E8F0;
        border-radius: 10px;
        padding: 20px;
        margin-bottom: 16px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.05);
    }
    
    .metric-container {
        background: #F8FAFC;
        border: 1px solid #E2E8F0;
        border-top: 4px solid #2563EB;
        border-radius: 8px;
        padding: 16px;
        text-align: center;
        box-shadow: 0 1px 2px rgba(0,0,0,0.05);
    }
    .metric-label {
        font-size: 12px;
        font-weight: 600;
        color: #64748B;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }
    .metric-value {
        font-size: 22px;
        font-weight: 700;
        color: #0F172A;
        margin-top: 6px;
    }
    
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
    }
    .stTabs [data-baseweb="tab"] {
        height: 48px;
        white-space: pre-wrap;
        background-color: #F1F5F9;
        border-radius: 8px;
        color: #475569;
        font-weight: 600;
        padding: 10px 16px;
    }
    .stTabs [aria-selected="true"] {
        background-color: #2563EB !important;
        color: white !important;
    }
    
    .stButton>button {
        border-radius: 8px;
        font-weight: 600;
        height: 44px;
        transition: all 0.2s ease;
    }
    
    .streamlit-expanderHeader {
        font-weight: 600;
        color: #1E293B;
    }
</style>
""", unsafe_allow_html=True)

# Header Utama
st.markdown("""
<div class="header-box">
    <h1>🏭 Warehouse Bottleneck Decision Support System (DSS)</h1>
    <p>Platform Analisis Antrean Stokhastik Gudang & Generator Skenario Intervensi Berbasis AI Gemini Flash</p>
</div>
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
    # Menggunakan endpoint Gemini Flash versi terbaru
    return genai.GenerativeModel('models/gemini-3.6-flash')

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
        "num_forklifts": int (jumlah forklift),
        "demurrage_rate": int (tarif denda rupiah per jam per truk)
    }
    Jika ada parameter yang tidak disebutkan di teks, gunakan nilai default:
    arrival_rate: 8.0, unloading_time_mean: 25.0, num_bays: 2, num_forklifts: 3, demurrage_rate: 150000.
    """
    
    try:
        model = get_gemini_model()
        response = model.generate_content(f"{sys_instruction}\n\nTeks Deskripsi:\n{prompt_text}")
        text_resp = response.text.strip()
        
        match = re.search(r'\{.*\}', text_resp, re.DOTALL)
        if match:
            clean_json = match.group(0)
            data = json.loads(clean_json)
            return data, None
        else:
            return None, f"Gagal menguraikan JSON dari respon AI: {text_resp}"
    except Exception as e:
        return None, str(e)

def generate_ai_scenarios(base_params, base_demurrage):
    if not API_KEY:
        return None, "API Key belum dikonfigurasi."
    
    prompt = f"""
    Sistem Gudang saat ini memiliki kondisi dasar:
    - Kedatangan Truk: {base_params['arrival_rate']} truk/jam
    - Waktu Unloading: {base_params['unloading_time_mean']} menit
    - Jumlah Loading Bay: {base_params['num_bays']}
    - Jumlah Forklift: {base_params['num_forklifts']}
    - Total Denda Demurrage Dasar: Rp {base_demurrage:,.0f}

    Berikan 3 usulan skenario intervensi terbaik untuk mengurangi kemacetan dan denda demurrage.
    Hasilkan output JSON murni tanpa markdown dengan format persis berikut:
    {{
        "scenarios": [
            {{
                "name": "Nama Skenario 1",
                "num_bays": int,
                "num_forklifts": int,
                "bay_cost_per_day": int (biaya sewa/investasi bay per hari dalam Rp),
                "forklift_cost_per_day": int (biaya sewa/investasi forklift per hari dalam Rp),
                "rationale": "Penjelasan singkat alasan teknis"
            }}
        ]
    }}
    """
    try:
        model = get_gemini_model()
        response = model.generate_content(prompt)
        match = re.search(r'\{.*\}', response.text.strip(), re.DOTALL)
        if match:
            return json.loads(match.group(0)), None
        return None, "Format respon skenario AI tidak valid."
    except Exception as e:
        return None, str(e)

# ==========================================
# 4. ENGINE SIMULASI SIMPY
# ==========================================
def run_warehouse_simulation(arrival_rate, unloading_time_mean, num_bays, num_forklifts, sim_hours=24):
    env = simpy.Environment()
    
    bays = simpy.Resource(env, capacity=num_bays)
    forklifts = simpy.Resource(env, capacity=num_forklifts)
    
    waiting_times = []
    unloading_times = []
    queue_log = []
    
    def monitor_queue(env):
        while True:
            queue_log.append({
                'time': env.now,
                'queue_length': len(bays.queue)
            })
            yield env.timeout(30)
            
    def truck_process(env, truck_id):
        arrival_time = env.now
        
        with bays.request() as req_bay:
            yield req_bay
            wait_bay_time = env.now - arrival_time
            
            with forklifts.request() as req_fork:
                yield req_fork
                
                actual_unloading = random.expovariate(1.0 / unloading_time_mean)
                yield env.timeout(actual_unloading)
                
                total_wait = wait_bay_time
                waiting_times.append(total_wait)
                unloading_times.append(actual_unloading)

    def truck_generator(env):
        truck_id = 0
        while True:
            inter_arrival = random.expovariate(arrival_rate / 60.0)
            yield env.timeout(inter_arrival)
            truck_id += 1
            env.process(truck_process(env, truck_id))

    env.process(truck_generator(env))
    env.process(monitor_queue(env))
    env.run(until=sim_hours * 60)
    
    total_trucks = len(waiting_times)
    avg_wait = np.mean(waiting_times) if waiting_times else 0
    max_wait = np.max(waiting_times) if waiting_times else 0
    avg_unloading = np.mean(unloading_times) if unloading_times else 0
    
    return {
        'total_trucks': total_trucks,
        'avg_wait_min': avg_wait,
        'max_wait_min': max_wait,
        'avg_unloading_min': avg_unloading,
        'queue_log': queue_log,
        'raw_waiting_times': waiting_times
    }

# ==========================================
# 5. MODUL UTAMA DENGAN TAB NAVIGASI
# ==========================================
tabs = st.tabs([
    "📌 Modul 1: Parameter & AI Parser", 
    "📊 Modul 2: Simulasi & Bottleneck", 
    "🤖 Modul 3: AI Scenario Generator", 
    "⚖️ Modul 4: Trade-off Analytics & Report"
])

# ------------------------------------------
# TAB 1: PARAMETER INPUT
# ------------------------------------------
with tabs[0]:
    st.subheader("⚙️ Ekstraksi & Konfigurasi Parameter Operasional")
    
    col_ai, col_manual = st.columns([1, 1], gap="large")
    
    with col_ai:
        st.markdown("""
        <div class="custom-card">
            <h4 style="margin-top:0; color:#1E293B;">🤖 Ekstraksi Otomatis via AI Gemini Flash</h4>
            <p style="font-size:13px; color:#64748B;">Ketik atau tempelkan narasi kondisi operasional lapangan di bawah ini:</p>
        </div>
        """, unsafe_allow_html=True)
        
        prompt_input = st.text_area(
            "Deskripsi Kondisi Lapangan / Logistik:",
            value="Saat ini rata-rata kedatangan truk adalah 8 truk per jam. Proses pembongkaran muatan memakan waktu sekitar 25 menit per truk. Gudang saat ini memiliki 2 loading bay dan disokong oleh 3 unit forklift. Denda demurrage yang berlaku adalah Rp 150.000 per jam per truk.",
            height=140
        )
        
        if st.button("🤖 Ekstrak Parameter via AI", type="primary"):
            with st.spinner("AI Gemini Flash sedang menguraikan data logistik..."):
                parsed_data, err = extract_parameters_to_json(prompt_input)
                if err:
                    st.error(f"Error Ekstraksi AI: {err}")
                else:
                    st.session_state['parsed_params'] = parsed_data
                    st.success("✅ Parameter berhasil diekstraksi dan diterapkan!")

    with col_manual:
        st.markdown("""
        <div class="custom-card">
            <h4 style="margin-top:0; color:#1E293B;">🎛️ Validasi & Setup Manual Parameter</h4>
            <p style="font-size:13px; color:#64748B;">Nilai di bawah ini otomatis terisi dari AI atau bisa disesuaikan manual:</p>
        </div>
        """, unsafe_allow_html=True)
        
        default_params = st.session_state.get('parsed_params', {
            "arrival_rate": 8.0,
            "unloading_time_mean": 25.0,
            "num_bays": 2,
            "num_forklifts": 3,
            "demurrage_rate": 150000
        })
        
        c1, c2 = st.columns(2)
        with c1:
            arr_rate = st.number_input("Kedatangan Truk (truk/jam):", min_value=1.0, max_value=50.0, value=float(default_params.get("arrival_rate", 8.0)))
            unl_time = st.number_input("Rata-rata Waktu Unloading (menit):", min_value=5.0, max_value=180.0, value=float(default_params.get("unloading_time_mean", 25.0)))
        with c2:
            n_bays = st.number_input("Jumlah Loading Bay:", min_value=1, max_value=20, value=int(default_params.get("num_bays", 2)))
            n_forks = st.number_input("Jumlah Forklift:", min_value=1, max_value=20, value=int(default_params.get("num_forklifts", 3)))
        
        demurrage_rate = st.number_input("Tarif Denda Demurrage (Rp/jam/truk):", min_value=0, value=int(default_params.get("demurrage_rate", 150000)), step=10000)

        st.session_state['active_params'] = {
            'arrival_rate': arr_rate,
            'unloading_time_mean': unl_time,
            'num_bays': n_bays,
            'num_forklifts': n_forks,
            'demurrage_rate': demurrage_rate
        }

# ------------------------------------------
# TAB 2: SIMULASI & BOTTLENECK
# ------------------------------------------
with tabs[1]:
    st.subheader("📊 Hasil Simulasi Operasional Gudang (24 Jam)")
    
    if 'active_params' in st.session_state:
        p = st.session_state['active_params']
        
        st.button("🚀 Jalankan Simulasi Eksisting", type="primary")
        
        sim_res = run_warehouse_simulation(
            p['arrival_rate'], p['unloading_time_mean'], p['num_bays'], p['num_forklifts']
        )
        st.session_state['base_sim_result'] = sim_res
        
        res = st.session_state['base_sim_result']
        excess_wait_hours = sum([max(0, w - 30) for w in res['raw_waiting_times']]) / 60.0
        total_demurrage_cost = excess_wait_hours * p['demurrage_rate']
        st.session_state['base_demurrage'] = total_demurrage_cost
        
        m1, m2, m3, m4 = st.columns(4)
        m1.markdown(f"""
        <div class="metric-container">
            <div class="metric-label">Total Truk Dilayani</div>
            <div class="metric-value">{res['total_trucks']} Truk</div>
        </div>
        """, unsafe_allow_html=True)
        
        m2.markdown(f"""
        <div class="metric-container" style="border-top-color: #F59E0B;">
            <div class="metric-label">Rata-Rata Antrean</div>
            <div class="metric-value">{res['avg_wait_min']:.1f} Menit</div>
        </div>
        """, unsafe_allow_html=True)
        
        m3.markdown(f"""
        <div class="metric-container" style="border-top-color: #EF4444;">
            <div class="metric-label">Waktu Tunggu Maksimal</div>
            <div class="metric-value">{res['max_wait_min']:.1f} Menit</div>
        </div>
        """, unsafe_allow_html=True)
        
        m4.markdown(f"""
        <div class="metric-container" style="border-top-color: #DC2626;">
            <div class="metric-label">Est. Denda Demurrage</div>
            <div class="metric-value">Rp {total_demurrage_cost:,.0f}</div>
        </div>
        """, unsafe_allow_html=True)
        
        st.markdown("<br>", unsafe_allow_html=True)
        
        df_queue = json.loads(json.dumps(res['queue_log']))
        fig_q = px.line(
            df_queue, 
            x=[q['time']/60.0 for q in df_queue], 
            y=[q['queue_length'] for q in df_queue],
            labels={'x': 'Jam Simulasi (0-24)', 'y': 'Jumlah Truk Mengantre'},
            title="📈 Dinamika Fluktuasi Panjang Antrean Truk Sepanjang Hari"
        )
        fig_q.update_traces(line_color='#2563EB', line_width=2.5)
        fig_q.update_layout(
            template="plotly_white",
            height=380,
            margin=dict(l=20, r=20, t=50, b=20)
        )
        st.plotly_chart(fig_q, use_container_width=True)

# ------------------------------------------
# TAB 3: AI SCENARIO GENERATOR
# ------------------------------------------
with tabs[2]:
    st.subheader("🤖 Generator Skenario Perbaikan Berbasis AI Gemini Flash")
    
    if 'base_sim_result' not in st.session_state:
        st.info("Silakan jalankan simulasi eksisting di Modul 2 terlebih dahulu.")
    else:
        p = st.session_state['active_params']
        base_demurrage = st.session_state.get('base_demurrage', 0)
        
        if st.button("🤖 Buat Skenario Usulan Otomatis via AI", type="primary"):
            with st.spinner("AI Gemini Flash sedang menganalisis titik bottleneck & merancang skenario..."):
                scenarios, err = generate_ai_scenarios(p, base_demurrage)
                if err:
                    st.error(f"Error AI Skenario: {err}")
                else:
                    st.session_state['ai_scenarios'] = scenarios.get('scenarios', [])
                    st.success("✨ Skenario berhasil dirancang oleh AI!")

        if 'ai_scenarios' in st.session_state:
            st.markdown("<br>", unsafe_allow_html=True)
            for idx, sc in enumerate(st.session_state['ai_scenarios']):
                with st.expander(f"📌 Skenario {idx+1}: {sc['name']}", expanded=True):
                    st.write(f"**Rasional Teknis:** {sc['rationale']}")
                    c_s1, c_s2, c_s3 = st.columns(3)
                    c_s1.info(f"**Loading Bay:** {sc['num_bays']} unit (+{sc['num_bays'] - p['num_bays']})")
                    c_s2.info(f"**Forklift:** {sc['num_forklifts']} unit (+{sc['num_forklifts'] - p['num_forklifts']})")
                    c_s3.warning(f"**Est. Biaya Investasi:** Rp {(sc.get('bay_cost_per_day', 0) + sc.get('forklift_cost_per_day', 0)):,.0f}/hari")

# ------------------------------------------
# TAB 4: TRADE-OFF ANALYTICS & EXPORT REPORT
# ------------------------------------------
with tabs[3]:
    st.subheader("⚖️ Analisis Trade-Off Finansial & Executive Summary")
    
    if 'ai_scenarios' not in st.session_state or 'base_sim_result' not in st.session_state:
        st.info("Jalankan simulasi dasar (Modul 2) dan buat skenario AI (Modul 3) terlebih dahulu untuk melihat analisis komparatif.")
    else:
        p = st.session_state['active_params']
        base_demurrage = st.session_state.get('base_demurrage', 0)
        base_res = st.session_state['base_sim_result']
        
        tradeoff_results = []
        
        # Skenario Eksisting
        tradeoff_results.append({
            'Skenario': 'Kondisi Eksisting',
            'Loading Bay': int(p['num_bays']),
            'Forklift': int(p['num_forklifts']),
            'Rata-Rata Antrean (Menit)': round(base_res['avg_wait_min'], 1),
            'Denda Demurrage (Rp)': int(round(base_demurrage)),
            'Biaya Investasi (Rp)': 0,
            'Total Biaya Operasional (Rp)': int(round(base_demurrage))
        })
        
        # Simulasi Skenario Usulan AI
        for sc in st.session_state['ai_scenarios']:
            sim_sc = run_warehouse_simulation(
                p['arrival_rate'], p['unloading_time_mean'], sc['num_bays'], sc['num_forklifts']
            )
            
            excess_hours = sum([max(0, w - 30) for w in sim_sc['raw_waiting_times']]) / 60.0
            demurrage = excess_hours * p['demurrage_rate']
            invest_cost = sc.get('bay_cost_per_day', 500000) + sc.get('forklift_cost_per_day', 300000)
            
            tradeoff_results.append({
                'Skenario': sc['name'],
                'Loading Bay': int(sc['num_bays']),
                'Forklift': int(sc['num_forklifts']),
                'Rata-Rata Antrean (Menit)': round(sim_sc['avg_wait_min'], 1),
                'Denda Demurrage (Rp)': int(round(demurrage)),
                'Biaya Investasi (Rp)': int(round(invest_cost)),
                'Total Biaya Operasional (Rp)': int(round(demurrage + invest_cost))
            })
            
        df_results = pd.DataFrame(tradeoff_results)
        
        # 1. Stacked Bar Chart Total Biaya
        st.markdown("#### 📊 Perbandingan Total Biaya Operasional")
        sc_names = [r['Skenario'] for r in tradeoff_results]
        
        fig_tradeoff = go.Figure(data=[
            go.Bar(name='Denda Demurrage (Rp)', x=sc_names, y=[r['Denda Demurrage (Rp)'] for r in tradeoff_results], marker_color='#EF4444'),
            go.Bar(name='Biaya Investasi Resource (Rp)', x=sc_names, y=[r['Biaya Investasi (Rp)'] for r in tradeoff_results], marker_color='#10B981')
        ])
        fig_tradeoff.update_layout(
            barmode='stack',
            template="plotly_white",
            height=380,
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            margin=dict(l=20, r=20, t=40, b=20)
        )
        st.plotly_chart(fig_tradeoff, use_container_width=True)
        
        # 2. Donut Charts Breakdown Biaya
        st.markdown("#### 🍩 Breakdown Struktur Biaya per Skenario")
        donut_cols = st.columns(len(tradeoff_results))
        
        for idx, row in enumerate(tradeoff_results):
            df_breakdown = pd.DataFrame({
                "Komponen Biaya": ["Denda Demurrage", "Biaya Investasi"],
                "Nominal": [row['Denda Demurrage (Rp)'], row['Biaya Investasi (Rp)']]
            })
            
            fig_donut = px.pie(
                df_breakdown,
                values="Nominal",
                names="Komponen Biaya",
                hole=0.5,
                title=f"<b>{row['Skenario']}</b>",
                color_discrete_sequence=["#EF4444", "#10B981"] if row['Biaya Investasi (Rp)'] > 0 else ["#EF4444", "#94A3B8"]
            )
            fig_donut.update_traces(textposition='inside', textinfo='percent')
            fig_donut.update_layout(showlegend=False, height=260, margin=dict(t=40, b=10, l=10, r=10))
            
            with donut_cols[idx]:
                st.plotly_chart(fig_donut, use_container_width=True)

        st.markdown("---")
        
        # 3. Tabel Keputusan DSS
        st.markdown("#### 📋 Tabel Matriks Keputusan DSS")
        st.dataframe(df_results, use_container_width=True)
        
        st.markdown("<br>", unsafe_allow_html=True)
        
        # 4. Export CSV Rapi untuk Excel
        st.markdown("#### 📥 Unduh Laporan Lanjutan")
        csv_data = df_results.to_csv(index=False, sep=';').encode('utf-8-sig')
        
        st.download_button(
            label="📄 Download Executive Summary (CSV Rapi)",
            data=csv_data,
            file_name="Executive_Summary_Bottleneck_Gudang.csv",
            mime="text/csv",
            help="Unduh tabel hasil analisis DSS yang rapi dan terformat untuk Microsoft Excel."
        )
