# V47 영구 저장 추가팩

기존 `server.py`, `outcome_validation.py`, `index.html`, `v46_boot.py`, `v46_dashboard.html`은 **그대로 유지**합니다.

## 설치
1. ZIP의 4개 파일(`Dockerfile`, `v47_boot.py`, `v47_storage.py`, `README_V47_KO.md`)을 GitHub 저장소 최상위에 업로드하고 `Dockerfile`만 덮어씁니다.
2. **영구 저장을 활성화하려면** 별도 PostgreSQL DB(예: Neon)를 생성하고 Render 서비스의 Environment에 `DATABASE_URL` 환경변수를 등록합니다. 비밀번호/접속 URL은 GitHub나 채팅에 올리지 마세요. PostgreSQL의 SSL 연결 옵션은 제공자 설정을 따릅니다.
3. Render 배포가 Live인지 확인합니다. `/api/storage-health`의 `configured:true`, `mode:remote_saved`를 확인합니다.
4. DB 연결 전에 배포하면 기존 V46처럼 실행되지만 `not_configured` 경고가 표시되며 기록 보존이 보장되지 않습니다.

## 데이터 안전
- 외부 PostgreSQL에 **SQLite 전체 파일 스냅샷**을 약 30초마다 보존합니다. 실시간 거래 로그나 완전한 무손실 복제는 아닙니다.
- 프로세스 종료 직전의 최대 약 30초 기록과 외부 저장 실패 중 기록은 유실될 수 있습니다.
- 최초 실행에 기존 SQLite 파일이 이미 있다면 이를 덮어쓰지 않습니다. 기존 파일이 없는 새 배포에서 원격 스냅샷을 복원합니다.
- **동시에 여러 인스턴스 실행 금지**: 마지막 저장한 인스턴스가 원격 스냅샷을 덮어쓸 수 있습니다.
- 무료 Render 서비스는 휴면 중에 관측을 수행하지 않습니다. 복원 후 관측 공백은 여전히 남습니다.
- 원격 DB 장애로 복원에 실패하면 **빈 데이터로 시작하지 않고 배포를 실패 처리**합니다.
- 스냅샷 100MB 초과 시 저장 실패로 보고합니다. 스냅샷이므로 장기적으로는 PostgreSQL 테이블 직접 기록 방식으로 전환하는 것이 좋습니다.
- `/api/storage-health`는 DB 접속 문자열이나 비밀번호를 노출하지 않습니다.

## 제한
기존 서버가 살아 있는 동안 처음 `DATABASE_URL`을 추가할 때, 이전 임시 디스크에만 있던 기록을 자동으로 이전할 수는 없습니다. 이미 사라진 기록은 복원 불가합니다.
