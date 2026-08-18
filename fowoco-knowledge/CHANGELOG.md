# Changelog

## Unreleased

- PDF·이미지·HWP·HWPX·XLSX·CSV 공통 Document IR과 Field Evidence 계약 추가
- 공식 Template과 회사 전용 Tenant Template의 소유권·승격·격리 정책 추가
- Excel 수식·cache·날짜·숨김·병합 Cell과 행별 오류 보존 규칙 및 6개 Fixture 추가
- 6대 Workflow의 Master/Subflow 관계, 공통 상태·이벤트·단계 의존성·완료 증빙 계약 추가
- Workflow별 정상·정보 누락·수동 검토 경로를 고정한 Runtime E2E Fixture 18건 추가
- 외부기관 처리와 민감 판단의 HR Gate, 병렬 READY 조건, 복합 Intent 분해 정책 검증 추가
- Workflow Slot에 UI·Agent 공용 한글 표시명, 쉬운 표현, 출처 우선순위, 담당 주체와 검증 규칙 추가
- 이름 변형·복합 요청·Intent 경계·OUT_OF_SCOPE·베트남어 안내 E2E Gold 후보 11건 추가
- 여권·외국인등록증 제출 상태를 Knowledge 소유 조회형 Context Slot으로 정의
- 단일 `EXPIRY_RENEWAL`에서 재계약 `WF-CON-001`과 체류연장 `WF-STY-001`을 분리·확인하는 대표 계약 추가
- 대상 탐색, 핵심정보 보존, 내부 키 노출과 자동 실행 차단 검증 추가
- 최종 검수 Intent 데이터 1,340건을 manifest의 기준 원본으로 지정
- Train 1,072건 / Validation 268건의 실제 ID 경로·SHA-256·최종 라벨 분포 정정
- 검수 전 데이터와 최종 데이터의 용도, Hugging Face와 Git LFS의 역할 구분
- Intent split Schema와 중복·누락·해시·분포 검증 추가

## 0.2.0 - 2026-07-16

- 필요서류 187건과 EPS 세부업종 847건의 원본 해시·버전을 고정
- 제조업 필요서류 122건과 제조업 세부업종 569건 정규화
- 데이터 적재·검증·조회 CLI 추가
- 고용변동 신고와 계약·고용허가·체류 연장 절차 분리
- 고용변동 신고의 HR 사실확인·기한 후보 계산·증빙 완료 기준 추가
- 다국어 사업내용의 표본 불일치로 번역 사용을 보류하고 품질 제한 문서화

## 0.1.0 - 2026-07-16

- FOWOCO 6개 Intent와 9개 Domain 정의
- MVP Workflow Catalog와 필수 Slot 정책 추가
- 공식 출처 레지스트리와 문서 체크리스트 추가
- Seed·평가 데이터, 스키마, 검증 CLI 추가
