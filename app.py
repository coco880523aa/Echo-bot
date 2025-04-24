from flask import Flask, request, abort

from linebot.v3 import (
    WebhookHandler
)
from linebot.v3.exceptions import (
    InvalidSignatureError
)
from linebot.v3.messaging import (
    Configuration,
    ApiClient,
    MessagingApi,
    ReplyMessageRequest,
    TextMessage,
    ImageMessage  ##for 圖片
)
from linebot.v3.webhooks import (
    MessageEvent,
    TextMessageContent
)
import re
from datetime import datetime
import psycopg2## 連線postgresql的套件
import pandas as pd## 建立資料結構的套件
import os
app = Flask(__name__)

configuration = Configuration(access_token=os.getenv('CHANNEL_ACCESS_TOKEN'))#Messaging API
line_handler = WebhookHandler(os.getenv('CHANNEL_SECRET'))##line developers>basic settings>Channel secret


@app.route("/callback", methods=['POST'])
def callback():
    # get X-Line-Signature header value
    signature = request.headers['X-Line-Signature']

    # get request body as text
    body = request.get_data(as_text=True)
    app.logger.info("Request body: " + body)

    # handle webhook body
    try:
        line_handler.handle(body, signature)
    except InvalidSignatureError:
        app.logger.info("Invalid signature. Please check your channel access token/channel secret.")
        abort(400)

    return 'OK'
##event.message.text 為使用者發送的訊息
#訊息事件
@line_handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event):
    text=event.message.text
    conn, cursor = connect_postgresql()
    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)
        if text == '你好':
            line_bot_api.reply_message_with_http_info(
                ReplyMessageRequest(
                    # reply_token=event.reply_token,messages=[TextMessage(text=event.message.text)]#回應訊息給使用者的地方
                    reply_token=event.reply_token,messages=[TextMessage(text='你好')]#回應訊息給使用者的地方
                
                )
            )
        elif text == '圖片':
            url = request.url_root + 'static/Logo.jpg'
            url = url.replace("http", "https")
            app.logger.info("url=" + url)
            line_bot_api.reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[
                        ImageMessage(original_content_url=url, preview_image_url=url)
                    ]
                )
            )
        elif re.search(r"請問.*\d{4}年\d{1,2}月\d{1,2}日.*雨量", text):
            a, b = parse_query(text)
            result=get_rainfall(a, b, conn, cursor)
            safe_text = str(result) if result is not None else "找不到資料，請確認地區與日期是否正確。"
            line_bot_api.reply_message_with_http_info(
                ReplyMessageRequest(
                    # reply_token=event.reply_token,messages=[TextMessage(text=event.message.text)]#回應訊息給使用者的地方
                    reply_token=event.reply_token,messages=[TextMessage(type="text",text=safe_text)]#回應訊息給使用者的地方
                
                )
            )
            cursor.close()
            conn.close()           
        else:
            line_bot_api.reply_message_with_http_info(
                ReplyMessageRequest(
                    # reply_token=event.reply_token,messages=[TextMessage(text=event.message.text)]#回應訊息給使用者的地方
                    reply_token=event.reply_token,messages=[TextMessage(text='不知道')]#回應訊息給使用者的地方
                
                )
            )
def connect_postgresql(
    dbname="test",
    user="postgres",
    password="raaaa43016",
    host="127.0.0.1",
    port="5432"
):#####建立 PostgreSQL 資料庫連線回傳: conn, cursor#####
    try:
        conn = psycopg2.connect(
            database=dbname,
            user=user,
            password=password,
            host=host,
            port=port
        )
        cursor = conn.cursor()
        print("✅ 成功連接 PostgreSQL")
        return conn, cursor
    except Exception as e:
        print("❌ 資料庫連線失敗:", e)
        return None, None
def get_rainfall(StationName: str, Date: str, conn, cursor):
    Date = Date.strip() + "T00:00:00"
    cursor = conn.cursor()
    sql = """
        SELECT weatherElements 
        FROM rainfall_data 
        WHERE StationName = %s AND Date = %s
    """
    cursor.execute(sql, (StationName, Date))
    result = cursor.fetchone()
    if result:
        print(f"{StationName} 在 {Date} 的降雨量為 {result[0]} mm")
        return result[0]
    else:
        print(f"查無資料：{StationName} 在 {Date} 沒有對應的降雨紀錄")
        return None   
def parse_query(text):
    # 偵測地名（最簡版可直接用中文字前的兩三字）
    loc_match = re.search(r"請問(\D+?)\d{4}年", text)
    a = loc_match.group(1).strip() if loc_match else None

    # 偵測日期格式
    date_match = re.search(r"(\d{4})年(\d{1,2})月(\d{1,2})日", text)
    if date_match:
        year, month, day = map(int, date_match.groups())
        b = datetime(year, month, day).strftime("%Y-%m-%d")
    else:
        b = None

    return a, b
if __name__ == "__main__":
    app.run()