import streamlit as st
import pandas as pd
import os, json, re
from datetime import datetime, date, timedelta
from urllib.parse import urlencode, quote, unquote
from io import BytesIO

# =========================
# 基本設定（依你的圖片）
# =========================
APP_TITLE = "✨ 活動報到＋集點系統"
LOG_CSV = "logs.csv"

CATEGORY_POINTS = {
    "志工": 1,
    "美食": 1,
    "中華文化": 2,
}
CATEGORY_TIPS = {
    "志工": "參與志工活動、擔任出隊籌備人員、帶朋友參與志工活動",
    "美食": "擔任廚師、協助送餐、參與／帶動美食 DIY 社課",
    "中華文化": "獻供、辦道、參與心靈成長營、讀書會",
}
REWARDS = {
    3: "晚餐免費",
    6: "手搖飲料",
    10: "活動免費",
    20: "志工慶功宴（崇德發）",
}
REQUIRED_COLS = ["時間","姓名","類別","獲得點數","備註","活動日期","活動名稱"]

# =========================
# 資料層（CSV）
# =========================
def ensure_csv():
    if not os.path.exists(LOG_CSV):
        pd.DataFrame(columns=REQUIRED_COLS).to_csv(LOG_CSV, index=False)

def load_logs():
    ensure_csv()
    df = pd.read_csv(LOG_CSV)
    for c in REQUIRED_COLS:
        if c not in df.columns: df[c] = ""
    return df

def append_log(row: dict):
    df = load_logs()
    df.loc[len(df)] = row
    df.to_csv(LOG_CSV, index=False)

# =========================
# 小工具
# =========================
def make_qr_png(url: str) -> BytesIO:
    import qrcode
    buf = BytesIO()
    qrcode.make(url).save(buf, format="PNG")
    buf.seek(0)
    return buf

def event_param(title: str, category: str, edate: str) -> str:
    payload = {"title": title or "未命名活動",
               "category": category or "志工",
               "date": edate or date.today().isoformat()}
    return quote(json.dumps(payload, ensure_ascii=False))

def parse_event_param(s: str):
    try:
        j = json.loads(unquote(s)) if s else {}
    except Exception:
        j = {}
    return (
        j.get("title","未命名活動"),
        j.get("category","志工"),
        j.get("date", date.today().isoformat())
    )

def clean_name(raw: str) -> str:
    if not raw: return ""
    s = re.sub(r"[（(].*?[）)]", "", raw)        # 移除括號註記
    s = re.sub(r"[、，,]", " ", s).strip()
    return re.sub(r"\s+", " ", s)

def total_points(df):
    if df.empty: return pd.DataFrame(columns=["姓名","總點數"])
    return (df.groupby("姓名")["獲得點數"].sum()
            .reset_index().rename(columns={"獲得點數":"總點數"})
            .sort_values("總點數", ascending=False, ignore_index=True))

def reward_text(points: int) -> str:
    got = [f"{k}點：{REWARDS[k]}" for k in sorted(REWARDS) if points >= k]
    return "✅ 已解鎖｜" + "、".join(got) if got else "尚未解鎖獎勵，繼續加油～"

def next_hint(points: int) -> str:
    for t in sorted(REWARDS):
        if points < t: return f"再 {t - points} 點可獲得「{REWARDS[t]}」"
    return "你已達最高獎勵門檻 🎉"

# =========================
# App
# =========================
def main():
    st.set_page_config(page_title="活動報到＋集點", page_icon="📝", layout="centered")
    st.title(APP_TITLE)
    st.caption("類別：志工(1)｜美食(1)｜中華文化(2)；獎勵：3/6/10/20 點")

    df_logs = load_logs()

    # 讀 URL 參數：?mode=checkin&event=<json>
    qp = st.query_params
    mode = qp.get("mode","")
    event_q = qp.get("event","")
    ev_title, ev_category, ev_date = parse_event_param(event_q)

    tab_admin, tab_qr = st.tabs(["📥 管理與統計", "📱 產生報到 QR"])

    # ---------- 📥 管理與統計 ----------
    with tab_admin:
        st.subheader("線上報到")
        st.info(f"活動：**{ev_title}**｜類別：**{ev_category}**（{CATEGORY_TIPS.get(ev_category,'')}）｜日期：{ev_date}")

        name = st.text_input("請輸入姓名（括號註記會自動忽略）", placeholder="例：王小明(帶朋友)")
        note = st.text_input("備註（可留空）", value="")
        if st.button("送出報到"):
            n = clean_name(name)
            if not n:
                st.warning("請先輸入姓名")
            elif ev_category not in CATEGORY_POINTS:
                st.error("此連結缺少或帶入了錯誤的活動類別，請重新產生 QR")
            else:
                # 一人一次：同（活動日期＋活動名稱＋類別＋姓名）不可重複
                duplicated = not df_logs[
                    (df_logs["姓名"]==n) &
                    (df_logs["活動日期"]==ev_date) &
                    (df_logs["活動名稱"]==ev_title) &
                    (df_logs["類別"]==ev_category)
                ].empty
                if duplicated:
                    st.warning("今天此活動此類別已報到過囉！")
                else:
                    row = {
                        "時間": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "姓名": n,
                        "類別": ev_category,
                        "獲得點數": CATEGORY_POINTS[ev_category],
                        "備註": note.strip(),
                        "活動日期": ev_date,
                        "活動名稱": ev_title,
                    }
                    append_log(row)
                    df_logs = load_logs()
                    st.success(f"✅ {n} 報到成功！本次 +{row['獲得點數']} 點")

        st.divider()
        st.markdown("### 📌 類別與集點方式")
        for k in ["志工","美食","中華文化"]:
            st.markdown(f"- **{k}（{CATEGORY_POINTS[k]}點）**：{CATEGORY_TIPS[k]}")

        st.divider()
        st.markdown("### 👤 個人查詢（含日期篩選）")
        qname = st.text_input("查詢姓名")
        if qname:
            who = clean_name(qname)
            his = df_logs[df_logs["姓名"]==who].copy()
            his["_時間_dt"] = pd.to_datetime(his["時間"], errors="coerce")
            c1, c2 = st.columns(2)
            d1 = c1.date_input("起始日期", value=None)
            d2 = c2.date_input("結束日期（含當天）", value=None)
            if d1: his = his[his["_時間_dt"] >= pd.to_datetime(d1)]
            if d2: his = his[his["_時間_dt"] < pd.to_datetime(d2) + timedelta(days=1)]
            pts = int(his["獲得點數"].sum()) if not his.empty else 0
            st.info(f"👤 {who} 累積：**{pts}** 點")
            st.caption(reward_text(pts))
            st.caption(next_hint(pts))
            if not his.empty:
                st.dataframe(his.drop(columns=["_時間_dt"]).sort_values("時間", ascending=False), use_container_width=True)

        st.markdown("### 🏆 排行榜")
        st.dataframe(total_points(df_logs), use_container_width=True)

        st.markdown("### 📒 全部紀錄")
        st.dataframe(df_logs.sort_values("時間", ascending=False), use_container_width=True)

        st.download_button("下載 CSV", data=df_logs.to_csv(index=False).encode("utf-8-sig"),
                           file_name="logs.csv", mime="text/csv")

    # ---------- 📱 產生報到 QR ----------
    with tab_qr:
        st.subheader("產生報到 QR（通用一張，掃了自己填姓名）")
        pub_url = st.text_input("公開網址（Cloudflare / Streamlit）", placeholder="https://xxxx.trycloudflare.com")
        c1, c2 = st.columns(2)
        with c1:
            title_in = st.text_input("活動標題", placeholder="例如：迎新晚會")
        with c2:
            cat_in = st.selectbox("活動類別", list(CATEGORY_POINTS.keys()))
        ed = st.date_input("活動日期（預設今天）", value=date.today(), format="YYYY-MM-DD")

        if st.button("生成報到連結與 QR"):
            if not pub_url.strip():
                st.warning("請先貼上公開網址")
            else:
                ev = event_param(title_in, cat_in, ed.isoformat())
                url = f"{pub_url}?{urlencode({'mode':'checkin','event':ev})}"
                st.text_input("報到連結", value=url, label_visibility="visible", disabled=True)
                png = make_qr_png(url)
                st.image(png, caption="掃描此 QR 進入報到頁")
                st.download_button("下載 QR Code", data=png.getvalue(),
                                   file_name=f"checkin_{cat_in}_{ed}.png", mime="image/png")

    if mode == "checkin":
        st.toast("已進入報到頁，請填姓名送出。")

if __name__ == "__main__":
    main()
