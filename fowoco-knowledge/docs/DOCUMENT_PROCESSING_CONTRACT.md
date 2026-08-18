# 범용 문서·Excel 처리 계약

## 목표

PDF·이미지·HWP·HWPX·XLSX·CSV Parser가 제각각인 결과를 내더라도 Server와 Client는
하나의 `Document IR`만 읽는다. 알려진 양식은 근거가 표시된 후보값을 만들고, 새 양식과
처리 불가 문서는 업무 DB에 자동 반영하지 않고 HR 검토로 전환한다.

## 공통 흐름

```text
업로드
  → 형식·암호화·용량 검사
  → 문서 역할·유형·Template 분류
  → Parser/OCR로 필드 후보와 원본 근거 생성
  → Schema·Tenant·민감도 검증
  → HR 수정·승인
  → 승인된 값만 업무에 반영
```

## 지원 수준

| 형식 | 현재 계약 | 자동 처리 기준 | 수동 전환 기준 |
| --- | --- | --- | --- |
| PDF | 텍스트·페이지·좌표 | 승인된 공식/사업장 Template | 암호화·스캔 품질 저하·미분류 |
| 이미지 | OCR text·좌표·confidence | 승인된 OCR Template | 낮은 confidence·유사/미분류 layout |
| HWP | 구조·텍스트 후보 | 승인 Parser와 Template | 손상·암호화·지원하지 않는 control |
| HWPX | XML locator·Template field | 승인된 Template version | locator 불일치·layout fingerprint 변경 |
| XLSX | Sheet·Header·Cell·수식/cache | Header mapping과 행 검증 통과 | Sheet/Header 미탐지·행별 오류 |
| CSV | 인코딩·구분자·개행·행 | Header mapping 통과 | 인코딩/구분자 불명확·Header 미탐지 |

이 표는 “모든 파일을 정확히 읽는다”는 보장이 아니다. 실제 Parser 지원 여부와 품질은
AI·Server 구현 및 Smoke Test 결과로 별도 표시한다.

## 필드 근거

모든 후보 필드는 다음 중 하나를 가져야 한다.

- `AVAILABLE`: 원문 문자열과 페이지 또는 Sheet/Cell 위치
- `UNAVAILABLE`: 값을 만들 수 없는 구체적인 이유

AI가 추측한 값만 있거나 좌표·Cell 근거가 없는 값은 승인 후보가 될 수 없다. HR의
수정값은 원본 후보와 분리해 감사 가능한 상태로 저장한다.

## Template 소유권

- `OFFICIAL`: FOWOCO가 공식 출처·locator test·HR 검토를 거쳐 전 사업장에 배포
- `TENANT`: 한 회사가 검토·승격하며 `owner_company_ref`가 같은 회사에만 노출
- AI가 발견한 유사 양식은 항상 `DRAFT`이며 자동으로 Active가 되지 않음
- Active version은 수정하지 않고 새 version으로 승격

## Excel·CSV 규칙

- 숨김 Sheet/행/열과 병합 Cell을 제거하지 않고 메타데이터에 기록
- 날짜 serial, 금액, 백분율, 문자형 숫자의 원본값과 정규화값을 함께 보존
- 수식 문자열과 cached value를 보존하고 Parser가 임의 재계산하지 않음
- 오류 행은 `REVIEW_REQUIRED` 또는 `REJECTED`로 분리하고 정상 행은 유지
- 암호화 파일, 읽을 Sheet 없음, Header 미탐지는 전체 수동 처리

## 팀 공통 Contract Test

`data/evaluation/document_ir_cases.jsonl`의 6개 비식별 Fixture를 AI·Server·Client가
공유한다. 새 Parser가 추가돼도 반환 결과가 이 Schema를 통과해야 한다. 실제 파일
미리보기·다운로드 구현은 Server 범위이며 이 계약은 결과 데이터 형식만 소유한다.
