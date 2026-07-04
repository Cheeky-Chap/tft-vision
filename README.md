# TFT Vision — Screen Capture & ROI Crop MVP 1
#
# ## 개요
# TFT 게임 화면을 캡처하고 관심 영역(ROI)을 추출하는 MVP 1 단계 프로젝트.
# Overwolf 의존성 없이 순수 화면 캡처 기반으로 데이터 수집 파이프라인을 구축한다.
#
# ## 프로젝트 구조
#
# ```
# tft-vision/
# ├── src/
# │   ├── capture/          # 화면 캡처 모듈
# │   │   └── screen_capture.py
# │   ├── crop/             # ROI crop 모듈
# │   │   ├── roi_definitions.py
# │   │   ├── cropper.py
# │   │   └── game_region.py    # ← NEW: 게임 영역 crop
# │   └── config/           # 설정
# │       └── settings.py
# ├── captures/             # 원본 캡처 (git 제외)
# │   └── game/             # game region crop 결과 (git 제외)
# ├── crops/                # ROI crop 결과 (git 제외)
# │   ├── player_level/
# │   ├── player_gold/
# │   ├── player_streak/
# │   ├── item_area/
# │   ├── shop/
# │   ├── stage_info/
# │   ├── player_list/
# │   ├── enemy_bench/
# │   ├── enemy_board/
# │   ├── my_board/
# │   └── my_bench/
# ├── logs/                 # 실행 로그 (git 제외)
# ├── requirements.txt
# ├── .gitignore
# └── README.md
# ```
#
# ## 파이프라인 흐름
#
# ```
# 전체 모니터 캡처
#     ↓ (선택) --game-region
# Game Frame crop (게임 창 영역만)
#     ↓
# ROI crop (my_board, shop, bench, ...)
#     ↓
# crops/ 저장
# ```
#
# - `--game-region` 미설정 시: 전체 모니터 → 바로 ROI crop (기존 방식)
# - `--game-region` 설정 시: 전체 모니터 → 게임 영역 crop → ROI crop
#
# ## Windows 노트북 실행 방법
#
# ### 1. Python 가상환경 생성
# ```powershell
# cd C:\path\to\tft-vision
# python -m venv .venv
# .venv\Scripts\Activate.ps1
# ```
#
# ### 2. 패키지 설치
# ```powershell
# pip install -r requirements.txt
# ```
#
# ### 3. 모니터 확인 (듀얼 모니터인 경우)
# ```powershell
# python -m src.capture_loop --list-monitors
# ```
# 출력 예시:
# ```
# Index   Left    Top  Width  Height  Name
# ─────   ─────   ───  ─────  ──────  ──────────────────────────────
#     0      0      0   3840   1080  Virtual Desktop (all)
#     1      0      0   1920   1080  Monitor 1
#     2   1920      0   1920   1080  Monitor 2
# ```
#
# ### 4. 듀얼 모니터 설정
# TFT가 실행 중인 모니터가 Monitor 2(index=2)라면 `.env` 파일을 편집:
# ```ini
# MONITOR_INDEX=2
# ```
# 또는 `--monitor` 옵션 직접 지정:
# ```powershell
# python -m src.capture_loop --monitor 2
# ```
#
# **MONITOR_INDEX 값 설명:**
# - `MONITOR_INDEX=1` → 첫 번째 모니터 (기본값, 노트북 내장 화면)
# - `MONITOR_INDEX=2` → 두 번째 모니터 (외부 모니터)
# - `MONITOR_INDEX=0` → 전체 가상 데스크톱 (모든 모니터를 하나로 합친 영역)
#
# ### 5. 게임 영역 설정 (Game Region Crop)
#
# 2560x1440 외부 모니터에서 1920x1080 **테두리 없는 창모드**로 TFT를 실행하면,
# 게임 창이 모니터 가운데 정렬되어 좌상단 기준 (320, 180)에 위치합니다.
#
# `.env`에 설정:
# ```ini
# MONITOR_INDEX=2
# GAME_REGION_LEFT=320
# GAME_REGION_TOP=180
# GAME_REGION_WIDTH=1920
# GAME_REGION_HEIGHT=1080
# ```
#
# 또는 CLI에서 직접 지정:
# ```powershell
# python -m src.capture_loop --monitor 2 --game-region 320,180,1920,1080 --preview
# ```
#
# 게임 영역이 적용되면:
# 1. 전체 모니터(2560x1440) 캡처
# 2. (320,180,1920,1080) 영역 crop → 1920x1080 game frame
# 3. game frame 기준으로 기존 ROI crop 실행
# 4. 원본: `captures/`, game frame: `captures/game/`, ROI: `crops/` 저장
#
# ### 6. 실행
# ```powershell
# # 기본 (1회 캡처 + ROI crop)
# python -m src.capture_loop
#
# # 외부 모니터 + 게임 영역 지정
# python -m src.capture_loop --monitor 2 --game-region 320,180,1920,1080 --preview
#
# # 외부 모니터 + .env 설정 사용
# python -m src.capture_loop --preview
#
# # 연속 캡처 (10회, 2초 간격)
# python -m src.capture_loop --interval 2.0 --count 10
#
# # 캡처만 (ROI crop 없음)
# python -m src.capture_loop --capture-only
# ```
#
# ## 캡처 저장 경로
# - 원본 (전체 모니터): `captures/YYYYMMDD_HHMMSS.png`
# - Game frame: `captures/game/YYYYMMDD_HHMMSS.png`
# - ROI: `crops/{roi_name}/YYYYMMDD_HHMMSS.png`
#
# ## 명령줄 옵션
# | 옵션 | 설명 |
# |------|------|
# | `--list-monitors` | 사용 가능한 모니터 목록 출력 |
# | `--monitor INDEX` | 캡처할 모니터 인덱스 (기본: .env의 MONITOR_INDEX 또는 1) |
# | `--game-region LEFT,TOP,WIDTH,HEIGHT` | 게임 영역 crop 좌표 (예: 320,180,1920,1080) |
# | `--interval SEC` | 캡처 간격 초 단위 (기본 1.0) |
# | `--count N` | 캡처 횟수 (기본 1, 0=무한) |
# | `--capture-only` | ROI crop 없이 원본만 저장 |
# | `--preview` | ROI crop 결과 창 표시 |
# | `--no-save` | 저장 없이 메모리만 처리 |
#
# ## ROI 목록
#
# | ROI 이름 | 영역 (1920x1080) | 설명 |
# |---------|-----------------|------|
# | `item_area` | (0,270)-(110,780) | 좌측 아이템/장비 영역 |
# | `player_level` | (260,870)-(470,920) | 레벨 |
# | `player_gold` | (910,880)-(1040,920) | 골드 |
# | `player_streak` | (1040,870)-(1120,920) | 연승/연패 스트릭 |
# | `shop` | (470,920)-(1490,1080) | 상점 카드 5개 |
# | `stage_info` | (730,0)-(1180,40) | 라운드/스테이지 정보 |
# | `player_list` | (1620,180)-(1920,800) | 상대 목록 (우측) |
# | `enemy_bench` | (550,55)-(1350,190) | 상대 벤치 |
# | `enemy_board` | (520,195)-(1380,430) | 상대 보드 (육각형 그리드) |
# | `my_board` | (450,425)-(1460,760) | 내 보드 (육각형 그리드) |
# | `my_bench` | (350,760)-(1410,890) | 내 벤치 |
# | `full_screen` | (0,0)-(1920,1080) | 전체 화면 |
#
# > 좌표는 실제 `captures/game/*.png` 이미지로 보정 완료.
#
# ## 주의사항
# - TFT 게임이 **전체화면(1920x1080)** 또는 **테두리 없는 창모드** 상태여야 함
# - 듀얼 모니터일 경우 `--list-monitors`로 TFT 실행 모니터 확인 후 MONITOR_INDEX 설정
# - 게임 영역 좌표는 **모니터 절대 좌표** 기준 (--list-monitors로 모니터 left/top 확인)
# - `.env`에 캡처 핫키/딜레이/모니터 설정 가능
# - 개인 스크린샷, 토큰, API key는 절대 commit 금지
