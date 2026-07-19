# TFT Vision — Screen Capture & ROI Crop MVP 1

## 저장소와 운영 환경

이 저장소는 Windows 캡처 클라이언트의 소스·정적 챔피언 별칭·도구·문서만
관리한다. 미니PC의 `/opt/data/projects/tft-vision`과
`/opt/data/projects/tft`는 동일 커밋을 가진 같은 프로젝트 복제본이며,
GitHub에서는 하나의 `tft-vision` 저장소만 사용한다.

실제 캡처 이미지, crop, 사람이 작성한 labels, 로그, `.env`, 모델 가중치,
학습 데이터셋은 저장소에 포함하지 않는다. `hermes-agent`, `trading-bot`,
Misaka Discord gateway와 실행 의존성은 없다.

## 자동 개발 및 검토 흐름

`codex-auto` 라벨이 붙은 GitHub 이슈는 자동 작업 대상으로 사용한다. 작업은
`origin/main` 기준의 별도 worktree와 작업 브랜치에서 진행하며, 로컬 검증을
통과한 변경만 원격 브랜치에 push하고 Draft PR로 제출한다.

```text
codex-auto 이슈
→ 별도 worktree/브랜치에서 구현
→ 로컬 검증
→ 작업 브랜치 push
→ Draft PR 생성
→ Codex 코드 검토
→ GATE_GO 또는 NEEDS_HUMAN
→ Host가 현재 reviewed head의 GitHub native squash auto-merge 적격성 확인
→ GitHub ruleset과 required checks가 병합 통제
→ MERGED → DEPLOYMENT_REQUIRED → POST_MERGE_VERIFYING → OPERATIONALLY_VERIFIED
```

Codex 검토는 중대한 문제를 찾는 보조 절차이며 모든 결함이 없음을 보장하지
않는다. 현재 default-branch 정책은 `merge.enabled: true`, `method: squash`,
`admin_bypass: false`이다. Codex는 병합을 수행하거나 auto-merge를 등록하지
않는다. 모든 Host 테스트·리뷰·head SHA·보호 규칙이 충족된 경우에만 Host
runner가 GitHub native auto-merge를 등록할 수 있고, 최종 병합은 GitHub ruleset과
required checks가 통제한다. `MERGED`는 배포나 Windows 실행 검증 완료를
의미하지 않는다. 자동 배포는 수행하지 않는다.

작업 티켓·설계 결정·리뷰 증거·병합 후 수동 검증은 다음 문서를 따른다.

- [시스템 개요](docs/architecture/system-overview.md)
- [안전 경계](docs/architecture/safety-boundaries.md)
- [AI 작업 티켓 템플릿](docs/plans/WORK-TICKET-TEMPLATE.md)
- [Epic #4 의존성 그래프](docs/plans/EPIC-4-DEPENDENCY-GRAPH.md)
- [리뷰 패키지 규격](docs/review/REVIEW-PACKAGE-SPEC.md)
- [병합 후 운영 검증](docs/operations/POST-MERGE-VERIFICATION.md)

### 로컬 검증

```powershell
python -m compileall -q src
python -m src.capture_loop --help
```

화면 캡처 검증에는 Windows 데스크톱이 필요하다. Headless Linux 환경에서는
위 명령과 정적 검증을 실행할 수 있지만 Windows 화면 캡처가 성공했다고
간주해서는 안 된다.

### 오프라인 상태 스냅샷

저장된 ROI crop은 캡처 기능을 실행하지 않고 구조화된 JSON으로 확인할 수 있다.
입력 디렉터리에는 `player_gold.png`처럼 ROI 이름과 같은 이미지 파일을 두거나,
`player_gold/` 하위에 지원 이미지 하나를 둔다. 확장자는 PNG, JPG, JPEG이며 한
ROI에서 여러 후보가 발견되면 해당 ROI는 안전하게 `unavailable`로 표시된다.

```powershell
python -m src.analyze_crops --input-dir crops --pretty
python -m src.analyze_crops --input-dir samples/session_xxx/frame_0001 --output state.json
```

기본 `analyze_crops` 호출은 실제 OCR이나 모델 추론을 수행하지 않는다. 숫자 HUD는
로컬 Tesseract 실행 파일을 명시적으로 사용하는 별도 검사 명령으로 확인한다.

### 골드·레벨 오프라인 OCR 검사

`player_gold.png`와 `player_level.png`가 있는 입력 디렉터리를 지정하면 원본 crop,
결정적 OpenCV 전처리 이미지, OCR 원문, 파싱 값과 상태를 JSON 및 단일 HTML에서
대조할 수 있다. Tesseract는 자동 설치되지 않으며 기본적으로 PATH에서 찾는다.

```powershell
python -m src.inspect_hud_ocr --input-dir D:\tft-samples\frame_0001 --output-dir D:\tft-samples\frame_0001\ocr-review
python -m src.inspect_hud_ocr --input-dir crops --output-dir ocr-review --tesseract-cmd C:\Tools\Tesseract-OCR\tesseract.exe
```

결과 디렉터리에는 `result.json`, `report.html`, `debug/`가 생성된다. 결과물과 실제
crop은 저장소에 커밋하지 않는다. 실행 파일 누락은 `unavailable`, 실행 실패나
timeout은 `error`, 빈 문자열·범위 밖 값은 `unknown`으로 남아 값을 추측하지 않는다.

### 로컬 게임플레이 영상 수집

직접 보유하거나 사용 허가를 받은 로컬 MP4, MKV, MOV, WebM 영상은 일정 간격의
프레임과 provenance manifest, 사람이 편집할 초기 라벨 JSON으로 변환할 수 있다.
다운로드나 네트워크 접근은 수행하지 않으며 출력 경로는 저장소 밖을 사용한다.

```powershell
python -m src.ingest_video --input D:\videos\game_001.mp4 --output-dir D:\datasets\game_001 --interval-seconds 2 --source-id game_001 --usage-rights owned --pretty
```

기본적으로 비어 있지 않은 출력 디렉터리는 거부한다. `--overwrite`는 이전
manifest가 기록한 프레임과 이 도구의 manifest/labels만 교체하고 다른 파일은
보존한다. `--dedupe-threshold`를 지정하면 연속 프레임의 축소 grayscale 평균
차이가 임계값 이하일 때 선택적으로 건너뛴다.

### 오프라인 프레임 리뷰

영상 데이터셋의 `manifest.json`, `labels.json`, 선택적인 `analyses.jsonl`을
외부 네트워크나 CDN 없이 열 수 있는 단일 HTML 갤러리로 만들 수 있다. 분석
레코드가 아직 없으면 관찰 내용을 추측하지 않는 `pending` 레코드를 먼저 만든다.

```powershell
python -m src.build_review_report --dataset-dir D:\datasets\game_001 --output D:\datasets\game_001\review.html
```

`--output`은 데이터셋 디렉터리 내부의 HTML 파일 경로여야 한다. `manifest.json`,
`labels.json`, 분석 JSONL 파일 또는 manifest에 기록된 프레임 이미지 경로와 같을
수 없다.

템플릿 설명 생성기는 결정적인 한국어 문장을 만들며, 후속 로컬 분석기는
`FrameAnalysisRecord`에 자체 설명과 출처를 저장할 수 있다. 이미지, 분석 JSONL,
HTML 결과는 저장소가 아닌 데이터셋 출력 디렉터리에 보관한다.
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
# ├── data/                # 챔피언 매핑 등 정적 데이터
# │   └── champion_aliases.json  # 한글→영문 챔피언명 매핑
# ├── tools/               # CLI 도구
# │   ├── label_samples.py # 수동 데이터 레이블링 (이미지 전체)
# │   ├── label_units.py   # Unit-level 라벨링 (체력바 클릭)
# │   └── dedupe_samples.py# 샘플 중복 제거 (SHA256 + perceptual hash)
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
# | `--hotkey KEY` | 핫키 캡처 모드: KEY를 누를 때 1장 캡처 (예: d), q=종료, Esc=즉시종료 |
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
# ## 핫키 캡처 모드 (--hotkey)
#
# `--hotkey` 옵션으로 게임 플레이 중 특정 키를 누를 때마다 자동으로 캡처합니다.
# **프로그램이 키를 대신 누르지 않습니다** — 사용자가 직접 누른 키를 감지해서 캡처만 합니다.
# 자동 리롤/자동 구매/자동 클릭 기능은 없습니다.
#
# ```powershell
# # D 키를 누를 때마다 1장 캡처 (게임 영역 + 샘플 수집)
# python -m src.capture_loop --monitor 2 --game-region 320,180,1920,1080 --sample-run --hotkey d
#
# # 다른 키로 캡처 (예: F5)
# python -m src.capture_loop --monitor 2 --sample-run --hotkey f5
# ```
#
# > ⚠️ `--hotkey`는 `--manual`과 동시에 사용할 수 없습니다.
#
# ### 동작 방식
#
# - **pynput** 글로벌 키 리스너 사용 — 게임 창이 포커스된 상태에서도 키 감지 가능
# - 백그라운드 스레드에서 키 입력을 감지하고 메인 루프에 이벤트 전달
# - `D` 키 누름 → 1회 캡처 (300ms 디바운스)
# - `q` 키 → 저장 후 종료
# - **Esc** → 즉시 종료
# - `--interval`, `--count` 옵션은 무시됨 (사용자 키 입력 기반)
# - `--sample-run`, `--debug-roi`와 함께 사용 가능
# - 자동 조작/판단 기능 없음 — 순수 캡처 도구
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
# 단일 폴더 (기존 방식)
python -m src.tools.label_samples samples/session_xxx/shop_slot_1 --roi shop_slot_1

# 상점 5개 슬롯 통합 라벨링 (--shop)
python -m src.tools.label_samples samples/session_xxx --shop

# 여러 폴더를 명시적으로 지정
python -m src.tools.label_samples samples/xxx/shop_slot_1 samples/xxx/shop_slot_2 samples/xxx/shop_slot_3 samples/xxx/shop_slot_4 samples/xxx/shop_slot_5 --roi shop_card

# 내 보드 — structured 모드
python -m src.tools.label_samples samples/session_xxx/my_board --roi my_board

# 골드/레벨 등 — simple 모드
python -m src.tools.label_samples samples/session_xxx/player_gold --roi player_gold

# 기존 레이블 덮어쓰기
python -m src.tools.label_samples samples/session_xxx/shop_slot_1 --roi shop_slot_1 --overwrite

# 이미지 표시 창 없이 경로만 출력 (SSH/원격 터미널)
python -m src.tools.label_samples samples/session_xxx/shop_slot_2 --roi shop_slot_2 --no-display
```

### 상점 통합 라벨링 (`--shop`)

상점 카드 인식 학습을 위해 `shop_slot_1~5`를 하나의 `shop_card` 데이터셋으로 취급합니다.

```powershell
# 세션 폴더 아래 shop_slot_1~5를 모두 스캔하여 통합 라벨링
python -m src.tools.label_samples samples/session_20260704_153000 --shop
```

- 5개 슬롯의 이미지를 섞어서 한 번에 라벨링
- CSV는 세션 폴더 아래 `labels_shop_card.csv`에 저장
- `roi` = `shop_card` (모든 슬롯 동일)
- `slot` 컬럼에 원래 슬롯 번호(1~5) 보존
- 개별 `shop_slot_N/labels.csv`는 건드리지 않음 (폴더 구조 유지)
- 학습 시 `labels_shop_card.csv`만 불러오면 5개 슬롯 전체 데이터셋 사용 가능
- 실제 게임 판단(슬롯 위치 기반 로직)에는 개별 폴더 구조 활용

### 모드별 동작

| 모드 | 대상 ROI | 입력 방식 | 예시 |
|------|---------|----------|------|
| **champion** | `shop_slot_*`, `shop_card` | 챔피언 이름 1개 (한글/영문) | `아리`, `야스오`, `모름` |
| **structured** | `my_board`, `my_bench`, `enemy_board`, `enemy_bench` | 기물 목록: `이름_별,...` | `아리_2,야스오_1,럭스_unknown` |
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
| `image_path` | 이미지 파일명 (폴더 내 상대 경로, 예: shop_slot_1/xxx.png) |
| `roi` | ROI 이름 (예: shop_card, shop_slot_1, my_board) |
| `slot` | 슬롯 번호 (shop_card 통합 시 1~5, 단일 폴더시 빈값) |
| `champion` | 챔피언 이름 (영문 canonical id, 여러 기물은 쉼표分隔) |
| `star_level` | 별 개수 (1/2/3/unknown, 쉼표分隔) |
| `items` | 아이템 (향후 사용) |
| `position` | 보드 위치 (향후 사용) |
| `label_raw` | 사람이 입력한 원본 레이블 (한글 원문 보존) |
| `label_normalized` | 정규화된 레이블 (영문 ID, special 값) |
| `notes` | 추가 메모 (선택) |
| `created_at` | 레이블링 시각 (ISO 8601) |

### 레이블 규칙

| 규칙 | 설명 |
|------|------|
| **챔피언 이름** | 한글 또는 영문 소문자 (예: `아리` / `ahri`, `리 신` / `leesin`) |
| **별 개수** | `1`, `2`, `3` 또는 애매하면 `unknown` |
| **모르는 챔피언** | `모름` 입력 → 자동 `unknown` 정규화 |
| **나쁜 crop** | `잘못됨` 입력 → 자동 `bad` 정규화 |
| **보드/벤치 형식** | `이름_별개수,이름_별개수,...` (예: `아리_2,야스오_1`) |
| **빈 보드/벤치** | 그냥 `Enter` 입력 (건너뜀) |

### 한글 입력 정규화

한글로 입력한 챔피언명은 `src/data/champion_aliases.json` 매핑을 통해
내부적으로 영문 canonical id로 정규화됩니다.

| 입력 (한글) | 정규화 (영문) |
|------------|--------------|
| `아리` | `ahri` |
| `야스오` | `yasuo` |
| `리 신` | `leesin` |
| `모름` | `unknown` |
| `잘못됨` | `bad` |
| `아리_2,야스오_1` | `ahri_2,yasuo_1` |

> CSV에는 **두 값 모두 저장**됩니다: `label_raw`(한글 원문), `label_normalized`(영문 정규화).
> 매핑되지 않은 이름은 원본이 그대로 보존됩니다.
> `champion_aliases.json`은 부분 매핑이며, 라벨링 작업 중 필요시 확장합니다.

### 레이블 예시

| ROI | 입력 (label_raw) | champion | star_level | label_normalized |
|-----|------|----------|------------|-------|
| `shop_slot_1` | `아리` | ahri | | ahri |
| `shop_slot_2` | `모름` | unknown | | unknown |
| `shop_slot_3` | `잘못됨` | bad | | bad |
| `my_board` | `아리_2,야스오_1,럭스_unknown` | ahri,yasuo,lux | 2,1,unknown | ahri_2,yasuo_1,lux_unknown |
| `my_bench` | `세트_3` | sett | 3 | sett_3 |
| `player_gold` | `12` | | | 12 |
| `stage_info` | `2-1` | | | 2-1 |

> `labels.csv`는 `samples/` 하위 폴더 내에 생성되며, `.gitignore`에 포함되어
> commit되지 않습니다.

## Unit-level 보드/벤치 라벨링 (label_units)

보드/벤치 crop 이미지에서 기물의 **체력바 중심**을 클릭하여 unit-level 데이터를 수집합니다.
직접 찍은 좌표는 이후 자동 체력바 감지 모델의 학습 데이터로 활용됩니다.

```powershell
# 내 보드 라벨링
python -m src.tools.label_units samples/session_xxx/my_board --roi my_board

# 내 벤치 라벨링
python -m src.tools.label_units samples/session_xxx/my_bench --roi my_bench

# 상대 보드/벤치
python -m src.tools.label_units samples/session_xxx/enemy_board --roi enemy_board
python -m src.tools.label_units samples/session_xxx/enemy_bench --roi enemy_bench
```

### 조작법

| 입력 | 동작 |
|------|------|
| **좌클릭** | 체력바 중심 좌표 선택 → 터미널에서 정보 입력 |
| **n** | 현재 이미지 완료 후 다음 이미지 |
| **q** | 저장 후 종료 |
| **Esc** | 즉시 종료 |
| **u** (터미널) | 마지막 입력 취소 |

### 라벨링 흐름

1. 이미지가 OpenCV 창에 표시됨
2. 기물의 **체력바 중심** (초록색 막대 가운데)을 좌클릭
3. 터미널에서 순서대로 입력
4. champion: 한글/영문 챔피언명 (Enter=취소, u=undo)
5. star_level: 1 / 2 / 3 / unknown
6. items: 아이템 (쉼표로 여러 개, 없으면 Enter)
7. notes: 메모 (선택)
8. 저장 후 같은 이미지에서 계속 클릭 가능
9. 모든 기물을 클릭했으면 `n` 입력 (또는 키보드 n)
10. 직전 입력 실수 시 champion 프롬프트에서 `u` 입력

### CSV 컬럼

| 컬럼 | 설명 |
|------|------|
| `image_path` | 이미지 파일명 |
| `roi` | ROI 이름 |
| `champion_raw` | 사용자 입력 원본 (한글 보존) |
| `champion_normalized` | 정규화된 영문 ID |
| `star_level` | 별 개수 (1/2/3/unknown) |
| `healthbar_x` | 체력바 중심 X 좌표 (원본 해상도) |
| `healthbar_y` | 체력바 중심 Y 좌표 (원본 해상도) |
| `items` | 아이템 (쉼표 구분) |
| `notes` | 추가 메모 |
| `created_at` | 라벨링 시각 |

> ⚠️ **중요: 기물 몸통이 아니라 체력바 중심을 클릭해야 합니다.**
> 체력바는 기물 상단에 있는 초록색 막대로, 그 막대의 정중앙을 클릭합니다.
> 이후 자동 체력바 감지 모델 학습에 이 좌표가 사용됩니다.
> 정확성이 애매하면 가급적 체력바 범위 내에서 중앙에 가깝게 클릭합니다.

### `label_samples` vs `label_units` 비교

| 항목 | label_samples | label_units |
|------|--------------|-------------|
| 대상 ROI | shop_card, player_gold, stage_info 등 | my_board, my_bench, enemy_board, enemy_bench |
| 입력 방식 | 텍스트로 기재 | 체력바 클릭 + 텍스트 |
| 레이블 단위 | 이미지 전체 | 이미지 내 개별 기물 |
| 좌표 | 없음 | healthbar_x, healthbar_y |
| 주 용도 | OCR/숫자 인식 | 기물 위치 + 속성 인식 |

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
# - `--debug-roi` contact sheet에서 각 슬롯 crop 결과 확인 가능
#
# ## 샘플 중복 제거 (dedupe_samples)
#
# 수집된 샘플 데이터에서 중복 이미지를 정리합니다.
# **라벨링 완료된 이미지는 기본적으로 보호**됩니다 (--include-labeled로 해제).
#
# ### 사용법
#
# ```powershell
# # Dry-run (기본)
# python -m src.tools.dedupe_samples samples/session_xxx
#
# # 중복 파일 이동
# python -m src.tools.dedupe_samples samples/session_xxx --move-duplicates
#
# # 상점 통합 중복 검사
# python -m src.tools.dedupe_samples samples/session_xxx --shop --move-duplicates
#
# # 라벨링된 이미지도 포함
# python -m src.tools.dedupe_samples samples/session_xxx --move-duplicates --include-labeled
#
# # 임계값 조정 (기본 5)
# python -m src.tools.dedupe_samples samples/session_xxx --threshold 10
# ```
#
# ### 중복 판정
#
# | 단계 | 방식 | 설명 |
# |------|------|------|
# | 1차 | SHA256 | 완전 동일 파일 검출 |
# | 2차 | Average hash | 8×8 축소 → 평균 기반 유사도 |
#
# - `--threshold 0`: exact match만
# - `--threshold 5` (기본): 약간 차이까지 유사 중복
# - OpenCV 미설치 시 SHA256만 동작 (fallback)
#
# ### --shop 옵션
# shop_slot_1~5를 shop_card로 통합하여 중복 검사.
# 같은 챔피언 카드가 여러 슬롯에 중복 수집된 경우 검출.
#
# ### 라벨 보호
# - labels.csv 등록 이미지는 이동하지 않음 (기본)
# - `--include-labeled`로 해제 가능
#
# ### 동작
# - 기본 dry-run: 출력만 + duplicates_report.csv 저장
# - `--move-duplicates`: `_duplicates/ROI_NAME/`로 이동
#
# ### 리포트 컬럼
# original_path, duplicate_path, roi, similarity_score, action, created_at
#
# > samples/와 _duplicates/는 .gitignore로 보호됩니다.
#
# ## 주의사항
# - TFT 게임이 **전체화면(1920x1080)** 또는 **테두리 없는 창모드** 상태여야 함
# - 듀얼 모니터일 경우 `--list-monitors`로 TFT 실행 모니터 확인 후 MONITOR_INDEX 설정
- 게임 영역 좌표는 **모니터 절대 좌표** 기준 (--list-monitors로 모니터 left/top 확인)
- `.env`에 캡처 핫키/딜레이/모니터 설정 가능
- 개인 스크린샷, 토큰, API key는 절대 commit 금지
