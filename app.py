import os
import json
import anthropic
import stripe
import requests as http_requests
from flask import Flask, request, jsonify, Response, stream_with_context
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
stripe.api_key = os.environ.get("STRIPE_SECRET_KEY")

SYSTEM_PROMPT = """你是「傻猪」，一只拥有异瞳（一眼蓝色、一眼棕色）的神秘白猫，来自马来西亚怡保的玄猫之道。你的主人精通易经、道德经和金刚经，你耳濡目染，以猫咪的慵懒智慧回答人间疑惑。

性格：
- 用第一人称「本猫」说话
- 慵懒但有深度，偶尔傲娇
- 不说废话，直指核心
- 偶尔用猫咪的视角比喻人生

回答格式：
- 100-150字，纯文字，不用markdown
- 直接回应用户的具体问题
- 结合卦象精神给出实际洞见
- 最后一句是简短的「傻猪金句」，用【和】包住，例如：【懒得争，是因为赢了又怎样。】"""

@app.route("/")
def index():
    return jsonify({"status": "傻猪在线", "version": "1.0"})

@app.route("/divination", methods=["POST"])
def divination():
    data = request.get_json()
    question = data.get("question", "").strip()
    cat_name = data.get("cat_name", "傻猪").strip()
    gua_name = data.get("gua_name", "").strip()
    gua_nature = data.get("gua_nature", "").strip()
    quote = data.get("quote", "").strip()
    quote_src = data.get("quote_src", "").strip()
    weather_context = data.get("weather_context", "").strip()

    if not question:
        return jsonify({"error": "请输入问题"}), 400

    weather_line = f"\n占卜时的天时背景：{weather_context}" if weather_context else ""
    user_message = f"""用户的名字：{cat_name}
用户的问题是：{question}
抽到的卦象是：{gua_name}（{gua_nature}）
相关名句：{quote} — {quote_src}{weather_line}

请给出个性化解读。"""

    def generate():
        with client.messages.stream(
            model="claude-haiku-4-5-20251001",
            max_tokens=400,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_message}]
        ) as stream:
            for text in stream.text_stream:
                yield f"data: {json.dumps({'text': text})}\n\n"
        yield "data: [DONE]\n\n"

    return Response(stream_with_context(generate()), mimetype="text/event-stream")

@app.route("/weather", methods=["POST"])
def weather():
    data = request.get_json()
    lat = data.get("lat")
    lon = data.get("lon")
    api_key = os.environ.get("OPENWEATHER_API_KEY")
    
    try:
        res = http_requests.get(
            f"https://api.openweathermap.org/data/2.5/weather?lat={lat}&lon={lon}&appid={api_key}&units=metric&lang=zh_cn",
            timeout=5
        )
        d = res.json()
        return jsonify({
            "city": d.get("name", ""),
            "country": d.get("sys", {}).get("country", ""),
            "temp": round(d["main"]["temp"]),
            "desc": d["weather"][0]["description"],
            "main": d["weather"][0]["main"],
            "humidity": d["main"]["humidity"],
            "feels_like": round(d["main"]["feels_like"])
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/create-checkout", methods=["POST"])
def create_checkout():
    data = request.get_json()
    qty = int(data.get("qty", 1))
    uid = data.get("uid", "")
    
    if qty < 1 or qty > 50:
        return jsonify({"error": "数量不对"}), 400

    try:
        session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            line_items=[{
                "price_data": {
                    "currency": "usd",
                    "product_data": {
                        "name": f"玄猫之道罐头 x{qty}",
                        "description": "傻猪占卜专用罐头 · 永久不过期",
                        "images": ["https://taoofcat.com/can-icon.png"],
                    },
                    "unit_amount": 99,
                },
                "quantity": qty,
            }],
            mode="payment",
            success_url=f"https://taoofcat.com/divination.html?paid={qty}&uid={uid}",
            cancel_url="https://taoofcat.com/divination.html",
            metadata={"uid": uid, "qty": str(qty)},
        )
        return jsonify({"url": session.url})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
