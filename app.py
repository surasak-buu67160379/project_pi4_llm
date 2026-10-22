import streamlit as st
import pandas as pd
import requests
import json
import re
import html
import sqlite3
from datetime import datetime

# ตั้งค่าหน้าเว็บ
st.set_page_config(
    page_title="ระบบประเมินค่าซ่อมและหักเงินประกัน (Tenant Check-out)",
    page_icon="🏢",
    layout="wide"
)

# Custom CSS ตกแต่งหน้าเว็บ
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Sans+Thai:wght@400;500;600&family=Noto+Serif+Thai:wght@600;700&display=swap');
    :root { --ink:#12302E; --mist:#EEF3F1; --paper:#FFFFFF; --brass:#B7862B; --brick:#B4432F; --pine:#1F7A5A; --line:#D5E0DC; --muted:#5B7370; }
    html, body, .stApp, .stApp * { font-family:'IBM Plex Sans Thai', sans-serif; }
    .stApp { background:var(--mist); color:var(--ink); }
    header[data-testid="stHeader"] { background:transparent; }
    .block-container { max-width:1080px; padding-top:2.2rem; }

    .hero { background:var(--ink); border-radius:18px; padding:32px 36px; margin-bottom:24px; }
    .hero h1 { font-family:'Noto Serif Thai', serif; font-size:1.9rem; line-height:1.4; margin:0 0 10px; padding:0; color:#F4F8F6; }
    .hero p { margin:0 0 16px; color:#B9CFCB; font-size:1rem; }
    .chip { display:inline-block; border:1.5px dashed #C99B3E; color:#E8C985; border-radius:999px; padding:4px 14px; font-size:.85rem; margin-right:8px; }

    button[data-baseweb="tab"] { height:44px; border-radius:9px; padding:0 20px; font-weight:500; color:var(--muted); }
    button[data-baseweb="tab"][aria-selected="true"] { background:var(--paper); color:var(--ink); box-shadow:0 1px 3px rgba(18,48,46,.14); }
    [data-baseweb="tab-list"] { gap:6px; background:#DDE7E4; padding:5px; border-radius:12px; }
    [data-baseweb="tab-highlight"], [data-baseweb="tab-border"] { display:none; }
    .stApp h2, .stApp h3 { font-family:'Noto Serif Thai', serif; color:var(--ink); }

    [data-testid="stForm"] { background:var(--paper); border:1px solid var(--line); border-radius:16px; padding:28px; }
    .stTextInput input, .stNumberInput input, .stTextArea textarea, [data-baseweb="select"] > div { border-radius:10px; }
    .stTextInput input:focus, .stNumberInput input:focus, .stTextArea textarea:focus { border-color:var(--pine); box-shadow:0 0 0 2px rgba(31,122,90,.25); }
    .stButton > button, .stFormSubmitButton > button, .stDownloadButton > button { border-radius:10px; padding:.55rem 1.4rem; font-weight:600; }
    .stButton > button[kind="primary"], .stFormSubmitButton > button[kind="primary"] { background:var(--ink); border:0; color:#fff; }
    .stButton > button[kind="primary"]:hover, .stFormSubmitButton > button[kind="primary"]:hover { background:#1D4A46; }
    button:focus-visible { outline:3px solid var(--brass); outline-offset:2px; }

    .card-box { background:var(--paper); border:1px solid var(--line); border-left:6px solid var(--brass); border-radius:14px; padding:22px 26px; margin:14px 0 18px; }
    .room-badge { display:inline-block; background:var(--ink); color:#F4F8F6; border-radius:8px; padding:3px 12px; font-weight:600; font-size:.9rem; }
    .card-box h4 { font-family:'Noto Serif Thai', serif; font-size:1.3rem; margin:10px 0 14px; color:var(--ink); }
    .kv { display:grid; grid-template-columns:160px 1fr; gap:6px 16px; font-size:.97rem; }
    .kv span { color:var(--muted); }

    .slip { background:var(--paper); border:1px solid var(--line); border-radius:16px; padding:26px 30px 22px; max-width:560px; margin:10px 0 18px; }
    .slip-head { display:flex; justify-content:space-between; font-weight:600; padding-bottom:14px; border-bottom:2px solid var(--ink); }
    .slip-row { display:flex; justify-content:space-between; padding:10px 0; border-bottom:1px solid var(--line); }
    .slip-row.deduct b { color:var(--brick); }
    .slip-cut { border-top:2px dashed var(--brass); margin:16px 0 14px; }
    .slip-total { display:flex; justify-content:space-between; align-items:baseline; }
    .slip-total b { font-family:'Noto Serif Thai', serif; font-size:2.1rem; color:var(--pine); }
    .note { background:#F6EFDD; border-left:4px solid var(--brass); border-radius:10px; padding:14px 18px; margin:8px 0 18px; }
    @media (max-width:640px) { .hero { padding:24px 20px; } .hero h1 { font-size:1.5rem; } .kv { grid-template-columns:1fr; } }
    </style>
""", unsafe_allow_html=True)

st.markdown("""
    <div class="hero">
        <h1>ตรวจรับห้องพักและประเมินหักเงินประกัน</h1>
        <p>ผู้เช่าแจ้งย้ายออก เจ้าของห้องตรวจสอบ แล้วระบบสรุปยอดคืนเงินประกันให้ทันที</p>
        <span class="chip">ประเมินด้วย Edge AI</span><span class="chip">บันทึกลง SQLite</span>
    </div>
""", unsafe_allow_html=True)

# ==========================================
# DATABASE SETUP (SQLite)
# ==========================================
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
            created_at TEXT
        )
    """)
    conn.commit()
    return conn

conn = init_db()

CATEGORY_MAP = {
    "pavement_surface": "พื้นผิวและพื้นห้อง (ไม้/กระเบื้อง)",
    "water_network": "ระบบน้ำและท่อประปา",
    "lighting": "ระบบแสงสว่างและไฟฟ้า",
    "sanitation": "สุขภัณฑ์และความสะอาด",
    "Wall": "ผนังและกำแพง"
}

@st.cache_data
def load_cost_db():
    try:
        return pd.read_csv("repair_cost_db.csv")
    except Exception:
        return pd.DataFrame()

cost_df = load_cost_db()

# สร้าง Tab แยกบทบาท
tab_tenant, tab_landlord, tab_history = st.tabs([
    "ผู้เช่า: แจ้งย้ายออก", 
    "เจ้าของห้อง: ตรวจสอบและประเมิน",
    "ประวัติเคสทั้งหมด"
])

# ==========================================
# TAB 1: ฝั่งผู้เช่า (Tenant)
# ==========================================
with tab_tenant:
    st.subheader("แบบฟอร์มแจ้งย้ายออกและรายงานความเสียหาย")
    st.write("กรอกข้อมูลห้องพักและรายละเอียดจุดที่ชำรุด เพื่อส่งเรื่องให้เจ้าของห้องตรวจสอบ")
    
    with st.form("tenant_form"):
        col1, col2 = st.columns(2)
        with col1:
            tenant_name = st.text_input("ชื่อ-นามสกุล ผู้เช่า:", "คุณสมชาย ใจดี")
            room_no = st.text_input("หมายเลขห้องพัก:", "A-302")
            initial_deposit = st.number_input("ยอดเงินประกันที่วางไว้ (บาท):", value=5000, step=500)
            
        with col2:
            category_th = st.selectbox("หมวดหมู่จุดที่เสียหาย:", list(CATEGORY_MAP.values()))
            category_key = [k for k, v in CATEGORY_MAP.items() if v == category_th][0]
            location_detail = st.text_input("ตำแหน่งภายในห้อง:", "เช่น ผนังห้องนอน / พื้นห้องนั่งเล่น")
        
        issue_description = st.text_area(
            "รายละเอียดความเสียหาย:", 
            "พบรอยขีดข่วนลึกบนพื้นไม้ลามิเนต และสวิตช์ไฟเสีย 1 จุด",
            height=100
        )
        
        uploaded_image = st.file_uploader("แนบรูปถ่ายจุดที่เสียหาย (ถ้ามี):", type=["jpg", "jpeg", "png"])
        
        submitted = st.form_submit_button("ส่งเรื่องแจ้งย้ายออก", type="primary")
        if submitted:
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO inspections (room_no, tenant_name, deposit, category_th, location, description, status, mat_cost, lab_cost, final_deduct, final_remaining, ai_analysis, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, 0, 0, 0, 0, 'รอดำเนินการตรวจสอบ', ?)
            """, (room_no, tenant_name, initial_deposit, category_th, location_detail, issue_description, "🟡 รอการตรวจสอบ", current_time))
            conn.commit()
            st.success("🎉 ส่งเรื่องแจ้งย้ายออกสำเร็จ! ข้อมูลถูกบันทึกลงฐานข้อมูลและส่งให้เจ้าของห้องเรียบร้อยแล้ว")

# ==========================================
# TAB 2: ฝั่งเจ้าของห้อง (Landlord)
# ==========================================
with tab_landlord:
    st.subheader("ตรวจสอบเคสที่รอการประเมิน")
    
    # ดึงข้อมูลเคสที่มีสถานะ "🟡 รอการตรวจสอบ" จาก SQLite
    cursor = conn.cursor()
    cursor.execute("SELECT id, room_no, tenant_name, deposit, category_th, location, description FROM inspections WHERE status = '🟡 รอการตรวจสอบ'")
    pending_cases = cursor.fetchall()
    
    if not pending_cases:
        st.info("👍 ไม่มีเคสค้างตรวจสอบในระบบตอนนี้ (คุณสามารถไปที่ Tab ฝั่งผู้เช่าเพื่อทดลองยื่นเรื่องใหม่ได้)")
    else:
        case_options = {f"ห้อง {c[1]} - {c[2]} ({c[4]})": c[0] for c in pending_cases}
        selected_case_label = st.selectbox("เลือกเคสที่ต้องการตรวจสอบ:", list(case_options.keys()))
        selected_id = case_options[selected_case_label]
        
        # ดึงรายละเอียดเคสที่เลือก
        cursor.execute("SELECT room_no, tenant_name, deposit, category_th, category_th, location, description FROM inspections WHERE id = ?", (selected_id,))
        # ใช้ query ดึงข้อมูลแบบเต็ม
        cursor.execute("SELECT room_no, tenant_name, deposit, category_th, location, description FROM inspections WHERE id = ?", (selected_id,))
        case_data = cursor.fetchone()
        
        room_no, tenant_name, deposit, category_th, location, description = case_data
        
        # ค้นหา key ของ category
        category_key = [k for k, v in CATEGORY_MAP.items() if v == category_th][0]
        matching_costs = cost_df[cost_df["category"] == category_key] if not cost_df.empty else pd.DataFrame()
        cost_reference_str = matching_costs.to_string(index=False) if not matching_costs.empty else "ไม่มีข้อมูลเรทราคา"

        st.markdown(f"""
            <div class="card-box">
                <span class="room-badge">ห้อง {room_no}</span>
                <h4>{tenant_name}</h4>
                <div class="kv">
                    <span>เงินประกันตั้งต้น</span><b>{deposit:,} บาท</b>
                    <span>จุดที่เสียหาย</span><b>{category_th} ({location})</b>
                    <span>ปัญหาที่แจ้ง</span><div>{description}</div>
                </div>
            </div>
        """, unsafe_allow_html=True)

        if st.button("ให้ AI ประเมินและคำนวณยอดหักประกัน", type="primary"):
            with st.spinner("กำลังให้ AI วิเคราะห์ และ Python คำนวณตรวจสอบความถูกต้อง..."):
                
                prompt = f"""
                คุณเป็นผู้ประเมินความเสียหายห้องพัก วิเคราะห์เคสนี้และตอบกลับมาเป็น JSON รูปแบบนี้เท่านั้น ห้ามมีข้อความอื่นนอกเหนือจาก JSON:
                {{
                  "analysis": "อธิบายสั้นๆ ว่าความเสียหายนี้ควรหักเงินหรือไม่",
                  "material_cost": ตัวเลขค่าวัสดุเป็น integer เช่น 300,
                  "labor_cost": ตัวเลขค่าแรงเป็น integer เช่น 200,
                  "suggested_deduct": ตัวเลขยอดหักเงินรวมเป็น integer เช่น 500
                }}
                
                ข้อมูลเคส:
                - เงินประกันตั้งต้น: {deposit} บาท
                - ปัญหา: [{category_th}] {description} ({location})
                - เรทราคาอ้างอิง:
                {cost_reference_str}
                """
                
                mat_cost, lab_cost, ai_deduct = 0, 0, 0
                ai_analysis = "ไม่สามารถวิเคราะห์ได้"
                
                try:
                    response = requests.post(
                        "http://localhost:11434/api/generate",
                        json={"model": "qwen2.5:0.5b", "prompt": prompt, "stream": False}
                    )
                    if response.status_code == 200:
                        raw_ai_text = response.json().get("response", "")
                        match = re.search(r'\{.*\}', raw_ai_text, re.DOTALL)
                        if match:
                            json_data = json.loads(match.group(0))
                            ai_analysis = json_data.get("analysis", "")
                            mat_cost = int(json_data.get("material_cost", 0))
                            lab_cost = int(json_data.get("labor_cost", 0))
                            ai_deduct = int(json_data.get("suggested_deduct", 0))
                except Exception:
                    ai_analysis = "เกิดข้อผิดพลาดในการเชื่อมต่อ Ollama"

                # PYTHON SANITY CHECK & RE-CALCULATION
                calculated_total_cost = mat_cost + lab_cost
                final_deduct = calculated_total_cost if calculated_total_cost > 0 else ai_deduct
                if final_deduct > deposit:
                    final_deduct = deposit
                final_remaining = deposit - final_deduct

                # อัปเดตข้อมูลลงฐานข้อมูล SQLite
                cursor.execute("""
                    UPDATE inspections 
                    SET status = '🟢 ประเมินเสร็จสิ้น', mat_cost = ?, lab_cost = ?, final_deduct = ?, final_remaining = ?, ai_analysis = ?
                    WHERE id = ?
                """, (mat_cost, lab_cost, final_deduct, final_remaining, ai_analysis, selected_id))
                conn.commit()

                st.success("✅ ประเมินและบันทึกผลลงฐานข้อมูลสำเร็จ!")
                
                # แสดงผล Metric Cards
                st.markdown("---")
                st.markdown("### ผลการประเมินและสรุปยอดเงินประกัน")
                
                st.markdown(f"""
                <div class="slip">
                    <div class="slip-head"><span>ใบสรุปการคืนเงินประกัน</span><span>ห้อง {room_no}</span></div>
                    <div class="slip-row"><span>เงินประกันตั้งต้น</span><b>{deposit:,} บาท</b></div>
                    <div class="slip-row deduct"><span>ค่าวัสดุและอุปกรณ์</span><b>-{mat_cost:,} บาท</b></div>
                    <div class="slip-row deduct"><span>ค่าแรงช่าง</span><b>-{lab_cost:,} บาท</b></div>
                    <div class="slip-row deduct"><span>ยอดหักค่าซ่อมรวม</span><b>-{final_deduct:,} บาท</b></div>
                    <div class="slip-cut"></div>
                    <div class="slip-total"><span>คืนผู้เช่าสุทธิ</span><b>{final_remaining:,} บาท</b></div>
                </div>
                """, unsafe_allow_html=True)

                st.markdown("### เหตุผลการพิจารณา")
                st.markdown(f'<div class="note"><b>ความเห็นจาก AI:</b> {html.escape(ai_analysis)}</div>', unsafe_allow_html=True)
                
                report_text = f"""--- [ ใบสรุปผลการตรวจสอบห้องพักและหักเงินประกัน ] ---
ห้อง: {room_no} | ผู้เช่า: {tenant_name}
ปัญหาที่พบ: {description}
----------------------------------------
- ค่าวัสดุและอุปกรณ์: {mat_cost:,} บาท
- ค่าแรงช่าง: {lab_cost:,} บาท
- รวมค่าใช้จ่ายซ่อมแซมทั้งหมด: {final_deduct:,} บาท
- ยอดเงินประกันตั้งต้น: {deposit:,} บาท
- ยอดเงินประกันคงเหลือคืนผู้เช่าสุทธิ: {final_remaining:,} บาท
----------------------------------------
ความเห็นผู้ตรวจสอบ: {ai_analysis}"""

                st.text_area("📋 ข้อความสรุปสำหรับส่งให้ผู้เช่า (คัดลอกด้านล่างนี้):", report_text, height=180)
                st.download_button("ดาวน์โหลดรายงานสรุป (.txt)", report_text, file_name=f"Report_Room_{room_no}.txt", mime="text/plain")

# ==========================================
# TAB 3: ประวัติเคสทั้งหมด (History Database)
# ==========================================
with tab_history:
    st.subheader("ประวัติการแจ้งย้ายออกและผลการประเมินทั้งหมด")
    
    # 1. ดึงข้อมูลจากฐานข้อมูล SQLite
    df_history = pd.read_sql("""
        SELECT 
            id, 
            room_no, 
            tenant_name, 
            category_th, 
            created_at, 
            deposit, 
            status, 
            final_deduct, 
            final_remaining 
        FROM inspections
    """, conn)
    
    if df_history.empty:
        st.info("ยังไม่มีข้อมูลประวัติในฐานข้อมูล")
    else:
        # 2. แปลงชื่อคอลัมน์เป็นภาษาไทยอ่านง่าย และแยกส่วนชัดเจน
        df_display = df_history.rename(columns={
            "id": "รหัสรายการ",
            "room_no": "เลขห้องพัก",
            "tenant_name": "ชื่อผู้เช่า",
            "category_th": "จุดที่แจ้งชำรุด",
            "created_at": "วันที่แจ้งเรื่อง",
            "deposit": "เงินประกันตั้งต้น (บาท)",
            "status": "สถานะ",
            "final_deduct": "ยอดหักค่าซ่อม (บาท)",
            "final_remaining": "เงินประกันคงเหลือคืน (บาท)"
        })
        
        # 3. จัดลำดับคอลัมน์ (ส่วนผู้เช่าขึ้นก่อน ตามด้วยส่วนเจ้าของห้อง)
        column_order = [
            "รหัสรายการ",
            "เลขห้องพัก", 
            "ชื่อผู้เช่า", 
            "จุดที่แจ้งชำรุด", 
            "วันที่แจ้งเรื่อง",
            "สถานะ",
            "เงินประกันตั้งต้น (บาท)", 
            "ยอดหักค่าซ่อม (บาท)", 
            "เงินประกันคงเหลือคืน (บาท)"
        ]
        
        df_display = df_display[column_order]
        
        # แสดงตารางผลลัพธ์
        st.dataframe(df_display, use_container_width=True, hide_index=True)
        
        st.markdown("---")
        if st.button("ล้างประวัติทั้งหมดในฐานข้อมูล", type="secondary"):
            cursor = conn.cursor()
            cursor.execute("DELETE FROM inspections")
            conn.commit()
            st.success("ล้างข้อมูลสำเร็จ!")
            st.rerun()