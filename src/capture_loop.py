#!/usr/bin/env python3
"""
TFT Vision MVP 1 — Capture + ROI Crop.

사용법:
    Windows 노트북에서:
        python -m src.capture_loop --interval 1.0 --count 10

    외부 모니터 게임 캡처:
        python -m src.capture_loop --monitor 2 --game-region 320,180,1920,1080 --preview

    캡처만:
        python -m src.capture_loop --capture-only
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


def _load_dotenv():
    """.env 파일 로드 (없으면 무시)."""
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass


def _resolve_monitor_index(args) -> int:
    """모니터 인덱스 결정: --monitor > .env MONITOR_INDEX > 기본 1."""
    if args.monitor is not None:
        return args.monitor
    _load_dotenv()
    env_val = os.environ.get("MONITOR_INDEX") or os.getenv("MONITOR_INDEX")
    if env_val is not None:
        try:
            return int(env_val)
        except (ValueError, TypeError):
            pass
    return 1


def _resolve_game_region(args) -> tuple | None:
    """게임 영역 결정: --game-region > .env GAME_REGION_* > None."""
    if args.game_region is not None:
        from src.crop.game_region import GameRegionCropper
        return GameRegionCropper.parse_region(args.game_region)
    _load_dotenv()
    from src.crop.game_region import GameRegionCropper
    return GameRegionCropper.load_from_env()


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
    parser.add_argument(
        "--game-region", type=str, default=None,
        help="게임 영역 LEFT,TOP,WIDTH,HEIGHT (예: 320,180,1920,1080). "
             "설정 시 모니터 전체 대신 게임 영역만 crop 후 ROI 분석",
    )
    args = parser.parse_args()

    # 모니터 인덱스 및 게임 영역 결정
    monitor_index = _resolve_monitor_index(args)
    game_region = _resolve_game_region(args)

    # Windows 환경 확인
    try:
        from src.capture.screen_capture import ScreenCapture, ScreenCaptureError
    except ImportError:
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
        print()
        if game_region:
            l, t, w, h = game_region
            print(f"Game region: ({l},{t}) {w}x{h} (from .env GAME_REGION_*)")
        sys.exit(0)

    try:
        cap = ScreenCapture(monitor_index=monitor_index, save_dir="captures")
        monitor_info = cap._get_monitor_info()
        logger.info(
            "MVP 1 시작 | monitor=%d (%dx%d) interval=%.1fs count=%s preview=%s",
            monitor_index,
            monitor_info["width"],
            monitor_info["height"],
            args.interval,
            "∞" if args.count == 0 else str(args.count),
            args.preview,
        )

        # Game region crop 준비
        game_cropper = None
        if game_region:
            from src.crop.game_region import GameRegionCropper
            l, t, w, h = game_region
            game_cropper = GameRegionCropper(
                left=l, top=t, width=w, height=h,
                save_dir="captures/game",
            )
            logger.info(
                "Game region active | monitor=%dx%d → game=(%d,%d) %dx%d",
                monitor_info["width"], monitor_info["height"],
                l, t, w, h,
            )

        # ROI crop 준비
        if not args.capture_only:
            from src.crop.cropper import ROICropper
            cropper = ROICropper(base_dir="crops")

        count = 0
        while args.count == 0 or count < args.count:
            count += 1

            # 1) 전체 모니터 캡처
            img, full_path = cap.capture_and_save()
            frame_for_roi = img

            # 2) Game region crop (설정된 경우)
            game_path = None
            if game_cropper is not None:
                try:
                    game_frame, game_path = game_cropper.crop_and_save(img)
                    frame_for_roi = game_frame
                    logger.info(
                        "[%d/%s] Game frame: %s (%dx%d)",
                        count, args.count or "∞",
                        game_path, game_frame.shape[1], game_frame.shape[0],
                    )
                except Exception as e:
                    logger.warning("Game region crop failed: %s — falling back to full frame", e)
                    frame_for_roi = img

            if args.no_save:
                logger.info("[%d/%s] Captured (no-save) | game_region=%s",
                            count, args.count or "∞", bool(game_cropper))
            else:
                logger.info(
                    "[%d/%s] Captured: %s%s",
                    count, args.count or "∞",
                    full_path,
                    f" game={game_path}" if game_path else "",
                )

            # 3) ROI crop (game frame 또는 전체 모니터 기준)
            if not args.capture_only:
                crops = cropper.crop_and_save(frame_for_roi)
                for name, crop_path in crops.items():
                    logger.debug("  ROI %s: %s", name, crop_path)

                # Preview
                if args.preview:
                    for name, img_crop in cropper.crop_all(frame_for_roi).items():
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
