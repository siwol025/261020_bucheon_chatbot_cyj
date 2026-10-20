import json
import os
import sys
import time

from dotenv import load_dotenv
from groq import Groq

try:
    import msvcrt  # Windows 전용: 타자 효과 중 키를 누르면 건너뛰기
except ImportError:
    msvcrt = None

# 환경 변수 불러오기
load_dotenv()

GROQ_MODEL = "openai/gpt-oss-20b"
GEMINI_MODEL = "gemini-3.8-flash"
MAX_HP = 10

# 터미널 연출: 색상과 타자 효과는 직접 보는 터미널에서만 켠다 (파이프/리다이렉트 시 꺼짐)
USE_COLOR = sys.stdout.isatty() or bool(os.getenv("FORCE_COLOR"))
ANIM = sys.stdout.isatty()
if USE_COLOR:
    os.system("")  # Windows 터미널에서 ANSI 색상 활성화

# 장소 이름에 맞춘 색상(ANSI). 앞에 있는 항목이 우선한다.
SCENES = [
    ("슬라임 왕", "92"),
    ("만화박물관", "35"),
    ("스타필드", "94"),
    ("호수공원", "36"),
    ("지하상가", "33"),
    ("부천역", "33"),
]


def paint(text, code):
    return f"\033[{code}m{text}\033[0m" if USE_COLOR else text


def scene_color(turn):
    for text in (turn.get("stage", ""), turn["story"]):
        for key, code in SCENES:
            if key in text:
                return code
    return "37"


def key_pressed():
    if msvcrt and msvcrt.kbhit():
        while msvcrt.kbhit():
            msvcrt.getwch()
        return True
    return False


def typewrite(text, delay=0.025):
    """글자를 한 글자씩 출력한다. 아무 키나 누르면 나머지를 바로 보여준다."""
    if not ANIM:
        print(text)
        return
    for i, ch in enumerate(text):
        if key_pressed():
            print(text[i:], end="")
            break
        print(ch, end="", flush=True)
        time.sleep(0.12 if ch in ".,!?…" else delay)
    print()

# 1. 게임 마스터(GM) 규칙 지정
SYSTEM_PROMPT = f"""너는 '부천 던전' 텍스트 어드벤처의 게임 마스터야.
배경: 한밤중의 부천. 부천 만화박물관, 중동 스타필드, 상동 호수공원, 부천역 지하상가가 이어진 던전이 열렸고
도시를 지배하는 '야근 슬라임 왕'을 쓰러뜨려야 탈출할 수 있다. 분위기는 유머러스하고 약간 황당하게.

규칙:
- story는 반드시 2문장, 공백 포함 100자 이내로 쓴다. 현재형으로, 보이고 들리고 느껴지는 장면 하나만 생생하게 보여주고 설명은 빼라. 마지막 문장은 긴장을 올리는 짧은 한 줄(대사나 소리)로 끝내라. 같은 소재를 반복하거나 줄거리를 요약하지 마라.
- 선택지는 정확히 3개, 각 20자 이내의 행동 문장으로 쓴다. 서로 성격이 다르게(대담함/신중함/엉뚱함) 구성한다.
- 플레이어가 선택지 번호 대신 자유롭게 행동을 입력해도 그 행동을 반영한다.
- 체력(hp)은 0~{MAX_HP}. 위험하면 줄고, 회복 아이템이나 휴식으로 오를 수 있다.
- 아이템은 의미 있는 것만 inventory에 유지한다. 이전 상태는 매 턴 직접 넘겨받은 값을 이어서 쓴다.
- 서술과 상태는 반드시 일치해야 한다. 플레이어가 획득한 아이템은 그 턴 inventory에 추가하고, 사용하거나 잃은 아이템은 제거한다. 서술에서 피해를 입거나 회복하면 hp도 그만큼 바꾼다.
- 보스전에서 플레이어가 무모하게 행동하면 hp를 3~5 깎고, hp가 0이 되면 곧바로 패배 장면으로 끝낸다. 적절한 아이템으로 공략하면 승리로 끝낸다.
- 플레이어 메시지 끝의 턴 번호를 따른다. 턴 1~4는 부천의 장소를 하나씩 탐험하며 아이템을 얻고 단서를 모으는 구간이다. 이 구간에는 슬라임 왕이 직접 나오지 않고 졸개나 함정만 나온다. 턴 5부터 슬라임 왕과 최종 전투를 시작하고 턴 10 안에 끝낸다.
- stage에는 현재 장소 이름을 짧게 쓴다. 예: "부천역 지하상가", "만화박물관", "스타필드", "호수공원".
- 매 장면은 새 장소나 새 사건으로 시작한다. 장면 첫머리에 장소의 감각 하나(소리, 냄새, 빛)를 넣어 몰입시킨다.
- hp가 0이 되면 status를 "lose", 보스를 쓰러뜨리면 "win", 그 외에는 "playing".

반드시 아래 JSON 객체 하나만 출력해. 다른 텍스트는 금지.
{{"stage": "현재 장소", "story": "장면 묘사", "choices": ["선택지1", "선택지2", "선택지3"],
 "hp": 숫자, "inventory": ["아이템", ...], "status": "playing|win|lose"}}"""


def call_groq(messages):
    client = Groq(api_key=os.getenv("GROQ_API_KEY"))
    res = client.chat.completions.create(
        model=GROQ_MODEL,
        messages=messages,
        temperature=0.9,  # 높을수록 창의적인 전개
        max_completion_tokens=1000,
        reasoning_effort="low",
        response_format={"type": "json_object"},
    )
    return res.choices[0].message.content


def call_gemini(messages):
    # groq 한도 소진 시 대체 호출 (GEMINI_API_KEY 필요)
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
    contents = [
        types.Content(
            role="user" if m["role"] == "user" else "model",
            parts=[types.Part(text=m["content"])],
        )
        for m in messages
        if m["role"] != "system"
    ]
    res = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=contents,
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            response_mime_type="application/json",
            temperature=0.9,
        ),
    )
    return res.text


def ask_gm(messages):
    """Groq로 먼저 시도하고, 실패하면 Gemini로 넘어간다."""
    try:
        return call_groq(messages)
    except Exception as e:
        print(f"[알림] Groq 호출 실패({type(e).__name__}) -> Gemini로 전환합니다.")
        if not os.getenv("GEMINI_API_KEY"):
            raise RuntimeError("GEMINI_API_KEY가 없어 대체 호출을 할 수 없습니다.") from e
        return call_gemini(messages)


def parse_turn(raw):
    """모델 응답을 JSON으로 변환. 코드블록이 섞여도 처리한다."""
    text = raw.strip()
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("JSON을 찾지 못했습니다.")
    return json.loads(text[start : end + 1])


def show_turn(turn, prev_hp, prev_items):
    hp = max(0, min(MAX_HP, int(turn.get("hp", MAX_HP))))
    inventory = [str(x) for x in turn.get("inventory", [])]
    scene = scene_color(turn)

    # 장소 헤더 + 이야기(타자 효과)
    print("\n" + paint("=" * 50, scene))
    if turn.get("stage"):
        print(paint(f"▶ {turn['stage']}", f"1;{scene}"))
    typewrite(turn["story"])
    print(paint("-" * 50, scene))

    # HP: 감소는 빨강, 회복은 초록, 위험(3 이하)은 빨강
    bar = f"[{'#' * hp}{'.' * (MAX_HP - hp)}]"
    if hp < prev_hp:
        bar_line = paint(f"HP {bar} {hp}/{MAX_HP} ▼{prev_hp - hp}", "1;91")
    elif hp > prev_hp:
        bar_line = paint(f"HP {bar} {hp}/{MAX_HP} ▲{hp - prev_hp}", "1;92")
    else:
        bar_line = paint(f"HP {bar} {hp}/{MAX_HP}", "91" if hp <= 3 else "32")

    # 가방: 새로 얻은 아이템에는 NEW 표시
    shown = [paint(f"{n} NEW", "1;93") if n not in prev_items else n for n in inventory]
    print(f"{bar_line}   가방: {', '.join(shown) or '없음'}")

    for i, c in enumerate(turn.get("choices", []), 1):
        print(f"  {paint(i, scene)}. {c}")
    return hp


def main():
    print("=== 부천 던전: 야근 슬라임 왕을 쓰러뜨려라 ===")
    print("번호를 고르거나 하고 싶은 행동을 직접 입력하세요. (exit: 종료)")

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": "게임을 시작해줘. 첫 장면을 보여줘. hp는 10, inventory는 비어 있어. (턴 1)"},
    ]
    turn_no = 1
    prev_hp, prev_items = MAX_HP, set()

    while True:
        # 2. GM 응답 받기 (JSON 파싱 실패 시 1회 재시도)
        turn = None
        for _ in range(2):
            try:
                raw = ask_gm(messages)
                turn = parse_turn(raw)
                break
            except (ValueError, KeyError, json.JSONDecodeError):
                continue
            except Exception as e:
                print(f"[오류] {e}")
                return
        if turn is None:
            print("[오류] GM 응답을 해석하지 못했어요. 다시 실행해 주세요.")
            return

        hp = show_turn(turn, prev_hp, prev_items)
        prev_hp, prev_items = hp, {str(x) for x in turn.get("inventory", [])}
        messages.append({"role": "assistant", "content": json.dumps(turn, ensure_ascii=False)})

        # 3. 종료 판정
        status = turn.get("status", "playing")
        if hp == 0 or status == "lose":
            print(paint("\n*** GAME OVER: 야근의 늪에 빠졌습니다... ***", "1;91"))
            break
        if status == "win":
            print(paint("\n*** CLEAR! 부천에 평화(와 칼퇴)가 찾아왔습니다! ***", "1;93"))
            break

        # 4. 플레이어 입력
        choice = input("\n나의 행동 > ").strip()
        if choice.lower() == "exit":
            print("게임을 종료합니다.")
            break
        if choice.isdigit() and 1 <= int(choice) <= len(turn.get("choices", [])):
            choice = turn["choices"][int(choice) - 1]
        if not choice:
            choice = "주변을 살펴본다"

        turn_no += 1
        state = f"(턴 {turn_no}, 현재 hp={hp}, inventory={turn.get('inventory', [])})"
        messages.append({"role": "user", "content": f"{choice} {state}"})


if __name__ == "__main__":
    main()
