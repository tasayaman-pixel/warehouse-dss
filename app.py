import streamlit as st
import pandas as pd
import plotly.express as px

# -------------------------------------------------------------------
# MODUL 4: ANALISIS BIAYA, BREAKDOWN COST, & EXPORT REPORT
# -------------------------------------------------------------------
st.header("📊 Modul 4: Analisis Kelayakan Biaya & Rekomendasi DSS")

# (Asumsi data skenario sudah dihitung dari simulasi sebelumnya)
# Contoh data struktur hasil perbandingan skenario:
data_skenario = [
    {
        "Skenario": "Skenario Eksisting",
        "Loading Bay": 2,
        "Forklift": 2,
        "Avg Waiting Time (Jam)": 4.5,
        "Demurrage Cost (Rp)": 15000000,
        "Facility Cost (Rp)": 4000000,
        "Total Cost (Rp)": 19000000
    },
    {
        "Skenario": "Skenario Optimal (AI)",
        "Loading Bay": 3,
        "Forklift": 3,
        "Avg Waiting Time (Jam)": 0.8,
        "Demurrage Cost (Rp)": 2000000,
        "Facility Cost (Rp)": 6000000,
        "Total Cost (Rp)": 8000000
    }
]

df_skenario = pd.DataFrame(data_skenario)

# --- VISUALISASI BREAKDOWN BIAYA (DONUT CHART) ---
st.subheader("🍩 Breakdown Struktur Biaya (Cost Composition)")
col_chart1, col_chart2 = st.columns(2)

for i, row in df_skenario.iterrows():
    # Menyiapkan data breakdown biaya per skenario
    df_breakdown = pd.DataFrame({
        "Komponen Biaya": ["Biaya Denda (Demurrage)", "Biaya Operasional/Fasilitas"],
        "Nominal (Rp)": [row["Demurrage Cost (Rp)"], row["Facility Cost (Rp)"]]
    })
    
    # Membuat Donut Chart menggunakan Plotly
    fig_donut = px.pie(
        df_breakdown, 
        values="Nominal (Rp)", 
        names="Komponen Biaya", 
        hole=0.4,
        title=f"Breakdown Biaya: <b>{row['Skenario']}</b>",
        color_discrete_sequence=px.colors.qualitative.Pastel
    )
    fig_donut.update_traces(textposition='inside', textinfo='percent+label')
    fig_donut.update_layout(showlegend=False, height=350, margin=dict(t=40, b=20, l=10, r=10))

    if i % 2 == 0:
        with col_chart1:
            st.plotly_chart(fig_donut, use_container_width=True)
    else:
        with col_chart2:
            st.plotly_chart(fig_donut, use_container_width=True)

# --- TABEL RINGKASAN SKENARIO ---
st.subheader("📋 Ringkasan Perbandingan Skenario")
st.dataframe(df_skenario, use_container_width=True)

# --- EXPORT EXECUTIVE SUMMARY REPORT (CSV) ---
st.subheader("📥 Export Laporan Lanjutan")
st.write("Unduh ringkasan hasil analisis biaya dan skenario untuk kebutuhan dokumentasi manajemen/direksi.")

# Mengubah DataFrame menjadi format CSV
csv_data = df_skenario.to_csv(index=False).encode('utf-8')

# Tombol Download Streamlit
st.download_button(
    label="📄 Download Executive Summary (CSV)",
    data=csv_data,
    file_name="Executive_Summary_Simulasi_Gudang.csv",
    mime="text/csv",
    help="Klik untuk mengunduh laporan ringkasan skenario dalam format CSV"
)
