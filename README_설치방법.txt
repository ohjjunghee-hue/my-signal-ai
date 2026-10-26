MY SIGNAL AI PRO V31 — 서버+갤럭시 통합 패키지

포함: server.py(빗썸 시장 수집·위험 판정·뉴스 RSS·SQLite), index.html(갤럭시 웹 화면), Dockerfile, railway.json, test_engine.py.

[Railway 배포]
1. ZIP을 압축 해제하고 GitHub의 비공개 저장소에 파일을 올립니다.
2. Railway에서 New Project → Deploy from GitHub Repo → 해당 저장소 선택.
3. Variables에 ACCESS_TOKEN=본인이 정한 길고 추측하기 어려운 암호, SCAN_SECONDS=300, DEEP_MARKETS=25, DATA_DIR=/data 를 설정합니다.
4. Railway에서 Volume을 만들고 /data 경로에 연결합니다. 연결하지 않으면 재배포 시 기록이 사라질 수 있습니다.
5. Networking에서 HTTPS 도메인을 생성합니다. 휴대전화 브라우저로 https://... 접속 후 암호 입력.
6. 갤럭시 브라우저 메뉴에서 '홈 화면에 추가'로 바로가기 생성.

[PC에서 로컬 테스트]
Python 3.10+ 설치 후 같은 폴더에서 python -m unittest -v test_engine 실행.
python server.py 실행 후 http://127.0.0.1:8765 접속.

[제약]
서버는 24시간 실행 가능한 구조이나 실제 운영은 클라우드 요금제/배포 상태에 달려 있습니다.
빗썸 API의 실시간 WebSocket 체결·호가 감시는 미구현이며 주기적 REST 조회 방식입니다.
SNS·LLM 분석·푸시 알림·실제 +10% 확률 예측·정교한 백테스트는 미구현입니다.
뉴스 RSS는 정보 목록이며 매수 점수에 반영하지 않습니다.
BUY 자동 추천/자동매매를 하지 않습니다. READY는 관찰 후보입니다.
실거래 성능은 미검증이며 투자 판단에 단독 사용하지 마세요.
