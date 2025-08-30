# ✨ 活動報到＋集點系統

這是一個使用 [Streamlit](https://streamlit.io) 開發的簡易活動報到與集點系統。

## 功能
- 📱 報到 QR 產生：主辦方產生活動 QR，參加者掃描後即可報到
- 📝 線上報到：輸入姓名後系統自動登記積分
- ✅ 防重複：同一天、同活動、同類別、同姓名僅能報到一次
- 👤 個人明細：查詢個人積分與紀錄，支援日期篩選
- 🏆 排行榜：即時排名
- 📒 完整紀錄：所有報到紀錄，可下載 CSV

## 安裝與啟動
```bash
git clone https://github.com/<你的帳號>/checkin-app.git
cd checkin-app
pip install -r requirements.txt
streamlit run app.py
