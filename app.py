import streamlit as st
import pandas as pd
import os, json, re
from datetime import datetime, date, timedelta
from urllib.parse import urlencode, quote, unquote
from io import BytesIO

# =========================
# 預設設定
# =========================
DEFAULT_CONFIG = {
    "categories": [
        {"category": "志工", "points": 1, "tips": "參與志工活動、擔任出隊籌備人員、帶朋友參與志工活動"},
        {"category": "美食", "points": 1, "tips": "擔任廚師、協助送餐、參與／帶動美食 DIY 社課"},
        {"category": "中華文化", "points": 2, "tips": "獻供、辦道、參與心靈成長營、讀書會"},
    ],
    "rewards": [
        {"threshold": 3,  "reward": "晚餐免費"},
        {"threshold": 6,  "reward": "手搖飲料"},
        {"threshold": 10, "reward": "活動免費"},
        {"threshold": 20, "reward": "志工慶功宴（崇德發）"},
    ],
    "log_csv": "logs.csv"
}

APP_TITLE = "✨ 集點計分器＋報到QR"
REQUIRED_COLS = ["時間","姓名","類別","獲得點數","備註","活動日期","活動名稱"]

# =========================
# 資料存取
# =========================
def ensure_csv(csv_path: str):
    if not os.path.exists(csv_path):
        pd.DataFrame(columns=REQUIRED_COLS).to_csv(csv_path, index=False)

def load_logs(csv_path: str) -> pd.DataFrame:
    ensure_csv(csv_path)
    df = pd.read_csv(csv_path)
    for c in REQUIRED_COLS:
        if c not in df.columns: df[c] = ""
    return df

def append_logs(csv_path: str, rows: list[dict]):
    df = load_logs(csv_path)
    for r in rows:
        df.loc[len(df)] = r
    df.to_csv(csv_path, index=False)

# =========================
# 小工具
# =========================
def make_qr_png(url: str) -> BytesIO:
    import qrcode
    buf = BytesIO()
    qrcode.make(url).save(buf, format="PNG")
    buf.seek(0); return buf

def event_param(title: str, category: str, edate: str) -> str:
    payload = {"title": title or "未命名活動",
               "category": category or "",
               "date": edate or date.today().isoformat()}
    return quote(json.dumps(payload, ensure_ascii=False))

def parse_event_param(s: str):
    try:
        j = json.loads(unquote(s)) if s else {}
    except Exception:
        j = {}
    return (j.get("title","未命名活動"),
            j.get("category",""),
            j.get("date", date.today().isoformat()))

def clean_names(raw: str) -> list[str]:
    """支援輸入多位姓名，用 、 ， , 空白 分隔"""
    if not raw: return []
    s = re.sub(r"[（(].*?[）)]", "", raw)
    s = re.sub(r"[、，,]", " ", s)
    return [n.strip() for n in s.split() if n.strip()]

def total_points(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty: return pd.DataFrame(columns=["姓名","總點數"])
    return (
        df.groupby("姓名")["獲得點數"].sum()
        .reset_index().rename(columns={"獲得點數":"總點數"})
        .sort_values("總點數", ascending=False, ignore_index=True)
    )

def reward_text(points: int, rewards: list) -> str:
    got = [f"{int(r['threshold'])}點：{r['reward']}" for r in sorted(rewards, key=lambda x: int(x["threshold"])) if points >= int(r["threshold"])]
    return "✅ 已解鎖｜" + "、".join(got) if got else "尚未解鎖獎勵，繼續加油～"

def next_hint(points: int, rewards: list) -> str:
    for r in sorted(rewards, key=lambda x: int(x["threshold"])):
        t = int(r["threshold"])
        if points < t: return f"再 {t - points} 點可獲得「{r['reward']}」"
    return "你已達最高獎勵門檻 🎉"

# =========================
# 主程式
# =========================
def main():
    st.set_page_config(page_title=APP_TITLE, page_icon="🔢", layout="wide")

    # 載入設定
    cfg = DEFAULT_CONFIG
    csv_path = cfg["log_csv"]
    CATEGORY_POINTS = {r["category"]: int(r["points"]) for r in cfg["categories"]}
    CATEGORY_TIPS   = {r["category"]: r.get("tips","") for r in cfg["categories"]}
    REWARDS_LIST    = cfg["rewards"]

    # 讀取紀錄
    df_logs = load_logs(csv_path)

    # URL 參數
    qp = st.query_params
    mode = qp.get("mode","")
    evt = qp.get("event","")
    ev_title, ev_cat, ev_date = parse_event_param(evt)

    # =============== 📱 產生 QRcode ===============
    if st.sidebar.button("📱 產生 QRcode", use_container_width=True): st.session_state["page"]="qr"
    if st.sidebar.button("📝 現場報到", use_container_width=True): st.session_state["page"]="checkin"
    if st.sidebar.button("📅 依日期查看參與者", use_container_width=True): st.session_state["page"]="bydate"
    if st.sidebar.button("👤 個人明細", use_container_width=True): st.session_state["page"]="detail"
    if st.sidebar.button("📒 完整記錄", use_container_width=True): st.session_state["page"]="all"
    if st.sidebar.button("🏆 排行榜", use_container_width=True): st.session_state["page"]="rank"
    page = st.session_state.get("page","qr")

    st.title(APP_TITLE)

    # 📱 產生 QR
    if page=="qr":
        st.header("📱 產生 QRcode")
        pub_url = st.text_input("公開網址（本頁網址）", placeholder="https://xxxx.streamlit.app")
        title_in = st.text_input("活動標題", placeholder="例如：迎新晚會")
        col1, col2 = st.columns(2)
        with col1:
            cat_in = st.selectbox("類別", list(CATEGORY_POINTS.keys()))
        with col2:
            ed = st.date_input("活動日期", value=date.today(), format="YYYY/MM/DD")

        if st.button("生成報到連結與 QR"):
            if not pub_url.strip():
                st.warning("請先貼上公開網址")
            else:
                ev = event_param(title_in, cat_in, ed.isoformat())
                url = f"{pub_url}?{urlencode({'mode':'checkin','event':ev})}"
                st.text_input("報到連結", value=url, disabled=True)
                st.image(make_qr_png(url), caption="掃描此 QR 進入報到頁")

    # 📝 現場報到
    elif page=="checkin":
        st.header("📝 現場報到")
        st.info(f"活動：**{ev_title}**｜類別：**{ev_cat}**（{CATEGORY_TIPS.get(ev_cat,'')}）｜日期：{ev_date}")
        names_raw = st.text_area("輸入姓名（可多位，用空白、逗號、頓號分隔；括號註記會忽略）")
        note = st.text_input("備註（可留空）", value="")
        if st.button("送出報到"):
            names = clean_names(names_raw)
            if not names:
                st.warning("請輸入至少一位姓名")
            elif ev_cat not in CATEGORY_POINTS:
                st.error("此 QR 未帶入正確類別")
            else:
                new_rows = []
                for n in names:
                    duplicated = not df_logs[
                        (df_logs["姓名"]==n) &
                        (df_logs["活動日期"]==ev_date) &
                        (df_logs["活動名稱"]==ev_title) &
                        (df_logs["類別"]==ev_cat)
                    ].empty
                    if duplicated:
                        st.warning(f"{n} 今天已報到過（同活動/類別）")
                    else:
                        new_rows.append({
                            "時間": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            "姓名": n,
                            "類別": ev_cat,
                            "獲得點數": CATEGORY_POINTS[ev_cat],
                            "備註": note.strip(),
                            "活動日期": ev_date,
                            "活動名稱": ev_title,
                        })
                if new_rows:
                    append_logs(csv_path, new_rows)
                    st.success(f"✅ 已報到 {len(new_rows)} 人：{ '、'.join([r['姓名'] for r in new_rows]) }")

    # 📅 依日期查看參與者
    elif page=="bydate":
        st.header("📅 依日期查看參與者")
        if df_logs.empty:
            st.info("尚無資料")
        else:
            c1, c2, c3 = st.columns(3)
            d = c1.date_input("活動日期", value=None, format="YYYY/MM/DD")
            cat = c2.selectbox("類別", ["全部"]+list(CATEGORY_POINTS.keys()))
            title = c3.text_input("活動標題關鍵字")
            df = df_logs.copy()
            if d: df = df[df["活動日期"]==d.isoformat()]
            if cat!="全部": df = df[df["類別"]==cat]
            if title.strip(): df = df[df["活動名稱"].str.contains(title.strip(), na=False)]
            st.dataframe(df.sort_values("時間", ascending=False), use_container_width=True)

    # 👤 個人明細
    elif page=="detail":
        st.header("👤 個人明細")
        query_name = st.text_input("查詢姓名")
        if query_name:
            df = df_logs.copy()
            df["_dt"] = pd.to_datetime(df["時間"], errors="coerce")
            c1,c2 = st.columns(2)
            d1 = c1.date_input("起始日期", value=None)
            d2 = c2.date_input("結束日期", value=None)
            df = df[df["姓名"]==clean_names(query_name)[0] if clean_names(query_name) else ""]
            if d1: df = df[df["_dt"]>=pd.to_datetime(d1)]
            if d2: df = df[df["_dt"]<pd.to_datetime(d2)+timedelta(days=1)]
            pts = int(df["獲得點數"].sum()) if not df.empty else 0
            st.info(f"{query_name} 累積：{pts} 點")
            st.caption(reward_text(pts, REWARDS_LIST))
            st.caption(next_hint(pts, REWARDS_LIST))
            if not df.empty:
                st.dataframe(df.drop(columns=["_dt"]).sort_values("時間", ascending=False), use_container_width=True)

    # 📒 完整記錄
    elif page=="all":
        st.header("📒 完整記錄")
        st.dataframe(df_logs.sort_values("時間", ascending=False), use_container_width=True)

    # 🏆 排行榜
    elif page=="rank":
        st.header("🏆 排行榜")
        st.dataframe(total_points(df_logs), use_container_width=True)

if __name__=="__main__":
    main()
