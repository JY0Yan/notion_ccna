import os
from flask import Flask, request, jsonify
import requests

app = Flask(__name__)

NOTION_TOKEN = os.environ.get("NOTION_TOKEN")
DATABASE_ID = os.environ.get("DATABASE_ID")

HEADERS = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Content-Type": "application/json",
    "Notion-Version": "2022-06-28"
}

# 前端網頁介面
@app.route('/', methods=['GET'])
def home():
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <title>CCNA Word Bot</title>
        <style>
            body { font-family: sans-serif; display: flex; justify-content: center; align-items: center; margin: 0; padding: 10px; background-color: #191919; color: #fff; }
            input, button { padding: 8px; margin: 4px; border-radius: 4px; border: 1px solid #444; background: #333; color: white; }
            button { background-color: #2eaadc; cursor: pointer; border: none; font-weight: bold; }
            button:hover { background-color: #1b85b8; }
            #msg { font-size: 14px; margin-left: 10px; color: #4ade80; }
            .container { display: flex; align-items: center; flex-wrap: wrap; }
        </style>
    </head>
    <body>
        <div class="container">
            <input type="text" id="word" placeholder="輸入單字 (如 OSPF)">
            <input type="text" id="trans" placeholder="中文解釋 (新單字填)">
            <button onclick="sendWord()">新增 / +1</button>
            <span id="msg"></span>
        </div>
        <script>
            function sendWord() {
                const word = document.getElementById('word').value.trim();
                const trans = document.getElementById('trans').value.trim();
                const msgSpan = document.getElementById('msg');
                if(!word) return;
                
                msgSpan.style.color = "#fbbf24";
                msgSpan.innerText = "處理中...";
                fetch('/upsert_word', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ word: word, translation: trans })
                })
                .then(r => r.json())
                .then(data => {
                    msgSpan.style.color = "#4ade80";
                    msgSpan.innerText = data.message || data.error;
                    document.getElementById('word').value = '';
                    document.getElementById('trans').value = '';
                    setTimeout(() => msgSpan.innerText = '', 4000); // 4秒後清除提示
                })
                .catch(err => { 
                    msgSpan.style.color = "#f87171";
                    msgSpan.innerText = "發生錯誤，請檢查伺服器狀態"; 
                });
            }
        </script>
    </body>
    </html>
    """

# 資料庫處理邏輯
@app.route('/upsert_word', methods=['POST'])
def upsert_word():
    data = request.json
    word = data.get('word')
    translation = data.get('translation', '')

    if not word:
        return jsonify({"error": "單字不能為空"}), 400

    search_url = f"https://api.notion.com/v1/databases/{DATABASE_ID}/query"
    search_payload = {
        "filter": {"property": "單字", "title": {"equals": word}}
    }
    
    response = requests.post(search_url, json=search_payload, headers=HEADERS)
    results = response.json().get('results', [])

    if results:
        page_id = results[0]['id']
        current_count = results[0]['properties']['查詢次數']['number']
        if current_count is None:
            current_count = 0
            
        update_url = f"https://api.notion.com/v1/pages/{page_id}"
        update_payload = {"properties": {"查詢次數": {"number": current_count + 1}}}
        requests.patch(update_url, json=update_payload, headers=HEADERS)
        return jsonify({"status": "updated", "message": f"「{word}」已存在，次數已更新為 {current_count + 1}"})

    else:
        create_url = "https://api.notion.com/v1/pages"
        create_payload = {
            "parent": {"database_id": DATABASE_ID},
            "properties": {
                "單字": {"title": [{"text": {"content": word}}]},
                "中文解釋": {"rich_text": [{"text": {"content": translation}}]},
                "查詢次數": {"number": 1}
            }
        }
        requests.post(create_url, json=create_payload, headers=HEADERS)
        return jsonify({"status": "created", "message": f"已新增單字「{word}」！"})
