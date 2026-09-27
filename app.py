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
    page_title="DSS Bottleneck Gudang & AI Scenario Generator",
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
# 5. TAMPILAN UTAMA STREAMLIT
# ==========================================
st.title("🏭 Warehouse Bottleneck Decision Support System (DSS)")
st.caption("Aplikasi Sistem Pendukung Keputusan Berbasis Simulasi SimPy & AI Gemini")

tabs = st.tabs(["📌 Modul 1: Parameter & AI Parser", "📊 Modul 2: Simulasi & Bottleneck", "🤖 Modul 3: AI Scenario Generator", "⚖️ Modul 4: Trade-off Analytics"])

# ------------------------------------------
# TAB 1: PARAMETER INPUT
# ------------------------------------------
with tabs[0]:
    st.header("Ekstraksi Parameter Operasional")
    
    col_ai, col_manual = st.columns([1, 1])
    
    with col_ai:
        st.subheader("🤖 Ekstraksi Otomatis via AI")
        prompt_input = st.text_area(
            "Masukkan Deskripsi Kondisi Lapangan / Logistik:",
            value="Saat ini rata-rata kedatangan truk adalah 8 truk per jam. Proses pembongkaran muatan memakan waktu sekitar 25 menit per truk. Gudang saat ini memiliki 2 loading bay dan disokong oleh 3 unit forklift.",
            height=130
        )
        
        if st.button("🤖 Ekstrak Parameter via AI"):
            with st.spinner("AI sedang menguraikan data logistik..."):
                parsed_data, err = extract_parameters_to_json(prompt_input)
                if err:
                    st.error(f"Error Ekstraksi AI: {err}")
                else:
                    st.session_state['parsed_params'] = parsed_data
                    st.success("Berhasil mengekstraksi parameter!")

    with col_manual:
        st.subheader("⚙️ Validasi & Setup Parameter")
        
        default_params = st.session_state.get('parsed_params', {
            "arrival_rate": 6.0,
            "unloading_time_mean": 30.0,
            "num_bays": 2,
            "num_forklifts": 3
        })
        
        arr_rate = st.number_input("Kedatangan Truk (truk/jam):", min_value=1.0, max_value=50.0, value=float(default_params.get("arrival_rate", 6.0)))
        unl_time = st.number_input("Rata-rata Waktu Unloading (menit):", min_value=5.0, max_value=180.0, value=float(default_params.get("unloading_time_mean", 30.0)))
        n_bays = st.number_input("Jumlah Loading Bay:", min_value=1, max_value=20, value=int(default_params.get("num_bays", 2)))
        n_forks = st.number_input("Jumlah Forklift:", min_value=1, max_value=20, value=int(default_params.get("num_forklifts", 3)))
        demurrage_rate = st.number_input("Tarif Denda Demurrage (Rp/jam/truk):", min_value=0, value=150000, step=10000)

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
    st.header("Hasil Simulasi Operasional Gudang (24 Jam)")
    
    if 'active_params' in st.session_state:
        p = st.session_state['active_params']
        
        if st.button("🚀 Jalankan Simulasi Eksisting"):
            sim_res = run_warehouse_simulation(
                p['arrival_rate'], p['unloading_time_mean'], p['num_bays'], p['num_forklifts']
            )
            st.session_state['base_sim_result'] = sim_res
            
        if 'base_sim_result' in st.session_state:
            res = st.session_state['base_sim_result']
            
            excess_wait_hours = sum([max(0, w - 30) for w in res['raw_waiting_times']]) / 60.0
            total_demurrage_cost = excess_wait_hours * p['demurrage_rate']
            st.session_state['base_demurrage'] = total_demurrage_cost
            
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Total Truk Melayani", f"{res['total_trucks']} Truk")
            c2.metric("Rata-rata Antrean", f"{res['avg_wait_min']:.1f} Menit")
            c3.metric("Waktu Tunggu Maksimal", f"{res['max_wait_min']:.1f} Menit")
            c4.metric("Est. Denda Demurrage", f"Rp {total_demurrage_cost:,.0f}")
            
            st.subheader("📈 Dinamika Panjang Antrean Truk (24 Jam)")
            df_queue = json.loads(json.dumps(res['queue_log']))
            fig_q = px.line(
                df_queue, x=[q['time']/60.0 for q in df_queue], y=[q['queue_length'] for q in df_queue],
                labels={'x': 'Jam Simulasi', 'y': 'Jumlah Truk Mengantre'},
                title="Panjang Antrean Truk Sepanjang Hari"
            )
            st.plotly_chart(fig_q, use_container_width=True)

# ------------------------------------------
# TAB 3: AI SCENARIO GENERATOR
# ------------------------------------------
with tabs[2]:
    st.header("Usulan Skenario Perbaikan Berbasis AI")
    
    if 'base_sim_result' not in st.session_state:
        st.warning("Silakan jalankan simulasi eksisting di Modul 2 terlebih dahulu!")
    else:
        p = st.session_state['active_params']
        base_demurrage = st.session_state.get('base_demurrage', 0)
        
        if st.button("🤖 Buat Skenario Usulan Otomatis via AI"):
            with st.spinner("AI sedang merancang skenario efisiensi..."):
                scenarios, err = generate_ai_scenarios(p, base_demurrage)
                if err:
                    st.error(f"Error AI Skenario: {err}")
                else:
                    st.session_state['ai_scenarios'] = scenarios.get('scenarios', [])
                    st.success("Skenario berhasil dibuat!")

        if 'ai_scenarios' in st.session_state:
            for idx, sc in enumerate(st.session_state['ai_scenarios']):
                with st.expander(f"📌 {sc['name']}", expanded=True):
                    st.write(f"**Rasional Teknis:** {sc['rationale']}")
                    c_s1, c_s2, c_s3 = st.columns(3)
                    c_s1.write(f"**Loading Bay:** {sc['num_bays']} unit (+{sc['num_bays'] - p['num_bays']})")
                    c_s2.write(f"**Forklift:** {sc['num_forklifts']} unit (+{sc['num_forklifts'] - p['num_forklifts']})")
                    c_s3.write(f"**Est. Biaya Investasi/Sewa:** Rp {(sc.get('bay_cost_per_day', 0) + sc.get('forklift_cost_per_day', 0)):,.0f}/hari")

# ------------------------------------------
# TAB 4: TRADE-OFF ANALYTICS
# ------------------------------------------
with tabs[3]:
    st.header("Analisis Trade-Off & Keputusan Optimal")
    
    if 'ai_scenarios' not in st.session_state or 'base_sim_result' not in st.session_state:
        st.info("Jalankan simulasi dasar dan buat skenario AI terlebih dahulu untuk melihat analisis trade-off.")
    else:
        p = st.session_state['active_params']
        base_demurrage = st.session_state.get('base_demurrage', 0)
        
        tradeoff_results = []
        
        tradeoff_results.append({
            'Skenario': 'Kondisi Eksisting',
            'Denda Demurrage': base_demurrage,
            'Biaya Investasi': 0,
            'Total Biaya Operasional': base_demurrage
        })
        
        for sc in st.session_state['ai_scenarios']:
            sim_sc = run_warehouse_simulation(
                p['arrival_rate'], p['unloading_time_mean'], sc['num_bays'], sc['num_forklifts']
            )
            
            excess_hours = sum([max(0, w - 30) for w in sim_sc['raw_waiting_times']]) / 60.0
            demurrage = excess_hours * p['demurrage_rate']
            invest_cost = sc.get('bay_cost_per_day', 500000) + sc.get('forklift_cost_per_day', 300000)
            
            tradeoff_results.append({
                'Skenario': sc['name'],
                'Denda Demurrage': demurrage,
                'Biaya Investasi': invest_cost,
                'Total Biaya Operasional': demurrage + invest_cost
            })
            
        sc_names = [r['Skenario'] for r in tradeoff_results]
        fig_tradeoff = go.Figure(data=[
            go.Bar(name='Denda Demurrage (Rp)', x=sc_names, y=[r['Denda Demurrage'] for r in tradeoff_results]),
            go.Bar(name='Biaya Investasi Resource (Rp)', x=sc_names, y=[r['Biaya Investasi'] for r in tradeoff_results])
        ])
        fig_tradeoff.update_layout(barmode='stack', title="Perbandingan Trade-off Total Biaya per Skenario Usulan")
        st.plotly_chart(fig_tradeoff, use_container_width=True)
        
        st.subheader("📋 Tabel Perbandingan Keputusan DSS")
        st.dataframe(tradeoff_results, use_container_width=True)
