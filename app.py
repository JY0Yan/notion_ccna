import os
from flask import Flask, request, jsonify
import requests

app = Flask(__name__)

# 從 Render 的系統環境變數讀取機密資訊
NOTION_TOKEN = os.environ.get("NOTION_TOKEN")
DATABASE_ID = os.environ.get("DATABASE_ID")

HEADERS = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Content-Type": "application/json",
    "Notion-Version": "2022-06-28"
}

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