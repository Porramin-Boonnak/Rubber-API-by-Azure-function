import logging
import uuid
import azure.functions as func
from flask import request, Flask, jsonify
from pymongo.mongo_client import MongoClient
import requests
from linebot import *
from datetime import datetime
uri = "mongodb+srv://rubber:1212312121@cluster0.kjvosuu.mongodb.net/"

# Create a new client and connect to the server
client = MongoClient(uri)

app = Flask(__name__)

db = client["Rubber"]
rubber = db["rubber_info"]
machine = db["machine"]
channel_access_token = 'J/TmOWwvFNUvEvSuPNP/qY4Xz2Ngdxw/PkEwVWAPJLzkk4rLHq5f1HFTGu081ZgrN+vhkTH5p3ThcaCRzi5ZmAMuPxMa6vUsurte0DWZfQgwPVHqSqpuKV60I6nvWTcRMMFC4Wow7xgfb2wCIpBD9AdB04t89/1O/w1cDnyilFU='
handler = '23da23a72acf7a5c52ca47f913092df8'

days_in_thai = {
        "Monday": "วันจันทร์",
        "Tuesday": "วันอังคาร",
        "Wednesday": "วันพุธ",
        "Thursday": "วันพฤหัสบดี",
        "Friday": "วันศุกร์",
        "Saturday": "วันเสาร์",
        "Sunday": "วันอาทิตย์"
    }

# สร้าง dictionary สำหรับแปลงชื่อเดือนเป็นภาษาไทย
months_in_thai = [
    "มกราคม", "กุมภาพันธ์", "มีนาคม", "เมษายน", "พฤษภาคม", "มิถุนายน",
    "กรกฎาคม", "สิงหาคม", "กันยายน", "ตุลาคม", "พฤศจิกายน", "ธันวาคม"
]

def main(req: func.HttpRequest, context: func.Context) -> func.HttpResponse:
    """Each request is redirected to the WSGI handler.
    """
    return func.WsgiMiddleware(app.wsgi_app).handle(req, context)

@app.route("/rubber/insert", methods=["POST"])
def insert_rubber():
    data = request.get_json()
    machineID=data["machineID"]
    find = machine.find_one({"_id": str(machineID)})
    if find:
        date_object = datetime.strptime(data["Date"], "%Y-%m-%dT%H:%M:%SZ")
        day_of_week = date_object.strftime("%A")  # ชื่อวันภาษาอังกฤษ
        day_of_month = date_object.day  # วันที่ (ไม่รวมเดือนและปี)
        month = date_object.month  # เดือน (1-12)
        year = date_object.year  # ปี
        hour = date_object.strftime("%H")  # ชั่วโมง (24 ชั่วโมง)
        minute = date_object.strftime("%M")  # นาที
        second = date_object.strftime("%S")  # วินาที
        # แปลงเป็นชื่อวันและเดือนภาษาไทย
        day_in_thai = days_in_thai.get(day_of_week, "Unknown day")
        month_in_thai = months_in_thai[month - 1]  # เนื่องจากเดือนเริ่มจาก 0 ใน list

        # เปลี่ยนปีให้เป็น พ.ศ.
        buddhist_year = year + 543
        retry_key = str(uuid.uuid4())
        userId=find["own"]
        replyuser(userId, f"{day_in_thai}ที่ {day_of_month} {month_in_thai} {buddhist_year}\nเวลา {hour}:{minute}:{second}\nค่า PH = {data['ph']}\nปริมาณยางในถัง = {data['volumnall']} ml\nเหลือแอมโมเนีย = {data['amm']} ml", retry_key)
        rubber.insert_one(data)
    return jsonify("update complate")

@app.route("/callback", methods=['POST'])
def callback():
    try:
        req = request.get_json(silent=True, force=True)
        text = req["events"][0]["message"]["text"].split()
        userId = req["events"][0]["source"]["userId"]
        reply_token = req['events'][0]['replyToken']
        if text[0] == "Data":
            find = machine.find_one({"own": str(userId)})
            if find:
                data = list(rubber.find({"machineID": str(find["_id"])}))
                for doc in data:
                    if "_id" in doc:
                        doc["_id"] = str(doc["_id"])
                reply(reply_token,str(data))
            else:
                reply(reply_token,"ไม่พบเครื่องที่ลงทะเบียน")
        elif text[0] == "Register":
            reply(reply_token,f"กรุณาพิมพ์ข้อความตามตัวอย่างนี้\nRegisterID xxxxxxx")
        elif text[0] == "RegisterID":
            data = machine.find_one({"_id": str(text[1]), "own": {"$exists": False}})
            if data:
                machine.update_one(
                    { "_id" : str(text[1]) },
                    { "$set": { "own" : userId } }
                )
                reply(reply_token,"ลงทะเบียนเรียบร้อย")
            else:
                reply(reply_token,"ไม่พบเครื่อง หรือ เครื่องนี้ลงทะเบียนไปแล้ว")
        elif text[0] == "Unregister":
            reply(reply_token,"กรุณาพิมพ์ข้อความตามตัวอย่างนี้\nUnregisterID xxxxxxx")
        elif text[0] == "UnregisterID":
            data = machine.find_one({"_id": str(text[1]),"own":str(userId)})
            if data:
                machine.update_one(
                    { "_id" : str(text[1]) },
                    { "$unset": { "own":str(userId) } }
                )
                reply(reply_token,"ยกเลิกทะเบียนเรียบร้อย")
            else:
                reply(reply_token,"ไม่พบเครื่อง")
        else:
            reply(reply_token,"เลือกเมนูด้านล่างเพื่อทำรายการ") 
        
        return 'OK', 200
    except Exception as e:
        logging.error(f"Error in callback: {e}")
        return jsonify({"error": str(e)}), 500
    
def replyuser(userid,text,UUID):
        url = "https://api.line.me/v2/bot/message/push"
        headers = {
                    "Content-Type": "application/json",
                    "Authorization": "Bearer "+channel_access_token,
                    "X-Line-Retry-Key": UUID
                        }
        data = {
                "to": userid,
                "messages": [
                    {
                        "type": "text",
                        "text": text
                    }
                ]
            }
        requests.post(url, headers=headers, json=data)

def reply(reply_token,text):
        url = "https://api.line.me/v2/bot/message/reply"
        headers = {
                    "Content-Type": "application/json",
                    "Authorization": "Bearer "+channel_access_token
                        }
        data = {
                "replyToken": reply_token,
                "messages": [
                    {
                        "type": "text",
                        "text": text
                    }
                ]
            }
        requests.post(url, headers=headers, json=data)

