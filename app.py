import json
import random
import google.generativeai as genai
import numpy as np
import plotly.graph_objects as go
import simpy
import streamlit as st

# ==========================================
# 1. KONFIGURASI HALAMAN & CUSTOM CSS
# ==========================================
st.set_page_config(
    page_title="Warehouse Optimization & DSS",
    page_icon="📦",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
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
""",
    unsafe_allow_html=True,
)

# ==========================================
# 2. KONFIGURASI GEMINI API
# ==========================================
API_KEY = st.secrets.get("GEMINI_API_KEY", "")

if API_KEY:
    try:
        # Jika kunci berupa OAuth Token (AQ...), set sebagai Bearer Token/Access Token
        if API_KEY.startswith("AQ."):
            import google.auth.credentials
            credentials = google.auth.credentials.AnonymousCredentials()
            genai.configure(api_key=API_KEY, client_options={"api_key": API_KEY})
        else:
            genai.configure(api_key=API_KEY)
    except Exception as e:
        st.error(f"Gagal memuat API Key: {e}")

# ==========================================
# 3. BACKEND LOGIC & SIMULASI SIMPY
# ==========================================
def extract_parameters_to_json(case_text):
    if not API_KEY:
        st.warning("⚠️ API Key belum dikonfigurasi di Streamlit Secrets.")
        return None
    try:
        model = genai.GenerativeModel("gemini-1.5-flash")
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
            request_options={"timeout": 120.0},
        )
        return json.loads(response.text)
    except Exception as e:
        st.error(f"Error Ekstraksi AI: {e}")
        return None


def generate_ai_scenarios(params):
    if not API_KEY:
        return None
    try:
        model = genai.GenerativeModel("gemini-3.6-flash")
        prompt = f"""
        Berdasarkan parameter gudang saat ini:
        - Loading Bay: {params['num_loading_bays']}
        - Forklift: {params['num_forklifts']}
        - Laju Kedatangan: {params['arrival_rate_per_hour']} truk/jam
        - Waktu Bongkar Muat: {params['processing_time_min']}-{params['processing_time_max']} menit

        Berikan 3 rekomendasi skenario usulan penambahan resource (Loading Bay & Forklift) beserta alasannya.
        Kembalikan HANYA format JSON list:
        [
            {{"name": "Skenario Moderat", "add_bay": 1, "add_forklift": 1, "reason": "Penambahan seimbang untuk mengatasi antrean sedang"}},
            {{"name": "Skenario Hemat OpEx", "add_bay": 0, "add_forklift": 2, "reason": "Fokus menambah forklift tanpa investasi bay baru"}},
            {{"name": "Skenario Kapasitas Tinggi", "add_bay": 2, "add_forklift": 2, "reason": "Mengatasi lonjakan antrean secara maksimal"}}
        ]
        """
        response = model.generate_content(
            prompt,
            generation_config={"response_mime_type": "application/json"},
        )
        return json.loads(response.text)
    except Exception as e:
        st.error(f"Error Scenario Generator: {e}")
        return None


def run_warehouse_simulation(
    num_bays, num_forklifts, arrival_rate, proc_min, proc_max, sim_hours=24
):
    env = simpy.Environment()
    bays = simpy.Resource(env, capacity=max(1, int(num_bays)))
    forklifts = simpy.Resource(env, capacity=max(1, int(num_forklifts)))

    waiting_times = []
    trucks_completed = 0
    bay_busy_time = 0

    # Untuk tracking grafik antrean terhadap waktu
    queue_tracker = []

    def queue_monitor(env):
        while True:
            queue_length = len(bays.queue) + len(forklifts.queue)
            queue_tracker.append((env.now, queue_length))
            yield env.timeout(0.5)  # Catat setiap 30 menit

    def truck_process(env, name):
        nonlocal trucks_completed, bay_busy_time
        arrival_time = env.now

        with bays.request() as bay_req, forklifts.request() as fork_req:
            yield bay_req & fork_req
            wait_time = env.now - arrival_time
            waiting_times.append(wait_time)

            service_duration = random.uniform(proc_min / 60, proc_max / 60)
            yield env.timeout(service_duration)

            trucks_completed += 1
            bay_busy_time += service_duration

    def truck_generator(env):
        truck_id = 0
        while True:
            inter_arrival = random.expovariate(max(0.1, arrival_rate))
            yield env.timeout(inter_arrival)
            truck_id += 1
            env.process(truck_process(env, f"Truck_{truck_id}"))

    env.process(truck_generator(env))
    env.process(queue_monitor(env))
    env.run(until=sim_hours)

    avg_waiting = np.mean(waiting_times) if waiting_times else 0
    bay_utilization = (
        (bay_busy_time / (sim_hours * num_bays)) * 100
        if num_bays > 0
        else 0
    )

    return {
        "completed": trucks_completed,
        "avg_waiting_hours": avg_waiting,
        "avg_waiting_mins": avg_waiting * 60,
        "utilization_pct": min(bay_utilization, 100.0),
        "queue_tracker": queue_tracker,
    }


# ==========================================
# 4. NAVIGASI SIDEBAR & INITIAL STATE
# ==========================================
st.sidebar.image(
    "https://cdn-icons-png.flaticon.com/512/2897/2897785.png", width=80
)
st.sidebar.title("Warehouse DSS Menu")
st.sidebar.caption("Optimization & Bottleneck Simulation")

menu = st.sidebar.radio(
    "Pilih Modul:",
    [
        "📋 1. Case & AI Parsing",
        "⚙️ 2. System Parameters",
        "🧪 3. Simulation & Experiment",
        "📊 4. Decision Support & Analytics",
    ],
)

if "params" not in st.session_state:
    st.session_state["params"] = {
        "entity_name": "Truk Kontainer",
        "num_loading_bays": 2,
        "num_forklifts": 2,
        "arrival_rate_per_hour": 4,
        "processing_time_min": 30,
        "processing_time_max": 50,
        "demurrage_cost_per_hour": 150000,
        "bay_daily_cost": 300000,      # Biaya sewa/maintenance 1 Bay per hari
        "forklift_daily_cost": 200000  # Biaya sewa 1 Forklift per hari
    }

# ==========================================
# 5. HALAMAN 1: CASE & AI PARSING
# ==========================================
if menu == "📋 1. Case & AI Parsing":
    st.header("📋 Interpretasi Kasus Operasional Gudang")
    st.write(
        "Masukkan deskripsi kasus di bawah. AI akan mengekstrak parameternya, dan Anda dapat mengonfirmasi/mengedit nilainya sebelum digunakan."
    )

    default_text = "Gudang logistik PT Jaya memiliki 2 loading bay dan 2 unit forklift. Kedatangan truk kontainer rata-rata 4 unit per jam. Waktu bongkar muat berkisar antara 30 hingga 50 menit per truk. Denda keterlambatan (demurrage cost) yang harus dibayar perusahaan adalah Rp 150.000 per jam per truk yang mengantre."

    case_input = st.text_area(
        "Teks Narasi Kasus (Natural Language Input):",
        value=default_text,
        height=120,
    )

    if st.button("🤖 Ekstrak Parameter via AI", type="primary"):
        with st.spinner("AI sedang mengurai isi teks kasus..."):
            res = extract_parameters_to_json(case_input)
            if res:
                st.session_state["parsed_temp"] = res
                st.success("✅ AI Selesai Mengekstrak! Silakan periksa & konfirmasi parameter di bawah ini.")

    st.markdown("---")
    st.subheader("🔍 Validasi & Konfirmasi Parameter Hasil Ekstraksi AI")

    # Ambil data temp atau data aktif
    current = st.session_state.get("parsed_temp", st.session_state["params"])

    with st.form("confirm_form"):
        c1, c2, c3 = st.columns(3)
        v_entity = c1.text_input("Entitas Utama:", value=current.get("entity_name", "Truk Kontainer"))
        v_bays = c2.number_input("Jumlah Loading Bay:", value=int(current.get("num_loading_bays", 2)), min_value=1)
        v_forks = c3.number_input("Jumlah Forklift:", value=int(current.get("num_forklifts", 2)), min_value=1)

        c4, c5, c6 = st.columns(3)
        v_arrival = c4.number_input("Kedatangan (Truk/Jam):", value=float(current.get("arrival_rate_per_hour", 4)))
        v_min = c5.number_input("Bongkar Min (Mnt):", value=float(current.get("processing_time_min", 30)))
        v_max = c6.number_input("Bongkar Max (Mnt):", value=float(current.get("processing_time_max", 50)))

        v_cost = st.number_input("Denda Demurrage (Rp/Jam/Truk):", value=float(current.get("demurrage_cost_per_hour", 150000)))

        submit_btn = st.form_submit_button("✅ Konfirmasi & Simpan ke Modul System Parameters")
        if submit_btn:
            st.session_state["params"].update({
                "entity_name": v_entity,
                "num_loading_bays": v_bays,
                "num_forklifts": v_forks,
                "arrival_rate_per_hour": v_arrival,
                "processing_time_min": v_min,
                "processing_time_max": v_max,
                "demurrage_cost_per_hour": v_cost
            })
            st.success("🎉 Parameter resmi dikonfirmasi dan disimpan!")

# ==========================================
# 6. HALAMAN 2: SYSTEM PARAMETERS
# ==========================================
elif menu == "⚙️ 2. System Parameters":
    st.header("⚙️ Konfigurasi & Manual Override Parameter")
    p = st.session_state["params"]

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Fasilitas & Beban Operasional")
        bays = st.number_input("Kapasitas Loading Bay:", value=int(p["num_loading_bays"]), min_value=1)
        forks = st.number_input("Jumlah Unit Forklift:", value=int(p["num_forklifts"]), min_value=1)
        arrival = st.number_input("Laju Kedatangan Truk (per jam):", value=float(p["arrival_rate_per_hour"]))

    with col2:
        st.subheader("Waktu & Estimasi Biaya")
        p_min = st.number_input("Waktu Bongkar Muat Min (menit):", value=float(p["processing_time_min"]))
        p_max = st.number_input("Waktu Bongkar Muat Max (menit):", value=float(p["processing_time_max"]))
        cost = st.number_input("Denda Demurrage (Rp/Jam/Truk):", value=float(p["demurrage_cost_per_hour"]))

    st.markdown("---")
    st.subheader("💰 Biaya Tambahan Resource (Untuk Analisis Trade-off)")
    c_b, c_f = st.columns(2)
    bay_c = c_b.number_input("Biaya Operasional 1 Bay Baru (/Hari):", value=float(p.get("bay_daily_cost", 300000)))
    fork_c = c_f.number_input("Biaya Sewa 1 Forklift Baru (/Hari):", value=float(p.get("forklift_daily_cost", 200000)))

    st.session_state["params"].update({
        "num_loading_bays": bays,
        "num_forklifts": forks,
        "arrival_rate_per_hour": arrival,
        "processing_time_min": p_min,
        "processing_time_max": p_max,
        "demurrage_cost_per_hour": cost,
        "bay_daily_cost": bay_c,
        "forklift_daily_cost": fork_c
    })

# ==========================================
# 7. HALAMAN 3: SIMULATION & EXPERIMENT
# ==========================================
elif menu == "🧪 3. Simulation & Experiment":
    st.header("🧪 Eksperimen & Scenario Generation")
    p = st.session_state["params"]

    # Fitur AI Scenario Generator
    st.subheader("🤖 AI Scenario Generator")
    if st.button("✨ Minta AI Analisis & Rekomendasikan Skenario"):
        with st.spinner("AI sedang membuat beberapa alternatif skenario..."):
            ai_scenarios = generate_ai_scenarios(p)
            if ai_scenarios:
                st.session_state["ai_scenarios"] = ai_scenarios

    if "ai_scenarios" in st.session_state:
        st.write("Pilih salah satu usulan skenario dari AI untuk langsung dipasang:")
        cols = st.columns(len(st.session_state["ai_scenarios"]))
        for idx, sc in enumerate(st.session_state["ai_scenarios"]):
            with cols[idx]:
                st.info(f"**{sc['name']}**\n\n+ {sc['add_bay']} Bay, + {sc['add_forklift']} Forklift\n\n_{sc['reason']}_")
                if st.button(f"Gunakan Skenario {idx+1}", key=f"sc_btn_{idx}"):
                    st.session_state["selected_add_bay"] = sc['add_bay']
                    st.session_state["selected_add_fork"] = sc['add_forklift']
                    st.success(f"Skenario '{sc['name']}' terpilih!")

    st.markdown("---")
    st.subheader("🛠️ Pengaturan Manual Skenario Usulan")
    c1, c2 = st.columns(2)
    with c1:
        st.info("📌 **Kondisi Baseline (Awal)**")
        st.write(f"• Loading Bay: **{p['num_loading_bays']} unit**")
        st.write(f"• Forklift: **{p['num_forklifts']} unit**")

    with c2:
        st.success("🛠️ **Skenario Usulan**")
        default_bay = st.session_state.get("selected_add_bay", 0)
        default_fork = st.session_state.get("selected_add_fork", 1)
        add_bay = st.slider("Tambah Loading Bay:", 0, 4, default_bay)
        add_fork = st.slider("Tambah Forklift:", 0, 4, default_fork)

    if st.button("🚀 Jalankan Simulasi & Bandingkan", type="primary"):
        with st.spinner("Menjalankan Simulasi Discrete-Event SimPy..."):
            base_res = run_warehouse_simulation(
                p['num_loading_bays'], p['num_forklifts'], p['arrival_rate_per_hour'], p['processing_time_min'], p['processing_time_max']
            )
            improved_res = run_warehouse_simulation(
                p['num_loading_bays'] + add_bay, p['num_forklifts'] + add_fork, p['arrival_rate_per_hour'], p['processing_time_min'], p['processing_time_max']
            )

            # Hitung Biaya Denda
            cost_demurrage_base = base_res["completed"] * base_res["avg_waiting_hours"] * p["demurrage_cost_per_hour"]
            cost_demurrage_imp = improved_res["completed"] * improved_res["avg_waiting_hours"] * p["demurrage_cost_per_hour"]

            # Hitung Biaya Tambahan Resource
            resource_cost_added = (add_bay * p["bay_daily_cost"]) + (add_fork * p["forklift_daily_cost"])

            # Total Cost (Trade-off)
            total_cost_base = cost_demurrage_base
            total_cost_imp = cost_demurrage_imp + resource_cost_added

            st.session_state["sim_results"] = {
                "base": base_res,
                "improved": improved_res,
                "cost_demurrage_base": cost_demurrage_base,
                "cost_demurrage_imp": cost_demurrage_imp,
                "resource_cost_added": resource_cost_added,
                "total_cost_base": total_cost_base,
                "total_cost_imp": total_cost_imp,
                "add_bay": add_bay,
                "add_fork": add_fork
            }
            st.success("✅ Simulasi Selesai! Buka menu 📊 4. Decision Support & Analytics untuk melihat dashboard.")

# ==========================================
# 8. HALAMAN 4: DECISION SUPPORT & ANALYTICS
# ==========================================
elif menu == "📊 4. Decision Support & Analytics":
    st.header("📊 Decision Support System & Trade-Off Analytics")

    if "sim_results" not in st.session_state:
        st.warning("⚠️ Jalankan simulasi terlebih dahulu di menu 🧪 3. Simulation & Experiment.")
    else:
        res = st.session_state["sim_results"]
        b = res["base"]
        imp = res["improved"]

        st.subheader("⚡ Ringkasan Performa Dashboard")
        c1, c2, c3 = st.columns(3)
        c1.metric("Throughput Truk Selesai", f"{imp['completed']} Truk", delta=f"{imp['completed'] - b['completed']} Truk")
        c2.metric("Rata-rata Waktu Tunggu", f"{imp['avg_waiting_mins']:.1f} Mnt", delta=f"{(imp['avg_waiting_mins'] - b['avg_waiting_mins']):.1f} Mnt", delta_color="inverse")
        
        cost_diff = res['total_cost_imp'] - res['total_cost_base']
        c3.metric("Total Biaya Operasional (Denda + Resource)", f"Rp {res['total_cost_imp']:,.0f}", delta=f"Rp {cost_diff:,.0f}", delta_color="inverse")

        st.markdown("---")

        # Visualisasi Grafik Utama
        col_left, col_right = st.columns(2)
        with col_left:
            st.subheader("⏱️ Perbandingan Waktu Tunggu Truk")
            fig_time = go.Figure(data=[
                go.Bar(name='Kondisi Awal', x=['Waktu Tunggu'], y=[b['avg_waiting_mins']], marker_color='#EF5350'),
                go.Bar(name='Skenario Usulan', x=['Waktu Tunggu'], y=[imp['avg_waiting_mins']], marker_color='#66BB6A')
            ])
            fig_time.update_layout(barmode='group', height=300)
            st.plotly_chart(fig_time, use_container_width=True)

        with col_right:
            st.subheader("💰 Breakdown Total Biaya (Denda vs Sewa Resource)")
            fig_cost = go.Figure(data=[
                go.Bar(name='Kondisi Awal (Denda)', x=['Denda Demurrage'], y=[res['cost_demurrage_base']], marker_color='#EF5350'),
                go.Bar(name='Usulan (Denda)', x=['Denda Demurrage'], y=[res['cost_demurrage_imp']], marker_color='#29B6F6'),
                go.Bar(name='Usulan (Biaya Resource Baru)', x=['Sewa Tool Baru'], y=[res['resource_cost_added']], marker_color='#FFA726')
            ])
            fig_cost.update_layout(barmode='group', height=300)
            st.plotly_chart(fig_cost, use_container_width=True)

        st.markdown("---")
        # Visualisasi Alur Antrean Truk (Process Queue Flow)
        st.subheader("📈 Dinamika Antrean Truk Sepanjang Hari (24 Jam)")
        st.caption("Grafik memperlihatkan perubahan jumlah truk yang mengantre saat menunggu Loading Bay & Forklift.")

        q_base = np.array(b["queue_tracker"])
        q_imp = np.array(imp["queue_tracker"])

        fig_queue = go.Figure()
        fig_queue.add_trace(go.Scatter(x=q_base[:, 0], y=q_base[:, 1], mode='lines', name='Antrean Kondisi Awal', line=dict(color='#EF5350', width=2)))
        fig_queue.add_trace(go.Scatter(x=q_imp[:, 0], y=q_imp[:, 1], mode='lines', name='Antrean Skenario Usulan', line=dict(color='#66BB6A', width=2)))
        fig_queue.update_layout(xaxis_title="Jam Operasional", yaxis_title="Jumlah Truk Mengantre", height=320)
        st.plotly_chart(fig_queue, use_container_width=True)

        st.markdown("---")
        st.subheader("💡 Rekomendasi Keputusan Managerial (Trade-Off Analysis)")

        net_savings = res['total_cost_base'] - res['total_cost_imp']
        if net_savings > 0:
            st.success(f"""
            **Rekomendasi Terpilih:**
            Skenario usulan penambahan **{res['add_bay']} Loading Bay** dan **{res['add_fork']} Forklift** **SANGAT LAYAK (FEASIBLE)**.
            
            - **Penghematan Bersih (Net Benefit):** Rp {net_savings:,.0f} / hari (setelah dikurangi biaya penambahan resource sebesar Rp {res['resource_cost_added']:,.0f}).
            - **Efisiensi Antrean:** Memotong waktu tunggu truk hingga **{abs(imp['avg_waiting_mins'] - b['avg_waiting_mins']):.1f} menit/truk**.
            """)
        else:
            st.warning(f"""
            **Rekomendasi Terpilih:**
            Skenario usulan penambahan **{res['add_bay']} Loading Bay** dan **{res['add_fork']} Forklift** **KURANG EFISIEN (OVER-INVESTMENT)**.
            
            - **Kerugian Biaya:** Penambahan resource memakan biaya tambahan **Rp {res['resource_cost_added']:,.0f}**, padahal penurunan biaya denda denda hanya sebesar Rp {res['cost_demurrage_base'] - res['cost_demurrage_imp']:,.0f}.
            - **Saran:** Coba kurangi jumlah tambahan resource hingga menemukan titik imbang (trade-off) yang paling optimal.
            """)
