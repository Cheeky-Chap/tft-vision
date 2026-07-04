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
# │   │   └── cropper.py
# │   └── config/           # 설정
# │       └── settings.py
# ├── captures/             # 원본 캡처 (git 제외)
# ├── crops/                # ROI crop 결과 (git 제외)
# ├── logs/                 # 실행 로그 (git 제외)
# ├── requirements.txt
# ├── .gitignore
# └── README.md
# ```
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
# ### 5. 실행
# ```powershell
# # 1) 캡처 저장만 (기본)
# python -m src.capture.screen_capture
#
# # 2) ROI crop까지
# python -m src.crop.cropper
#
# # 3) 캡처 루프 (1회, ROI crop 포함)
# python -m src.capture_loop
#
# # 4) 연속 캡처 (10회, 2초 간격)
# python -m src.capture_loop --interval 2.0 --count 10
#
# # 5) ROI 미리보기 표시
# python -m src.capture_loop --preview
# ```
#
# ## 캡처 저장 경로
# - 원본: `captures/YYYYMMDD_HHMMSS.png`
# - ROI: `crops/{roi_name}/YYYYMMDD_HHMMSS.png`
#
# ## 명령줄 옵션
# | 옵션 | 설명 |
# |------|------|
# | `--list-monitors` | 사용 가능한 모니터 목록 출력 |
# | `--monitor INDEX` | 캡처할 모니터 인덱스 (기본: .env의 MONITOR_INDEX 또는 1) |
# | `--interval SEC` | 캡처 간격 초 단위 (기본 1.0) |
# | `--count N` | 캡처 횟수 (기본 1, 0=무한) |
# | `--capture-only` | ROI crop 없이 원본만 저장 |
# | `--preview` | ROI crop 결과 창 표시 |
# | `--no-save` | 저장 없이 메모리만 처리 |
#
# ## 주의사항
# - TFT 게임이 **전체화면(1920x1080)** 또는 **창모드(최대화)** 상태여야 함
# - 듀얼 모니터일 경우 `--list-monitors`로 TFT 실행 모니터 확인 후 MONITOR_INDEX 설정
# - `.env`에 캡처 핫키/딜레이/모니터 설정 가능
# - 개인 스크린샷, 토큰, API key는 절대 commit 금지
