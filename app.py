import streamlit as st
import simpy
import random
import numpy as np
import plotly.graph_objects as go
import json
import google.generativeai as genai

# ==========================================
# 1. KONFIGURASI HALAMAN & CUSTOM CSS
# ==========================================
st.set_page_config(
    page_title="Warehouse Optimization & DSS",
    page_icon="📦",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
    <style>
    .main { background-color: #f8f9fa; }
    .stMetric {
        background-color: #ffffff;
        padding: 15px;
        border-radius: 10px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
        border: 1px solid #e9ecef;
    }
    .stButton>button {
        width: 100%;
        border-radius: 8px;
        font-weight: bold;
    }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# 2. KONFIGURASI GEMINI API (MOCK / DIRECT)
# ==========================================
# Ganti dengan API Key Anda sendiri jika diperlukan
API_KEY = "AQ.Ab8RN6LYnnlRG7wd7Q9apiD0Hqfc7M8hXFzeZoqOoeONOrFwKQ"

if API_KEY != "YOUR_GEMINI_API_KEY_HERE":
    genai.configure(api_key=API_KEY)

# ==========================================
# 3. MODUL AI & SIMULASI (BACKEND LOGIC)
# ==========================================

def extract_parameters_to_json(case_text):
    """
    Fungsi untuk mengekstrak narasi kasus menjadi parameter JSON terstruktur menggunakan Gemini.
    """
    if API_KEY == "YOUR_GEMINI_API_KEY_HERE":
        st.warning("⚠️ API Key belum dikonfigurasi. Menggunakan data default/fallback.")
        return {
            "entity_name": "Truk Kontainer",
            "num_loading_bays": 2,
            "num_forklifts": 2,
            "arrival_rate_per_hour": 4,
            "processing_time_min": 30,
            "processing_time_max": 50,
            "demurrage_cost_per_hour": 150000
        }
    
    try:
        model = genai.GenerativeModel('gemini-3.6-flash')
        prompt = f"""
        Kamu adalah Pakar Pemodelan dan Simulasi Sistem Industri. 
        Analisis teks kasus operasional gudang logistik berikut, lalu ekstrak parameternya ke dalam format JSON.
        
        Format JSON wajib memiliki atribut berikut:
        - entity_name (string)
        - num_loading_bays (integer)
        - num_forklifts (integer)
        - arrival_rate_per_hour (number)
        - processing_time_min (number)
        - processing_time_max (number)
        - demurrage_cost_per_hour (number)

        Teks Kasus:
        "{case_text}"
        """
        
        response = model.generate_content(
            prompt,
            generation_config={"response_mime_type": "application/json"},
            request_options={"timeout": 120.0}
        )
        return json.loads(response.text)
    except Exception as e:
        st.error(f"Error Ekstraksi AI: {e}")
        return None

def run_warehouse_simulation(num_bays, num_forklifts, arrival_rate, proc_min, proc_max, sim_hours=24):
    """
    Engine Simulasi Discrete-Event menggunakan SimPy
    """
    env = simpy.Environment()
    bays = simpy.Resource(env, capacity=max(1, int(num_bays)))
    forklifts = simpy.Resource(env, capacity=max(1, int(num_forklifts)))
    
    waiting_times = []
    trucks_completed = 0
    bay_busy_time = 0

    def truck_process(env, name):
        nonlocal trucks_completed, bay_busy_time
        arrival_time = env.now
        
        # Minta Loading Bay dan Forklift sekaligus
        with bays.request() as bay_req, forklifts.request() as fork_req:
            yield bay_req & fork_req
            wait_time = env.now - arrival_time
            waiting_times.append(wait_time)
            
            # Waktu Pelayanan Uniform
            service_duration = random.uniform(proc_min/60, proc_max/60)
            yield env.timeout(service_duration)
            
            trucks_completed += 1
            bay_busy_time += service_duration

    def truck_generator(env):
        truck_id = 0
        while True:
            # Poisson Process -> Inter-arrival Exponential
            inter_arrival = random.expovariate(max(0.1, arrival_rate))
            yield env.timeout(inter_arrival)
            truck_id += 1
            env.process(truck_process(env, f"Truck_{truck_id}"))

    env.process(truck_generator(env))
    env.run(until=sim_hours)
    
    avg_waiting = np.mean(waiting_times) if waiting_times else 0
    bay_utilization = (bay_busy_time / (sim_hours * num_bays)) * 100 if num_bays > 0 else 0
    
    return {
        "completed": trucks_completed,
        "avg_waiting_hours": avg_waiting,
        "avg_waiting_mins": avg_waiting * 60,
        "utilization_pct": min(bay_utilization, 100.0)
    }

# ==========================================
# 4. NAVIGASI SIDEBAR & INITIAL STATE
# ==========================================
st.sidebar.image("https://cdn-icons-png.flaticon.com/512/2897/2897785.png", width=80)
st.sidebar.title("Warehouse DSS Menu")
st.sidebar.caption("Optimization & Bottleneck Simulation")

menu = st.sidebar.radio(
    "Pilih Modul:",
    [
        "📋 1. Case & AI Parsing",
        "⚙️ 2. System Parameters",
        "🧪 3. Simulation & Experiment",
        "📊 4. Decision Support & Analytics"
    ]
)

# Initialize Session State
if "params" not in st.session_state:
    st.session_state["params"] = {
        "entity_name": "Truk Kontainer",
        "num_loading_bays": 2,
        "num_forklifts": 2,
        "arrival_rate_per_hour": 4,
        "processing_time_min": 30,
        "processing_time_max": 50,
        "demurrage_cost_per_hour": 150000
    }

# ==========================================
# 5. HALAMAN 1: CASE & AI PARSING
# ==========================================
if menu == "📋 1. Case & AI Parsing":
    st.header("📋 Interpretasi Kasus Operasional Gudang")
    st.write("Masukkan deskripsi permasalahan operasional gudang di bawah ini. AI Gemini akan membaca narasi tersebut dan mengekstrak parameternya secara otomatis.")
    
    default_text = "Gudang logistik PT Jaya memiliki 2 loading bay dan 2 unit forklift. Kedatangan truk kontainer rata-rata 4 unit per jam. Waktu bongkar muat berkisar antara 30 hingga 50 menit per truk. Denda keterlambatan (demurrage cost) yang harus dibayar perusahaan adalah Rp 150.000 per jam per truk yang mengantre."
    
    case_input = st.text_area("Teks Narasi Kasus (Natural Language Input):", value=default_text, height=130)
    
    col_btn, col_empty = st.columns([1, 2])
    with col_btn:
        if st.button("🤖 Ekstrak Parameter via AI", type="primary"):
            with st.spinner("AI sedang mengurai isi teks kasus..."):
                res = extract_parameters_to_json(case_input)
                if res:
                    st.session_state["params"] = res
                    st.success("✅ Parameter Berhasil Diekstrak!")

    st.markdown("---")
    st.subheader("💡 Ringkasan Parameter Hasil Ekstraksi")
    
    p = st.session_state["params"]
    col1, col2, col3 = st.columns(3)
    col1.metric("Entitas Utama", p.get("entity_name", "N/A"))
    col2.metric("Loading Bay", f"{p.get('num_loading_bays', 0)} Unit")
    col3.metric("Forklift Available", f"{p.get('num_forklifts', 0)} Unit")
    
    col4, col5, col6 = st.columns(3)
    col4.metric("Kedatangan (Arrival Rate)", f"{p.get('arrival_rate_per_hour', 0)} / Jam")
    col5.metric("Durasi Bongkar Muat", f"{p.get('processing_time_min', 0)}-{p.get('processing_time_max', 0)} Mnt")
    col6.metric("Biaya Demurrage", f"Rp {p.get('demurrage_cost_per_hour', 0):,}/Jam")

# ==========================================
# 6. HALAMAN 2: SYSTEM PARAMETERS
# ==========================================
elif menu == "⚙️ 2. System Parameters":
    st.header("⚙️ Konfigurasi & Manual Override Parameter")
    st.write("Anda dapat menyesuaikan kembali variabel operasional sebelum menjalankan simulasi digital twin.")
    
    p = st.session_state["params"]
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Fasilitas & Beban")
        bays = st.number_input("Kapasitas Loading Bay:", value=int(p.get("num_loading_bays", 2)), min_value=1)
        forks = st.number_input("Jumlah Unit Forklift:", value=int(p.get("num_forklifts", 2)), min_value=1)
        arrival = st.number_input("Laju Kedatangan Truk (per jam):", value=float(p.get("arrival_rate_per_hour", 4.0)))

    with col2:
        st.subheader("Waktu & Biaya Operational")
        p_min = st.number_input("Waktu Bongkar Muat Min (menit):", value=float(p.get("processing_time_min", 30)))
        p_max = st.number_input("Waktu Bongkar Muat Max (menit):", value=float(p.get("processing_time_max", 50)))
        cost = st.number_input("Biaya Demurrage/Denda (Rp/Jam):", value=float(p.get("demurrage_cost_per_hour", 150000)))

    # Save Update Back to Session
    st.session_state["params"] = {
        "entity_name": p.get("entity_name", "Truk Kontainer"),
        "num_loading_bays": bays,
        "num_forklifts": forks,
        "arrival_rate_per_hour": arrival,
        "processing_time_min": p_min,
        "processing_time_max": p_max,
        "demurrage_cost_per_hour": cost
    }
    
    st.info("💡 Perubahan di halaman ini akan langsung diperbarui ke modul simulasi.")

# ==========================================
# 7. HALAMAN 3: SIMULATION & EXPERIMENT
# ==========================================
elif menu == "🧪 3. Simulation & Experiment":
    st.header("🧪 Eksperimen & Skenario Simulasi Antrean")
    st.write("Jalankan simulasi kondisi eksisting (Baseline) dan bandingkan dengan skenario usulan (Improvement).")
    
    p = st.session_state["params"]
    
    c1, c2 = st.columns(2)
    with c1:
        st.info("📌 **Skenario Baseline (Eksisting)**")
        st.write(f"• Loading Bay: **{p['num_loading_bays']} unit**")
        st.write(f"• Forklift: **{p['num_forklifts']} unit**")
        st.write(f"• Kedatangan Truk: **{p['arrival_rate_per_hour']} unit/jam**")
    
    with c2:
        st.success("🛠️ **Skenario Perbaikan (Usulan Intervensi)**")
        add_bay = st.slider("Tambah Loading Bay:", 0, 4, 0)
        add_fork = st.slider("Tambah Forklift:", 0, 4, 1)
        st.write(f"• Bay Total: **{p['num_loading_bays'] + add_bay} unit**")
        st.write(f"• Forklift Total: **{p['num_forklifts'] + add_fork} unit**")

    if st.button("🚀 Jalankan Eksperimen Simulasi (24 Jam Operational)", type="primary"):
        with st.spinner("Menjalankan Simulasi SimPy..."):
            # Baseline Simulation
            base_res = run_warehouse_simulation(
                p['num_loading_bays'], 
                p['num_forklifts'], 
                p['arrival_rate_per_hour'], 
                p['processing_time_min'], 
                p['processing_time_max']
            )
            
            # Improved Simulation
            improved_res = run_warehouse_simulation(
                p['num_loading_bays'] + add_bay, 
                p['num_forklifts'] + add_fork, 
                p['arrival_rate_per_hour'], 
                p['processing_time_min'], 
                p['processing_time_max']
            )
            
            # Calculate Costs
            cost_base = base_res["completed"] * base_res["avg_waiting_hours"] * p["demurrage_cost_per_hour"]
            cost_improved = improved_res["completed"] * improved_res["avg_waiting_hours"] * p["demurrage_cost_per_hour"]
            
            st.session_state["sim_results"] = {
                "base": base_res,
                "improved": improved_res,
                "cost_base": cost_base,
                "cost_improved": cost_improved,
                "add_bay": add_bay,
                "add_fork": add_fork
            }
            st.success("✅ Simulasi Selesai! Buka menu 📊 4. Decision Support & Analytics untuk melihat rekomendasi.")

# ==========================================
# 8. HALAMAN 4: DECISION SUPPORT & ANALYTICS
# ==========================================
elif menu == "📊 4. Decision Support & Analytics":
    st.header("📊 Decision Support & Analytics Dashboard")
    
    if "sim_results" not in st.session_state:
        st.warning("⚠️ Belum ada data simulasi. Silakan jalankan simulasi terlebih dahulu pada menu **🧪 3. Simulation & Experiment**.")
    else:
        res = st.session_state["sim_results"]
        b = res["base"]
        imp = res["improved"]
        
        st.subheader("⚡ Ringkasan Perbandingan Performa")
        
        c1, c2, c3 = st.columns(3)
        c1.metric(
            label="Total Truk Terlayani (24 Jam)", 
            value=f"{imp['completed']} Truk", 
            delta=f"{imp['completed'] - b['completed']} Truk"
        )
        c2.metric(
            label="Rata-rata Waktu Tunggu", 
            value=f"{imp['avg_waiting_mins']:.1f} Mnt", 
            delta=f"{(imp['avg_waiting_mins'] - b['avg_waiting_mins']):.1f} Mnt",
            delta_color="inverse"
        )
        c3.metric(
            label="Estimasi Denda Demurrage", 
            value=f"Rp {res['cost_improved']:,.0f}", 
            delta=f"Rp {(res['cost_improved'] - res['cost_base']):,.0f}",
            delta_color="inverse"
        )

        st.markdown("---")
        
        # Visualisasi Grafik
        col_left, col_right = st.columns(2)
        
        with col_left:
            st.subheader("⏱️ Analisis Waktu Tunggu (Menit)")
            fig_time = go.Figure(data=[
                go.Bar(name='Baseline', x=['Waktu Tunggu'], y=[b['avg_waiting_mins']], marker_color='#EF5350'),
                go.Bar(name='Usulan', x=['Waktu Tunggu'], y=[imp['avg_waiting_mins']], marker_color='#66BB6A')
            ])
            fig_time.update_layout(barmode='group', height=300)
            st.plotly_chart(fig_time, use_container_width=True)

        with col_right:
            st.subheader("💰 Biaya Kerugian Demurrage (Rp)")
            fig_cost = go.Figure(data=[
                go.Bar(name='Baseline', x=['Denda Demurrage'], y=[res['cost_base']], marker_color='#EF5350'),
                go.Bar(name='Usulan', x=['Denda Demurrage'], y=[res['cost_improved']], marker_color='#29B6F6')
            ])
            fig_cost.update_layout(barmode='group', height=300)
            st.plotly_chart(fig_cost, use_container_width=True)

        st.markdown("---")
        st.subheader("💡 Rekomendasi Keputusan Managerial")
        
        saving = res['cost_base'] - res['cost_improved']
        if saving > 0:
            st.success(f"""
            **Rekomendasi:**
            Skenario Perbaikan (Penambahan **{res['add_bay']} Loading Bay** & **{res['add_fork']} Forklift**) sangat DIREKOMENDASIKAN.
            
            - **Penghematan Biaya Denda:** Memangkas kerugian akibat antrean hingga **Rp {saving:,.0f}** per hari.
            - **Efisiensi Waktu:** Mengurangi rata-rata waktu tunggu truk sebesar **{abs(imp['avg_waiting_mins'] - b['avg_waiting_mins']):.1f} menit**.
            """)
        else:
            st.info("""
            **Rekomendasi:**
            Kondisi eksisting (Baseline) sudah cukup optimal untuk menangani laju kedatangan saat ini. Penambahan fasilitas tidak memberikan dampak penghematan yang signifikan.
            """)