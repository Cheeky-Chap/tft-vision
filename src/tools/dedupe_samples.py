#!/usr/bin/env python3
"""TFT Vision — 샘플 중복 제거 도구.

수집된 샘플 데이터에서 완전 중복(SHA256) 및 유사 중복(average hash)을
검출하여 정리합니다. ROI별로 검사하며 --shop 옵션으로 shop_slot_1~5를
통합 검사할 수 있습니다.

사용법:
    # Dry-run (기본)
    python -m src.tools.dedupe_samples samples/session_xxx

    # 중복 파일 이동
    python -m src.tools.dedupe_samples samples/session_xxx --move-duplicates

    # 상점 5개 슬롯 통합 중복 검사 + 이동
    python -m src.tools.dedupe_samples samples/session_xxx --shop --move-duplicates

    # 임계값 조정 (유사도 민감도, 기본 5)
    python -m src.tools.dedupe_samples samples/session_xxx --threshold 10

    # 라벨링된 이미지도 포함
    python -m src.tools.dedupe_samples samples/session_xxx --move-duplicates --include-labeled
"""

import argparse
import csv
import hashlib
import logging
import sys
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s %(message)s",
)
logger = logging.getLogger("tft-vision.dedupe_samples")

# 샘플 수집 대상 ROI (sample_collector.SAMPLE_ROIS와 동일)
SAMPLE_ROIS = [
    "shop_slot_1",
    "shop_slot_2",
    "shop_slot_3",
    "shop_slot_4",
    "shop_slot_5",
    "player_gold",
    "player_level",
    "player_streak",
    "stage_info",
    "item_area",
    "player_list",
    "enemy_board",
    "enemy_bench",
    "my_board",
    "my_bench",
]

SHOP_SLOTS = {"shop_slot_1", "shop_slot_2", "shop_slot_3", "shop_slot_4", "shop_slot_5"}
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tiff"}

REPORT_FIELDS = [
    "original_path",
    "duplicate_path",
    "roi",
    "similarity_score",
    "action",
    "created_at",
]


# ── 해시 함수 ──────────────────────────────────────────────────


def sha256_hash(filepath: Path) -> str:
    """파일의 SHA256 해시."""
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def average_hash(filepath: Path, hash_size: int = 8) -> str:
    """OpenCV 기반 average hash.

    이미지를 hash_size×hash_size로 리사이즈 → 그레이스케일 → 평균 →
    각 픽셀 > 평균 → 1, else → 0 → 64비트 hex 문자열.

    cv2를 사용할 수 없으면 빈 문자열 반환 (SHA256 exact match만 동작).
    """
    try:
        import cv2
    except ImportError:
        return ""

    img = cv2.imread(str(filepath))
    if img is None:
        return ""
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    resized = cv2.resize(gray, (hash_size, hash_size), interpolation=cv2.INTER_AREA)
    avg = resized.mean()
    bits = (resized > avg).flatten()
    # 64비트를 hex 문자열로
    hex_str = ""
    for i in range(0, len(bits), 4):
        nibble = 0
        for j in range(4):
            if i + j < len(bits) and bits[i + j]:
                nibble |= 1 << (3 - j)
        hex_str += hex(nibble)[2:]
    return hex_str


def hamming_distance(hash1: str, hash2: str) -> int:
    """두 hex hash 문자열의 해밍 거리."""
    if not hash1 or not hash2:
        return 999
    max_len = max(len(hash1), len(hash2))
    # hex 문자열 → 바이너리 확장
    b1 = bin(int(hash1, 16))[2:].zfill(max_len * 4)
    b2 = bin(int(hash2, 16))[2:].zfill(max_len * 4)
    return sum(1 for a, b in zip(b1, b2) if a != b)


# ── 이미지 수집 ────────────────────────────────────────────────


def scan_session(session_dir: Path) -> dict[str, list[Path]]:
    """세션 폴더를 스캔하여 ROI별 이미지 목록 반환.

    Returns:
        {roi_name: [image_path, ...]}
    """
    rois: dict[str, list[Path]] = {}
    for subdir in sorted(session_dir.iterdir()):
        if not subdir.is_dir():
            continue
        name = subdir.name
        if name.startswith("_") or name.startswith("."):
            continue
        images = sorted(
            p for p in subdir.iterdir()
            if p.suffix.lower() in IMAGE_EXTS
        )
        if images:
            rois[name] = images
    return rois


def load_labeled_images(session_dir: Path) -> set[str]:
    """세션 폴더에서 기존 labels.csv/labels_shop_card.csv에
    등록된 이미지 경로(상대 경로)를 수집.

    Returns:
        {"shop_slot_1/xxx.png", "shop_slot_2/yyy.png", ...}
    """
    labeled: set[str] = set()

    # 개별 ROI 폴더의 labels.csv
    for roi_dir in session_dir.iterdir():
        if not roi_dir.is_dir():
            continue
        csv_path = roi_dir / "labels.csv"
        if csv_path.exists():
            with open(csv_path, "r", newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    img_path = row.get("image_path", "").strip()
                    if img_path:
                        labeled.add(img_path)

    # 통합 shop_card labels
    shop_csv = session_dir / "labels_shop_card.csv"
    if shop_csv.exists():
        with open(shop_csv, "r", newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                img_path = row.get("image_path", "").strip()
                if img_path:
                    labeled.add(img_path)

    return labeled


# ── ROI 그룹 구성 ──────────────────────────────────────────────


def build_roi_groups(
    rois: dict[str, list[Path]], shop_mode: bool,
) -> list[tuple[str, list[Path]]]:
    """ROI 그룹 목록 구성.

    shop_mode=True면 shop_slot_1~5를 'shop_card' 하나로 통합.
    Returns:
        [("shop_card", [...]), ("player_gold", [...]), ...]
    """
    groups: list[tuple[str, list[Path]]] = []

    if shop_mode:
        shop_images: list[Path] = []
        for slot_name in [f"shop_slot_{i}" for i in range(1, 6)]:
            if slot_name in rois:
                shop_images.extend(rois[slot_name])
        if shop_images:
            groups.append(("shop_card", shop_images))

        # shop 외 나머지 ROI
        for name, images in rois.items():
            if name not in SHOP_SLOTS:
                groups.append((name, images))
    else:
        for name, images in rois.items():
            groups.append((name, images))

    return groups


# ── 중복 검출 ─────────────────────────────────────────────────


def find_duplicates(
    images: list[Path],
    threshold: int,
) -> list[dict]:
    """이미지 목록에서 중복 검출.

    1. SHA256 exact match 그룹화
    2. exact match 그룹 내 첫 번째만 keep, 나머지를 duplicate로
    3. 그 다음 average hash로 유사 비교 (N^2 회피를 위해 hash로 1차 grouping)

    Returns:
        [{"original": Path, "duplicate": Path, "score": int}, ...]
    """
    if len(images) < 2:
        return []

    results: list[dict] = []

    # 1) SHA256 해시 계산
    sha_map: dict[str, list[Path]] = defaultdict(list)
    hash_map: dict[str, str] = {}  # path -> a_hash hex
    ahash_map: dict[str, str] = {}  # path -> a_hash hex

    for img in images:
        sha = sha256_hash(img)
        sha_map[sha].append(img)

    # 2) exact match 처리
    for sha, paths in sha_map.items():
        if len(paths) < 2:
            continue
        # 첫 번째를 original으로
        original = paths[0]
        for dup in paths[1:]:
            results.append({
                "original": original,
                "duplicate": dup,
                "score": 0,  # exact match
                "type": "exact",
            })

    # 3) 유사 중복 (average hash, threshold 기반)
    # exact match로 처리되지 않은 이미지만 대상
    processed: set[Path] = set()
    for r in results:
        processed.add(r["original"])
        processed.add(r["duplicate"])

    remaining = [p for p in images if p not in processed]

    if len(remaining) < 2:
        return results

    # average hash 계산
    for img in remaining:
        h = average_hash(img)
        if h:
            ahash_map[str(img)] = h

    # hash를 4비트 단위로 버킷화하여 유사 후보 축소
    # 같은 상위 48비트를 공유하면 비교 대상
    buckets: dict[str, list[Path]] = defaultdict(list)
    for img in remaining:
        h = ahash_map.get(str(img), "")
        if h and len(h) >= 12:
            bucket_key = h[:12]  # 상위 48비트
            buckets[bucket_key].append(img)

    seen_pairs: set[tuple[str, str]] = set()

    for bucket_key, bucket_images in buckets.items():
        if len(bucket_images) < 2:
            continue
        for i in range(len(bucket_images)):
            for j in range(i + 1, len(bucket_images)):
                a, b = bucket_images[i], bucket_images[j]
                ha = ahash_map.get(str(a), "")
                hb = ahash_map.get(str(b), "")
                if not ha or not hb:
                    continue
                dist = hamming_distance(ha, hb)
                if dist <= threshold and dist > 0:
                    # 중복 쌍 정규화 (파일명 사전순 → original/duplicate 결정)
                    pair_key = (str(a), str(b)) if str(a) <= str(b) else (str(b), str(a))
                    if pair_key in seen_pairs:
                        continue
                    seen_pairs.add(pair_key)
                    # 더 큰 파일(용량)을 original로 (보통 더 품질 좋음)
                    if a.stat().st_size >= b.stat().st_size:
                        orig, dup = a, b
                    else:
                        orig, dup = b, a
                    results.append({
                        "original": orig,
                        "duplicate": dup,
                        "score": dist,
                        "type": "similar",
                    })

    return results


# ── 리포트 ─────────────────────────────────────────────────────


def write_report(report_path: Path, rows: list[dict]):
    """중복 리포트 CSV 저장."""
    with open(report_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=REPORT_FIELDS)
        writer.writeheader()
        for row in rows:
            out = {k: row.get(k, "") for k in REPORT_FIELDS}
            writer.writerow(out)


# ── 메인 ────────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(
        description="TFT Vision — 샘플 중복 제거 도구",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "사용 예:\n"
            "  dry-run:        %(prog)s samples/session_xxx\n"
            "  이동:           %(prog)s samples/session_xxx --move-duplicates\n"
            "  상점 통합:      %(prog)s samples/session_xxx --shop --move-duplicates\n"
            "  임계값 조정:    %(prog)s samples/session_xxx --threshold 10\n"
        ),
    )
    parser.add_argument(
        "session_dir", type=str,
        help="샘플 세션 폴더 경로 (samples/session_xxx)",
    )
    parser.add_argument(
        "--move-duplicates", action="store_true",
        help="중복 이미지를 _duplicates/ROI_NAME/ 폴더로 이동 (기본: dry-run)",
    )
    parser.add_argument(
        "--shop", action="store_true",
        help="shop_slot_1~5를 shop_card로 통합하여 중복 검사",
    )
    parser.add_argument(
        "--threshold", type=int, default=5,
        help="유사 중복 판정 임계값 (0=exact only, 기본 5, 낮을수록 엄격)",
    )
    parser.add_argument(
        "--include-labeled", action="store_true",
        help="labels.csv/labels_shop_card.csv에 등록된 이미지도 중복 대상에 포함",
    )
    args = parser.parse_args()

    session_dir = Path(args.session_dir)
    if not session_dir.is_dir():
        parser.error(f"세션 폴더 없음: {session_dir}")

    threshold = max(0, args.threshold)

    # OpenCV 가용성 확인 (유사 중복 검출에 필요)
    cv2_available = False
    try:
        import cv2
        cv2_available = True
    except ImportError:
        pass

    # ── 스캔 ───────────────────────────────────────────────────

    print(f"{'='*62}")
    print(f"  TFT Vision — 샘플 중복 제거")
    print(f"{'='*62}")
    print(f"  세션:      {session_dir}")
    print(f"  모드:      {'dry-run' if not args.move_duplicates else 'move duplicates'}")
    print(f"  임계값:    {threshold}" + (" (exact match only)" if threshold == 0 else ""))
    if not cv2_available:
        print(f"  ⚠  OpenCV 미설치 — SHA256 exact match만 동작")
        print(f"     pip install opencv-python 으로 유사 중복 검출 활성화")
    print(f"  상점 통합: {'예 (shop_card)' if args.shop else '개별 슬롯'}")
    print(f"  라벨 포함: {'예' if args.include_labeled else '아니오 (기본 보호)'}")
    print()

    # ROI 스캔
    rois = scan_session(session_dir)
    if not rois:
        print("  이미지가 있는 ROI 폴더를 찾을 수 없습니다.")
        sys.exit(0)

    print(f"  발견된 ROI: {len(rois)}개")
    for name, images in sorted(rois.items()):
        print(f"    {name}: {len(images)}개")
    print()

    # 라벨링된 이미지 로드
    labeled_images: set[str] = set()
    if not args.include_labeled:
        labeled_images = load_labeled_images(session_dir)
        if labeled_images:
            print(f"  라벨링 보호: {len(labeled_images)}개 이미지 (--include-labeled로 포함 가능)")
            print()

    # ROI 그룹 구성
    groups = build_roi_groups(rois, shop_mode=args.shop)

    all_duplicates: list[dict] = []
    total_duplicates = 0
    total_skipped_labeled = 0

    for roi_name, images in groups:
        print(f"{'─'*62}")
        print(f"  ROI: {roi_name} ({len(images)}개 이미지)")

        # 라벨링 보호: labeled 이미지 제외
        if labeled_images:
            filtered: list[Path] = []
            skipped = 0
            for img in images:
                # 상대 경로: ROI_NAME/filename.png
                rel = f"{roi_name}/{img.name}"
                if rel in labeled_images:
                    skipped += 1
                else:
                    filtered.append(img)
            if skipped:
                print(f"    라벨링 보호로 제외: {skipped}개")
                total_skipped_labeled += skipped
            images = filtered

        if len(images) < 2:
            print("    중복 검사 스킵 (2개 미만)")
            continue

        # 중복 검출
        dupes = find_duplicates(images, threshold)

        if not dupes:
            print("    중복 없음")
            continue

        total_duplicates += len(dupes)
        print(f"    중복 발견: {len(dupes)}쌍")
        for d in dupes:
            # 실제 소스 폴더 기준 상대 경로
            dup_rel = f"{d['duplicate'].parent.name}/{d['duplicate'].name}"
            orig_rel = f"{d['original'].parent.name}/{d['original'].name}"
            d_type = "EXACT" if d["type"] == "exact" else f"SIM(d={d['score']})"
            print(f"      [{d_type}] {dup_rel}")
            print(f"              → {orig_rel}")

            # 리포트용 행
            report_row = {
                "original_path": str(d["original"]),
                "duplicate_path": str(d["duplicate"]),
                "roi": roi_name,
                "similarity_score": str(d["score"]),
                "action": "dry-run",
                "created_at": datetime.now().isoformat(),
            }
            all_duplicates.append(report_row)

    print()
    print(f"{'='*62}")

    if total_duplicates == 0:
        print(f"  중복 없음 — 샘플 데이터가 깔끔합니다.")
        print(f"{'='*62}")
        sys.exit(0)

    print(f"  총 중복 쌍: {total_duplicates}쌍")
    if total_skipped_labeled > 0:
        print(f"  라벨링 보호로 제외: {total_skipped_labeled}개")

    # ── 리포트 저장 ────────────────────────────────────────────

    report_path = session_dir / "duplicates_report.csv"
    write_report(report_path, all_duplicates)
    print(f"  리포트:    {report_path}")

    # ── 이동 실행 ──────────────────────────────────────────────

    if args.move_duplicates:
        moved_count = 0
        for row in all_duplicates:
            dup_path = Path(row["duplicate_path"])
            roi_name = row["roi"]
            dest_dir = session_dir / "_duplicates" / roi_name
            dest_dir.mkdir(parents=True, exist_ok=True)
            dest_path = dest_dir / dup_path.name

            # 대상에 이미同名 파일이 있으면 숫자 접미사
            if dest_path.exists():
                stem = dup_path.stem
                suffix = dup_path.suffix
                counter = 1
                while dest_path.exists():
                    dest_path = dest_dir / f"{stem}_{counter}{suffix}"
                    counter += 1

            dup_path.rename(dest_path)
            moved_count += 1
            row["action"] = f"moved_to_{dest_dir.name}/{dest_path.name}"

        # 이동 후 리포트 갱신
        write_report(report_path, all_duplicates)
        print(f"  이동 완료: {moved_count}개 → {session_dir / '_duplicates'}/")
    else:
        print(f"  dry-run:   --move-duplicates로 실제 이동 가능")
        for row in all_duplicates:
            row["action"] = "dry-run"
        write_report(report_path, all_duplicates)

    print(f"{'='*62}")


if __name__ == "__main__":
    main()
