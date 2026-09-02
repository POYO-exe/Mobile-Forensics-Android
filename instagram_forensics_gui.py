import os
import re
import sys
import html
import json
import shutil
import sqlite3
import subprocess
import requests
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QTextEdit, QLabel, QTabWidget, QMessageBox, QListWidget, QSplitter,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
    QListWidgetItem, QFileDialog
)
from PySide6.QtGui import QPixmap, QIcon
from PySide6.QtCore import Qt, QSize


PACKAGE_NAME = "com.instagram.android"

LOCAL_DIR = Path("instagram_extracted")

DEFAULT_DB_DIR = Path(r"C:\Users\djark\OneDrive\Desktop\모바일 포렌식\instagram_extracted\insta_forensic\databases")

RECOVERED_IMAGE_DIR = Path("instagram_recovered_images")
RECOVERED_DELIVERY_MEDIA_DIR = Path("recovered_delivery_media")

URL_RE = re.compile(r'https?://[^\s"\'<>\\]+')

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
VIDEO_EXTS = {".mp4", ".mov", ".m4v"}


class InstagramForensics(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Instagram Forensics Extractor")
        self.resize(1500, 920)

        self.extracted_path = LOCAL_DIR
        self.recovered_images = []
        self.recovered_media_files = []

        self.init_ui()

    def init_ui(self):
        main_layout = QVBoxLayout(self)

        title = QLabel("Instagram Forensics Extractor")
        title.setStyleSheet("font-size: 24px; font-weight: bold; padding: 10px;")
        main_layout.addWidget(title)

        button_layout = QHBoxLayout()

        self.btn_check = QPushButton("ADB 연결 확인")
        self.btn_root = QPushButton("루팅 권한 확인")
        self.btn_extract = QPushButton("Instagram 데이터 추출")
        self.btn_recover_images = QPushButton("이미지 파일 복구")
        self.btn_delivery_media = QPushButton("DB 이미지 변환")
        self.btn_gallery_refresh = QPushButton("갤러리 새로고침")
        self.btn_open_folder = QPushButton("복원 폴더 열기")
        self.btn_all = QPushButton("전체 복구")

        for btn in [
            self.btn_check,
            self.btn_root,
            self.btn_extract,
            self.btn_recover_images,
            self.btn_delivery_media,
            self.btn_gallery_refresh,
            self.btn_open_folder,
            self.btn_all,
        ]:
            button_layout.addWidget(btn)

        main_layout.addLayout(button_layout)

        self.tabs = QTabWidget()

        self.log_box = QTextEdit()
        self.log_box.setReadOnly(True)

        # 기존 좌측 리스트 + 우측 미리보기
        self.image_list = QListWidget()
        self.image_preview = QLabel("이미지를 선택하면 미리보기가 표시됩니다.")
        self.image_preview.setAlignment(Qt.AlignCenter)
        self.image_preview.setMinimumHeight(500)
        self.image_preview.setStyleSheet("border: 1px solid #dddddd; background: #fafafa;")

        image_splitter = QSplitter()
        image_splitter.addWidget(self.image_list)
        image_splitter.addWidget(self.image_preview)
        image_splitter.setStretchFactor(0, 1)
        image_splitter.setStretchFactor(1, 4)

        # 갤러리 탭
        gallery_wrap = QWidget()
        gallery_layout = QVBoxLayout(gallery_wrap)

        self.gallery_info = QLabel("복원된 이미지를 갤러리 형태로 보여줍니다. 썸네일을 클릭하면 미리보기 탭에서 크게 볼 수 있습니다.")
        self.gallery_info.setStyleSheet("padding: 8px; font-weight: bold;")

        self.gallery_list = QListWidget()
        self.gallery_list.setViewMode(QListWidget.IconMode)
        self.gallery_list.setIconSize(QSize(180, 180))
        self.gallery_list.setResizeMode(QListWidget.Adjust)
        self.gallery_list.setMovement(QListWidget.Static)
        self.gallery_list.setSpacing(12)
        self.gallery_list.setWordWrap(True)
        self.gallery_list.setSelectionMode(QAbstractItemView.SingleSelection)

        gallery_layout.addWidget(self.gallery_info)
        gallery_layout.addWidget(self.gallery_list)

        # DB URL 변환 결과 테이블
        self.media_table = QTableWidget()
        self.media_table.setColumnCount(9)
        self.media_table.setHorizontalHeaderLabels([
            "복원 파일", "DB 파일", "테이블", "행", "컬럼", "URL", "상태", "크기", "확장자"
        ])
        self.media_table.setAlternatingRowColors(True)
        self.media_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.media_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.media_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.media_table.horizontalHeader().setStretchLastSection(True)

        self.info_box = QTextEdit()
        self.info_box.setReadOnly(True)
        self.info_box.setPlainText(
            "기능 설명\n\n"
            "1. Instagram 데이터 추출\n"
            "   - 루팅폰에서 databases, shared_prefs, files, cache를 추출합니다.\n\n"
            "2. 이미지 파일 복구\n"
            "   - cache/files 안에 남은 JPG, PNG, WEBP 파일을 복사하거나 바이너리 내부에서 카빙합니다.\n\n"
            "3. DB 이미지 변환\n"
            "   - 아래 경로의 DB 파일을 기준으로 실행합니다.\n"
            f"   - {DEFAULT_DB_DIR}\n"
            "   - delivery_media_room_db_* 파일을 자동으로 찾습니다.\n"
            "   - DB 컬럼 값을 전부 문자열로 바꾼 뒤 정규식으로 URL을 찾습니다.\n"
            "   - cdninstagram.com, fbcdn.net URL을 다운로드합니다.\n"
            "   - JPG, PNG, WEBP, MP4까지 저장합니다.\n\n"
            "4. 갤러리 보기\n"
            "   - 복원된 이미지를 썸네일 형태로 한 번에 보여줍니다.\n"
            "   - 썸네일을 클릭하면 복구 이미지 탭에서 크게 볼 수 있습니다.\n"
            "   - MP4는 썸네일 대신 VIDEO 항목으로 표시됩니다.\n\n"
            "주의\n"
            "   - DB 안에 사진 원본이 아니라 CDN URL이 저장된 경우가 많아 인터넷 연결이 필요합니다.\n"
            "   - URL이 만료되면 다운로드 실패할 수 있습니다.\n"
            "   - DB, DB-wal, DB-shm 파일을 같은 폴더에 두면 최신 데이터까지 읽을 가능성이 높습니다."
        )

        self.tabs.addTab(self.log_box, "로그")
        self.tabs.addTab(image_splitter, "복구 이미지")
        self.tabs.addTab(gallery_wrap, "갤러리 보기")
        self.tabs.addTab(self.media_table, "DB 이미지 변환 결과")
        self.tabs.addTab(self.info_box, "설명")

        main_layout.addWidget(self.tabs)

        self.btn_check.clicked.connect(self.check_adb)
        self.btn_root.clicked.connect(self.check_root)
        self.btn_extract.clicked.connect(self.extract_instagram_data)
        self.btn_recover_images.clicked.connect(self.recover_and_load_images)
        self.btn_delivery_media.clicked.connect(self.recover_delivery_media_from_db)
        self.btn_gallery_refresh.clicked.connect(self.refresh_gallery)
        self.btn_open_folder.clicked.connect(self.open_recovered_folder)
        self.btn_all.clicked.connect(self.recover_all)
        self.image_list.currentTextChanged.connect(self.show_image)
        self.media_table.cellDoubleClicked.connect(self.open_table_file)
        self.gallery_list.itemClicked.connect(self.open_gallery_item)

    def log(self, text):
        now = datetime.now().strftime("%H:%M:%S")
        self.log_box.append(f"[{now}] {text}")

    def run_cmd(self, cmd, timeout=60):
        self.log(f"$ {cmd}")
        try:
            result = subprocess.run(
                cmd,
                shell=True,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="ignore",
                timeout=timeout,
            )
            output = result.stdout.strip()
            error = result.stderr.strip()

            if output:
                self.log(output)
            if error:
                self.log(error)

            return result.returncode, output, error

        except subprocess.TimeoutExpired:
            self.log("명령어 실행 시간이 초과되었습니다.")
            return -1, "", "timeout"

    def check_adb(self):
        code, out, err = self.run_cmd("adb devices")

        lines = [line for line in out.splitlines() if line.strip()]
        devices = [line for line in lines[1:] if "\tdevice" in line]

        if devices:
            QMessageBox.information(self, "성공", "ADB 기기가 정상 연결되었습니다.")
        elif "unauthorized" in out:
            QMessageBox.warning(self, "주의", "휴대폰에서 USB 디버깅 허용을 눌러야 합니다.")
        else:
            QMessageBox.warning(self, "실패", "ADB 기기를 찾지 못했습니다.")

    def check_root(self):
        code, out, err = self.run_cmd('adb shell su -c "id"')

        if "uid=0" in out:
            QMessageBox.information(self, "성공", "루트 권한이 확인되었습니다.")
        else:
            QMessageBox.warning(self, "실패", "su 권한을 얻지 못했습니다.")

    def extract_instagram_data(self):
        if LOCAL_DIR.exists():
            shutil.rmtree(LOCAL_DIR)

        LOCAL_DIR.mkdir(parents=True, exist_ok=True)

        self.log("Instagram 데이터 추출을 시작합니다.")

        commands = [
            'adb shell su -c "rm -rf /sdcard/insta_forensics"',
            'adb shell su -c "mkdir -p /sdcard/insta_forensics"',
            f'adb shell su -c "cp -r /data/data/{PACKAGE_NAME}/databases /sdcard/insta_forensics/ 2>/dev/null"',
            f'adb shell su -c "cp -r /data/data/{PACKAGE_NAME}/shared_prefs /sdcard/insta_forensics/ 2>/dev/null"',
            f'adb shell su -c "cp -r /data/data/{PACKAGE_NAME}/files /sdcard/insta_forensics/ 2>/dev/null"',
            f'adb shell su -c "cp -r /data/data/{PACKAGE_NAME}/cache /sdcard/insta_forensics/ 2>/dev/null"',
            f'adb shell su -c "cp -r /data/user/0/{PACKAGE_NAME}/databases /sdcard/insta_forensics/databases_user0 2>/dev/null"',
            f'adb shell su -c "cp -r /data/user/0/{PACKAGE_NAME}/files /sdcard/insta_forensics/files_user0 2>/dev/null"',
            f'adb shell su -c "cp -r /data/user/0/{PACKAGE_NAME}/cache /sdcard/insta_forensics/cache_user0 2>/dev/null"',
            f'adb shell su -c "cp -r /sdcard/Android/data/{PACKAGE_NAME}/cache /sdcard/insta_forensics/sdcard_cache 2>/dev/null"',
            f'adb pull /sdcard/insta_forensics "{LOCAL_DIR}"',
        ]

        for cmd in commands:
            self.run_cmd(cmd, timeout=240)

        self.log("추출 완료")
        QMessageBox.information(self, "완료", "Instagram 데이터 추출이 완료되었습니다.")

    # =========================================================
    # 기존 이미지 파일 복구 기능
    # =========================================================

    def detect_image_type(self, data):
        if data.startswith(b"\xff\xd8\xff"):
            return "jpg"
        if data.startswith(b"\x89PNG\r\n\x1a\n"):
            return "png"
        if data.startswith(b"RIFF") and len(data) >= 12 and data[8:12] == b"WEBP":
            return "webp"
        if data.startswith(b"GIF87a") or data.startswith(b"GIF89a"):
            return "gif"
        return None

    def image_ext_from_file(self, path):
        try:
            with open(path, "rb") as f:
                head = f.read(32)
            return self.detect_image_type(head)
        except Exception:
            return None

    def copy_detected_image(self, src_path, index):
        ext = self.image_ext_from_file(src_path)
        if not ext:
            return None

        dst = RECOVERED_IMAGE_DIR / f"recovered_{index:05d}.{ext}"
        shutil.copy2(src_path, dst)
        return dst

    def carve_images_from_binary(self, src_path, start_index):
        recovered = []

        try:
            if src_path.stat().st_size > 150 * 1024 * 1024:
                return recovered
            data = src_path.read_bytes()
        except Exception:
            return recovered

        signatures = [
            (b"\xff\xd8\xff", b"\xff\xd9", "jpg", 2),
            (b"\x89PNG\r\n\x1a\n", b"IEND\xaeB`\x82", "png", 8),
            (b"RIFF", None, "webp", 0),
        ]

        for start_sig, end_sig, ext, end_extra in signatures:
            pos = 0
            while True:
                start = data.find(start_sig, pos)
                if start == -1:
                    break

                if ext == "webp":
                    if start + 12 > len(data) or data[start + 8:start + 12] != b"WEBP":
                        pos = start + 4
                        continue
                    size = int.from_bytes(data[start + 4:start + 8], "little") + 8
                    end = start + size
                else:
                    end_marker = data.find(end_sig, start + len(start_sig))
                    if end_marker == -1:
                        break
                    end = end_marker + end_extra

                if end <= start or end > len(data):
                    pos = start + len(start_sig)
                    continue

                blob = data[start:end]
                if len(blob) < 100:
                    pos = end
                    continue

                out_path = RECOVERED_IMAGE_DIR / f"carved_{start_index + len(recovered):05d}.{ext}"
                try:
                    out_path.write_bytes(blob)
                    pixmap = QPixmap(str(out_path))
                    if pixmap.isNull():
                        out_path.unlink(missing_ok=True)
                    else:
                        recovered.append(out_path)
                except Exception:
                    pass

                pos = end

        return recovered

    def recover_and_load_images(self):
        if not LOCAL_DIR.exists():
            QMessageBox.warning(self, "오류", "먼저 Instagram 데이터를 추출해야 합니다.")
            return

        if RECOVERED_IMAGE_DIR.exists():
            shutil.rmtree(RECOVERED_IMAGE_DIR)
        RECOVERED_IMAGE_DIR.mkdir(parents=True, exist_ok=True)

        self.recovered_images = []
        self.image_list.clear()
        self.image_preview.clear()
        self.image_preview.setText("복구된 이미지를 선택하면 미리보기가 표시됩니다.")

        self.log("이미지 파일 복구를 시작합니다.")

        all_files = []
        for root, dirs, files in os.walk(self.extracted_path):
            for file in files:
                all_files.append(Path(root) / file)

        copied_count = 0
        carved_count = 0

        for path in all_files:
            copied = self.copy_detected_image(path, copied_count + 1)
            if copied:
                self.recovered_images.append(copied)
                copied_count += 1
                continue

            carved = self.carve_images_from_binary(path, copied_count + carved_count + 1)
            if carved:
                self.recovered_images.extend(carved)
                carved_count += len(carved)

        self.recovered_images = sorted(set(self.recovered_images), key=lambda p: str(p))

        for img in self.recovered_images:
            self.image_list.addItem(str(img))

        self.refresh_gallery()

        self.tabs.setCurrentIndex(2)
        self.log(f"원본 이미지 복사: {copied_count}개")
        self.log(f"바이너리/캐시 이미지 복구: {carved_count}개")
        self.log(f"복구 이미지 저장 위치: {RECOVERED_IMAGE_DIR.resolve()}")

        QMessageBox.information(
            self,
            "완료",
            f"이미지 복구 완료\n총 {len(self.recovered_images)}개 이미지를 표시합니다."
        )

    # =========================================================
    # DB URL 기반 이미지/영상 변환 기능
    # =========================================================

    def safe_name(self, text):
        return "".join(c if c.isalnum() or c in "._-" else "_" for c in str(text))[:100]

    def value_to_text(self, value):
        if value is None:
            return ""

        if isinstance(value, bytes):
            return value.decode("utf-8", errors="ignore")

        return str(value)

    def find_urls_from_text(self, text):
        urls = URL_RE.findall(text)
        result = []

        for url in urls:
            url = html.unescape(url)
            url = url.rstrip(".,)}]")

            if "cdninstagram.com" in url or "fbcdn.net" in url:
                result.append(url)

        return list(dict.fromkeys(result))

    def try_json(self, value):
        text = self.value_to_text(value).strip()

        if not text.startswith("{") and not text.startswith("["):
            return None

        try:
            return json.loads(text)
        except Exception:
            return None

    def find_urls_from_json(self, obj):
        urls = []

        if isinstance(obj, dict):
            for k, v in obj.items():
                if k == "url" and isinstance(v, str):
                    if "cdninstagram.com" in v or "fbcdn.net" in v:
                        urls.append(html.unescape(v))
                else:
                    urls.extend(self.find_urls_from_json(v))

        elif isinstance(obj, list):
            for item in obj:
                urls.extend(self.find_urls_from_json(item))

        return urls

    def get_ext(self, url, content_type=""):
        content_type = content_type.lower()
        path = urlparse(url).path.lower()

        if "mp4" in content_type or ".mp4" in path:
            return ".mp4"
        if "webp" in content_type or ".webp" in path:
            return ".webp"
        if "png" in content_type or ".png" in path:
            return ".png"
        if "jpeg" in content_type or "jpg" in content_type or ".jpg" in path or ".jpeg" in path:
            return ".jpg"
        if "gif" in content_type or ".gif" in path:
            return ".gif"

        return ".bin"

    def get_db_dir(self):
        if DEFAULT_DB_DIR.exists():
            return DEFAULT_DB_DIR

        candidates = [
            Path("instagram_extracted") / "insta_forensic" / "databases",
            Path("instagram_extracted") / "insta_forensics" / "databases",
            Path("instagram_extracted") / "databases",
            Path("instagram_extracted") / "databases_user0",
            LOCAL_DIR / "insta_forensic" / "databases",
            LOCAL_DIR / "insta_forensics" / "databases",
            LOCAL_DIR / "databases",
            LOCAL_DIR / "databases_user0",
        ]

        for p in candidates:
            if p.exists():
                return p

        return DEFAULT_DB_DIR

    def find_delivery_media_dbs(self):
        db_dir = self.get_db_dir()

        if not db_dir.exists():
            return []

        dbs = []

        for p in db_dir.iterdir():
            name = p.name

            if name.endswith("-wal") or name.endswith("-shm") or name.endswith("-journal"):
                continue

            if name.startswith("delivery_media_room_db"):
                dbs.append(p)

        return sorted(dbs, key=lambda x: x.name)

    def prepare_db_copy(self, db_path):
        temp_dir = Path("temp_delivery_db")
        if temp_dir.exists():
            shutil.rmtree(temp_dir)
        temp_dir.mkdir(parents=True, exist_ok=True)

        temp_db = temp_dir / db_path.name
        shutil.copy2(db_path, temp_db)

        for suffix in ["-wal", "-shm", "-journal"]:
            side = db_path.parent / f"{db_path.name}{suffix}"
            if side.exists():
                shutil.copy2(side, temp_dir / side.name)

        return temp_db

    def add_media_row(self, out_path, db_path, table, rowid, column, url, status, size, ext):
        row = self.media_table.rowCount()
        self.media_table.insertRow(row)

        values = [
            str(out_path) if out_path else "",
            str(db_path),
            table,
            rowid,
            column,
            url,
            status,
            size,
            ext,
        ]

        for col, value in enumerate(values):
            self.media_table.setItem(row, col, QTableWidgetItem(str(value)))

    def download_file(self, url, filename, db_path, table, rowid, column):
        try:
            headers = {
                "User-Agent": "Mozilla/5.0",
                "Referer": "https://www.instagram.com/",
            }

            r = requests.get(url, headers=headers, timeout=25)

            if r.status_code != 200:
                self.add_media_row("", db_path, table, rowid, column, url, f"다운로드 실패 {r.status_code}", 0, "")
                return None

            ext = self.get_ext(url, r.headers.get("Content-Type", ""))
            out = RECOVERED_DELIVERY_MEDIA_DIR / f"{filename}{ext}"

            i = 1
            while out.exists():
                out = RECOVERED_DELIVERY_MEDIA_DIR / f"{filename}_{i}{ext}"
                i += 1

            out.write_bytes(r.content)

            if ext in IMAGE_EXTS:
                pixmap = QPixmap(str(out))
                if pixmap.isNull():
                    out.unlink(missing_ok=True)
                    self.add_media_row("", db_path, table, rowid, column, url, "이미지 열기 실패", len(r.content), ext)
                    return None

                self.image_list.addItem(str(out))
                self.recovered_images.append(out)

            else:
                self.recovered_media_files.append(out)

            self.add_media_row(out, db_path, table, rowid, column, url, "성공", len(r.content), ext)
            self.log(f"복원 완료: {out}")
            return out

        except Exception as e:
            self.add_media_row("", db_path, table, rowid, column, url, f"다운로드 오류: {e}", 0, "")
            self.log(f"다운로드 오류: {e}")
            return None

    def recover_delivery_media_from_db(self):
        db_dir = self.get_db_dir()

        if not db_dir.exists():
            QMessageBox.warning(
                self,
                "오류",
                f"DB 폴더를 찾지 못했습니다.\n\n확인 경로:\n{db_dir}"
            )
            return

        if RECOVERED_DELIVERY_MEDIA_DIR.exists():
            shutil.rmtree(RECOVERED_DELIVERY_MEDIA_DIR)
        RECOVERED_DELIVERY_MEDIA_DIR.mkdir(parents=True, exist_ok=True)

        self.media_table.setRowCount(0)

        dbs = self.find_delivery_media_dbs()

        if not dbs:
            QMessageBox.warning(
                self,
                "오류",
                f"delivery_media_room_db 파일을 찾지 못했습니다.\n\nDB 폴더:\n{db_dir}"
            )
            return

        self.log("DB 이미지 변환 시작")
        self.log(f"DB 폴더: {db_dir}")
        self.log(f"delivery_media_room_db 발견: {len(dbs)}개")

        total_urls = 0
        downloaded = 0
        seen_urls = set()

        for db_path in dbs:
            self.log(f"DB 분석 중: {db_path.name}")

            try:
                temp_db = self.prepare_db_copy(db_path)

                conn = sqlite3.connect(str(temp_db))
                conn.text_factory = lambda b: b.decode("utf-8", errors="ignore")
                cur = conn.cursor()

                cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
                tables = [row[0] for row in cur.fetchall()]

                for table in tables:
                    self.log(f"[테이블 분석] {db_path.name} / {table}")

                    try:
                        cur.execute(f'SELECT rowid, * FROM "{table}" LIMIT 50000')
                        columns = [desc[0] for desc in cur.description]

                        for row_data in cur.fetchall():
                            rowid = row_data[0]

                            for idx, value in enumerate(row_data[1:], start=1):
                                column = columns[idx]

                                urls = []

                                text = self.value_to_text(value)
                                urls.extend(self.find_urls_from_text(text))

                                parsed = self.try_json(value)
                                if parsed is not None:
                                    urls.extend(self.find_urls_from_json(parsed))

                                urls = list(dict.fromkeys(urls))

                                for n, url in enumerate(urls):
                                    if url in seen_urls:
                                        continue

                                    seen_urls.add(url)
                                    total_urls += 1

                                    filename = self.safe_name(
                                        f"{db_path.stem}_{table}_row{rowid}_{column}_{n}"
                                    )

                                    result = self.download_file(
                                        url,
                                        filename,
                                        db_path,
                                        table,
                                        rowid,
                                        column,
                                    )

                                    if result:
                                        downloaded += 1

                                    QApplication.processEvents()

                    except Exception as e:
                        self.log(f"테이블 스킵: {table} / {e}")

                conn.close()

            except Exception as e:
                self.log(f"DB 분석 실패: {db_path} / {e}")

        self.media_table.resizeColumnsToContents()
        self.refresh_gallery()
        self.tabs.setCurrentIndex(2)

        self.log("====================")
        self.log(f"URL 발견: {total_urls}")
        self.log(f"다운로드 성공: {downloaded}")
        self.log(f"저장 위치: {RECOVERED_DELIVERY_MEDIA_DIR.resolve()}")

        QMessageBox.information(
            self,
            "완료",
            f"DB 이미지 변환 완료\nURL 발견: {total_urls}개\n다운로드 성공: {downloaded}개\n\n저장 위치:\n{RECOVERED_DELIVERY_MEDIA_DIR.resolve()}"
        )

    # =========================================================
    # 갤러리 기능
    # =========================================================

    def collect_recovered_files(self):
        files = []

        for base in [RECOVERED_DELIVERY_MEDIA_DIR, RECOVERED_IMAGE_DIR]:
            if not base.exists():
                continue

            for p in sorted(base.rglob("*")):
                if p.is_file() and p.suffix.lower() in IMAGE_EXTS.union(VIDEO_EXTS):
                    files.append(p)

        # 중복 제거
        return sorted(set(files), key=lambda x: str(x))

    def refresh_gallery(self):
        self.gallery_list.clear()

        files = self.collect_recovered_files()
        image_count = 0
        video_count = 0

        for p in files:
            ext = p.suffix.lower()

            item = QListWidgetItem()
            item.setData(Qt.UserRole, str(p))

            if ext in IMAGE_EXTS:
                pixmap = QPixmap(str(p))
                if pixmap.isNull():
                    continue

                icon_pixmap = pixmap.scaled(
                    180,
                    180,
                    Qt.KeepAspectRatio,
                    Qt.SmoothTransformation
                )

                item.setIcon(QIcon(icon_pixmap))
                item.setText(p.name)
                image_count += 1

            elif ext in VIDEO_EXTS:
                # PySide6 기본만 사용해서 간단한 VIDEO 아이콘 생성
                video_icon = QPixmap(180, 180)
                video_icon.fill(Qt.black)
                item.setIcon(QIcon(video_icon))
                item.setText(f"VIDEO\n{p.name}")
                video_count += 1

            item.setSizeHint(QSize(210, 230))
            self.gallery_list.addItem(item)

        self.gallery_info.setText(
            f"갤러리 보기 - 이미지 {image_count}개 / 영상 {video_count}개 / 전체 {len(files)}개"
        )
        self.log(f"갤러리 새로고침 완료: 이미지 {image_count}개 / 영상 {video_count}개")
        self.tabs.setCurrentIndex(2)

    def open_gallery_item(self, item):
        path = item.data(Qt.UserRole)

        if not path:
            return

        p = Path(path)

        if p.suffix.lower() in IMAGE_EXTS:
            self.show_image(path)
        else:
            self.log(f"영상 파일입니다. 저장 위치: {path}")
            QMessageBox.information(self, "영상 파일", f"MP4 파일은 미리보기 대신 저장 경로를 확인하세요.\n\n{path}")

    def open_recovered_folder(self):
        target = RECOVERED_DELIVERY_MEDIA_DIR

        if not target.exists():
            target = RECOVERED_IMAGE_DIR

        if not target.exists():
            QMessageBox.warning(self, "오류", "복원 폴더가 아직 없습니다.")
            return

        if sys.platform.startswith("win"):
            os.startfile(str(target.resolve()))
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(target.resolve())])
        else:
            subprocess.Popen(["xdg-open", str(target.resolve())])

    def recover_all(self):
        if LOCAL_DIR.exists():
            self.recover_and_load_images()

        self.recover_delivery_media_from_db()
        self.refresh_gallery()

    def show_image(self, path):
        if not path:
            return

        pixmap = QPixmap(path)

        if pixmap.isNull():
            self.image_preview.setText("이미지를 열 수 없습니다.")
            return

        scaled = pixmap.scaled(
            self.image_preview.width(),
            self.image_preview.height(),
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation,
        )

        self.image_preview.setPixmap(scaled)
        self.tabs.setCurrentIndex(1)

    def open_table_file(self, row, col):
        item = self.media_table.item(row, 0)
        if not item:
            return

        path = item.text().strip()

        if not path:
            return

        p = Path(path)

        if p.suffix.lower() in IMAGE_EXTS:
            self.show_image(path)
        else:
            self.log(f"이미지가 아닌 파일입니다. 저장 위치: {path}")
            QMessageBox.information(self, "파일 저장 위치", path)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = InstagramForensics()
    win.show()
    sys.exit(app.exec())
