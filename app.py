# app.py
import streamlit as st
import pandas as pd
import os, json, re
from datetime import datetime, date, timedelta
from urllib.parse import urlencode, quote, unquote
from io import BytesIO

# ============== 預設設定（可被左側設定覆蓋） ==============
DEFAULT_CONFIG = {
    "categories": [
        {"category": "志工",   "points": 1, "tips": "參與志工活動、擔任出隊籌備人員、帶朋友參與志工活動"},
        {"category": "美食",   "points": 1, "tips": "擔任廚師、協助送餐、參與／帶動美食 DIY 社課"},
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

REQUIRED_COLS = ["時間","姓名","類別","獲得點數","備註","活動日期","活動名稱"]

# ============== 設定檔 I/O ==============
def load_config(path: str) -> dict:
    if not path or not os.path.exists(path):
        return json.loads(json.dumps(DEFAULT_CONFIG, ensure_ascii=False))
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return json.loads(json.dumps(DEFAULT_CONFIG, ensure_ascii=False))
    # 補齊缺欄
    for k, v in DEFAULT_CONFIG.items():
        if k not in data: data[k] = v
    return data

def save_config(path: str, cfg: dict):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)

# ============== 資料層（CSV） ==============
def ensure_csv(csv_path: str):
    if not os.path.exists(csv_path):
        pd.DataFrame(columns=REQUIRED_COLS).to_csv(csv_path, index=False)

def load_logs(csv_path: str) -> pd.DataFrame:
    ensure_csv(csv_path)
    df = pd.read_csv(csv_path)
    for c in REQUIRED_COLS:
        if c not in df.columns: df[c] = ""
    return df

def append_rows(csv_path: str, rows: list[dict]):
    df = load_logs(csv_path)
    for r in rows:
        df.loc[len(df)] = r
    df.to_csv(csv_path, index=False)

# ============== 工具 ==============
def make_qr_png(url: str) -> BytesIO:
    import qrcode
    buf = BytesIO()
    qrcode.make(url).save(buf, format="PNG")
    buf.seek(0); return buf

def event_pack(title: str, category: str, edate: str) -> str:
    payload = {
        "title": title or "未命名活動",
        "category": category or "",
        "date": edate or date.today().isoformat()
    }
    return quote(json.dumps(payload, ensure_ascii=False))

def event_unpack(s: str):
    try:
        j = json.loads(unquote(s)) if s else {}
    except Exception:
        j = {}
    return (
        j.get("title","未命名活動"),
        j.get("category",""),
        j.get("date", date.today().isoformat())
    )

def clean_names(raw: str) -> list[str]:
    """一次輸入多位姓名：用 空白 / , / ， / 、 分隔；自動移除括號註記"""
    if not raw: return []
    s = re.sub(r"[（(].*?[）)]", "", raw)     # 去括號註記
    s = re.sub(r"[、，,]", " ", s)           # 統一分隔
    return [n.strip() for n in s.split() if n.strip()]

def total_points(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty: return pd.DataFrame(columns=["姓名","總點數"])
    return (
        df.groupby("姓名")["獲得點數"].sum()
        .reset_index().rename(columns={"獲得點數":"總點數"})
        .sort_values("總點數", ascending=False, ignore_index=True)
    )

def reward_text(points: int, rewards: list) -> str:
    got = [f"{int(r['threshold'])}點：{r['reward']}"
           for r in sorted(rewards, key=lambda x: int(x["threshold"]))
           if points >= int(r["threshold"])]
    return "✅ 已解鎖｜" + "、".join(got) if got else "尚未解鎖獎勵，繼續加油～"

def next_hint(points: int, rewards: list) -> str:
    for r in sorted(rewards, key=lambda x: int(x["threshold"])):
        t = int(r["threshold"])
        if points < t: return f"再 {t - points} 點可獲得「{r['reward']}」"
    return "你已達最高獎勵門檻 🎉"

# ============== App ==============
def main():
    st.set_page_config(page_title="活動參與集點", page_icon="🔢", layout="wide")

    # 左側設定面板（可拉開）
    st.sidebar.title("⚙️ 設定")
    cfg_path = st.sidebar.text_input("設定檔路徑", value="points_config.json")
    csv_path = st.sidebar.text_input("資料儲存 CSV 路徑", value="logs.csv")

    cfg = load_config(cfg_path)

    with st.sidebar.expander("➕ 編輯集點項目與點數", expanded=True):
        cat_df = st.data_editor(
            pd.DataFrame(cfg["categories"]),
            use_container_width=True, num_rows="dynamic",
            column_config={"category": "類別", "points": "點數", "tips": "集點方式說明"},
        )
        if st.button("💾 儲存設定（集點項目）", use_container_width=True):
            cfg["categories"] = cat_df.to_dict(orient="records")
            cfg["log_csv"] = csv_path
            save_config(cfg_path, cfg)
            st.success("已儲存！重新整理後生效")

    with st.sidebar.expander("🎁 編輯獎勵門檻", expanded=False):
        rew_df = st.data_editor(
            pd.DataFrame(cfg["rewards"]),
            use_container_width=True, num_rows="dynamic",
            column_config={"threshold": "門檻點數", "reward": "獎勵"},
        )
        if st.button("💾 儲存設定（獎勵）", use_container_width=True):
            cfg["rewards"] = rew_df.to_dict(orient="records")
            cfg["log_csv"] = csv_path
            save_config(cfg_path, cfg)
            st.success("已儲存！重新整理後生效")

    # 轉換成程式可用結構
    CATEGORY_POINTS = {r["category"]: int(r["points"]) for r in cfg["categories"] if r.get("category")}
    CATEGORY_TIPS   = {r["category"]: r.get("tips","") for r in cfg["categories"] if r.get("category")}
    REWARDS_LIST    = cfg["rewards"]

    # 載入紀錄
    df_logs = load_logs(csv_path)

    # 主頁頂部導覽（主控分頁）
    st.markdown("<h1 style='margin-bottom:4px'> 🔢活動參與集點 </h1>", unsafe_allow_html=True)
    nav = st.radio(
        "頁面導覽",
        ["📱 產生 QRcode", "📝 現場報到", "📅 依日期查看參與者", "👤 個人明細", "📒 完整記錄", "🏆 排行榜"],
        horizontal=True, label_visibility="collapsed", index=0
    )

    # URL 參數（for 現場報到）
    qp = st.query_params
    event_q = qp.get("event","")
    ev_title, ev_cat, ev_date = event_unpack(event_q)

    # --------- 📱 產生 QRcode ---------
    if nav == "📱 產生 QRcode":
        st.subheader("生成報到 QR Code")
        pub_url = st.text_input("公開網址（本頁網址）", placeholder="https://your-app.streamlit.app 或 Cloudflare URL")
        title_in = st.text_input("活動標題", placeholder="例如：迎新晚會")
        c1, c2 = st.columns(2)
        with c1:
            cat_in = st.selectbox("類別", list(CATEGORY_POINTS.keys()) or ["請先於左側新增類別"])
        with c2:
            ed = st.date_input("活動日期", value=date.today(), format="YYYY/MM/DD")

        if st.button("生成報到連結與 QR", use_container_width=True):
            if not pub_url.strip():
                st.warning("請先貼上公開網址")
            elif not CATEGORY_POINTS:
                st.error("尚未設定任何類別，請到左側新增後再試。")
            else:
                ev = event_pack(title_in, cat_in, ed.isoformat())
                url = f"{pub_url}?{urlencode({'mode':'checkin','event':ev})}"
                st.text_input("報到連結（複製給同學掃）", value=url, disabled=True)
                png = make_qr_png(url)
                st.image(png, caption="掃描此 QR 進入報到頁")
                st.download_button("下載 QR Code", data=png.getvalue(),
                                   file_name=f"checkin_{cat_in}_{ed}.png", mime="image/png")

    # --------- 📝 現場報到（一次多位） ---------
    elif nav == "📝 現場報到":
        st.subheader("現場報到")
        st.info(f"活動：**{ev_title or '未命名活動'}**｜類別：**{ev_cat or '未指定'}**（{CATEGORY_TIPS.get(ev_cat,'')}）｜日期：{ev_date or date.today().isoformat()}")
        names_raw = st.text_area("輸入姓名（可多位；用空白、逗號、頓號分隔；括號註記會忽略）", height=100)
        note = st.text_input("備註（可留空）", value="")
        if st.button("送出報到", use_container_width=True):
            names = clean_names(names_raw)
            if not names:
                st.warning("請輸入至少一位姓名")
            elif ev_cat not in CATEGORY_POINTS:
                st.error("此連結未帶入正確類別，請用『產生 QRcode』重建")
            else:
                new_rows, duplicated_list = [], []
                for n in names:
                    dup = not df_logs[
                        (df_logs["姓名"]==n) &
                        (df_logs["活動日期"]==(ev_date or date.today().isoformat())) &
                        (df_logs["活動名稱"]==(ev_title or "未命名活動")) &
                        (df_logs["類別"]==ev_cat)
                    ].empty
                    if dup:
                        duplicated_list.append(n)
                    else:
                        new_rows.append({
                            "時間": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            "姓名": n,
                            "類別": ev_cat,
                            "獲得點數": CATEGORY_POINTS[ev_cat],
                            "備註": note.strip(),
                            "活動日期": ev_date or date.today().isoformat(),
                            "活動名稱": ev_title or "未命名活動",
                        })
                if new_rows:
                    append_rows(csv_path, new_rows)
                    st.success(f"✅ 已報到 {len(new_rows)} 人：{ '、'.join([r['姓名'] for r in new_rows]) }")
                if duplicated_list:
                    st.warning(f"已報到過：{ '、'.join(duplicated_list) }（同活動/日期/類別）")

    # --------- 📅 依日期查看參與者 ---------
    elif nav == "📅 依日期查看參與者":
        st.subheader("依日期查看參與者")
        df = df_logs.copy()
        c1, c2, c3 = st.columns(3)
        d = c1.date_input("活動日期", value=None, format="YYYY/MM/DD")
        cat = c2.selectbox("類別", ["全部"] + list(CATEGORY_POINTS.keys()))
        kw  = c3.text_input("活動標題關鍵字", placeholder="可留空")
        if d: df = df[df["活動日期"] == d.isoformat()]
        if cat != "全部": df = df[df["類別"] == cat]
        if kw.strip(): df = df[df["活動名稱"].str.contains(kw.strip(), na=False)]
        st.dataframe(df.sort_values("時間", ascending=False), use_container_width=True)

    # --------- 👤 個人明細 ---------
    elif nav == "👤 個人明細":
        st.subheader("個人明細")
        qn = st.text_input("查詢姓名")
        if qn:
            who = clean_names(qn)[0] if clean_names(qn) else ""
            df = df_logs[df_logs["姓名"]==who].copy()
            df["_dt"] = pd.to_datetime(df["時間"], errors="coerce")
            c1, c2 = st.columns(2)
            d1 = c1.date_input("起始日期", value=None)
            d2 = c2.date_input("結束日期（含當天）", value=None)
            if d1: df = df[df["_dt"] >= pd.to_datetime(d1)]
            if d2: df = df[df["_dt"] < pd.to_datetime(d2) + timedelta(days=1)]
            pts = int(df["獲得點數"].sum()) if not df.empty else 0
            st.info(f"👤 {who} 累積：**{pts}** 點")
            st.caption(reward_text(pts, REWARDS_LIST))
            st.caption(next_hint(pts, REWARDS_LIST))
            if not df.empty:
                st.dataframe(df.drop(columns=["_dt"]).sort_values("時間", ascending=False), use_container_width=True)

    # --------- 📒 完整記錄 ---------
    elif nav == "📒 完整記錄":
        st.subheader("完整記錄")
        st.dataframe(df_logs.sort_values("時間", ascending=False), use_container_width=True)
        st.download_button("下載 CSV", data=df_logs.to_csv(index=False).encode("utf-8-sig"),
                           file_name=os.path.basename(csv_path), mime="text/csv")

    # --------- 🏆 排行榜 ---------
    elif nav == "🏆 排行榜":
        st.subheader("排行榜")
        st.dataframe(total_points(df_logs), use_container_width=True)

if __name__ == "__main__":
    main()
