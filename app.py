import streamlit as st
import pandas as pd
import sqlite3
from datetime import date
import hashlib

# ==================== INISIALISASI DATABASE ====================
def init_db():
    conn = sqlite3.connect('keuangan.db')
    c = conn.cursor()
    
    # Tabel Users (Login)
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        username TEXT PRIMARY KEY,
        password TEXT
    )''')
    
    # Tabel Pinjaman / Hutang
    c.execute('''CREATE TABLE IF NOT EXISTS loans (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tanggal TEXT,
        jenis TEXT,                -- Piutang / Hutang
        kategori TEXT,             -- Supir Truck, Supir Truck Inti, Anggota Gudang
        jenis_pinjaman TEXT,       -- Kontan / Cicilan
        jumlah REAL,
        keterangan TEXT,
        jatuh_tempo TEXT,
        jumlah_dibayar REAL DEFAULT 0
    )''')
    
    # User default: admin / admin123
    hashed = hashlib.sha256('admin123'.encode()).hexdigest()
    c.execute("INSERT OR IGNORE INTO users VALUES (?, ?)", ('admin', hashed))
    
    conn.commit()
    conn.close()

def hash_password(pw):
    return hashlib.sha256(pw.encode()).hexdigest()

def check_login(username, password):
    conn = sqlite3.connect('keuangan.db')
    c = conn.cursor()
    c.execute("SELECT password FROM users WHERE username=?", (username,))
    row = c.fetchone()
    conn.close()
    return row and row[0] == hash_password(password)

# ==================== MAIN APP ====================
init_db()

if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False

if not st.session_state.logged_in:
    st.title("🔐 Login - Laporan Piutang & Hutang")
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        username = st.text_input("Username", placeholder="admin")
        password = st.text_input("Password", type="password", placeholder="admin123")
        
        if st.button("Login", use_container_width=True):
            if check_login(username, password):
                st.session_state.logged_in = True
                st.session_state.username = username
                st.success("Login berhasil! 🎉")
                st.rerun()
            else:
                st.error("Username atau password salah")
else:
    st.sidebar.title(f"👋 Selamat datang, {st.session_state.username}")
    if st.sidebar.button("🚪 Logout"):
        st.session_state.logged_in = False
        st.rerun()

    menu = st.sidebar.selectbox(
        "📌 Menu",
        ["🏠 Dashboard", "➕ Tambah Transaksi", "📊 Laporan", "📤 Import Data"]
    )

    # ===================== DASHBOARD =====================
    if menu == "🏠 Dashboard":
        st.title("🏠 Dashboard Piutang & Hutang")
        conn = sqlite3.connect('keuangan.db')
        df = pd.read_sql("SELECT * FROM loans", conn)
        conn.close()

        if df.empty:
            st.info("Belum ada data transaksi. Silakan tambah atau import dulu.")
        else:
            # Hitung sisa
            df['sisa'] = df['jumlah'] - df['jumlah_dibayar']
            
            col1, col2 = st.columns(2)
            with col1:
                total_piutang = df[df['jenis'] == 'Piutang']['sisa'].sum()
                st.metric("Total Piutang Belum Lunas", f"Rp {total_piutang:,.0f}")
            with col2:
                total_hutang = df[df['jenis'] == 'Hutang']['sisa'].sum()
                st.metric("Total Hutang Belum Lunas", f"Rp {total_hutang:,.0f}")

            st.subheader("Piutang per Kategori")
            piutang = df[df['jenis'] == 'Piutang'].groupby('kategori')['sisa'].sum()
            st.bar_chart(piutang)

            st.subheader("Hutang per Kategori")
            hutang = df[df['jenis'] == 'Hutang'].groupby('kategori')['sisa'].sum()
            st.bar_chart(hutang)

    # ===================== TAMBAH TRANSAKSI =====================
    elif menu == "➕ Tambah Transaksi":
        st.title("➕ Tambah Piutang / Hutang Baru")
        
        with st.form("form_tambah"):
            tanggal = st.date_input("Tanggal", date.today())
            jenis = st.selectbox("Jenis Transaksi", ["Piutang", "Hutang"])
            kategori = st.selectbox("Kategori", ["Supir Truck", "Supir Truck Inti", "Anggota Gudang"])
            jenis_pinjaman = st.selectbox("Jenis Pinjaman", ["Kontan", "Cicilan"])
            jumlah = st.number_input("Jumlah (Rp)", min_value=0.0, step=1000.0)
            keterangan = st.text_input("Keterangan")
            jatuh_tempo = st.date_input("Jatuh Tempo", date.today())
            
            submitted = st.form_submit_button("💾 Simpan Transaksi")
            if submitted:
                conn = sqlite3.connect('keuangan.db')
                c = conn.cursor()
                c.execute('''INSERT INTO loans 
                    (tanggal, jenis, kategori, jenis_pinjaman, jumlah, keterangan, jatuh_tempo)
                    VALUES (?, ?, ?, ?, ?, ?, ?)''',
                    (str(tanggal), jenis, kategori, jenis_pinjaman, jumlah, keterangan, str(jatuh_tempo)))
                conn.commit()
                conn.close()
                st.success("✅ Data berhasil disimpan!")

    # ===================== LAPORAN =====================
    elif menu == "📊 Laporan":
        st.title("📊 Laporan Piutang & Hutang")
        conn = sqlite3.connect('keuangan.db')
        df = pd.read_sql("SELECT * FROM loans ORDER BY tanggal DESC", conn)
        conn.close()

        if df.empty:
            st.info("Belum ada data")
        else:
            df['sisa'] = df['jumlah'] - df['jumlah_dibayar']
            filter_jenis = st.multiselect("Filter Jenis", ["Piutang", "Hutang"], default=["Piutang", "Hutang"])
            df_filter = df[df['jenis'].isin(filter_jenis)]
            
            st.dataframe(df_filter, use_container_width=True, hide_index=True)
            
            st.subheader("Ringkasan per Kategori & Jenis Pinjaman")
            summary = df_filter.groupby(['jenis', 'kategori', 'jenis_pinjaman']).agg({
                'jumlah': 'sum',
                'jumlah_dibayar': 'sum',
                'sisa': 'sum'
            }).reset_index()
            st.dataframe(summary, use_container_width=True)

            # Download
            csv = df.to_csv(index=False).encode()
            st.download_button("📥 Download Laporan CSV", csv, "laporan_piutang_hutang.csv", "text/csv")

    # ===================== IMPORT DATA =====================
    elif menu == "📤 Import Data":
        st.title("📤 Import dari Excel atau Google Sheets")
        tab1, tab2 = st.tabs(["📄 Import Excel", "📊 Import Google Sheets"])

        with tab1:
            uploaded = st.file_uploader("Upload file Excel (.xlsx)", type=["xlsx", "xls"])
            if uploaded:
                df_imp = pd.read_excel(uploaded)
                st.write("Preview data:")
                st.dataframe(df_imp.head(10))
                
                if st.button("🚀 Import ke Database"):
                    required = ['Tanggal', 'Jenis', 'Kategori', 'Jenis Pinjaman', 'Jumlah', 'Keterangan', 'Jatuh Tempo']
                    if all(col in df_imp.columns for col in required):
                        conn = sqlite3.connect('keuangan.db')
                        c = conn.cursor()
                        for _, row in df_imp.iterrows():
                            tgl = row['Tanggal']
                            if isinstance(tgl, pd.Timestamp):
                                tgl = tgl.strftime('%Y-%m-%d')
                            jt = row['Jatuh Tempo']
                            if isinstance(jt, pd.Timestamp):
                                jt = jt.strftime('%Y-%m-%d')
                            
                            c.execute('''INSERT INTO loans 
                                (tanggal, jenis, kategori, jenis_pinjaman, jumlah, keterangan, jatuh_tempo)
                                VALUES (?, ?, ?, ?, ?, ?, ?)''',
                                (tgl, row['Jenis'], row['Kategori'], row['Jenis Pinjaman'],
                                 float(row['Jumlah']), row['Keterangan'], jt))
                        conn.commit()
                        conn.close()
                        st.success(f"✅ {len(df_imp)} baris berhasil diimport!")
                    else:
                        st.error(f"Kolom harus mengandung: {required}")

        with tab2:
            st.info("Cara Google Sheets:\n1. Buka Google Sheet\n2. File → Share → Publish to web\n3. Pilih sheet → CSV → Publish\n4. Copy link yang muncul")
            gs_url = st.text_input("Paste Google Sheet CSV Link (Publish to web)")
            
            if gs_url and st.button("📥 Load & Import Google Sheets"):
                try:
                    df_gs = pd.read_csv(gs_url)
                    st.write("Preview:")
                    st.dataframe(df_gs.head(10))
                    
                    if st.button("🚀 Import ke Database (Google Sheets)"):
                        required = ['Tanggal', 'Jenis', 'Kategori', 'Jenis Pinjaman', 'Jumlah', 'Keterangan', 'Jatuh Tempo']
                        if all(col in df_gs.columns for col in required):
                            conn = sqlite3.connect('keuangan.db')
                            c = conn.cursor()
                            for _, row in df_gs.iterrows():
                                tgl = row['Tanggal']
                                if isinstance(tgl, pd.Timestamp):
                                    tgl = tgl.strftime('%Y-%m-%d')
                                jt = row['Jatuh Tempo']
                                if isinstance(jt, pd.Timestamp):
                                    jt = jt.strftime('%Y-%m-%d')
                                
                                c.execute('''INSERT INTO loans 
                                    (tanggal, jenis, kategori, jenis_pinjaman, jumlah, keterangan, jatuh_tempo)
                                    VALUES (?, ?, ?, ?, ?, ?, ?)''',
                                    (tgl, row['Jenis'], row['Kategori'], row['Jenis Pinjaman'],
                                     float(row['Jumlah']), row['Keterangan'], jt))
                            conn.commit()
                            conn.close()
                            st.success(f"✅ {len(df_gs)} baris berhasil diimport dari Google Sheets!")
                        else:
                            st.error(f"Kolom harus mengandung: {required}")
                except Exception as e:
                    st.error(f"Gagal membaca Google Sheets: {e}")