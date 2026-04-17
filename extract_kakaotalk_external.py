import os
import csv
import hashlib
import shutil
import subprocess
from pathlib import Path

# =========================================================
# 설정
# =========================================================

# adb.exe 경로
ADB_PATH = r"C:\Users\djark\OneDrive\Desktop\platform-tools\adb.exe"

# 원격 카카오톡 경로
REMOTE_PATHS = [
    "/sdcard/Android/data/com.kakao.talk/browser-photos",
    "/sdcard/Android/data/com.kakao.talk/contents",
]

# 작업 폴더
BASE_DIR = Path("kakao_image_restore")
RAW_DIR = BASE_DIR / "raw"
RESTORED_DIR = BASE_DIR / "restored_images"
REPORT_DIR = BASE_DIR / "reports"

# 이미지만 대상으로 함
KNOWN_IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"}

# 파일 헤더 기반 탐지
def detect_image_type(file_path: Path):
    try:
        with open(file_path, "rb") as f:
            header = f.read(32)

        # JPG
        if header.startswith(b"\xFF\xD8\xFF"):
            return ".jpg"

        # PNG
        if header.startswith(b"\x89PNG\r\n\x1a\n"):
            return ".png"

        # GIF
        if header.startswith(b"GIF87a") or header.startswith(b"GIF89a"):
            return ".gif"

        # BMP
        if header.startswith(b"BM"):
            return ".bmp"

        # WEBP
        if len(header) >= 12 and header[:4] == b"RIFF" and header[8:12] == b"WEBP":
            return ".webp"

        return None
    except Exception:
        return None


def ensure_dir(path: Path):
    path.mkdir(parents=True, exist_ok=True)


def run_cmd(cmd):
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        shell=False
    )
    return result.returncode, result.stdout, result.stderr


def adb_cmd(args):
    return run_cmd([ADB_PATH] + args)


def check_adb():
    if not Path(ADB_PATH).is_file():
        raise FileNotFoundError(f"adb.exe 경로가 잘못됨: {ADB_PATH}")

    code, out, err = adb_cmd(["devices"])
    if code != 0:
        raise RuntimeError(f"adb devices 실패:\n{err or out}")

    lines = [x.strip() for x in out.splitlines() if x.strip()]
    devices = [x for x in lines[1:] if "\tdevice" in x]

    if not devices:
        raise RuntimeError("연결된 안드로이드 기기가 없거나 USB 디버깅 승인 안 됨")

    print("[*] 연결된 기기:")
    for d in devices:
        print("   ", d)


def pull_remote_dir(remote_path: str):
    """
    원격 폴더를 로컬 raw 아래로 pull
    """
    subdir = remote_path.strip("/").replace("/", "_")
    local_dir = RAW_DIR / subdir
    ensure_dir(local_dir)

    print(f"[+] Pulling: {remote_path}")
    code, out, err = adb_cmd(["pull", remote_path, str(local_dir)])
    if code != 0:
        print(f"[!] pull 실패: {remote_path}")
        print(err or out)
    else:
        print(f"[+] 완료: {remote_path} -> {local_dir}")


def sha256_file(path: Path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def unique_output_path(dst_dir: Path, base_name: str, ext: str):
    candidate = dst_dir / f"{base_name}{ext}"
    if not candidate.exists():
        return candidate

    i = 1
    while True:
        candidate = dst_dir / f"{base_name}_{i}{ext}"
        if not candidate.exists():
            return candidate
        i += 1


def restore_images_from_raw():
    """
    raw 폴더 전체를 뒤져서:
    - 원래 이미지 확장자 있으면 그대로 복사
    - 확장자 없거나 이상하면 헤더 보고 복원
    - 중복은 해시로 제거
    """
    restored_count = 0
    duplicate_count = 0
    skipped_count = 0

    seen_hashes = set()
    records = []

    for root, _, files in os.walk(RAW_DIR):
        for name in files:
            src = Path(root) / name
            ext = src.suffix.lower()

            detected_ext = None

            # 이미 확장자가 이미지면 일단 후보
            if ext in KNOWN_IMAGE_EXTS:
                detected_ext = ext
            else:
                # 확장자가 없거나 이상한 경우 헤더 검사
                detected_ext = detect_image_type(src)

            if not detected_ext:
                skipped_count += 1
                continue

            try:
                file_hash = sha256_file(src)
            except Exception as e:
                print(f"[!] 해시 계산 실패: {src} / {e}")
                skipped_count += 1
                continue

            if file_hash in seen_hashes:
                duplicate_count += 1
                records.append({
                    "source_path": str(src),
                    "restored_path": "",
                    "status": "duplicate_skipped",
                    "ext": detected_ext,
                    "sha256": file_hash,
                    "size": src.stat().st_size
                })
                continue

            seen_hashes.add(file_hash)

            # 저장 파일명
            # 확장자 없는 숫자 파일이면 원본 stem 사용
            base_name = src.stem if src.stem else "image"
            dst = unique_output_path(RESTORED_DIR, base_name, detected_ext)

            try:
                shutil.copy2(src, dst)
                restored_count += 1

                records.append({
                    "source_path": str(src),
                    "restored_path": str(dst),
                    "status": "restored",
                    "ext": detected_ext,
                    "sha256": file_hash,
                    "size": src.stat().st_size
                })
            except Exception as e:
                print(f"[!] 복사 실패: {src} / {e}")
                records.append({
                    "source_path": str(src),
                    "restored_path": "",
                    "status": f"copy_failed: {e}",
                    "ext": detected_ext,
                    "sha256": file_hash,
                    "size": src.stat().st_size
                })

    return records, restored_count, duplicate_count, skipped_count


def export_csv(records):
    csv_path = REPORT_DIR / "restored_images_inventory.csv"
    with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["source_path", "restored_path", "status", "ext", "sha256", "size"]
        )
        writer.writeheader()
        writer.writerows(records)
    return csv_path


def write_summary(restored_count, duplicate_count, skipped_count, csv_path):
    txt_path = REPORT_DIR / "summary.txt"
    with open(txt_path, "w", encoding="utf-8") as f:
        f.write("KakaoTalk Image Restore Summary\n")
        f.write("=" * 40 + "\n")
        f.write(f"복원 성공: {restored_count}\n")
        f.write(f"중복 스킵: {duplicate_count}\n")
        f.write(f"이미지 아님/스킵: {skipped_count}\n")
        f.write(f"이미지 저장 폴더: {RESTORED_DIR.resolve()}\n")
        f.write(f"CSV 인벤토리: {csv_path.resolve()}\n")
    return txt_path


def main():
    ensure_dir(BASE_DIR)
    ensure_dir(RAW_DIR)
    ensure_dir(RESTORED_DIR)
    ensure_dir(REPORT_DIR)

    print("[*] KakaoTalk 이미지 자동 복원 시작")

    # 1) ADB 체크
    check_adb()

    # 2) 원격 폴더 pull
    for remote in REMOTE_PATHS:
        pull_remote_dir(remote)

    # 3) 로컬 raw에서 이미지 자동 복원
    print("[*] 이미지 복원 중...")
    records, restored_count, duplicate_count, skipped_count = restore_images_from_raw()

    # 4) CSV / 요약 저장
    csv_path = export_csv(records)
    summary_path = write_summary(restored_count, duplicate_count, skipped_count, csv_path)

    print("\n[+] 완료")
    print(f"[+] 복원 성공: {restored_count}")
    print(f"[+] 중복 스킵: {duplicate_count}")
    print(f"[+] 이미지 아님/스킵: {skipped_count}")
    print(f"[+] 이미지 저장 위치: {RESTORED_DIR.resolve()}")
    print(f"[+] CSV: {csv_path.resolve()}")
    print(f"[+] 요약: {summary_path.resolve()}")


if __name__ == "__main__":
    main()
