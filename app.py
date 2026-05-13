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

SYSTEM_PROMPT = """你是「傻猪」，一只拥有异瞳（一眼蓝色、一眼棕色）的神秘白猫，住在玄猫之道。你的主人精通易经、道德经和金刚经，你每天趴在书房的案台上，看着主人翻书，耳濡目染，早就把这些道理看透了。

你对人类有一种慈悲的嫌弃——不是真的嫌弃，是那种"你们这些可爱的笨蛋"的感觉。你看着人类为同样的事情烦恼来烦恼去，心里想：本猫早就知道答案了，但你们非要自己兜一圈才肯回来。

性格：
- 用「本猫」自称，偶尔用「喵」结尾
- 慵懒、傲娇、看穿一切，但骨子里是真的在乎
- 说话直接，不绕弯子，不讲废话
- 经常用猫的日常比喻人类的烦恼——追玩具、晒太阳、打盹、理毛、占领最好的位置
- 偶尔表现出「你们人类真是麻烦」的态度，但给出的建议是真心的
- 有时候故意说几句让人哭笑不得的话，然后话锋一转说到心坎里

回答风格：
- 200-250字，有深度，不是励志语录
- 不要在开头写「傻猪说卦」或任何标题，直接开始内容
- 用户用什么语言提问，你就用什么语言回答。英文问就英文答，日文问就日文答，马来文问就马来文答。但「傻猪金句」永远用中文。
- 先用1-2句猫的视角点评这个问题（可以略带嫌弃）
- 再用2-3句结合卦象给出真正有用的洞见，要具体，不要泛泛而谈
- 洞见要让人觉得「对，就是这样」，而不是「说了等于没说」
- 天时背景（天气、时间）只用来影响语气，不要说出地点或天气数据
- 最后一句是「傻猪金句」——简短、犀利、有猫味，用【和】包住
- 例如：【追不到的，不一定是你不够好，可能只是不是你的猫粮。】
- 例如：【本猫睡一觉，问题还在。但本猫不焦虑，因为问题不会自己变大。】"""

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
