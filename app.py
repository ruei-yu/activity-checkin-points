import streamlit as st
import pandas as pd
import os
from datetime import datetime, timedelta
from io import BytesIO

APP_TITLE = "✨ 活動報到＋集點系統（含 QR 報到＆個人明細）"
LOG_CSV = "logs.csv"
USE_GOOGLE_SHEETS = False

CATEGORY_POINTS = {"志工": 1, "美食": 1, "中華文化": 2}
REWARDS = {3: "晚餐免費", 6: "手搖飲料", 10: "活動免費", 20: "志工慶功宴（崇德發）"}
REQUIRED_COLS = ["時間", "姓名", "類別", "獲得點數", "備註", "活動日期", "活動名稱"]

# ========== 資料處理 ==========
def ensure_csv():
    if not os.path.exists(LOG_CSV):
        pd.DataFrame(columns=REQUIRED_COLS).to_csv(LOG_CSV, index=False)

def read_logs_csv():
    ensure_csv()
    df = pd.read_csv(LOG_CSV)
    for col in REQUIRED_COLS:
        if col not in df.columns:
            df[col] = ""
    return df

def append_log(row):
    df = read_logs_csv()
    df.loc[len(df)] = row
    df.to_csv(LOG_CSV, index=False)

def total_points(df_logs):
    if df_logs.empty:
        return pd.DataFrame(columns=["姓名", "總點數"])
    return (
        df_logs.groupby("姓名")["獲得點數"].sum().reset_index()
        .rename(columns={"獲得點數": "總點數"})
        .sort_values("總點數", ascending=False, ignore_index=True)
    )

def reward_text(points):
    earned = [f"{k}點：{REWARDS[k]}" for k in sorted(REWARDS) if points >= k]
    return "✅ 已解鎖｜" + "、".join(earned) if earned else "尚未解鎖獎勵，繼續加油～"

def next_hint(points):
    for t in sorted(REWARDS):
        if points < t:
            return f"再 {t - points} 點可獲得「{REWARDS[t]}」"
    return "你已達最高獎勵門檻 🎉"

def build_url(base_url, params):
    from urllib.parse import urlencode
    return f"{base_url}?{urlencode(params)}"

def make_qr(url):
    import qrcode
    buf = BytesIO()
    qrcode.make(url).save(buf, format="PNG")
    buf.seek(0)
    return buf

# ========== UI ==========
def main():
    st.set_page_config(page_title="活動報到＋集點", page_icon="📝", layout="centered")
    st.title(APP_TITLE)
    st.caption("類別：志工(1)｜美食(1)｜中華文化(2)；獎勵：3/6/10/20 點")

    df_logs = read_logs_csv()

    qp = st.query_params
    mode = qp.get("mode", "")
    q_name = qp.get("name", "")
    q_category = qp.get("category", "")
    q_event_date = qp.get("edate", "")
    q_event_title = qp.get("etitle", "")

    tab_qr, tab_checkin, tab_lookup, tab_board, tab_logs = st.tabs(
        ["🔳 產生 QR", "📝 現場報到", "👤 個人明細", "🏆 排行榜", "📒 完整紀錄"]
    )

    # ========== 1) 產生 QR ==========
    with tab_qr:
        st.subheader("產生活動 QR（共用）")
        base_url = st.text_input("App 網址", placeholder="https://your-app.streamlit.app")
        col1, col2 = st.columns(2)
        with col1:
            edate = st.date_input("活動日期", value=None, format="YYYY-MM-DD")
        with col2:
            etitle = st.text_input("活動名稱", placeholder="例如：大學星攻略2")
        category = st.selectbox("活動類別", list(CATEGORY_POINTS.keys()))
        if st.button("產生活動 QR"):
            if base_url.strip():
                params = {"mode": "checkin", "category": category}
                if edate: params["edate"] = str(edate)
                if etitle: params["etitle"] = etitle
                url = build_url(base_url, params)
                st.image(make_qr(url), caption=url)
                st.code(url, language="text")
            else:
                st.warning("請輸入 App 網址")

    # ========== 2) 現場報到 ==========
    with tab_checkin:
        st.subheader("現場報到")
        st.info(f"活動：**{q_event_title or '未命名'}**｜類別：**{q_category or '未指定'}**｜日期：{q_event_date or '未填'}")
        name = st.text_input("請輸入姓名")
        if st.button("送出報到"):
            if not name.strip():
                st.warning("請輸入姓名")
            elif not q_category:
                st.error("此 QR 未帶入活動類別，請重新產生")
            else:
                row = {
                    "時間": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "姓名": name.strip(),
                    "類別": q_category,
                    "獲得點數": CATEGORY_POINTS.get(q_category, 0),
                    "備註": "",
                    "活動日期": q_event_date,
                    "活動名稱": q_event_title,
                }
                append_log(row)
                df_logs = read_logs_csv()
                st.success(f"✅ {name} 報到完成！+{row['獲得點數']} 點")

    # ========== 3) 個人明細 ==========
    with tab_lookup:
        st.subheader("個人明細")
        query_name = st.text_input("查詢姓名", value=q_name)
        if query_name.strip():
            df_logs["_時間_dt"] = pd.to_datetime(df_logs["時間"], errors="coerce")
            col1, col2 = st.columns(2)
            start_date = col1.date_input("起始日期", value=None)
            end_date = col2.date_input("結束日期", value=None)

            his = df_logs[df_logs["姓名"] == query_name].copy()
            if start_date: his = his[his["_時間_dt"] >= pd.to_datetime(start_date)]
            if end_date: his = his[his["_時間_dt"] < pd.to_datetime(end_date) + timedelta(days=1)]

            tp = int(his["獲得點數"].sum()) if not his.empty else 0
            st.info(f"👤 {query_name}：{tp} 點")
            st.caption(reward_text(tp))
            st.caption(next_hint(tp))
            if not his.empty:
                st.dataframe(his.drop(columns=["_時間_dt"]).sort_values("時間", ascending=False))

    # ========== 4) 排行榜 ==========
    with tab_board:
        st.subheader("積分排行榜")
        st.dataframe(total_points(df_logs))

    # ========== 5) 完整紀錄 ==========
    with tab_logs:
        st.subheader("完整紀錄")
        if df_logs.empty:
            st.write("尚無紀錄")
        else:
            st.dataframe(df_logs.sort_values("時間", ascending=False))

if __name__ == "__main__":
    main()
