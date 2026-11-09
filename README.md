# 캠슐랭 (Campuslin)

같은 학교 학생끼리 만드는 학교 주변 밥집·술집 지도 (Flask + SQLite + 카카오맵)

## 핵심 기능
1. **학교 인증 기반 맛집 등록·리뷰**: 학교 이메일 인증, 카카오 장소 검색으로 가게 등록(중복 방지), 영수증 '방문 인증' 배지, 1인 1가게 1리뷰, 욕설 필터, 신고 3회 시 숨김
2. **학생 맞춤 필터 지도**: 가격대·좌석 규모·종류·기타 필터, 리뷰어 과반이 고른 태그만 표시, 마커 클러스터링
3. **모임 장소 투표**: 후보 2~5곳으로 투표 링크 생성, 로그인 없이 투표 가능, 5초마다 결과 갱신

## 폴더 구조
```
campuslin/
├─ app.py              # 서버 (라우트, API)
├─ models.py           # DB 테이블
├─ utils.py            # 태그 정의, 리뷰 집계, 메일 발송
├─ requirements.txt
├─ .env.example        # 설정 예시 → .env 로 복사
├─ templates/          # HTML 화면
└─ static/             # CSS, JS
```

## PyCharm에서 실행하기
1. PyCharm → **Open** → `campuslin` 폴더 열기
2. **Settings → Project → Python Interpreter**에서 가상환경(venv) 만들기 (Python 3.10 이상)
3. PyCharm 하단 **Terminal**에서:
   ```bash
   pip install -r requirements.txt
   ```
4. `.env.example`을 복사해서 `.env`로 이름 바꾸기
5. `app.py` 우클릭 → **Run 'app'**
6. 브라우저에서 http://localhost:5000 접속

> 처음에는 `.env`에서 `DEV_LOGIN=1`로 두면 OAuth 없이 테스트 로그인이 됩니다.
> 메일 설정이 비어 있으면 **인증 코드가 PyCharm 실행 콘솔에 출력**됩니다.

## 카카오 설정
[Kakao Developers](https://developers.kakao.com) → 내 애플리케이션 → 애플리케이션 추가

| 용도 | 설정 위치 | .env |
|---|---|---|
| 지도·장소 검색 | 앱 키 → **JavaScript 키** / 플랫폼 → Web → `http://localhost:5000` 등록 / 카카오맵 사용 설정 ON | `KAKAO_JS_KEY` |
| 카카오 로그인 | 앱 키 → **REST API 키** / 카카오 로그인 활성화 / Redirect URI `http://localhost:5000/auth/kakao/callback` / 동의항목 '닉네임' / 보안 → Client Secret | `KAKAO_REST_KEY`, `KAKAO_CLIENT_SECRET` |

> `localhost`와 `127.0.0.1`은 다른 도메인으로 취급됩니다. 등록한 주소와 같은 주소로 접속하세요.

## 학교 설정
`.env`의 `SCHOOL_NAME`, `SCHOOL_EMAIL_DOMAINS`, `SCHOOL_LAT`, `SCHOOL_LNG`는 **처음 실행할 때 DB에 저장**됩니다.
나중에 바꾸려면 `instance/campuslin.db` 파일을 지우고 다시 실행하세요. (등록한 데이터도 지워집니다)

## 배포 전 체크리스트
- `DEV_LOGIN=0`
- `SECRET_KEY`를 긴 랜덤 문자열로 변경
- 배포 도메인을 카카오 Web 플랫폼과 Redirect URI에 추가
- `.env`, `instance/`는 GitHub에 올리지 않기 (`.gitignore`에 포함됨)
- 초기 데이터: 학교 주변 가게 20~30곳 미리 등록

## 학교 주변 가게 자동 등록 (카카오 로컬 API)
`.env`에 `KAKAO_REST_KEY`(카카오 개발자 콘솔 → 플랫폼 키 → REST API 키)를 넣고 터미널에서:
```bash
python import_places.py --dry-run            # 미리 보기 (저장 안 함)
python import_places.py                      # 반경 1km 음식점 등록
python import_places.py --radius 1.5 --cafe  # 반경 1.5km, 카페 포함
```
- 웹페이지 크롤링이 아닌 카카오 공식 API를 사용합니다.
- 가게 정보만 등록하고 리뷰는 만들지 않습니다. 여러 번 실행해도 중복 등록되지 않습니다.

## 실제 서비스 운영 (내 컴퓨터 + ngrok)
- `start_campuslin.bat` 더블클릭 → 운영 서버(`serve.py`)와 ngrok 터널이 함께 켜짐
- 접속 주소: `https://eagle-retiring-spry.ngrok-free.dev`
- 끄기: 뜬 검은 창 두 개 닫기 / 코드 수정 후에는 두 창을 닫고 다시 실행
- `serve.py`는 `DEV_LOGIN=1`, 기본 SECRET_KEY, 로그인 키·메일 설정 누락 시 실행을 막음

## 자동 백업
- 서버가 켜질 때 1번, 그 뒤 6시간마다 DB·사진을 `../campuslin_backups`에 복사 (DB는 최근 30개 보관)
- 직접 백업: `python backup_db.py`
- 복구: 서버 창 닫기 → 원하는 `campuslin_날짜.db`를 `instance/campuslin.db`로 덮어쓰기 → 다시 실행

## 운영자 페이지 (`/admin`)
- `.env`의 `ADMIN_EMAILS`에 운영자의 인증 학교 이메일 등록 → 상단에 🛠 운영 메뉴 표시
- 서비스 현황·최근 14일 추이, 신고된 리뷰·사진 복구/삭제, 폐업 신고 가게 처리

## 카카오맵 리뷰 가져오기 (시연용)
리뷰가 적은 초기 화면을 보완하기 위해, 운영자가 카카오맵 리뷰 일부를 출처와 함께 보여주는 시연용 기능입니다.

> **가져온 이유**: 이 서버는 정식 서비스 운영이 아니라, 학교 주변 맛집을 찾을 때의 불편함을 해결하는 서비스를
> 구현해 보기 위한 **과제 제출용**으로 만들었습니다. 실제 학생들에게 리뷰를 직접 받기 어려운 상황이라,
> 서비스가 어떻게 동작하는지 보여주기 위해 **임시로** 카카오맵 리뷰를 가져왔습니다.
> 실제로 운영한다면 이 기능은 끄고, 학교 인증을 거친 학생 리뷰만으로 채우는 것이 원래 목표입니다.

- **켜기/끄기**: `.env`의 `KAKAO_REVIEW_DEMO=1`일 때만 동작 (시연 후 `0`으로 변경)
- **가져오는 방법**: 운영자 페이지 → ⭐ 카카오맵 리뷰 가져오기 → "캠슐랭으로 보내기" 버튼을 즐겨찾기에 추가 →
  카카오맵 가게 페이지를 연 상태에서 버튼 클릭 → 그 페이지의 리뷰가 캠슐랭에 저장됨
- 서버가 카카오에 자동으로 접속해 수집하지 않고, 운영자가 직접 연 가게 페이지에서만 가져옵니다.
- 가게당 최대 5개, 같은 리뷰는 중복 저장되지 않음
- **표시 방식**: 가게 상세 화면 아래 "카카오맵 리뷰 (출처: 카카오맵)" 칸에 따로 표시
- 캠슐랭 별점·랭킹·통계·필터에는 포함되지 않음 (학교 인증 리뷰와 분리)
- 가져온 리뷰는 DB(`instance/`)에만 저장되어 GitHub에 올라가지 않음
- 시연이 끝나면 같은 페이지의 "가져온 카카오맵 리뷰 전부 지우기"로 삭제

### 가져오지 못한 가게
등록된 가게 중 아래 경우는 카카오맵 리뷰를 가져오지 못했습니다.
- 카카오맵에 **리뷰가 하나도 없는** 가게
- 리뷰는 있지만 **별점만 있고 글로 작성된 리뷰가 없는** 가게

이런 가게는 상세 화면에 "카카오맵 리뷰" 칸이 나타나지 않으며, 캠슐랭 학생 리뷰가 쌓이면 그 리뷰로 채워집니다.
