# 부천 던전 - 텍스트 어드벤처 챗봇

Groq API(`openai/gpt-oss-20b`)가 게임 마스터가 되어 진행하는 터미널 텍스트 어드벤처 게임입니다.
한밤중 부천에 열린 던전에서 **야근 슬라임 왕**을 쓰러뜨리고 탈출하세요.

## 주요 기능
- 매 턴 3개의 선택지 제공 (번호 입력 또는 원하는 행동을 자유롭게 입력)
- 체력(HP) 바와 가방(아이템) 상태 표시
- 승리 / 패배 자동 판정
- Groq 호출 실패(한도 소진 등) 시 Gemini API로 자동 전환

## 설치
```bash
git clone https://github.com/siwol025/261020_bucheon_chatbot_cyj.git
cd 261020_bucheon_chatbot_cyj
pip install -r requirements.txt
```

## API 키 설정
1. `.env.example`을 복사해 `.env` 파일을 만듭니다.
   ```bash
   copy .env.example .env      # macOS/Linux: cp .env.example .env
   ```
2. `.env`에 키를 입력합니다.
   ```
   GROQ_API_KEY=발급받은_groq_키
   GEMINI_API_KEY=발급받은_gemini_키   # 선택: Groq 한도 소진 시 대체
   ```
- Groq 키: https://console.groq.com/keys
- Gemini 키: https://aistudio.google.com/apikey
- `.env`는 `.gitignore`에 포함되어 있어 깃허브에 올라가지 않습니다. 절대 키를 커밋하지 마세요.

## 실행
```bash
python app.py
```

## 플레이 방법
- 숫자(`1`~`3`)를 입력하면 해당 선택지를 실행합니다.
- 선택지 외의 행동도 문장으로 입력할 수 있습니다. 예: `슬라임에게 커피를 건넨다`
- `exit`를 입력하면 종료됩니다.

## 웹 버전 (Claude 아티팩트)
같은 세계관을 claude.ai 아티팩트로 옮긴 버전입니다. 게임 마스터를 Claude가 맡으며 API 키가 필요 없습니다.
- 소스: `artifact/bucheon_dungeon.html`
- 링크: https://claude.ai/artifact/R84pg48mFwGzEPDX2ovfFF (공유 설정 후 접속 가능)

## 파일 구성
| 파일 | 설명 |
|------|------|
| `app.py` | 게임 본체 (Groq 호출, Gemini 대체 호출, 화면 출력) |
| `artifact/bucheon_dungeon.html` | claude.ai 아티팩트용 웹 버전 |
| `requirements.txt` | 필요 라이브러리 목록 |
| `.env.example` | 환경 변수 예시 |
| `.gitignore` | `.env` 등 커밋 제외 목록 |
