"""repair_estimator.py - ให้ AI เลือก "วิธีซ่อม/วัสดุ/งาน" จากแคตตาล็อก แล้วให้โค้ดคิดราคาเอง
ออกแบบให้ prompt สั้น กระชับ ตอบกลับใน 2-4 วินาที เหมาะกับ Raspberry Pi 4
"""
import re
import pandas as pd

KEYWORD_MAP = {
    "lighting": ["ไฟ", "หลอด", "สวิตช์", "ปลั๊ก", "พัดลม", "แสง"],
    "water_network": ["น้ำรั่ว", "ท่อน้ำ", "ก๊อก", "รั่ว", "ซึม", "ชำระ", "วาล์ว", "สายน้ำดี"],
    "sanitation": ["ส้วม", "ชักโครก", "สุขภัณฑ์", "แอร์", "ล้าง", "คราบ", "กลิ่น", "กระจก", "อ่าง"],
    "pavement_surface": ["พื้น", "กระเบื้อง", "ลามิเนต", "รอยร้าว", "บัว"],
    "Wall": ["ผนัง", "กำแพง", "ทาสี", "สีลอก", "รอยเจาะ", "โป๊ว"],
    "Door": ["ประตู", "ลูกบิด", "บานพับ", "กลอน", "ล็อค", "กุญแจ", "วงกบ", "บานประตู"]
}

SYNONYMS = {
    'ส้วม': ['ส้วม', 'สุขภัณฑ์', 'ชักโครก'],
    'โถส้วม': ['ส้วม', 'สุขภัณฑ์', 'ชักโครก'],
    'หลอดไฟ': ['หลอดไฟ', 'หลอด'],
    'ลอดไฟ': ['หลอดไฟ', 'หลอด'],
    'ไฟ': ['หลอดไฟ', 'สวิตช์', 'ปลั๊ก'],
    'ก๊อก': ['ก๊อก', 'สายน้ำ'],
    'ท่อ': ['ท่อ', 'ข้อต่อ', 'อุดตัน'],
    'แอร์': ['แอร์'],
    'พื้น': ['กระเบื้อง', 'ลามิเนต'],
    'ผนัง': ['ผนัง', 'กำแพง', 'ทาสี'],
    'ประตู': ['ประตู', 'ลูกบิด', 'บานพับ', 'กลอน'],
    'ลูกบิด': ['ลูกบิด', 'ประตู', 'กลอน', 'กุญแจ'],
    'บานพับ': ['บานพับ', 'ประตู'],
}


def load_catalog(materials_csv="materials.csv", labor_csv="labor.csv"):
    """อ่านแคตตาล็อกวัสดุและค่าแรง คืน (mats, labs) เป็น dict ตามรหัส ถ้าอ่านไม่ได้คืน ({}, {})"""
    try:
        m = pd.read_csv(materials_csv)
        l = pd.read_csv(labor_csv)
        mats = {str(r["id"]).strip().upper(): {
                    "category": r["category"], "name": r["name"],
                    "unit": r["unit"], "price": int(r["price_thb"])}
                for _, r in m.iterrows()}
        labs = {str(r["id"]).strip().upper(): {
                    "category": r["category"], "name": r["name"], "unit": r["unit"],
                    "price": int(r["price_thb"]), "min": int(r["min_charge_thb"])}
                for _, r in l.iterrows()}
        return mats, labs
    except Exception:
        return {}, {}


def filter_by_category(catalog, category_key=None, description="", max_items=4):
    """เลือกเฉพาะรายการที่ตรงกับปัญหามากที่สุด ไม่เกิน max_items เพื่อให้ AI ตอบเร็วที่สุดบน Pi 4"""
    target_cats = set([category_key]) if category_key else set()
    desc_lower = str(description).lower()
    for cat, kws in KEYWORD_MAP.items():
        if any(kw in desc_lower for kw in kws):
            target_cats.add(cat)

    pool = {k: v for k, v in catalog.items() if v.get("category") in target_cats} if target_cats else catalog

    search_words = []
    for k, syns in SYNONYMS.items():
        if k in desc_lower:
            search_words.extend(syns)

    def score(item):
        name = item[1]["name"].lower()
        s = 0
        for w in search_words:
            if w in name:
                s += 3
        if item[1].get("category") == category_key:
            s += 1
        return s

    sorted_items = sorted(pool.items(), key=score, reverse=True)
    return dict(sorted_items[:max_items])


def extract_issues(description):
    """แยกข้อความปัญหาออกเป็นจุดๆ เพื่อช่วยให้โมเดลขนาดเล็กมองเห็นครบทุกจุด ไม่ตกหล่น"""
    raw_parts = re.split(r'[\n,;|]|\s{2,}|\sและ\s|\sกับ\s', description)
    parts = [p.strip() for p in raw_parts if len(p.strip()) >= 3]
    if len(parts) <= 1:
        sub_parts = [p.strip() for p in description.split(' ') if len(p.strip()) >= 4]
        if len(sub_parts) > 1:
            parts = sub_parts
    return parts if parts else [description]


def build_prompt(category_th, description, location, mats, jobs):
    """สร้าง prompt โครงสร้างชัดเจน แจกแจงทุกจุดที่ชำรุด เพื่อให้ AI ตอบครบใน 2-4 วินาที"""
    mat_lines = "\n".join(f"{k}: {v['name']}" for k, v in mats.items())
    job_lines = "\n".join(f"{k}: {v['name']}" for k, v in jobs.items())

    issues = extract_issues(description)
    if len(issues) > 1:
        issue_str = "\n".join(f"- จุดที่ {i+1}: {iss}" for i, iss in enumerate(issues))
        rule = f"เคสนี้มีปัญหา {len(issues)} จุด ต้องเลือก id ให้ครบทุกจุด:\n{issue_str}"
    else:
        rule = f"เคส: [{category_th}] {str(description)[:150]} ({location})"

    ex_m = list(mats.keys())[:2] if len(mats) >= 2 else list(mats.keys())
    ex_j = list(jobs.keys())[:2] if len(jobs) >= 2 else list(jobs.keys())

    return f"""ประเมินความเสียหายห้องพัก เลือก id วัสดุและงานซ่อม ตอบเป็น JSON เท่านั้น
วัสดุ:
{mat_lines}
งานซ่อม:
{job_lines}

{rule}

ตัวอย่าง: {{"analysis": "ระบุจุดที่ชำรุด", "materials": {ex_m}, "jobs": {ex_j}}}
ตอบเป็น JSON:"""


def _to_int(v, default, lo, hi):
    try:
        n = int(round(float(v)))
    except Exception:
        n = default
    return max(lo, min(hi, n))


def estimate_from_ai(jd, mats, jobs, original_desc=""):
    """แปลงคำตอบ JSON ของ AI เป็นยอดเงิน พร้อมแจกแจงรายการให้ชัดเจน"""
    # 1. คำนวณค่าวัสดุ
    items, mat_total, seen_mats = [], 0, set()
    raw_items = jd.get("materials", [])
    if isinstance(raw_items, list):
        for it in raw_items:
            mid, qty = "", 1
            if isinstance(it, str):
                mid = it.strip().upper()
            elif isinstance(it, dict):
                mid = str(it.get("id", "")).strip().upper()
                qty = _to_int(it.get("qty", 1), 1, 1, 20)
            if mid not in mats or mid in seen_mats:
                continue
            seen_mats.add(mid)
            sub = mats[mid]["price"] * qty
            items.append({
                "id": mid, "name": mats[mid]["name"], "unit": mats[mid]["unit"],
                "qty": qty, "price": mats[mid]["price"], "sub": sub
            })
            mat_total += sub

    # 2. คำนวณค่าแรง (รองรับทั้ง list 'jobs' และ single 'job')
    job_items, lab_total, seen_jobs = [], 0, set()
    raw_jobs = jd.get("jobs", [])
    if isinstance(raw_jobs, list) and raw_jobs:
        for it in raw_jobs:
            jid, jq = "", 1
            if isinstance(it, str):
                jid = it.strip().upper()
            elif isinstance(it, dict):
                jid = str(it.get("id", "")).strip().upper()
                jq = _to_int(it.get("qty", 1), 1, 1, 50)
            if jid not in jobs or jid in seen_jobs:
                continue
            seen_jobs.add(jid)
            sub = max(jobs[jid]["price"] * jq, jobs[jid]["min"])
            job_items.append({
                "id": jid, "name": jobs[jid]["name"], "unit": jobs[jid]["unit"],
                "qty": jq, "price": jobs[jid]["price"], "sub": sub
            })
            lab_total += sub
    elif "job" in jd:
        val = jd.get("job")
        jid = str(val).strip().upper() if isinstance(val, (str, int)) else ""
        if jid in jobs and jid not in seen_jobs:
            jq = _to_int(jd.get("job_qty", 1), 1, 1, 50)
            sub = max(jobs[jid]["price"] * jq, jobs[jid]["min"])
            job_items.append({
                "id": jid, "name": jobs[jid]["name"], "unit": jobs[jid]["unit"],
                "qty": jq, "price": jobs[jid]["price"], "sub": sub
            })
            lab_total += sub

    analysis_text = str(jd.get("analysis", "")).strip()
    if not analysis_text or "ระบุ" in analysis_text or "สรุป" in analysis_text:
        analysis_text = f"ตรวจพบความเสียหายตามที่แจ้ง: {original_desc}" if original_desc else "ตรวจพบความเสียหายตามรายการที่เลือก"

    note = [analysis_text]
    if not items and not job_items:
        note.append("⚠️ AI ไม่พบรายการที่ตรงกับแคตตาล็อก กรุณาตรวจสอบหรือกรอกราคาเอง")

    note_text = "\n".join(p for p in note if p)

    # รายละเอียดแจกแจงรายการ
    detail = []
    if items:
        mat_str = ", ".join(f"{i['name']} x{i['qty']} {i['unit']} ({i['sub']:,} บ.)" for i in items)
        detail.append(f"📦 วัสดุ: {mat_str}")
    if job_items:
        lab_str = ", ".join(f"{j['name']} x{j['qty']} {j['unit']} ({j['sub']:,} บ.)" for j in job_items)
        detail.append(f"👷 ค่าแรง: {lab_str}")

    full_analysis = "\n\n".join([note_text] + detail) if detail else note_text

    return {
        "note": note_text,
        "analysis": full_analysis,
        "mat": mat_total,
        "lab": lab_total,
        "ai_deduct": mat_total + lab_total,
        "items": items,
        "jobs": job_items,
        "job": job_items[0] if job_items else None,
    }