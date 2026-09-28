# 진행 기록 (자동 이어하기용)

사용자 요청(2026-09-28 03:10경): PLAN.md 1~4단계를 한 번에 끝까지 만든다. 사용자는 자는 중.
아침에 결과를 바로 확인할 수 있게 해 둔다. 한도에 걸려 끊기면 예약 작업이 이 파일을 보고 이어 간다.

## 규칙
- 계획은 PLAN.md. 막히면 가장 단순한 쪽으로 결정하고 여기 "결정" 에 적는다. 사용자에게 묻지 않는다.
- 단계마다 실제로 돌려서 확인(테스트·브라우저)한 것만 완료로 적는다.
- 목소리·결과물은 SSD 에만. git push 없음.

## 상태
- [x] 0. 뼈대 — studio/ 백엔드 + tests (20개 통과, 가짜 모델)
- [x] 1. 기본 편집기 + 내보내기(iCloud)
- [x] 2. 자동 발음 검사
- [x] 3. 목소리 관리·녹음, 줄별 목소리/속도/쉼 (녹음 버튼은 마이크가 없어 실측 못 함, 업로드 경로는 실측)
- [x] 4. 초록 자막 영상
- [x] 5. ep01 로 끝까지 실제 검증 + README 갱신 + 아침 보고

## 결정

## 기록
- 메모리 실측: TTS(1.7B bf16) 생성 중 최대 10.9GB, ASR 1.7B-8bit 단독 3.2GB. 0.6B ASR 은 "사마귀→사막이" 오인 → 오탐 줄이려고 1.7B 채택.
  두 모델 상주 + mx.set_cache_limit(1GB). 앱에서 실측 후 문제면 TTS 8bit 로.

## 중단 지점 (03:4x, 사용량 한도)
- 백엔드 studio/ 완성: config, textsplit, check(자모 거리 ≥3 이면 틀림), store, engine(GPU 잠금), audio, subtitles(Pillow+ffmpeg), exporter, worker(큐+SSE), app(FastAPI, 127.0.0.1:7860, Host/Origin 검사, CSP).
  tests/test_studio.py 20개 통과 (가짜 모델). 줄 생성 API 에 ?manual= 추가함.
- 프론트 web/ (Vite React TS, npm install 완료): types.ts, api.ts, player.ts(재생·녹음 훅), App.tsx, components/Sidebar.tsx 작성됨.
- 남은 것:
  1. web/src/components/ProjectView.tsx — 탭: 줄(LineRow: 재생·발음결과 diff·목소리·속도·뒤쉼·테이크 칩·다시·무시, 하단 전체 듣기 바+현재 줄 강조),
     대본(textarea → PUT script → 전체 생성), 설정(기본 목소리·temperature·쉼·LUFS·자막 설정+미리보기 PNG·에피소드 삭제),
     내보내기(버튼·진행·파일 목록·Finder 열기·루마퓨전 사용법). App.tsx 가 넘기는 props 이름 그대로 맞출 것.
  2. web/src/components/VoicesView.tsx — 목소리 목록(재생·대본 수정·삭제), 추가(이름+녹음 30초/파일 올리기 → 받아쓰기 확인 안내, 읽을 예시 문장).
  3. web/src/index.css — 토큰 기반 라이트/다크, App.tsx·Sidebar 가 쓰는 클래스(app, sidebar, brand, side-*, main, empty, toast, btn primary/ghost/sm, row gap-s, dot live, muted, bad-text).
  4. ./studio 실행 스크립트 (web/dist 없으면 npm run build 후 python -m studio.app, 브라우저 열기).
  5. 실제 모델로 ep01 끝까지: 생성→발음검사→내보내기(iCloud) → 브라우저로 화면 확인·스크린샷, 메모리 실측.
  6. README 갱신, .gitignore 에 projects/ web/node_modules web/dist 추가, 아침 보고.

## 완료 (07:40)
- 백엔드 폴더 이름 studio/ → server/ (실행 스크립트 ./studio 와 이름이 겹쳐서). 포트 7870 (7860 은 plantid 가 사용 중).
- 실제 모델로 ep01 8줄: 전체 생성 → 발음 검사 전부 통과 → 7번 "사마귀→사막이"(짧은 줄 2자모) 발견 →
  짧은 줄은 더 엄격하게(25자모 미만 1, 이상 2) 기준 변경 → 다시 뽑기로 "사마귀입니다" 확인.
- 화면에서 확인: 에피소드 만들기, 대본 적용·생성, 실시간 상태, 속도/쉼 변경 저장, 전체 듣기+현재 줄 강조,
  줄별 목소리 변경→자동 재생성→되돌리면 옛 테이크 재사용, 쓰는 목소리 삭제 거부, 발음 확인 표시(찢→뛰)·이대로 쓰기,
  자막 설정·미리보기, 내보내기 → iCloud Drive/TTS/ep01 카직스 생물학/ (wav 29.7초 = 자막영상 29.7초, -14.4 LUFS).
- 다크 모드 확인. 테스트 23개 통과.
- 못 한 것: 브라우저 녹음 버튼(이 환경에 마이크 없음), 아이패드 루마퓨전에서 실제로 불러오기.
