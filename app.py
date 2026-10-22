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
            <input type="text" id="word" placeholder="輸入單字">
            <input type="text" id="trans" placeholder="中文 (新單字必填)">
            <button onclick="sendWord()">搜尋 / 新增</button>
            <span id="msg"></span>
        </div>
        <script>
            function sendWord() {
                const wordInput = document.getElementById('word');
                const transInput = document.getElementById('trans');
                const word = wordInput.value.trim();
                const trans = transInput.value.trim();
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
                    if (data.error) {
                        msgSpan.style.color = "#f87171"; // 顯示紅色錯誤提示
                        msgSpan.innerText = data.error;
                        // 如果是新單字未填中文，自動將打字游標聚焦到「中文」欄位，且不清空單字
                        if (data.need_translation) {
                            transInput.focus();
                        }
                    } else {
                        msgSpan.style.color = "#4ade80"; // 顯示綠色成功訊息
                        msgSpan.innerText = data.message;
                        wordInput.value = '';
                        transInput.value = '';
                        setTimeout(() => msgSpan.innerText = '', 4000);
                    }
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

@app.route('/upsert_word', methods=['POST'])
def upsert_word():
    data = request.json
    word = data.get('word', '').strip()
    translation = data.get('translation', '').strip()

    if not word:
        return jsonify({"error": "單字不能為空"}), 400

    search_url = f"https://api.notion.com/v1/databases/{DATABASE_ID}/query"
    search_payload = {"filter": {"property": "單字", "title": {"equals": word}}}
    
    # 1. 搜尋單字是否存在
    search_res = requests.post(search_url, json=search_payload, headers=HEADERS)
    if search_res.status_code != 200:
        return jsonify({"error": f"搜尋失敗: {search_res.json().get('message', '未知錯誤')}"}), 400
        
    results = search_res.json().get('results', [])

    if results:
        # 2. 單字已存在：直接將查詢次數 +1（不需要填寫中文解釋）
        page_id = results[0]['id']
        current_count = results[0]['properties']['查詢次數']['number']
        if current_count is None:
            current_count = 0
            
        update_url = f"https://api.notion.com/v1/pages/{page_id}"
        update_payload = {"properties": {"查詢次數": {"number": current_count + 1}}}
        
        update_res = requests.patch(update_url, json=update_payload, headers=HEADERS)
        if update_res.status_code != 200:
            return jsonify({"error": f"更新失敗: {update_res.json().get('message', '未知錯誤')}"}), 400
            
        return jsonify({"status": "updated", "message": f"「{word}」已存在，次數已更新為 {current_count + 1}"})

    else:
        # 3. 單字不存在（新單字）：強制檢查是否有填寫中文解釋
        if not translation:
            return jsonify({
                "error": f"「{word}」是新單字，請輸入中文解釋後再新增！",
                "need_translation": True
            }), 400

        # 通過檢查後才寫入 Notion
        create_url = "https://api.notion.com/v1/pages"
        create_payload = {
            "parent": {"database_id": DATABASE_ID},
            "properties": {
                "單字": {"title": [{"text": {"content": word}}]},
                "中文解釋": {"rich_text": [{"text": {"content": translation}}]},
                "查詢次數": {"number": 1}
            }
        }
        create_res = requests.post(create_url, json=create_payload, headers=HEADERS)
        if create_res.status_code != 200:
            return jsonify({"error": f"新增失敗: {create_res.json().get('message', '未知錯誤')}"}), 400
            
        return jsonify({"status": "created", "message": f"已新增單字「{word}」！"})
