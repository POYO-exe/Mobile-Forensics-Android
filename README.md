# Instagram Forensics Extractor

루팅된 Android 기기에서 Instagram 앱 데이터를 추출하여 SQLite 데이터베이스를 분석하고 화면에 표시하는 디지털 포렌식 실습 프로그램입니다.

> **주의**
>
> 본 프로그램은 본인이 소유하거나 분석 권한이 있는 Android 기기에서만 사용해야 합니다.
> Instagram 데이터 구조는 앱 버전에 따라 달라질 수 있으므로 일부 항목은 정상적으로 분석되지 않을 수 있습니다.

---

# 기능

- ADB 연결 확인
- Root 권한 확인
- Instagram 데이터 추출
- SQLite 데이터베이스 자동 탐색
- Follow / Following 관련 테이블 탐색
- DM 관련 테이블 탐색
- Profile 정보 탐색
- Search 기록 탐색
- 이미지 캐시 보기
- CSV 저장
- JSON 저장

---

# 개발 환경

- Python 3.11 이상
- Android Platform Tools (ADB)
- 루팅된 Android 기기
- USB 디버깅 활성화

---

# 1. 코드 준비

---

# 2. Python 가상환경 생성

Windows

```bash
python -m venv venv
```

Mac / Linux

```bash
python3 -m venv venv
```

---

# 3. 가상환경 실행

Windows CMD

```cmd
venv\Scripts\activate
```

Windows PowerShell

```powershell
.\venv\Scripts\Activate.ps1
```

Mac

```bash
source venv/bin/activate
```

Linux

```bash
source venv/bin/activate
```

정상적으로 실행되면

```
(venv)
```

가 표시됩니다.

---

# 4. 패키지 설치

```bash
pip install -r requirements.txt
```

설치 확인

```bash
pip list
```

예시

```
PySide6
Pillow
```

---

# 5. ADB 설치

Android Platform Tools를 설치합니다.

ADB가 정상인지 확인

```bash
adb version
```

예시

```
Android Debug Bridge version 1.0.41
```

---

# 6. 휴대폰 연결

USB 디버깅을 활성화합니다.

휴대폰 연결

```bash
adb devices
```

정상

```
List of devices attached

1234567890 device
```

---

# 7. Root 확인

```bash
adb shell
```

```bash
su
```

정상이라면

```
#
```

프롬프트가 나타납니다.

---

# 8. 프로그램 실행

```bash
python instagram_forensics_gui.py
```

---

# 사용 순서

프로그램 실행 후

```
ADB 연결 확인
↓

루팅 권한 확인
↓

Instagram 데이터 추출
↓

DB 자동 분석
↓

CSV / JSON 저장
```

순서대로 진행합니다.

---

# 추출되는 데이터

프로그램은 Instagram 내부 SQLite 데이터베이스를 자동으로 탐색하여 다음과 같은 정보를 분석합니다.

- Follow
- Following
- Profile
- DM
- Search History
- Cached Images

실제 추출 가능한 항목은 Instagram 버전에 따라 달라질 수 있습니다.

---

# 저장 위치

Instagram 추출

```
instagram_extracted/
```

분석 결과

```
instagram_report/
```

예시

```
follow.csv

follow.json

dm.csv

dm.json

profile.csv

search.csv
```

---

# 문제 해결

### unauthorized

```
adb devices

unauthorized
```

휴대폰 화면에서

```
USB 디버깅 허용
```

을 눌러야 합니다.

---

### device not found

ADB가 연결되지 않은 상태입니다.

확인

```bash
adb devices
```

---

### Root 권한 없음

```bash
adb shell

su
```

실행 시

```
#
```

가 나타나야 합니다.

---

### Instagram 데이터 추출 실패

Instagram 패키지가 존재하는지 확인합니다.

```bash
adb shell

su

ls /data/data/com.instagram.android
```

---

# 라이선스

교육 및 디지털 포렌식 실습 목적으로 작성되었습니다.

사용자는 관련 법률과 서비스 약관을 준수해야 합니다.