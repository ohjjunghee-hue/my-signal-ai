MY SIGNAL AI PRO V48 - 확인된 2개 문제 수정 패키지

적용 대상: GitHub 저장소의 server.py와 index.html (2026-10-28 확인 버전)
1. index.html에 남은 V45 제목을 V48로 변경
2. DEEP_MARKETS 설정 상한을 160 -> 500으로 변경. 기본값 80 유지.
   주의: 500으로 올리면 실제 API 부하/분석 시간/429 제한이 늘어날 수 있음.
   따라서 무작정 467로 설정하지 마세요. 전체 종목의 빠른 1차 선별과
   심층 분석의 단계적 분리 및 실측 부하 테스트가 추가로 필요합니다.

사용법 (PC 또는 GitHub Codespaces 터미널):
python apply_fix.py /path/to/my-signal-ai
python -m unittest -v test_fix.py

수정 전 원본은 *.pre_v48_fix.bak로 백업됩니다.
이 ZIP은 GitHub에 자동 반영되지 않습니다. 서버에 직접 실행하면 안 됩니다.
이 패키지는 2개 설정/표시 오류만 해결하며 전체 5개 영역 통합 개선 완료본이 아닙니다.
실제 GitHub 전체 코드에 대한 회귀 테스트 및 Render 재배포는 아직 미실시입니다.
