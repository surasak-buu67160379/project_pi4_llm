import streamlit as st
import pandas as pd
import requests
import json
import re
import html
import os
import sqlite3
from perf_monitor import run_with_monitor, log_perf  # วัด latency + CPU/RAM/Temp ของ Pi
from repair_estimator import load_catalog, filter_by_category, build_prompt, estimate_from_ai
from datetime import datetime

# ==========================================
# PAGE CONFIG – 16:9-friendly wide layout
# ==========================================
st.set_page_config(
    page_title="RoomGuard – ระบบตรวจรับห้องพักและประเมินเงินประกัน",
    page_icon="🏢",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ==========================================
# GLOBAL CSS
# ==========================================
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Sans+Thai:wght@300;400;500;600;700&family=Noto+Serif+Thai:wght@600;700;800&display=swap');

:root {
  --ink:#0F2421; --mist:#EBF2EF; --paper:#FFFFFF;
  --brass:#C99B3E; --brick:#C0402A; --pine:#1A7A56; --teal:#0D9488;
  --line:#D0DDD9; --muted:#5B7370; --dim:#8FA5A0;
  --grad-tenant: linear-gradient(135deg,#0D9488 0%,#0F766E 100%);
  --grad-landlord: linear-gradient(135deg,#B7862B 0%,#92650A 100%);
  --card-shadow: 0 4px 24px rgba(15,36,33,.12);
  --hover-shadow: 0 8px 32px rgba(15,36,33,.2);
}
html, body, .stApp, .stApp * { font-family:'IBM Plex Sans Thai', sans-serif !important; box-sizing:border-box; }
.stApp { background: var(--mist); color: var(--ink); }
header[data-testid="stHeader"] { background: transparent !important; }
.block-container { max-width: 1280px !important; padding: 1.5rem 2rem !important; }
section[data-testid="stSidebar"] { display:none !important; }
::-webkit-scrollbar { width:6px; height:6px; }
::-webkit-scrollbar-track { background: var(--mist); }
::-webkit-scrollbar-thumb { background: var(--line); border-radius:99px; }

/* TOPBAR */
.topbar { display:flex; align-items:center; justify-content:space-between; background:var(--ink); border-radius:16px; padding:14px 24px; margin-bottom:20px; }
.topbar-logo { font-family:'Noto Serif Thai',serif; font-size:1.35rem; color:#F4F8F6; font-weight:700; }
.topbar-logo span { color: var(--brass); }
.topbar-badge { display:inline-flex; align-items:center; gap:8px; background:rgba(255,255,255,.1); border:1px solid rgba(255,255,255,.18); border-radius:99px; padding:6px 16px; color:#E0EDEA; font-size:.88rem; }

/* STAT CARDS */
.stat-row { display:grid; grid-template-columns:repeat(4,1fr); gap:14px; margin-bottom:20px; }
.stat-card { background:var(--paper); border:1px solid var(--line); border-radius:14px; padding:18px 22px; box-shadow:var(--card-shadow); transition:.2s; }
.stat-card:hover { box-shadow:var(--hover-shadow); transform:translateY(-2px); }
.stat-card .s-icon { font-size:1.8rem; margin-bottom:6px; }
.stat-card .s-val { font-family:'Noto Serif Thai',serif; font-size:2rem; font-weight:800; color:var(--ink); line-height:1; margin-bottom:2px; }
.stat-card .s-label { color:var(--muted); font-size:.82rem; }

/* HERO BANNERS */
.tenant-hero { background:var(--grad-tenant); border-radius:18px; padding:32px 36px; margin-bottom:22px; display:flex; align-items:center; justify-content:space-between; gap:16px; }
.tenant-hero h1 { font-family:'Noto Serif Thai',serif; color:#fff; font-size:1.85rem; margin:0 0 8px; }
.tenant-hero p { color:rgba(255,255,255,.8); margin:0; font-size:.95rem; }
.landlord-hero { background:var(--grad-landlord); border-radius:18px; padding:32px 36px; margin-bottom:22px; display:flex; align-items:center; justify-content:space-between; gap:16px; }
.landlord-hero h1 { font-family:'Noto Serif Thai',serif; color:#fff; font-size:1.85rem; margin:0 0 8px; }
.landlord-hero p { color:rgba(255,255,255,.82); margin:0; font-size:.95rem; }
.hero-avatar { font-size:5rem; line-height:1; background:rgba(255,255,255,.15); border-radius:50%; width:90px; height:90px; display:flex; align-items:center; justify-content:center; flex-shrink:0; }

/* SECTION CARD */
.section-card { background:var(--paper); border:1px solid var(--line); border-radius:16px; padding:26px 30px; margin-bottom:18px; box-shadow:var(--card-shadow); }
.section-title { font-family:'Noto Serif Thai',serif; font-size:1.2rem; color:var(--ink); font-weight:700; margin:0 0 18px; display:flex; align-items:center; gap:8px; }

/* CASE CARD */
.case-card { background:var(--paper); border:1px solid var(--line); border-left:5px solid var(--brass); border-radius:12px; padding:18px 22px; margin:10px 0; }
.room-badge { display:inline-block; background:var(--ink); color:#F4F8F6; border-radius:8px; padding:2px 12px; font-weight:700; font-size:.9rem; }
.kv { display:grid; grid-template-columns:160px 1fr; gap:6px 16px; font-size:.95rem; }
.kv span { color:var(--muted); }

/* STATUS PILLS */
.status-pill { display:inline-flex; align-items:center; gap:6px; border-radius:99px; padding:5px 14px; font-size:.85rem; font-weight:600; }
.status-pill.pending { background:#FFF8E6; color:#92650A; border:1px solid #E8C566; }
.status-pill.done { background:#E8F5EF; color:#1A7A56; border:1px solid #6BC89A; }
.tenant-status-card { background:var(--paper); border:1px solid var(--line); border-radius:14px; padding:20px 24px; margin-bottom:16px; box-shadow:var(--card-shadow); }

/* SLIP */
.slip { background:var(--paper); border:1px solid var(--line); border-radius:16px; padding:28px 32px 22px; margin:10px 0 18px; max-width:560px; box-shadow:var(--card-shadow); }
.slip-head { display:flex; justify-content:space-between; font-weight:700; padding-bottom:14px; border-bottom:2px solid var(--ink); font-family:'Noto Serif Thai',serif; }
.slip-row { display:flex; justify-content:space-between; padding:10px 0; border-bottom:1px solid var(--line); }
.slip-row.deduct b { color:var(--brick); }
.slip-cut { border-top:2px dashed var(--brass); margin:16px 0 14px; }
.slip-total { display:flex; justify-content:space-between; align-items:baseline; }
.slip-total b { font-family:'Noto Serif Thai',serif; font-size:2.2rem; color:var(--pine); }
.note { background:#F6EFDD; border-left:4px solid var(--brass); border-radius:10px; padding:14px 18px; margin:8px 0 18px; }

/* BUTTONS & INPUTS */
.stButton > button, .stFormSubmitButton > button {
  border-radius:10px !important; font-weight:600 !important; padding:.6rem 1.6rem !important; transition:all .2s !important;
  background: #FFFFFF !important; border: 1.5px solid #D0DDD9 !important; color: #0F2421 !important;
}
.stButton > button:hover, .stFormSubmitButton > button:hover {
  background: #EBF2EF !important; border-color: #8FA5A0 !important; box-shadow: 0 2px 8px rgba(15,36,33,.1) !important;
}
.stButton > button[kind="primary"], .stFormSubmitButton > button[kind="primary"] { background:#0F2421 !important; border:0 !important; color:#fff !important; }
.stButton > button[kind="primary"]:hover { background:#1D4A46 !important; box-shadow:0 4px 16px rgba(15,36,33,.3) !important; transform:translateY(-1px) !important; }

/* INPUT FIELDS – visible borders */
.stTextInput input, .stTextArea textarea,
div[data-baseweb="input"] input {
  border: 1.5px solid #C8D8D4 !important;
  border-radius: 8px !important;
}
.stTextInput input:focus, .stTextArea textarea:focus,
div[data-baseweb="input"] input:focus {
  border-color: #0D9488 !important;
  box-shadow: 0 0 0 2px rgba(13,148,136,.18) !important;
}
div[data-baseweb="select"] > div:first-child {
  border: 1.5px solid #C8D8D4 !important;
  border-radius: 8px !important;
}
div[data-testid="stNumberInput"] div[data-baseweb="input"] {
  border: 1.5px solid #C8D8D4 !important;
  border-radius: 8px !important;
}
[data-testid="stFileUploader"] section {
  border: 1.5px dashed #C8D8D4 !important;
  border-radius: 8px !important;
}

[data-testid="stForm"] { background:var(--paper); border:1px solid var(--line); border-radius:16px; padding:28px 32px; box-shadow:var(--card-shadow); }

/* TABS */
button[data-baseweb="tab"] { height:44px; border-radius:10px; padding:0 22px; font-weight:600; color:var(--muted); }
button[data-baseweb="tab"][aria-selected="true"] { background:var(--paper); color:var(--ink); box-shadow:0 1px 4px rgba(15,36,33,.14); }
[data-baseweb="tab-list"] { gap:6px; background:#DDE7E4; padding:5px; border-radius:12px; }
[data-baseweb="tab-highlight"], [data-baseweb="tab-border"] { display:none; }
.stApp h2, .stApp h3 { font-family:'Noto Serif Thai',serif; color:var(--ink); }

/* CHIP */
.chip { display:inline-block; border:1.5px dashed #C99B3E; color:#E8C985; border-radius:999px; padding:4px 14px; font-size:.82rem; margin-right:8px; }

@media(max-width:900px){ .stat-row { grid-template-columns:repeat(2,1fr); } }
@media(max-width:640px){ .stat-row { grid-template-columns:1fr; } .kv { grid-template-columns:1fr; } }
</style>
""", unsafe_allow_html=True)

# ==========================================
# DATABASE SETUP
# ==========================================
@st.cache_resource
def init_db():
    conn = sqlite3.connect("room_inspection.db", check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS inspections (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            room_no TEXT,
            tenant_name TEXT,
            deposit INTEGER,
            category_th TEXT,
            location TEXT,
            description TEXT,
            status TEXT,
            mat_cost INTEGER,
            lab_cost INTEGER,
            final_deduct INTEGER,
            final_remaining INTEGER,
            ai_analysis TEXT,
            created_at TEXT,
            category_key TEXT,
            image_path TEXT
        )
    """)
    # เพิ่มคอลัมน์ใหม่ให้ฐานข้อมูลเดิม (ถ้ายังไม่มี)
    existing_cols = [row[1] for row in cursor.execute("PRAGMA table_info(inspections)")]
    for col in ("category_key", "image_path"):
        if col not in existing_cols:
            cursor.execute(f"ALTER TABLE inspections ADD COLUMN {col} TEXT")
    conn.commit()
    return conn

conn = init_db()

CATEGORY_MAP = {
    "pavement_surface": "พื้นผิวและพื้นห้อง (ไม้/กระเบื้อง)",
    "water_network":    "ระบบน้ำและท่อประปา",
    "lighting":         "ระบบแสงสว่างและไฟฟ้า",
    "sanitation":       "สุขภัณฑ์และความสะอาด",
    "Wall":             "ผนังและกำแพง",
    "Door":             "ประตู หน้าต่าง และอุปกรณ์ล็อค"
}

STATUS_PENDING = "🟡 รอการตรวจสอบ"
STATUS_DONE = "🟢 ประเมินเสร็จสิ้น"
OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "qwen2.5:0.5b"
OLLAMA_TIMEOUT = 180  # วินาที
UPLOAD_DIR = "uploads"

# Demo accounts: username -> (password, role, display_name, room_no)
USERS = {
    "tenant01": ("1234",  "tenant",   "คุณสมชาย ใจดี",      "A-302"),
    "tenant02": ("1234",  "tenant",   "คุณมาลี สวัสดี",     "B-104"),
    "landlord": ("admin", "landlord", "คุณเจ้าของ อาคารดี", None),
}

@st.cache_data
def load_cost_db():
    try:
        return pd.read_csv("repair_cost_db.csv")
    except Exception:
        return pd.DataFrame()

cost_df = load_cost_db()
if cost_df.empty:
    st.warning("ไม่พบหรืออ่านไฟล์ repair_cost_db.csv ไม่ได้ AI จะประเมินโดยไม่มีเรทราคาอ้างอิง")

@st.cache_data
def get_catalogs():
    return load_catalog("materials.csv", "labor.csv")

# ==========================================
# SESSION STATE INIT
# ==========================================
for _k, _v in [("logged_in", False), ("role", None), ("username", None),
               ("display_name", None), ("room_no", None), ("quick_login", None)]:
    if _k not in st.session_state:
        st.session_state[_k] = _v

# ==========================================
# AUTH HELPER
# ==========================================
def do_login(username, password):
    if username in USERS:
        pw, role, name, room = USERS[username]
        if pw == password:
            st.session_state.logged_in    = True
            st.session_state.role         = role
            st.session_state.username     = username
            st.session_state.display_name = name
            st.session_state.room_no      = room
            return True
    return False

# ==========================================
# LOGIN PAGE
# ==========================================
def render_login():
    ql = st.session_state.get("quick_login")
    if ql == "tenant":
        do_login("tenant01", "1234")
        st.session_state.quick_login = None
        st.rerun()
    elif ql == "landlord":
        do_login("landlord", "admin")
        st.session_state.quick_login = None
        st.rerun()

    st.markdown("""
    <div style="text-align:center;padding:32px 0 8px;">
        <div style="font-family:'Noto Serif Thai',serif;font-size:2.8rem;font-weight:800;color:var(--ink);line-height:1;">
            Room<span style="color:var(--teal);">Guard</span>
        </div>
        <div style="color:var(--muted);font-size:1rem;margin-top:6px;">
            ระบบตรวจรับห้องพักและประเมินเงินประกัน &middot; Powered by Edge AI
        </div>
    </div>
    """, unsafe_allow_html=True)

    _, mid, _ = st.columns([1, 1.5, 1])
    with mid:
        st.markdown("""
        <div style="background:#0F2421;border-radius:18px;padding:24px 28px 20px;margin-bottom:18px;">
            <div style="color:#F4F8F6;font-weight:700;font-size:1rem;margin-bottom:4px;">
                &#9889; เข้าสู่ระบบด่วน (Demo)
            </div>
            <div style="color:rgba(255,255,255,.70);font-size:.82rem;margin-bottom:16px;">
                กดปุ่มด้านล่างเพื่อเข้าระบบโดยไม่ต้องพิมพ์รหัสผ่าน
            </div>
        """, unsafe_allow_html=True)

        col_t, col_l = st.columns(2)
        with col_t:
            st.markdown("""<div style="color:#0F2421;font-size:.78rem;font-weight:600;margin-bottom:4px;text-align:center;">&#127968; ฝั่งผู้เช่า</div>""", unsafe_allow_html=True)
            if st.button("สมชาย · ห้อง A-302", use_container_width=True, key="btn_ql_tenant"):
                st.session_state.quick_login = "tenant"
                st.rerun()
        with col_l:
            st.markdown("""<div style="color:#0F2421;font-size:.78rem;font-weight:600;margin-bottom:4px;text-align:center;">&#127962; ฝั่งเจ้าของห้อง</div>""", unsafe_allow_html=True)
            if st.button("เจ้าของ · Admin Panel", use_container_width=True, key="btn_ql_landlord"):
                st.session_state.quick_login = "landlord"
                st.rerun()

        st.markdown("</div>", unsafe_allow_html=True)

        st.markdown("""
        <div style="display:flex;align-items:center;gap:10px;color:#8FA5A0;font-size:.85rem;margin:4px 0 16px;">
            <div style="flex:1;height:1px;background:#D0DDD9"></div>
            หรือเข้าสู่ระบบด้วย Username
            <div style="flex:1;height:1px;background:#D0DDD9"></div>
        </div>
        """, unsafe_allow_html=True)

        with st.form("login_form"):
            username_input = st.text_input("Username", placeholder="เช่น tenant01 / landlord")
            password_input = st.text_input("Password", type="password", placeholder="รหัสผ่าน")
            if st.form_submit_button("🔒 เข้าสู่ระบบ", type="primary", use_container_width=True):
                if do_login(username_input.strip(), password_input.strip()):
                    st.rerun()
                else:
                    st.error("Username หรือ Password ไม่ถูกต้อง")

        st.markdown("""
        <div style="background:#EBF2EF;border:1px solid #D0DDD9;border-radius:12px;padding:14px 18px;margin-top:14px;font-size:.82rem;color:#5B7370;">
            <b>Demo accounts:</b><br>
            &#128100; <b>tenant01</b> / 1234 &middot; ผู้เช่าห้อง A-302<br>
            &#128100; <b>tenant02</b> / 1234 &middot; ผู้เช่าห้อง B-104<br>
            &#128273; <b>landlord</b> / admin &middot; เจ้าของห้อง (Admin)
        </div>
        """, unsafe_allow_html=True)

# ==========================================
# TOPBAR
# ==========================================
def render_topbar():
    role  = st.session_state.role
    name  = html.escape(st.session_state.display_name or "")
    badge = "#0D9488" if role == "tenant" else "#C99B3E"
    label = "ผู้เช่า" if role == "tenant" else "เจ้าของห้อง"
    icon  = "🏠" if role == "tenant" else "🏢"

    col_logo, col_btn = st.columns([5, 1])
    with col_logo:
        st.markdown(f"""
        <div class="topbar">
            <div class="topbar-logo">Room<span>Guard</span></div>
            <div class="topbar-badge">
                {icon}&nbsp;<span style="color:{badge};font-weight:700;">{label}</span>
                <span style="opacity:.4;margin:0 4px;">|</span>{name}
            </div>
        </div>
        """, unsafe_allow_html=True)
    with col_btn:
        st.markdown('<div style="height:10px"></div>', unsafe_allow_html=True)
        if st.button("🚪 ออกจากระบบ", use_container_width=True):
            for k in ["logged_in","role","username","display_name","room_no","quick_login"]:
                st.session_state[k] = None
            st.session_state.logged_in = False
            for k in ["draft", "result", "tenant_flash"]:
                st.session_state.pop(k, None)
            st.rerun()

# ==========================================
# TENANT DASHBOARD
# ==========================================
def render_tenant():
    name_db = st.session_state.display_name
    room_db = st.session_state.room_no or "—"
    name = html.escape(name_db)   # ใช้แสดงผลใน HTML (ป้องกันการแทรก HTML)
    room = html.escape(room_db)
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*), COALESCE(SUM(final_remaining),0), COALESCE(SUM(final_deduct),0) FROM inspections WHERE tenant_name=?", (name_db,))
    tc, trem, tded = cursor.fetchone()
    cursor.execute("SELECT COUNT(*) FROM inspections WHERE tenant_name=? AND status=?", (name_db, STATUS_PENDING))
    tpend = cursor.fetchone()[0]

    st.markdown(f"""
    <div class="tenant-hero">
        <div>
            <h1>สวัสดีครับ, {name} 👋</h1>
            <p>ห้องพัก <b style="color:#fff;">{room}</b> &middot; จัดการเรื่องย้ายออกและติดตามสถานะเงินประกัน</p>
            <span class="chip" style="border-color:rgba(255,255,255,.4);color:rgba(255,255,255,.85);">ผู้เช่า</span>
            <span class="chip" style="border-color:rgba(255,255,255,.4);color:rgba(255,255,255,.85);">ห้อง {room}</span>
        </div>
        <div class="hero-avatar">🏠</div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown(f"""
    <div class="stat-row">
        <div class="stat-card"><div class="s-icon">📁</div><div class="s-val">{tc}</div><div class="s-label">เคสทั้งหมดของฉัน</div></div>
        <div class="stat-card" style="border-top:3px solid #E8C566;"><div class="s-icon">🟡</div><div class="s-val" style="color:#92650A;">{tpend}</div><div class="s-label">รอการตรวจสอบ</div></div>
        <div class="stat-card" style="border-top:3px solid var(--brick);"><div class="s-icon">💸</div><div class="s-val" style="color:var(--brick);">{tded:,}</div><div class="s-label">ยอดหักค่าซ่อมรวม (บาท)</div></div>
        <div class="stat-card" style="border-top:3px solid var(--pine);"><div class="s-icon">💰</div><div class="s-val" style="color:var(--pine);">{trem:,}</div><div class="s-label">ยอดเงินประกันที่จะคืน (บาท)</div></div>
    </div>
    """, unsafe_allow_html=True)

    flash = st.session_state.pop("tenant_flash", None)
    if flash:
        st.success(flash)

    tab_form, tab_status = st.tabs(["📋 แจ้งย้ายออก / รายงานความเสียหาย", "📊 สถานะเคสของฉัน"])

    with tab_form:
        st.markdown('<div class="section-card">', unsafe_allow_html=True)
        st.markdown('<div class="section-title">📝 แบบฟอร์มแจ้งย้ายออกและรายงานความเสียหาย</div>', unsafe_allow_html=True)

        with st.form("tenant_form"):
            col1, col2 = st.columns(2)
            with col1:
                # ชื่อและห้องมาจากบัญชีที่ล็อกอิน ไม่ให้แก้ในฟอร์ม
                st.text_input("ชื่อ-นามสกุล ผู้เช่า:", name_db, disabled=True)
                st.text_input("หมายเลขห้องพัก:", room_db, disabled=True)
                initial_deposit = st.number_input("ยอดเงินประกันที่วางไว้ (บาท):", min_value=0, value=5000, step=500)
            with col2:
                category_th     = st.selectbox("หมวดหมู่จุดที่เสียหาย:", list(CATEGORY_MAP.values()))
                category_key    = next((k for k, v in CATEGORY_MAP.items() if v == category_th), None)
                location_detail = st.text_input("ตำแหน่งภายในห้อง:", placeholder="เช่น ผนังห้องนอน / พื้นห้องนั่งเล่น")
            issue_description = st.text_area("รายละเอียดความเสียหาย:", placeholder="อธิบายลักษณะความเสียหายที่พบ...", height=110)
            uploaded_image = st.file_uploader("แนบรูปถ่ายจุดที่เสียหาย (ถ้ามี):", type=["jpg","jpeg","png"])

            if st.form_submit_button("📤 ส่งเรื่องแจ้งย้ายออก", type="primary", use_container_width=True):
                if not (location_detail.strip() and issue_description.strip()):
                    st.error("กรุณากรอกตำแหน่งภายในห้องและรายละเอียดความเสียหายให้ครบ")
                else:
                    # บันทึกรูปที่แนบลงโฟลเดอร์ แล้วเก็บ path ลงฐานข้อมูล
                    image_path = None
                    if uploaded_image is not None:
                        os.makedirs(UPLOAD_DIR, exist_ok=True)
                        ext = os.path.splitext(uploaded_image.name)[1].lower()
                        safe_room = re.sub(r"[^A-Za-z0-9_-]", "_", room_db)
                        image_path = os.path.join(UPLOAD_DIR, f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{safe_room}{ext}")
                        with open(image_path, "wb") as f:
                            f.write(uploaded_image.getbuffer())

                    cur2 = conn.cursor()
                    cur2.execute("""
                        INSERT INTO inspections
                          (room_no,tenant_name,deposit,category_th,category_key,location,description,status,mat_cost,lab_cost,final_deduct,final_remaining,ai_analysis,image_path,created_at)
                        VALUES (?,?,?,?,?,?,?,?,0,0,0,0,'รอดำเนินการตรวจสอบ',?,?)
                    """, (room_db, name_db, initial_deposit, category_th, category_key, location_detail.strip(),
                          issue_description.strip(), STATUS_PENDING, image_path,
                          datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
                    conn.commit()
                    st.session_state["tenant_flash"] = "🎉 ส่งเรื่องแจ้งย้ายออกสำเร็จ! ข้อมูลถูกบันทึกและส่งให้เจ้าของห้องแล้ว"
                    st.rerun()

        st.markdown('</div>', unsafe_allow_html=True)

    with tab_status:
        st.markdown('<div class="section-card">', unsafe_allow_html=True)
        st.markdown('<div class="section-title">📊 สถานะเคสทั้งหมดของคุณ</div>', unsafe_allow_html=True)
        cursor.execute(
            "SELECT id,room_no,category_th,status,deposit,final_deduct,final_remaining,created_at FROM inspections WHERE tenant_name=? ORDER BY id DESC",
            (name_db,)
        )
        my_cases = cursor.fetchall()
        if not my_cases:
            st.info("ยังไม่มีเคสที่แจ้งในระบบ")
        else:
            for c in my_cases:
                cid, rno, cat, status, dep, deduct, remaining, created = c
                pill = "done" if status == STATUS_DONE else "pending"
                st.markdown(f"""
                <div class="tenant-status-card">
                    <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:14px;">
                        <div><span class="room-badge">ห้อง {html.escape(str(rno))}</span>&nbsp;<span style="color:var(--muted);font-size:.85rem;">#{cid} &middot; {html.escape(str(created)[:10])}</span></div>
                        <span class="status-pill {pill}">{html.escape(str(status))}</span>
                    </div>
                    <div class="kv">
                        <span>จุดที่แจ้ง</span><b>{html.escape(str(cat))}</b>
                        <span>เงินประกันตั้งต้น</span><b>{dep:,} บาท</b>
                        <span>ยอดหักค่าซ่อม</span><b style="color:var(--brick);">-{deduct:,} บาท</b>
                        <span>คืนสุทธิ (ประเมิน)</span><b style="color:var(--pine);font-size:1.1rem;">{remaining:,} บาท</b>
                    </div>
                </div>
                """, unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

# ==========================================
# LANDLORD DASHBOARD
# ==========================================
def render_landlord():
    name   = html.escape(st.session_state.display_name or "")
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM inspections")
    total_cases = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM inspections WHERE status=?", (STATUS_PENDING,))
    pending_count = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM inspections WHERE status=?", (STATUS_DONE,))
    done_count = cursor.fetchone()[0]
    cursor.execute("SELECT COALESCE(SUM(final_deduct),0) FROM inspections WHERE status=?", (STATUS_DONE,))
    total_deducted = cursor.fetchone()[0]

    st.markdown(f"""
    <div class="landlord-hero">
        <div>
            <h1>แดชบอร์ดเจ้าของห้อง 🏢</h1>
            <p>ยินดีต้อนรับ <b style="color:#fff;">{name}</b> &middot; จัดการและประเมินเคสตรวจรับห้องพักทั้งหมด</p>
            <span class="chip">เจ้าของ</span><span class="chip">Admin Panel</span>
        </div>
        <div class="hero-avatar" style="background:rgba(255,255,255,.18);">🏢</div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown(f"""
    <div class="stat-row">
        <div class="stat-card"><div class="s-icon">📁</div><div class="s-val">{total_cases}</div><div class="s-label">เคสทั้งหมด</div></div>
        <div class="stat-card" style="border-top:3px solid #E8C566;"><div class="s-icon">🟡</div><div class="s-val" style="color:#92650A;">{pending_count}</div><div class="s-label">รอการตรวจสอบ</div></div>
        <div class="stat-card" style="border-top:3px solid #6BC89A;"><div class="s-icon">✅</div><div class="s-val" style="color:var(--pine);">{done_count}</div><div class="s-label">ประเมินเสร็จสิ้น</div></div>
        <div class="stat-card" style="border-top:3px solid var(--brass);"><div class="s-icon">💰</div><div class="s-val">{total_deducted:,}</div><div class="s-label">ยอดหักค่าซ่อมรวม (บาท)</div></div>
    </div>
    """, unsafe_allow_html=True)

    tab_pending, tab_all, tab_analytics = st.tabs([
        f"🟡 รอตรวจสอบ ({pending_count})",
        "📋 ประวัติทั้งหมด",
        "📈 Analytics"
    ])

    with tab_pending:
        cursor.execute("SELECT id,room_no,tenant_name,deposit,category_th,location,description FROM inspections WHERE status=?", (STATUS_PENDING,))
        pending_cases = cursor.fetchall()

        if not pending_cases:
            st.markdown('<div class="section-card">', unsafe_allow_html=True)
            st.success("✅ ไม่มีเคสรอการตรวจสอบ — ทุกเคสดำเนินการเสร็จแล้ว!")
            st.markdown('</div>', unsafe_allow_html=True)
        else:
            case_options = {f"[#{c[0]}] ห้อง {c[1]} – {c[2]} ({c[4]})": c[0] for c in pending_cases}
            st.markdown('<div class="section-card">', unsafe_allow_html=True)
            st.markdown('<div class="section-title">🔍 เลือกเคสเพื่อประเมิน</div>', unsafe_allow_html=True)
            selected_label = st.selectbox("เลือกเคส:", list(case_options.keys()), label_visibility="collapsed")
            selected_id    = case_options[selected_label]
            st.markdown('</div>', unsafe_allow_html=True)

            cursor.execute("SELECT room_no,tenant_name,deposit,category_th,category_key,location,description,image_path FROM inspections WHERE id=?", (selected_id,))
            room_no, tenant_name, deposit, category_th, category_key, location, description, image_path = cursor.fetchone()
            # เคสเก่าที่ยังไม่มี category_key ให้หาจากชื่อหมวด
            if not category_key:
                category_key = next((k for k, v in CATEGORY_MAP.items() if v == category_th), None)
            matching_costs = cost_df[cost_df["category"] == category_key] if (not cost_df.empty and category_key) else pd.DataFrame()
            cost_ref       = matching_costs.to_string(index=False) if not matching_costs.empty else "ไม่มีข้อมูลเรทราคา"

            esc = html.escape   # ป้องกันการแทรก HTML จากข้อมูลที่ผู้เช่ากรอก
            st.markdown(f"""
            <div class="case-card">
                <div style="margin-bottom:14px;">
                    <span class="room-badge">ห้อง {esc(str(room_no))}</span>&nbsp;
                    <span style="font-weight:700;font-size:1.05rem;">{esc(str(tenant_name))}</span>
                </div>
                <div class="kv">
                    <span>เงินประกันตั้งต้น</span><b>{deposit:,} บาท</b>
                    <span>หมวดหมู่ความเสียหาย</span><b>{esc(str(category_th))}</b>
                    <span>ตำแหน่งในห้อง</span><b>{esc(str(location))}</b>
                    <span>รายละเอียดปัญหา</span><div>{esc(str(description))}</div>
                </div>
            </div>
            """, unsafe_allow_html=True)

            if image_path and os.path.exists(image_path):
                st.image(image_path, caption="รูปถ่ายที่ผู้เช่าแนบ", width=320)

            if st.button("🤖 ให้ AI ประเมินและคำนวณยอดหักประกัน", type="primary"):
                # เริ่มประเมินใหม่ ล้างผลและค่าที่แก้ไขค้างจากรอบก่อน
                st.session_state.pop("result", None)
                st.session_state.pop("draft", None)
                st.session_state.pop("perf_text", None)
                st.session_state.pop(f"mat_{selected_id}", None)
                st.session_state.pop(f"lab_{selected_id}", None)

                with st.spinner("กำลังให้ AI วิเคราะห์..."):
                    all_mats, all_jobs = get_catalogs()
                    sub_mats = filter_by_category(all_mats, category_key, description)
                    sub_jobs = filter_by_category(all_jobs, category_key, description)
                    prompt = build_prompt(category_th, description, location, sub_mats, sub_jobs)

                    new_draft, error_msg = None, None
                    try:
                        response, perf = run_with_monitor(
                            requests.post,
                            OLLAMA_URL,
                            json={
                                "model": OLLAMA_MODEL,
                                "prompt": prompt,
                                "stream": False,
                                "format": "json",
                                "options": {
                                    "temperature": 0,
                                    "num_predict": 120,
                                    "num_ctx": 1024,
                                }
                            },
                            timeout=60
                        )
                        if response.status_code != 200:
                            error_msg = f"Ollama ตอบกลับด้วยรหัส {response.status_code}"
                        else:
                            # พิมพ์สรุป latency/CPU/RAM/Temp ลง terminal + บันทึก perf_log.csv
                            st.session_state["perf_text"] = log_perf(selected_id, perf, response.json(), OLLAMA_MODEL)
                            raw = response.json().get("response", "")
                            m = re.search(r'\{.*\}', raw, re.DOTALL)
                            if not m:
                                error_msg = "AI ตอบกลับในรูปแบบที่อ่านไม่ได้ (ไม่พบ JSON)"
                            else:
                                jd = json.loads(m.group(0))
                                est = estimate_from_ai(jd, all_mats, all_jobs, original_desc=description)
                                new_draft = {
                                    "id": selected_id,
                                    "analysis": est["analysis"],
                                    "mat": est["mat"],
                                    "lab": est["lab"],
                                    "ai_deduct": est["ai_deduct"],
                                    "items": est.get("items", []),
                                    "jobs": est.get("jobs", []),
                                }
                    except requests.exceptions.Timeout:
                        error_msg = "Ollama ใช้เวลาตอบนานเกิน 60 วินาที"
                    except requests.exceptions.ConnectionError:
                        error_msg = "เชื่อมต่อ Ollama ไม่ได้ ตรวจสอบว่าเปิด Ollama และติดตั้งโมเดลแล้ว"
                    except Exception as e:
                        error_msg = f"เกิดข้อผิดพลาดในการประเมิน: {e}"

                if new_draft:
                    st.session_state["draft"] = new_draft
                else:
                    # ไม่บันทึกอะไรลงฐานข้อมูล เคสยังคงสถานะรอการตรวจสอบ
                    st.error(f"❌ ประเมินไม่สำเร็จ: {error_msg} (เคสนี้ยังคงอยู่ในสถานะรอการตรวจสอบ)")

            # ผลประเมินเบื้องต้นจาก AI ให้เจ้าของห้องตรวจและแก้ไขได้ก่อนบันทึก
            draft = st.session_state.get("draft")
            if draft and draft["id"] == selected_id:
                st.markdown("### 🤖 ผลประเมินเบื้องต้นจาก AI (ตรวจและแก้ไขตัวเลขได้ก่อนบันทึก)")
                st.markdown(f'<div class="note" style="white-space:pre-wrap;line-height:1.6;">{html.escape(draft["analysis"])}</div>', unsafe_allow_html=True)
                if st.session_state.get("perf_text"):
                    st.caption(st.session_state["perf_text"])
                c1, c2 = st.columns(2)
                mat_cost = c1.number_input("🛠️ ค่าวัสดุ (บาท):", min_value=0, value=draft["mat"], step=50, key=f"mat_{selected_id}")
                lab_cost = c2.number_input("👷 ค่าแรง (บาท):", min_value=0, value=draft["lab"], step=50, key=f"lab_{selected_id}")
                st.caption(f"หากค่าวัสดุ + ค่าแรง เป็น 0 ระบบจะใช้ยอดหักที่ AI เสนอ ({draft['ai_deduct']:,} บาท) และยอดหักจะไม่เกินเงินประกัน")

                if st.button("💾 ยืนยันและบันทึกผลการประเมิน", type="primary"):
                    # PYTHON SANITY CHECK & RE-CALCULATION
                    calc_total   = mat_cost + lab_cost
                    final_deduct = calc_total if calc_total > 0 else draft["ai_deduct"]
                    if final_deduct > deposit:
                        final_deduct = deposit
                    final_remaining = deposit - final_deduct

                    cursor.execute("""
                        UPDATE inspections
                        SET status=?, mat_cost=?, lab_cost=?, final_deduct=?, final_remaining=?, ai_analysis=?
                        WHERE id=?
                    """, (STATUS_DONE, mat_cost, lab_cost, final_deduct, final_remaining, draft["analysis"], selected_id))
                    conn.commit()

                    st.session_state["result"] = {
                        "room_no": room_no, "tenant_name": tenant_name, "description": description,
                        "mat": mat_cost, "lab": lab_cost, "deposit": deposit,
                        "final_deduct": final_deduct, "final_remaining": final_remaining,
                        "analysis": draft["analysis"],
                    }
                    st.session_state.pop("draft", None)
                    st.rerun()

        # แสดงผลสรุปหลังบันทึก (เก็บใน session_state เพื่อไม่ให้หายเมื่อกดปุ่มอื่น เช่น ดาวน์โหลด)
        result = st.session_state.get("result")
        if result:
            st.success("✅ ประเมินและบันทึกผลสำเร็จ!")
            st.markdown("### 📄 ใบสรุปผลการประเมิน")
            st.markdown(f"""
            <div class="slip">
                <div class="slip-head"><span>ใบสรุปการคืนเงินประกัน</span><span>ห้อง {html.escape(str(result['room_no']))}</span></div>
                <div class="slip-row"><span>เงินประกันตั้งต้น</span><b>{result['deposit']:,} บาท</b></div>
                <div class="slip-row deduct"><span>ค่าวัสดุและอุปกรณ์</span><b>-{result['mat']:,} บาท</b></div>
                <div class="slip-row deduct"><span>ค่าแรงช่าง</span><b>-{result['lab']:,} บาท</b></div>
                <div class="slip-row deduct"><span>ยอดหักค่าซ่อมรวม</span><b>-{result['final_deduct']:,} บาท</b></div>
                <div class="slip-cut"></div>
                <div class="slip-total"><span>คืนผู้เช่าสุทธิ</span><b>{result['final_remaining']:,} บาท</b></div>
            </div>
            """, unsafe_allow_html=True)

            st.markdown("**💬 เหตุผลการพิจารณาจาก AI:**")
            st.markdown(f'<div class="note">{html.escape(result["analysis"])}</div>', unsafe_allow_html=True)

            report_text = f"""--- [ ใบสรุปผลการตรวจสอบห้องพักและหักเงินประกัน ] ---
ห้อง: {result['room_no']} | ผู้เช่า: {result['tenant_name']}
ปัญหาที่พบ: {result['description']}
----------------------------------------
- ค่าวัสดุและอุปกรณ์: {result['mat']:,} บาท
- ค่าแรงช่าง: {result['lab']:,} บาท
- รวมค่าใช้จ่ายซ่อมแซมทั้งหมด: {result['final_deduct']:,} บาท
- ยอดเงินประกันตั้งต้น: {result['deposit']:,} บาท
- ยอดเงินประกันคงเหลือคืนผู้เช่าสุทธิ: {result['final_remaining']:,} บาท
----------------------------------------
ความเห็นผู้ตรวจสอบ: {result['analysis']}"""
            col_dl1, col_dl2 = st.columns(2)
            with col_dl1:
                st.text_area("📋 ข้อความสรุปสำหรับส่งให้ผู้เช่า:", report_text, height=150)
            with col_dl2:
                st.download_button("⬇️ ดาวน์โหลดรายงานสรุป (.txt)", report_text,
                                   file_name=f"Report_Room_{result['room_no']}.txt", mime="text/plain",
                                   use_container_width=True)

    with tab_all:
        st.markdown('<div class="section-card">', unsafe_allow_html=True)
        st.markdown('<div class="section-title">📋 ประวัติการแจ้งย้ายออกทั้งหมด</div>', unsafe_allow_html=True)
        df_hist = pd.read_sql(
            "SELECT id,room_no,tenant_name,category_th,created_at,deposit,status,final_deduct,final_remaining FROM inspections ORDER BY id DESC",
            conn
        )
        if df_hist.empty:
            st.info("ยังไม่มีข้อมูลในฐานข้อมูล")
        else:
            df_hist.columns = ["รหัส","ห้อง","ผู้เช่า","จุดชำรุด","วันที่แจ้ง","ประกัน (บาท)","สถานะ","หัก (บาท)","คืน (บาท)"]
            st.dataframe(df_hist, use_container_width=True, hide_index=True)
            st.markdown("---")
            confirm_clear = st.checkbox("ยืนยันว่าต้องการล้างประวัติทั้งหมด (ลบแล้วกู้คืนไม่ได้)")
            if st.button("🗑️ ล้างประวัติทั้งหมด", type="secondary", disabled=not confirm_clear):
                conn.cursor().execute("DELETE FROM inspections")
                conn.commit()
                st.session_state.pop("draft", None)
                st.session_state.pop("result", None)
                st.success("ล้างข้อมูลสำเร็จ!")
                st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

    with tab_analytics:
        st.markdown('<div class="section-card">', unsafe_allow_html=True)
        st.markdown('<div class="section-title">📈 วิเคราะห์ข้อมูลเชิงลึก</div>', unsafe_allow_html=True)
        df_all = pd.read_sql("SELECT * FROM inspections", conn)
        if df_all.empty:
            st.info("ยังไม่มีข้อมูลเพียงพอ — ลองเพิ่มเคสก่อนนะครับ")
        else:
            col_a, col_b = st.columns(2)
            with col_a:
                st.markdown("**📊 เคสแยกตามหมวดหมู่ความเสียหาย**")
                st.bar_chart(df_all["category_th"].value_counts())
            with col_b:
                st.markdown("**📊 สัดส่วนสถานะเคส**")
                st.bar_chart(df_all["status"].value_counts())
            st.markdown("---")
            done_df = df_all[df_all["status"] == STATUS_DONE]
            c1, c2, c3 = st.columns(3)
            with c1:
                st.metric("ยอดหักเฉลี่ยต่อเคส", f"{int(done_df['final_deduct'].mean()):,} บาท" if not done_df.empty else "—")
            with c2:
                st.metric("คืนเฉลี่ยต่อเคส", f"{int(done_df['final_remaining'].mean()):,} บาท" if not done_df.empty else "—")
            with c3:
                pct = round(done_df["final_deduct"].sum() / max(done_df["deposit"].sum(), 1) * 100, 1) if not done_df.empty else 0
                st.metric("อัตราหักเงินประกันเฉลี่ย", f"{pct}%")
        st.markdown('</div>', unsafe_allow_html=True)

# ==========================================
# MAIN ROUTER
# ==========================================
if not st.session_state.logged_in:
    render_login()
else:
    render_topbar()
    if st.session_state.role == "tenant":
        render_tenant()
    elif st.session_state.role == "landlord":
        render_landlord()