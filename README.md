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
# ### 3. 실행
# ```powershell
# # 1) 캡처 저장만 (기본)
# python -m src.capture.screen_capture
#
# # 2) ROI crop까지
# python -m src.crop.cropper
# ```
#
# ## 캡처 저장 경로
# - 원본: `captures/YYYYMMDD_HHMMSS.png`
# - ROI: `crops/{roi_name}/YYYYMMDD_HHMMSS.png`
#
# ## 주의사항
# - TFT 게임이 **전체화면(1920x1080)** 또는 **창모드(최대화)** 상태여야 함
# - `.env`에 캡처 핫키/딜레이/모니터 설정 가능
# - 개인 스크린샷, 토큰, API key는 절대 commit 금지
