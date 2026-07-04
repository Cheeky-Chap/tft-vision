# TFT Vision — Screen Capture & ROI Crop MVP 1
#
# ## 개요
# TFT 게임 화면을 캡처하고 관심 영역(ROI)을 추출하는 MVP 1 단계 프로젝트.
# Overwolf 의존성 없이 순수 화면 캡처 기반으로 데이터 수집 파이프라인을 구축한다.
#
# **현재 상태: ROI calibration complete / sample collection ready**
#
# - 16개 ROI 좌표 보정 완료 (shop 5개 슬롯 분할 포함, 1920x1080 game frame 기준)
# - game region crop 지원 (2560x1440 모니터 → 1920x1080 게임 창)
# - 듀얼 모니터 환경 설정 완료
# - `--debug-roi`로 ROI 검증 가능
# - `--sample-run`으로 OCR 학습용 샘플 데이터 수집 가능
# - **OCR/인식은 아직 구현 전 — 다음 단계**
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
# │   │   └── game_region.py
# │   └── visualization/    # 시각화/디버그
# │       └── debug_roi.py  # ROI overlay + contact sheet
# ├── tools/               # CLI 도구
# │   └── label_samples.py # 수동 데이터 레이블링
# ├── collector/            # 데이터 수집 (신규)
# │   └── sample_collector.py  # --sample-run 세션 관리
# ├── config/               # 설정
# │   └── settings.py
# ├── captures/             # 원본 캡처 (git 제외)
# │   └── game/             # game region crop 결과 (git 제외)
# ├── crops/                # ROI crop 결과 (git 제외)
# │   ├── player_level/
# │   ├── player_gold/
# │   ├── player_streak/
# │   ├── item_area/
# │   ├── shop/
# │   ├── shop_slot_1/
# │   ├── shop_slot_2/
# │   ├── shop_slot_3/
# │   ├── shop_slot_4/
# │   ├── shop_slot_5/
# │   ├── stage_info/
# │   ├── player_list/
# │   ├── enemy_bench/
# │   ├── enemy_board/
# │   ├── my_board/
# │   └── my_bench/
# ├── debug/                # ROI 검증 이미지 (git 제외)
# │   ├── roi_overlay/      #   ROI 사각형이 그려진 game frame
# │   └── contact_sheet/    #   모든 crop을 한 장에 합친 이미지
# ├── logs/                 # 실행 로그 (git 제외)
# ├── samples/               # sample-run 샘플 데이터 (git 제외)
# │   └── session_*          # 세션별 정리된 crop + game frame
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
# | `--debug-roi` | ROI 검증용 overlay + contact sheet 생성 |
# | `--sample-run` | OCR 학습용 샘플 데이터 수집 (samples/session_*/) |
# | `--manual` | 수동 캡처 모드: Enter=캡처, q=종료, qq=즉시종료 |
#
# ## 수동 캡처 모드 (--manual)
#
# 자동 interval 캡처 대신, 사용자가 Enter를 누를 때마다 1장씩 캡처합니다.
#
# ```powershell
# # 기본 수동 캡처
# python -m src.capture_loop --monitor 2 --game-region 320,180,1920,1080 --manual
#
# # 수동 캡처 + 샘플 수집
# python -m src.capture_loop --monitor 2 --game-region 320,180,1920,1080 --sample-run --manual
#
# # 수동 캡처 + ROI 검증
# python -m src.capture_loop --monitor 2 --game-region 320,180,1920,1080 --debug-roi --manual
# ```
#
# ### 동작 방식
#
# ```
# [1] Enter=캡처, q=종료, qq=즉시종료:   ← Enter 입력 → 캡처 1회
# [2] Enter=캡처, q=종료, qq=즉시종료:   ← Enter 입력 → 캡처 2회
# [3] Enter=캡처, q=종료, qq=즉시종료: q ← 저장 후 종료
# ```
#
# - **Enter**: 현재 프레임 캡처 (captures/, crops/, samples/ 등 저장)
# - **q**: 저장 후 종료 (로그 메시지 출력)
# - **qq**: 즉시 종료
# - **Ctrl+C**: 안전하게 중단
# - `--interval`, `--count` 옵션은 무시됨 (사용자 입력 기반)
# - `--sample-run`, `--debug-roi`와 함께 사용 가능
#
# ## ROI 검증 (--debug-roi)
#
# `--debug-roi` 옵션으로 ROI 좌표가 올바른지 시각적으로 확인할 수 있습니다.
#
# ```powershell
# python -m src.capture_loop --monitor 2 --game-region 320,180,1920,1080 --debug-roi
# ```
#
# ### 생성되는 파일
#
# **debug/roi_overlay/ — ROI 오버레이**
# game frame 위에 모든 ROI 사각형과 이름이 그려진 이미지.
# 각 ROI가 올바른 위치를 커버하는지 한눈에 확인 가능.
#
# **debug/contact_sheet/ — ROI 접촉 시트**
# 모든 ROI crop 결과를 한 장의 이미지로 합친 contact sheet.
# 각 crop이 어떤 ROI에 해당하는지, UI 요소가 정확히 잘렸는지 확인 가능.
#
# > `debug/` 폴더는 `.gitignore`에 포함되어 commit되지 않습니다.
#
# ## ROI 목록
#
# | ROI 이름 | 영역 (1920x1080) | 설명 |
# |---------|-----------------|------|
# | `item_area` | (0,270)-(110,780) | 좌측 아이템/장비 영역 |
# | `player_level` | (260,870)-(470,920) | 레벨 |
# | `player_gold` | (910,880)-(1040,920) | 골드 |
# | `player_streak` | (1040,870)-(1120,920) | 연승/연패 스트릭 |
# | `shop` | (470,920)-(1490,1080) | 상점 카드 5개 (전체) |
# | `shop_slot_1` | (470,920)-(674,1080) | 상점 슬롯 1 (204×160) |
# | `shop_slot_2` | (674,920)-(878,1080) | 상점 슬롯 2 (204×160) |
# | `shop_slot_3` | (878,920)-(1082,1080) | 상점 슬롯 3 (204×160) |
# | `shop_slot_4` | (1082,920)-(1286,1080) | 상점 슬롯 4 (204×160) |
# | `shop_slot_5` | (1286,920)-(1490,1080) | 상점 슬롯 5 (204×160) |
# | `stage_info` | (730,0)-(1180,40) | 라운드/스테이지 정보 |
# | `player_list` | (1620,180)-(1920,800) | 상대 목록 (우측) |
# | `enemy_bench` | (550,35)-(1350,170) | 상대 벤치 |
# | `enemy_board` | (520,95)-(1380,410) | 상대 보드 |
# | `my_board` | (450,300)-(1460,730) | 내 보드 |
# | `my_bench` | (340,650)-(1560,840) | 내 벤치 |
# | `full_screen` | (0,0)-(1920,1080) | 전체 화면 |
#
# > 좌표는 실제 `captures/game/*.png` 이미지로 보정 완료.
#
# ## 상점 슬롯 분할
#
# `shop` ROI(470,920)-(1490,1080)는 5개의 챔피언 카드 슬롯으로 자동 분할됩니다.
#
# - `shop` 전체 영역을 5등분 (각 슬롯 204×160)
# - 각 슬롯은 개별 폴더에 저장: `crops/shop_slot_1/` ~ `crops/shop_slot_5/`
# - OCR/챔피언 이름 인식은 아직 구현 전
# - `--debug-roi` contact sheet에서 각 슬롯 crop 결과 확인 가능
#
# ## 샘플 데이터 수집 (--sample-run)
#
# `--sample-run`으로 OCR/인식 모델 학습용 데이터를 수집할 수 있습니다.
#
# ```powershell
# # 100 프레임 샘플 수집 (2초 간격, 게임 영역 지정)
# python -m src.capture_loop --monitor 2 --game-region 320,180,1920,1080 --sample-run --interval 2.0 --count 100
#
# # 무한 수집 (Ctrl+C로 중단)
# python -m src.capture_loop --monitor 2 --game-region 320,180,1920,1080 --sample-run --interval 5.0 --count 0
# ```
#
# ### 세션 폴더 구조
# ```
# samples/session_20260704_153000/
# ├── game/                 # 원본 game frame (1920x1080)
# │   ├── 20260704_153000_000001_0001.png
# │   ├── 20260704_153005_000002_0002.png
# │   └── ...
# ├── shop_slot_1/          # 상점 슬롯 1 crop (204×160)
# ├── shop_slot_2/          # 상점 슬롯 2 crop
# ├── shop_slot_3/          # 상점 슬롯 3 crop
# ├── shop_slot_4/          # 상점 슬롯 4 crop
# ├── shop_slot_5/          # 상점 슬롯 5 crop
# ├── player_gold/          # 골드 crop
# ├── player_level/         # 레벨 crop
# ├── player_streak/        # 연승/연패 스트릭 crop
# ├── stage_info/           # 라운드/스테이지 crop
# ├── item_area/            # 좌측 아이템/장비 영역 crop
# ├── player_list/          # 상대 목록 crop
# ├── enemy_board/          # 상대 보드 crop
# ├── enemy_bench/          # 상대 벤치 crop
# ├── my_board/             # 내 보드 crop
# └── my_bench/             # 내 벤치 crop
# ```
#
# > `samples/` 폴더는 `.gitignore`에 포함되어 commit되지 않습니다.
# > 각 파일명은 `{timestamp}_{frame_index:04d}.png` 형식입니다.
#
## 수동 데이터 레이블링 (label_samples)

수집된 샘플 이미지를 사람이 보고 직접 label(정답)을 입력하여 `labels.csv`로 저장합니다.
ROI 유형에 따라 세 가지 모드로 동작합니다.

### 사용법

```powershell
# 상점 슬롯 1 — champion 모드 (챔피언 이름만 입력)
python -m src.tools.label_samples samples/session_xxx/shop_slot_1 --roi shop_slot_1

# 내 보드 — structured 모드 (기물 목록: champ_starLevel,champ_starLevel)
python -m src.tools.label_samples samples/session_xxx/my_board --roi my_board

# 내 벤치 — structured 모드
python -m src.tools.label_samples samples/session_xxx/my_bench --roi my_bench

# 골드/레벨 등 — simple 모드 (자유 텍스트)
python -m src.tools.label_samples samples/session_xxx/player_gold --roi player_gold

# 기존 레이블 덮어쓰기
python -m src.tools.label_samples samples/session_xxx/shop_slot_1 --roi shop_slot_1 --overwrite

# 이미지 표시 창 없이 경로만 출력 (SSH/원격 터미널)
python -m src.tools.label_samples samples/session_xxx/shop_slot_2 --roi shop_slot_2 --no-display
```

### 모드별 동작

| 모드 | 대상 ROI | 입력 방식 | 예시 |
|------|---------|----------|------|
| **champion** | `shop_slot_1~5` | 챔피언 이름 1개 | `ahri`, `yasuo`, `unknown` |
| **structured** | `my_board`, `my_bench`, `enemy_board`, `enemy_bench` | 기물 목록: `champ_star,...` | `ahri_2,yasuo_1,lux_unknown` |
| **simple** | `player_gold`, `player_level`, `stage_info`, `player_streak`, `item_area`, `player_list` | 자유 텍스트 1개 | `12`, `2-1`, `3` |

### 레이블링 흐름

1. 도구 실행 → 대상 폴더 내 이미지 파일 스캔
2. 기존 `labels.csv` 로드 → 이미 레이블된 이미지는 건너뜀 (`--overwrite` 시 재입력)
3. ROI에 따라 모드 자동 선택
4. 이미지 하나씩 표시 (cv2 window, 800px 리사이즈)
5. 사용자 입력 → 즉시 `labels.csv`에 저장
6. `Enter` → 해당 이미지 건너뜀 (레이블 미저장)
7. `q` → 지금까지 저장 후 종료
8. `qq` → 즉시 종료 (마지막 레이블 미저장)
9. `Ctrl+C` → 안전하게 종료 (cv2 window 정리)

### CSV 컬럼

| 컬럼 | 설명 |
|------|------|
| `image_path` | 이미지 파일명 (폴더 내 상대 경로) |
| `roi` | ROI 이름 (예: shop_slot_1, my_board) |
| `champion` | 챔피언 이름 (여러 기물은 쉼표分隔) |
| `star_level` | 별 개수 (1/2/3/unknown, 쉼표分隔) |
| `items` | 아이템 (향후 사용) |
| `position` | 보드 위치 (향후 사용) |
| `label` | 사람이 입력한 원본 레이블 |
| `notes` | 추가 메모 (선택) |
| `created_at` | 레이블링 시각 (ISO 8601) |

### 레이블 규칙

| 규칙 | 설명 |
|------|------|
| **챔피언 이름** | 소문자 영어 (예: `ahri`, `yasuo`, `aatrox`, `lee_sin`) |
| **별 개수** | `1`, `2`, `3` 또는 애매하면 `unknown` |
| **모르는 챔피언** | `unknown` 입력 |
| **나쁜 crop** | `bad` 입력 (이미지 품질 불량, 잘린 이미지 등) |
| **보드/벤치 형식** | `챔피언_별개수,챔피언_별개수,...` (예: `ahri_2,yasuo_1`) |
| **빈 보드/벤치** | 그냥 `Enter` 입력 (건너뜀) 또는 `empty` |

### 레이블 예시

| ROI | 입력 | champion | star_level | label |
|-----|------|----------|------------|-------|
| `shop_slot_1` | `ahri` | ahri | | ahri |
| `shop_slot_2` | `unknown` | unknown | | unknown |
| `shop_slot_3` | `bad` | bad | | bad |
| `my_board` | `ahri_2,yasuo_1,lux_unknown` | ahri,yasuo,lux | 2,1,unknown | ahri_2,yasuo_1,lux_unknown |
| `my_bench` | `sett_3` | sett | 3 | sett_3 |
| `player_gold` | `12` | | | 12 |
| `stage_info` | `2-1` | | | 2-1 |

> `labels.csv`는 `samples/` 하위 폴더 내에 생성되며, `.gitignore`에 포함되어
> commit되지 않습니다.

## 지원 ROI 목록

모든 ROI는 `--debug-roi` contact sheet에서 시각적 확인이 가능합니다.

| ROI 이름 | 영역 (1920x1080) | 설명 |
|---------|-----------------|------|
| `item_area` | (0,270)-(110,780) | 좌측 아이템/장비 영역 |
| `player_level` | (260,870)-(470,920) | 레벨 |
| `player_gold` | (910,880)-(1040,920) | 골드 |
| `player_streak` | (1040,870)-(1120,920) | 연승/연패 스트릭 |
| `shop` | (470,920)-(1490,1080) | 상점 카드 5개 (전체) |
| `shop_slot_1` | (470,920)-(674,1080) | 상점 슬롯 1 (204×160) |
| `shop_slot_2` | (674,920)-(878,1080) | 상점 슬롯 2 (204×160) |
| `shop_slot_3` | (878,920)-(1082,1080) | 상점 슬롯 3 (204×160) |
| `shop_slot_4` | (1082,920)-(1286,1080) | 상점 슬롯 4 (204×160) |
| `shop_slot_5` | (1286,920)-(1490,1080) | 상점 슬롯 5 (204×160) |
| `stage_info` | (730,0)-(1180,40) | 라운드/스테이지 정보 |
| `player_list` | (1620,180)-(1920,800) | 상대 목록 (우측) |
| `enemy_bench` | (550,35)-(1350,170) | 상대 벤치 |
| `enemy_board` | (520,95)-(1380,410) | 상대 보드 |
| `my_board` | (450,300)-(1460,730) | 내 보드 |
| `my_bench` | (340,650)-(1560,840) | 내 벤치 |
| `full_screen` | (0,0)-(1920,1080) | 전체 화면 |

> 좌표는 실제 `captures/game/*.png` 이미지로 보정 완료.

## 상점 슬롯 분할

`shop` ROI(470,920)-(1490,1080)는 5개의 챔피언 카드 슬롯으로 자동 분할됩니다.

- `shop` 전체 영역을 5등분 (각 슬롯 204×160)
- 각 슬롯은 개별 폴더에 저장: `crops/shop_slot_1/` ~ `crops/shop_slot_5/`
- OCR/챔피언 이름 인식은 아직 구현 전
- `--debug-roi` contact sheet에서 각 슬롯 crop 결과 확인 가능

## 주의사항
- TFT 게임이 **전체화면(1920x1080)** 또는 **테두리 없는 창모드** 상태여야 함
- 듀얼 모니터일 경우 `--list-monitors`로 TFT 실행 모니터 확인 후 MONITOR_INDEX 설정
- 게임 영역 좌표는 **모니터 절대 좌표** 기준 (--list-monitors로 모니터 left/top 확인)
- `.env`에 캡처 핫키/딜레이/모니터 설정 가능
- 개인 스크린샷, 토큰, API key는 절대 commit 금지
