# TTS 작업실

내 목소리 TTS 나레이션 로컬 웹앱. 사용법·구조는 README.md, 설계 결정은 docs/PLAN.md, 진행 기록은 docs/PROGRESS.md.

- 드라이브 문서로 나레이션을 만들어 달라는 요청은 `.claude/skills/drive-narration/SKILL.md` 절차를 따른다.
- 켜기 `./studio` → http://127.0.0.1:7870 . **7860 은 다른 프로젝트(plantid)가 쓰고 있어 피했다.**
- 서버 테스트: `.venv/bin/python -m pytest tests` (가짜 모델). 화면: `cd web && npm run build`.
- 모델은 `.hf/` (HF_HOME). 16GB 맥이라 TTS·ASR 동시 상주 시 GPU 최대 12.5GB — 모델 더 키우지 말 것.
- 발음 검사 기준(server/check.py)은 실제 사례로 맞춘 값. 바꾸면 tests 의 실제 사례가 계속 통과하는지 볼 것.

## dorms 관점
- 혼자 쓰는 로컬 앱, 학생 데이터 없음 → edzip(개인정보처리방침) 트랙 해당 없음.
- 보안: 127.0.0.1 바인딩, Host/Origin 검사(DNS 리바인딩·CSRF), CSP·X-Frame-Options, `innerHTML` 미사용,
  업로드 크기 제한, 경로 탈출 차단(테스트 있음).
- 목소리 샘플(voices/)·결과물(projects/)은 SSD 에만. .gitignore 로 막아 둠.
