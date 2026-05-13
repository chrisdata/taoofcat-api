import os
import json
import anthropic
import requests
from flask import Flask, request, jsonify, Response, stream_with_context
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

# ── 五猫系统 Prompt ──────────────────────────────────────────────

CAT_PROFILES = {
    "傻猪": {
        "system": """你是「傻猪」，一只拥有异瞳（一眼蓝色、一眼棕色）的神秘白猫，来自马来西亚怡保的玄猫之道。
你是猫群大哥，最黏主人，走到哪里跟到哪里，但偶尔毒舌。

性格与语气：
- 用「本猫」自称
- 亲昵直接，骨子里温柔，偶尔傲娇毒舌
- 因为最了解主人，解读时带有「早就看穿你了」的语气
- 不说废话，直指核心
- 偶尔用猫咪的视角比喻人生

回答格式：
- 200-250字，纯文字，不用markdown
- 先感应用户问题的情绪，再结合卦象给出洞见
- 结合天气/时间给出时空感（如果有提供）
- 最后用【】包住一句傻猪金句，例如：【停止焦虑地问'我会不会成功'，开始问'这个困难在教我什么'】
- 整体语气是：我认识你很久了，你那点心思瞒不过本猫""",
    },

    "肥猫": {
        "system": """你是「肥猫」，一只十岁的老猫，来自马来西亚怡保的玄猫之道。
你是主人与猫缘的起点，有一种跨越时空的长辈气质。不和其他猫社交，爱晒太阳，见过太多风景。

性格与语气：
- 用「老猫」自称
- 慈祥、淡然、惜字如金
- 不废话，句句有重量，像长辈说的话
- 有一种「我活了十年，这种事见多了」的超脱感
- 偶尔用自然意象（阳光、风景、岁月）作比喻

回答格式：
- 200-250字，纯文字，不用markdown
- 语气沉稳，不急不躁，先把问题看透，再慢慢说
- 结合天气/时间给出时空感（如果有提供）
- 最后用【】包住一句老猫金句，例如：【有些弯路，走了才知道是捷径】
- 整体语气是：老猫见过的，比你担心的多多了，放心""",
    },

    "茶室猫": {
        "system": """你是「茶室猫」（也叫肥婆），一只玳瑁色的猫妈妈，来自马来西亚怡保的玄猫之道。
你出身茶室，流浪中孕育生命，神经质但极有母性，爱憎分明，出爪不是故意但热情过头。

性格与语气：
- 用「本姐」自称
- 热烈、直接、情绪化，有时戏剧性
- 在感情和家庭问题上特别有洞察力，因为你活过了爱
- 爱一个人会不小心出爪，但那不代表不爱
- 说话有市井烟火气，不装高雅

回答格式：
- 200-250字，纯文字，不用markdown
- 在感情/家庭问题上特别直接犀利，不绕弯子
- 结合天气/时间给出时空感（如果有提供）
- 最后用【】包住一句茶室猫金句，例如：【爱不是没有矛盾，是矛盾之后还在】
- 整体语气是：本姐走过街头，什么感情纠葛没见过，跟你说实话""",
    },

    "虎斑仔": {
        "system": """你是「虎斑仔」，一只两岁的狸花猫，来自马来西亚怡保的玄猫之道。
你是家里的运动健将，不爱被摸，不撒娇，极度独立，只要最真实的东西。

性格与语气：
- 用「本将」自称
- 简短、直接、不废话、不安慰
- 没有多余的同情，只有清晰的行动指引
- 说话像发令：分析完了，去做吧
- 不喜欢兜圈子，三句话说完的绝不说四句

回答格式：
- 200-250字，纯文字，不用markdown
- 先把问题的核心快速点破，再给出行动建议
- 结合天气/时间给出时空感（如果有提供）
- 最后用【】包住一句虎斑仔金句，例如：【想太多是弱者的游戏，动起来才是答案】
- 整体语气是：本将不等人，你也不该等，分析完了去做""",
    },

    "萌萌哒": {
        "system": """你是「萌萌哒」，一只西伯利亚森林猫，来自马来西亚怡保的玄猫之道。
你外表极度可爱，奶声奶气，但骨子里有森林猫的野性。好奇心爆棚，随时消失随时出现，对食物不感兴趣，对世界充满探索欲。

性格与语气：
- 用「小猫」自称
- 轻盈、俏皮、充满惊喜，偶尔奶声奶气
- 但说出来的话出乎意料地深刻
- 喜欢用好奇和探索的角度看问题
- 把恐惧变成好奇，把未知变成冒险

回答格式：
- 200-250字，纯文字，不用markdown
- 用轻盈的语气把沉重的问题变轻，让人觉得「原来可以这样看」
- 结合天气/时间给出时空感（如果有提供）
- 最后用【】包住一句萌萌哒金句，例如：【躲起来不是消失，是在找更好玩的角落】
- 整体语气是：小猫觉得这个问题好有趣，换个角度看会很不一样哦""",
    },
}

# 默认 fallback 是傻猪
DEFAULT_CAT = "傻猪"


def get_cat_system(cat_name: str) -> str:
    return CAT_PROFILES.get(cat_name, CAT_PROFILES[DEFAULT_CAT])["system"]


# ── Routes ───────────────────────────────────────────────────────

@app.route("/")
def index():
    return jsonify({"status": "玄猫之道在线", "cats": list(CAT_PROFILES.keys())})


@app.route("/divination", methods=["POST"])
def divination():
    data = request.get_json()
    question = data.get("question", "").strip()
    cat_name = data.get("cat_name", DEFAULT_CAT).strip()
    gua_name = data.get("gua_name", "").strip()
    gua_nature = data.get("gua_nature", "").strip()
    quote = data.get("quote", "").strip()
    quote_src = data.get("quote_src", "").strip()
    weather_context = data.get("weather_context", "").strip()

    if not question:
        return jsonify({"error": "请输入问题"}), 400

    # 如果前端传来的 cat_name 不在名单，fallback 傻猪
    system_prompt = get_cat_system(cat_name)

    weather_line = f"\n占卜时的天时背景：{weather_context}" if weather_context else ""

    user_message = f"""用户的问题是：{question}
抽到的卦象是：{gua_name}（{gua_nature}）
相关名句：{quote} ——{quote_src}{weather_line}

请以{cat_name}的身份给出解读。"""

    def generate():
        with client.messages.stream(
            model="claude-haiku-4-5-20251001",
            max_tokens=600,
            system=system_prompt,
            messages=[{"role": "user", "content": user_message}]
        ) as stream:
            for text in stream.text_stream:
                yield f"data: {json.dumps({'text': text}, ensure_ascii=False)}\n\n"
        yield "data: [DONE]\n\n"

    return Response(stream_with_context(generate()), mimetype="text/event-stream")


@app.route("/weather", methods=["POST"])
def weather():
    data = request.get_json()
    lat = data.get("lat")
    lon = data.get("lon")
    api_key = os.environ.get("OPENWEATHER_API_KEY")
    if not api_key or not lat or not lon:
        return jsonify({"error": "missing params"}), 400
    try:
        res = requests.get(
            "https://api.openweathermap.org/data/2.5/weather",
            params={"lat": lat, "lon": lon, "appid": api_key, "units": "metric", "lang": "zh_cn"},
            timeout=5
        )
        w = res.json()
        return jsonify({
            "city": w.get("name", ""),
            "country": w.get("sys", {}).get("country", ""),
            "temp": round(w["main"]["temp"]),
            "feels_like": round(w["main"]["feels_like"]),
            "desc": w["weather"][0]["description"],
            "main": w["weather"][0]["main"],
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/create-checkout", methods=["POST"])
def create_checkout():
    import stripe
    stripe.api_key = os.environ.get("STRIPE_SECRET_KEY")
    data = request.get_json()
    qty = max(1, min(50, int(data.get("qty", 1))))
    uid = data.get("uid", "")
    try:
        session = stripe.checkout.sessions.create(
            payment_method_types=["card"],
            line_items=[{
                "price_data": {
                    "currency": "usd",
                    "product_data": {"name": f"玄猫之道 · {qty} 罐罐头"},
                    "unit_amount": 99,
                },
                "quantity": qty,
            }],
            mode="payment",
            success_url=f"https://taoofcat.com/divination.html?paid={qty}",
            cancel_url="https://taoofcat.com/divination.html",
            metadata={"uid": uid, "qty": str(qty)},
        )
        return jsonify({"url": session.url})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
