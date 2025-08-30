import streamlit as st
import pandas as pd
import os
from datetime import datetime
from io import BytesIO

# =========================
# 基本設定
# =========================
APP_TITLE = "✨ 活動報到＋集點系統（含 QR 報到＆個人明細）"
LOG_CSV = "logs.csv"   # CSV 檔名（若用 Sheets，仍保留不影響）
USE_GOOGLE_SHEETS = False  # 要改成 True 時，請先完成 Secrets 設定（文末說明）

CATEGORY_POINTS = {
    "志工": 1,
    "美食": 1,
    "中華文化": 2,
}

REWARDS = {
    3: "晚餐免費",
    6: "手搖飲料",
    10: "活動免費",
    20: "志工慶功宴（崇德發）",
}

# =========================
# Google Sheets（選用）
# =========================
def get_gsheet_df():
    import gspread
    from google.oauth2.service_account import Credentials

    gcp_info = st.secrets["gcp_service_account"]  # 整份 service account JSON
    sheet_url = st.secrets["SHEET_URL"]           # 你的 Google Sheet 連結

    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]
    credentials = Credentials.from_service_account_info(gcp_info, scopes=scopes)
    gc = gspread.authorize(credentials)
    sh = gc.open_by_url(sheet_url)

    # 確保有 "logs" 工作表
    try:
        ws = sh.worksheet("logs")
    except Exception:
        ws = sh.add_worksheet(title="logs", rows=1000, cols=6)
        ws.append_row(["時間", "姓名", "類別", "獲得點數", "備註"])

    rows = ws.get_all_records()
    df = pd.DataFrame(rows)
    if df.empty:
        df = pd.DataFrame(columns=["時間", "姓名", "類別", "獲得點數", "備註"])
    return sh, ws, df

def append_gsheet_row(ws, row_dict):
    ws.append_row([row_dict.get(k, "") for k in ["時間","姓名","類別","獲得點數","備註"]])

# =========================
# CSV 資料層
# =========================
def ensure_csv():
    if not os.path.exists(LOG_CSV):
        pd.DataFrame(columns=["時間", "姓名", "類別", "獲得點數", "備註"]).to_csv(LOG_CSV, index=False)

def read_logs_csv():
    ensure_csv()
    return pd.read_csv(LOG_CSV)

def append_log_csv(log_row):
    df = read_logs_csv()
    df.loc[len(df)] = log_row
    df.to_csv(LOG_CSV, index=False)

# =========================
# 共用邏輯
# =========================
def total_points_by_name(df_logs):
    if df_logs.empty:
        return pd.DataFrame(columns=["姓名", "總點數"])
    g = df_logs.groupby("姓名")["獲得點數"].sum().reset_index()
    g = g.rename(columns={"獲得點數":"總點數"}).sort_values("總點數", ascending=False, ignore_index=True)
    return g

def next_reward_hint(points: int) -> str:
    for t in sorted(REWARDS):
        if points < t:
            return f"再 {t - points} 點可獲得「{REWARDS[t]}」"
    return "你已達最高獎勵門檻，太強了！🎉"

def reward_text(points: int) -> str:
    earned = [f"{k}點：{REWARDS[k]}" for k in sorted(REWARDS) if points >= k]
    return ("✅ 已解鎖｜" + "、".join(earned)) if earned else "尚未解鎖獎勵，繼續加油～"

def build_url(base_url: str, params: dict) -> str:
    from urllib.parse import urlencode
    return f"{base_url}?{urlencode(params)}"

def make_qr_image(url: str):
    import qrcode
    img = qrcode.make(url)
    buf = BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf

def get_storage_and_logs():
    if USE_GOOGLE_SHEETS:
        sh, ws, df_logs = get_gsheet_df()
        return "Google Sheets", df_logs, (sh, ws)
    else:
        df_logs = read_logs_csv()
        return "CSV 檔案", df_logs, None

def write_log(row, gsheet_context=None):
    if USE_GOOGLE_SHEETS and gsheet_context is not None:
        _, ws = gsheet_context
        append_gsheet_row(ws, row)
    else:
        append_log_csv(row)

# =========================
# UI 主程式
# =========================
def main():
    st.set_page_config(page_title="活動報到＋集點", page_icon="📝", layout="centered")
    st.title(APP_TITLE)
    st.caption("類別：志工(1)｜美食(1)｜中華文化(2)；獎勵：3/6/10/20 點")

    storage_type, df_logs, gctx = get_storage_and_logs()

    # 讀取 URL 參數（新版 API）
    qp = st.query_params
    mode = qp.get("mode", "")          # "checkin" / "detail" / ""
    q_name = qp.get("name", "")
    q_category = qp.get("category", "")  # "志工" / "美食" / "中華文化"
    q_note = qp.get("note", "")
    q_lock = qp.get("lock", "")        # "1" 表示鎖定（不可更改姓名/類別）
    q_go_detail_after = qp.get("go_detail", "")  # "1"：報到後顯示個人明細

    tab_qr, tab_checkin, tab_lookup, tab_board, tab_logs = st.tabs(
        ["🔳 產生 QR", "📝 現場報到", "👤 個人明細", "🏆 排行榜", "📒 完整紀錄"]
    )

    # ========== 1) 產生 QR ==========
    with tab_qr:
        st.subheader("產生活動用 / 個人用 QR")
        st.markdown("先填入你的 App 網址（如：`https://你的子網域.streamlit.app`）")

        base_url = st.text_input("App 網址", placeholder="https://your-app.streamlit.app")

        colA, colB = st.columns(2)
        with colA:
            st.markdown("#### A. 通用活動 QR（固定類別）")
            category_a = st.selectbox("選擇類別（固定在 QR 中）", list(CATEGORY_POINTS.keys()), key="qr_cat_a")
            go_detail_a = st.checkbox("報到後自動顯示個人明細", value=True, key="qr_detail_a")
            if st.button("產生通用活動 QR"):
                if not base_url.strip():
                    st.warning("請先輸入 App 網址")
                else:
                    params = {"mode": "checkin", "category": category_a}
                    if go_detail_a:
                        params["go_detail"] = "1"
                    url = build_url(base_url.strip(), params)
                    buf = make_qr_image(url)
                    st.image(buf, caption=url, use_container_width=False)
                    st.code(url, language="text")

        with colB:
            st.markdown("#### B. 個人快速 QR（鎖定姓名＋類別）")
            name_b = st.text_input("姓名（將寫死在 QR 中）", key="qr_name_b")
            category_b = st.selectbox("選擇類別（固定在 QR 中）", list(CATEGORY_POINTS.keys()), key="qr_cat_b")
            go_detail_b = st.checkbox("報到後自動顯示個人明細", value=True, key="qr_detail_b")
            if st.button("產生個人快速 QR（鎖定輸入）"):
                if not base_url.strip():
                    st.warning("請先輸入 App 網址")
                elif not name_b.strip():
                    st.warning("請輸入姓名")
                else:
                    params = {
                        "mode": "checkin",
                        "name": name_b.strip(),
                        "category": category_b,
                        "lock": "1"   # 鎖定姓名/類別不可改
                    }
                    if go_detail_b:
                        params["go_detail"] = "1"
                    url = build_url(base_url.strip(), params)
                    buf = make_qr_image(url)
                    st.image(buf, caption=url, use_container_width=False)
                    st.code(url, language="text")

        st.divider()
        st.markdown("#### C. 個人明細 QR")
        name_c = st.text_input("姓名（掃描直接查看個人累積明細）", key="qr_name_c")
        if st.button("產生個人明細 QR"):
            if not base_url.strip():
                st.warning("請先輸入 App 網址")
            elif not name_c.strip():
                st.warning("請輸入姓名")
            else:
                url = build_url(base_url.strip(), {"mode": "detail", "name": name_c.strip()})
                buf = make_qr_image(url)
                st.image(buf, caption=url, use_container_width=False)
                st.code(url, language="text")

    # ========== 2) 現場報到（支援 URL 參數帶入） ==========
    with tab_checkin:
        st.subheader("現場報到")
        # 若有 lock=1，則將欄位 disable
        lock_inputs = (q_lock == "1")

        with st.form("checkin"):
            name = st.text_input("姓名", value=q_name, placeholder="請輸入姓名", disabled=lock_inputs)
            category = st.selectbox("活動類別", list(CATEGORY_POINTS.keys()),
                                    index=(list(CATEGORY_POINTS.keys()).index(q_category) if q_category in CATEGORY_POINTS else 0),
                                    disabled=lock_inputs)
            note = st.text_input("備註（可留空）", value=q_note, placeholder="例：帶朋友參與志工活動")
            submitted = st.form_submit_button("報到並加點")

        if submitted:
            if not name.strip():
                st.warning("請輸入姓名")
            else:
                pts = CATEGORY_POINTS[category]
                now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                row = {
                    "時間": now_str,
                    "姓名": name.strip(),
                    "類別": category,
                    "獲得點數": pts,
                    "備註": note.strip(),
                }
                try:
                    write_log(row, gsheet_context=gctx)
                    # 重新讀資料
                    _, df_logs, _ = get_storage_and_logs()
                    st.success(f"✅ {name} 報到完成！本次「{category}」+{pts} 點")

                    # 即時顯示個人累積與明細
                    df_total = total_points_by_name(df_logs)
                    tp = int(df_total.loc[df_total["姓名"] == name.strip(), "總點數"].sum())
                    st.info(f"👤 {name} 累積點數：**{tp}**")
                    st.caption(reward_text(tp))
                    st.caption(next_reward_hint(tp))

                    his = df_logs[df_logs["姓名"] == name.strip()].copy()
                    if not his.empty:
                        st.write("個人紀錄（新→舊）：")
                        st.dataframe(his.sort_values("時間", ascending=False), use_container_width=True)

                    # 若 URL 有 go_detail=1，直接切到個人明細頁籤
                    if q_go_detail_after == "1":
                        st.switch_page("")  # 保持同頁，僅用提示
                        st.info("下方『個人明細』分頁可查看完整紀錄。也可用 C 欄的 QR 直達。")
                except Exception as e:
                    st.error(f"寫入失敗：{e}")

    # ========== 3) 個人明細（支援 URL 直達 + 日期篩選） ==========
    with tab_lookup:
        st.subheader("個人明細")
        df_total = total_points_by_name(df_logs)

        # 若 URL 有 name，就用它當預設
        qn_default = q_name if q_name else ""
        query_name = st.text_input("查詢姓名", value=qn_default, placeholder="輸入姓名查看累積點數")

        if query_name.strip():
            # 日期篩選區
            st.markdown("### 📅 日期篩選")
            col1, col2 = st.columns(2)
            with col1:
                start_date = st.date_input("起始日期", value=None)
            with col2:
                end_date = st.date_input("結束日期", value=None)

            # 個人紀錄
            his = df_logs[df_logs["姓名"] == query_name.strip()].copy()

            # 如果有選日期，篩選範圍
            if start_date:
                his = his[his["時間"] >= str(start_date)]
            if end_date:
                his = his[his["時間"] <= str(end_date)]

            tp = int(his["獲得點數"].sum()) if not his.empty else 0
            st.info(f"👤 {query_name} 篩選後累積點數：**{tp}**")
            st.caption(reward_text(tp))
            st.caption(next_reward_hint(tp))

            if not his.empty:
                st.write("個人紀錄（新→舊）：")
                st.dataframe(his.sort_values("時間", ascending=False), use_container_width=True)
            else:
                st.write("該日期區間沒有紀錄")

    # ========== 4) 排行榜 ==========
    with tab_board:
        st.subheader("積分排行榜")
        df_total = total_points_by_name(df_logs)
        st.dataframe(df_total, use_container_width=True)

    # ========== 5) 完整紀錄 ==========
    with tab_logs:
        st.subheader("完整紀錄")
        if df_logs.empty:
            st.write("尚無紀錄")
        else:
            st.dataframe(df_logs.sort_values("時間", ascending=False), use_container_width=True)

    # 若 URL 直接指定 mode=checkin 或 mode=detail，主動提示對應分頁
    if mode == "checkin":
        st.toast("已啟用『現場報到』模式（參數帶入中）")
    elif mode == "detail" and q_name:
        st.toast(f"已啟用『個人明細』模式：{q_name}")

if __name__ == "__main__":
    main()
