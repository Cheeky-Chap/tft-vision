#!/usr/bin/env python3
"""
TFT Vision MVP 1 — Capture + ROI Crop.

사용법:
    Windows 노트북에서:
        python -m src.capture_loop --interval 1.0 --count 10

    캡처만:
        python -m src.capture_loop --capture-only

    ROI 확인 (preview):
        python -m src.capture_loop --preview
"""

import argparse
import logging
import time
import sys
import os
from datetime import datetime
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s %(message)s",
)
logger = logging.getLogger("tft-vision")


def main():
    parser = argparse.ArgumentParser(description="TFT Vision MVP 1 — Capture & ROI Crop")
    parser.add_argument(
        "--list-monitors", action="store_true",
        help="사용 가능한 모니터 목록 출력 (index, 좌표, 해상도)",
    )
    parser.add_argument(
        "--interval", type=float, default=1.0,
        help="캡처 간격 (초, 기본 1.0)",
    )
    parser.add_argument(
        "--count", type=int, default=1,
        help="캡처 횟수 (기본 1, 0=무한)",
    )
    parser.add_argument(
        "--capture-only", action="store_true",
        help="ROI crop 없이 원본 캡처만 저장",
    )
    parser.add_argument(
        "--preview", action="store_true",
        help="ROI crop 결과를 창으로 표시 (디버그용)",
    )
    parser.add_argument(
        "--no-save", action="store_true",
        help="저장하지 않고 메모리만 처리",
    )
    parser.add_argument(
        "--monitor", type=int, default=None,
        help="캡처할 모니터 인덱스 (기본: .env의 MONITOR_INDEX 또는 1)",
    )
    args = parser.parse_args()

    # 모니터 인덱스 결정: --monitor > .env MONITOR_INDEX > 기본 1
    monitor_index = args.monitor
    if monitor_index is None:
        try:
            from dotenv import load_dotenv
            load_dotenv()
        except ImportError:
            pass
        env_val = os.environ.get("MONITOR_INDEX") or os.getenv("MONITOR_INDEX")
        if env_val is not None:
            try:
                monitor_index = int(env_val)
            except (ValueError, TypeError):
                monitor_index = 1
        else:
            monitor_index = 1

    # Windows 환경 확인
    try:
        from src.capture.screen_capture import ScreenCapture, ScreenCaptureError
    except ImportError as e:
        logger.error(
            "Windows 전용 모듈을 불러올 수 없습니다.\n"
            "Windows 노트북에서 실행하세요:\n"
            "  cd tft-vision\n"
            "  .venv\Scripts\Activate.ps1\n"
            "  pip install -r requirements.txt\n"
            "  python -m src.capture_loop"
        )
        sys.exit(1)

    # --list-monitors: 모니터 목록 출력 후 종료
    if args.list_monitors:
        monitors = ScreenCapture.list_monitors()
        print(f"\n{'Index':>5}  {'Left':>5}  {'Top':>5}  {'Width':>6}  {'Height':>6}  Name")
        print(f"{'─'*5}  {'─'*5}  {'─'*5}  {'─'*6}  {'─'*6}  {'─'*30}")
        for m in monitors:
            print(
                f"{m['index']:>5}  {m['left']:>5}  {m['top']:>5}  "
                f"{m['width']:>6}  {m['height']:>6}  {m['name']}"
            )
        print()
        print("TIP: .env 파일에서 MONITOR_INDEX 값을 바꿔서 캡처할 모니터를 선택하세요.")
        print("     MONITOR_INDEX=1 → 첫 번째 모니터 (기본)")
        print("     MONITOR_INDEX=2 → 두 번째 모니터")
        print("     MONITOR_INDEX=0 → 전체 가상 데스크톱 (모든 모니터)")
        sys.exit(0)

    try:
        cap = ScreenCapture(monitor_index=monitor_index, save_dir="captures")
        logger.info(
            "MVP 1 시작 | monitor=%d interval=%.1fs count=%s preview=%s",
            monitor_index,
            args.interval,
            "∞" if args.count == 0 else str(args.count),
            args.preview,
        )

        if not args.capture_only:
            from src.crop.cropper import ROICropper
            cropper = ROICropper(base_dir="crops")

        count = 0
        while args.count == 0 or count < args.count:
            count += 1

            # 캡처
            img, path = cap.capture_and_save()
            logger.info("[%d/%s] Captured: %s", count, args.count or "∞", path)

            # ROI crop
            if not args.capture_only:
                crops = cropper.crop_and_save(img)
                for name, crop_path in crops.items():
                    logger.debug("  ROI %s: %s", name, crop_path)

                # Preview
                if args.preview:
                    for name, img_crop in cropper.crop_all(img).items():
                        import cv2
                        cv2.imshow(f"ROI: {name}", img_crop)
                    cv2.waitKey(1)

            # 다음 캡처까지 대기
            if args.count == 0 or count < args.count:
                time.sleep(args.interval)

        logger.info("MVP 1 완료 — 총 %d 캡처", count)

    except KeyboardInterrupt:
        logger.info("사용자 중단")
    except Exception as e:
        logger.exception("치명적 오류: %s", e)
        sys.exit(1)
    finally:
        if args.preview:
            import cv2
            cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
