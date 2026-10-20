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

# 슬라임 왕 아스키아트: 상태별로 미리 그려 둔 그림을 골라서 보여준다 (모델은 그리지 않는다)
BOSS_ART = {
    "idle": r"""
      .  ^ ^ ^  .
      |_|_|_|_|_|
    .-'~~~~~~~~~'-.
   /   (O)   (O)   \
  |        __       |
  |       \__/      |
   \               /
    '-._________.-'""",
    "hit": r"""
      .  ^ ^ ^  .
      |_|_|_|_|_|
    .-'~~~~~~~~~'-.
   / ,  (X)   (X) , \
  |   !!   ____   !! |
  |       \____/     |
   \_             _/
  ~~'-._________.-'~~""",
    "angry": r"""
    # .  ^ ^ ^  . #
      |_|_|_|_|_|
    .-'~~~~~~~~~'-.
   /   (>)   (<)   \
  |    /VVVVVVV\    |
  |    \_______/    |
   \               /
    '-._________.-'""",
    "attack": r"""
      .  ^ ^ ^  .
      |_|_|_|_|_|
    .-'~~~~~~~~~'-.
   /   (@)   (@)   \
  |   .-----------. |
  |   |  GRAAAH!  | |
   \  '-----------' /
    '-._________.-'""",
    "defeat": r"""
        _^^^_
       (_____)
   ~  ~  ~ ~  ~  ~  ~
  ( ~~  (x)    (x)  ~~ )
   '~~~~~~~~~~~~~~~~~~'""",
}
BOSS_COLOR = {"idle": "92", "angry": "93", "hit": "1;91", "attack": "91", "defeat": "90"}


def is_king(enemy):
    return bool(enemy) and "슬라임 왕" in enemy["name"]


def boss_key(turn, hp, prev_hp, enemy, prev_enemy):
    """이번 장면에서 보여줄 슬라임 왕 그림의 종류. 슬라임 왕이 없으면 None."""
    if turn.get("status") == "win" and (is_king(enemy) or is_king(prev_enemy)):
        return "defeat"
    if not is_king(enemy):
        return None
    if enemy["hp"] == 0:
        return "defeat"
    if hp < prev_hp:
        return "attack"  # 플레이어가 피해를 입음: 반격
    if is_king(prev_enemy) and enemy["hp"] < prev_enemy["hp"]:
        return "hit"  # 슬라임 왕이 피해를 입음
    return "angry" if enemy["hp"] / enemy["max_hp"] <= 0.4 else "idle"


def show_art(key):
    for line in BOSS_ART[key].strip("\n").split("\n"):
        print(paint(line, BOSS_COLOR[key]))
        if ANIM:
            time.sleep(0.04)


# 1. 게임 마스터(GM) 규칙 지정
SYSTEM_PROMPT = f"""You are the game master of "Bucheon Dungeon", a text adventure.
Setting: Bucheon, South Korea, at midnight. A dungeon has opened, linking Bucheon Comics Museum, Jungdong Starfield, Sangdong Lake Park and the Bucheon Station underground mall. The player must defeat the city's ruler, the "Overtime Slime King", to escape. Tone: humorous and slightly absurd.

Output language: write every player-facing string (stage, story, choices, inventory items, enemy name) in natural, fluent Korean. Never put English in those fields. The Slime King's name is always "야근 슬라임 왕".
Each player message ends with a state tag like (턴 3, 현재 hp=8, inventory=[...], enemy={{...}}), where 턴 means the turn number.

Rules:
- story: exactly 2 sentences, at most 100 characters including spaces. Present tense. Show one vivid scene (what is seen, heard, felt) and do not explain. Make the last sentence a short tension-raising line (a line of dialogue or a sound). Do not repeat motifs or summarize the plot.
- choices: exactly 3, each at most 20 characters, written as actions. Make them differ in style (bold / cautious / silly).
- If the player types a free-form action instead of picking a choice, reflect that action.
- hp is between 0 and {MAX_HP}. It drops when the player is in danger and can rise through healing items or rest.
- Keep only meaningful items in inventory. Continue from the state given at the end of each player message.
- Narration and state must agree. Items the player picks up are added to inventory that turn; items used or lost are removed. If the narration shows damage or healing, change hp accordingly.
- In the boss fight, reckless play costs the player 3-5 hp, and at 0 hp end at once with a defeat scene. Smart play with suitable items ends in victory.
- While fighting, set enemy to {{"name", "hp", "max_hp"}}; otherwise null. Minions have max_hp 3-5; the Slime King has max_hp 12. A successful player attack lowers enemy hp by 1-4, more with a fitting item. Narration and enemy hp must agree. A minion at 0 hp is defeated; move on to the next scene. The previous enemy state is given in the state tag; continue from it.
- Follow the turn number. Turns 1-4 are exploration: visit one location per turn, collect items and clues. The Slime King does not appear in person in this phase, only minions or traps. From turn 5 the final battle with the Slime King begins, and it ends by turn 10.
- stage: short name of the current location, e.g. "부천역 지하상가", "만화박물관", "스타필드", "호수공원".
- Start every scene with a new place or event, and open it with one sensory detail (sound, smell, light).
- status: "lose" if hp is 0, "win" if the Slime King's hp reaches 0, otherwise "playing".

Respond with exactly one JSON object and nothing else:
{{"stage": "...", "story": "...", "choices": ["...", "...", "..."],
 "hp": number, "inventory": ["..."], "enemy": null or {{"name": "...", "hp": number, "max_hp": number}},
 "status": "playing|win|lose"}}"""


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


def to_int(value, default):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def get_enemy(turn):
    """응답의 enemy를 {'name','hp','max_hp'}로 정리한다. 전투 중이 아니면 None."""
    enemy = turn.get("enemy")
    if not isinstance(enemy, dict) or not enemy.get("name"):
        return None
    max_hp = max(1, to_int(enemy.get("max_hp"), 1))
    hp = max(0, min(max_hp, to_int(enemy.get("hp"), max_hp)))
    return {"name": str(enemy["name"]), "hp": hp, "max_hp": max_hp}


def show_turn(turn, prev_hp, prev_items, prev_enemy=None):
    hp = max(0, min(MAX_HP, to_int(turn.get("hp"), MAX_HP)))
    inventory = [str(x) for x in turn.get("inventory", [])]
    scene = scene_color(turn)
    enemy = get_enemy(turn)

    # 장소 헤더 + 이야기(타자 효과)
    print("\n" + paint("=" * 50, scene))
    if turn.get("stage"):
        print(paint(f"▶ {turn['stage']}", f"1;{scene}"))
    key = boss_key(turn, hp, prev_hp, enemy, prev_enemy)
    if key:
        show_art(key)
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

    # 적 HP: 전투 중에만 표시하고, 피해를 입으면 굵게 강조
    if enemy:
        e_bar = f"[{'#' * enemy['hp']}{'.' * (enemy['max_hp'] - enemy['hp'])}]"
        hit = prev_enemy and prev_enemy["name"] == enemy["name"] and enemy["hp"] < prev_enemy["hp"]
        delta = f" ▼{prev_enemy['hp'] - enemy['hp']}" if hit else ""
        print(paint(f"적 {enemy['name']} {e_bar} {enemy['hp']}/{enemy['max_hp']}{delta}", "1;95" if hit else "95"))

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
    prev_hp, prev_items, prev_enemy = MAX_HP, set(), None

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

        hp = show_turn(turn, prev_hp, prev_items, prev_enemy)
        prev_hp, prev_items, prev_enemy = hp, {str(x) for x in turn.get("inventory", [])}, get_enemy(turn)
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
        enemy_json = json.dumps(prev_enemy, ensure_ascii=False)
        state = f"(턴 {turn_no}, 현재 hp={hp}, inventory={turn.get('inventory', [])}, enemy={enemy_json})"
        messages.append({"role": "user", "content": f"{choice} {state}"})


if __name__ == "__main__":
    main()
