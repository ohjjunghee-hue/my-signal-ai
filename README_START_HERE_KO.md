# MY SIGNAL AI PRO — 통합 연구·검증 개발본

## 포함 기능
기존 서버/대시보드/차트, PRE/BUY 추적, 목표가 계산, 시장 가속 감시, 과거 15분봉 연구, 신호 성과 및 실패 감사. `event_validation.py`를 새로 추가해 봉별 목표가·손절가 도달 순서와 놓친 10% 상승 구간을 보수적으로 분석합니다.

## 빠른 실행
- 웹 대시보드: `python server.py` (기존 환경 설정 및 API 접속 필요)
- 연구용 캔들 수집: `python research_engine.py --markets KRW-BTC KRW-ETH --days 21 --output research_results`
- 신호 및 누락 감사: `python event_validation.py --input-dir research_results --output validation_results`
- 전체 테스트: `python -m unittest discover -p 'test_*.py'`

## 검증 상태
코드 단위 테스트는 수행 가능하지만 실제 빗썸 API 연동, 실시간 WebSocket, 장시간 운영, 실전 적중률은 검증되지 않았습니다. 15분봉만으로 3분봉 급등 직전 포착 능력을 입증할 수 없습니다. 목표가와 손절가가 같은 봉에서 터치되면 선후관계를 알 수 없으므로 성공으로 집계하지 않습니다.

## 배포 주의
현재 GitHub/Render 서비스는 자동 변경되지 않습니다. Render 무료 플랜의 임시 디스크에서는 SQLite 데이터가 재배포/재시작 시 사라질 수 있으므로 영구 볼륨/외부 DB를 설정해야 합니다. 본 프로그램은 연구·모의 판단 도구이며 실제 매매를 자동 실행하지 않습니다.
