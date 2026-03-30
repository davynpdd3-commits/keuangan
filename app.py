import streamlit as st
import pandas as pd
import sqlite3
from datetime import date
import hashlib

# ==================== INISIALISASI DATABASE ====================
def init_db():
    conn = sqlite3.connect('keuangan.db')
    c = conn.cursor()
    
    # Users
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        username TEXT PRIMARY KEY,
        password TEXT
    )''')
    
    # Loans
    c.execute('''CREATE TABLE IF NOT EXISTS loans (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tanggal TEXT,
        jenis TEXT,
        kategori TEXT,
        jenis_pinjaman TEXT,
        jumlah REAL,
        keterangan TEXT,
        jatuh_tempo TEXT,
        jumlah_dibayar REAL DEFAULT 0
    )''')

    # Payments (RIWAYAT PEMBAYARAN)
    c.execute('''CREATE TABLE IF NOT EXISTS payments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        loan_id INTEGER,
        tanggal TEXT,
        jumlah REAL
    )''')

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

# ==================== START ====================
init_db()

if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False

# ==================== LOGIN ====================
if not st.session_state.logged_in:
    st.title("🔐 Login - Laporan Piutang & Hutang")

    username = st.text_input("Username", placeholder="admin")
    password = st.text_input("Password", type="password")

    if st.button("Login"):
        if check_login(username, password):
            st.session_state.logged_in = True
            st.session_state.username = username
            st.success("Login berhasil!")
            st.rerun()
        else:
            st.error("Login gagal")

# ==================== APP ====================
else:
    st.sidebar.title(f"👋 {st.session_state.username}")

    if st.sidebar.button("Logout"):
        st.session_state.logged_in = False
        st.rerun()

    menu = st.sidebar.selectbox(
        "📌 Menu",
        ["🏠 Dashboard","➕ Tambah Transaksi","💰 Pembayaran","📊 Laporan","📤 Import Data"]
    )

    # ================= DASHBOARD =================
    if menu == "🏠 Dashboard":
        st.title("Dashboard")

        conn = sqlite3.connect('keuangan.db')
        df = pd.read_sql("SELECT * FROM loans", conn)
        conn.close()

        if not df.empty:
            df['sisa'] = df['jumlah'] - df['jumlah_dibayar']

            col1,col2 = st.columns(2)

            col1.metric(
                "Total Piutang",
                f"Rp {df[df['jenis']=='Piutang']['sisa'].sum():,.0f}"
            )

            col2.metric(
                "Total Hutang",
                f"Rp {df[df['jenis']=='Hutang']['sisa'].sum():,.0f}"
            )

            st.bar_chart(df.groupby('kategori')['sisa'].sum())

        else:
            st.info("Belum ada data.")

    # ================= TAMBAH =================
    elif menu == "➕ Tambah Transaksi":
        st.title("Tambah Transaksi")

        with st.form("form"):
            tanggal = st.date_input("Tanggal", date.today())
            jenis = st.selectbox("Jenis",["Piutang","Hutang"])
            kategori = st.selectbox("Kategori",
                ["Supir Truck Tangki","Supir Truck Inti","Anggota Gudang"])
            jenis_pinjaman = st.selectbox("Jenis Pinjaman",["PJS","Cicilan"])
            jumlah = st.number_input("Jumlah",min_value=0.0,step=1000.0)
            ket = st.text_input("Keterangan")
            jt = st.date_input("Jatuh Tempo",date.today())

            if st.form_submit_button("Simpan"):
                conn = sqlite3.connect('keuangan.db')
                c = conn.cursor()

                c.execute("""
                INSERT INTO loans
                (tanggal,jenis,kategori,jenis_pinjaman,jumlah,keterangan,jatuh_tempo)
                VALUES (?,?,?,?,?,?,?)
                """,(str(tanggal),jenis,kategori,jenis_pinjaman,jumlah,ket,str(jt)))

                conn.commit()
                conn.close()

                st.success("Data tersimpan")
                st.rerun()

    # ================= PEMBAYARAN PRO =================
    elif menu == "💰 Pembayaran":
        st.title("Pembayaran Hutang / Piutang")

        conn = sqlite3.connect('keuangan.db')
        df = pd.read_sql("SELECT * FROM loans", conn)

        if df.empty:
            st.info("Tidak ada transaksi")
        else:
            df['sisa'] = df['jumlah'] - df['jumlah_dibayar']
            aktif = df[df['sisa']>0]

            pilih = st.selectbox(
                "Pilih transaksi",
                aktif.index,
                format_func=lambda x:
                f"{aktif.loc[x,'jenis']} | "
                f"{aktif.loc[x,'kategori']} | "
                f"Sisa Rp {aktif.loc[x,'sisa']:,.0f}"
            )

            sisa = float(aktif.loc[pilih,"sisa"])
            loan_id = int(aktif.loc[pilih,"id"])

            st.info(f"Sisa: Rp {sisa:,.0f}")

            bayar = st.number_input(
                "Jumlah Bayar",
                min_value=0.0,
                max_value=sisa,
                step=1000.0
            )

            if st.button("Simpan Pembayaran"):

                c = conn.cursor()

                c.execute(
                    "INSERT INTO payments (loan_id,tanggal,jumlah) VALUES (?,?,?)",
                    (loan_id,str(date.today()),bayar)
                )

                c.execute(
                    "UPDATE loans SET jumlah_dibayar = jumlah_dibayar + ? WHERE id=?",
                    (bayar,loan_id)
                )

                conn.commit()
                conn.close()

                st.success("Pembayaran berhasil")
                st.rerun()

    # ================= LAPORAN =================
    elif menu == "📊 Laporan":
        st.title("Laporan")

        conn = sqlite3.connect('keuangan.db')
        df = pd.read_sql("SELECT * FROM loans ORDER BY tanggal DESC", conn)
        conn.close()

        if not df.empty:
            df['sisa']=df['jumlah']-df['jumlah_dibayar']
            df['status']=df['sisa'].apply(
                lambda x:"LUNAS ✅" if x<=0 else "BELUM"
            )

            st.dataframe(
                df[['tanggal','jenis','kategori','jumlah',
                    'jumlah_dibayar','sisa','status']],
                use_container_width=True
            )
        else:
            st.info("Belum ada data")

    # ================= IMPORT =================
    elif menu == "📤 Import Data":
        st.title("Import Excel")

        file = st.file_uploader("Upload Excel",type=["xlsx"])

        if file:
            df_imp = pd.read_excel(file)
            st.dataframe(df_imp.head())

            if st.button("Import"):
                conn = sqlite3.connect('keuangan.db')
                c = conn.cursor()

                for _,row in df_imp.iterrows():
                    c.execute("""
                    INSERT INTO loans
                    (tanggal,jenis,kategori,jenis_pinjaman,jumlah,keterangan,jatuh_tempo)
                    VALUES (?,?,?,?,?,?,?)
                    """,(row['Tanggal'],row['Jenis'],row['Kategori'],
                        row['Jenis Pinjaman'],float(row['Jumlah']),
                        row['Keterangan'],row['Jatuh Tempo']))

                conn.commit()
                conn.close()

                st.success("Import berhasil")
