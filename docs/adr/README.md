# Architecture Decision Records

ADR은 Knowledge의 지식 스키마, 출처 정책, 검수 체계와 데이터 계약처럼
되돌리기 어렵거나 소비 저장소에 영향을 주는 결정을 기록합니다.

## 작성 규칙

1. `NNNN-short-title.md` 형식으로 번호 증가
2. 상태는 `Proposed`, `Accepted`, `Superseded`, `Deprecated` 중 하나
3. 선택한 안뿐 아니라 대안과 선택하지 않은 이유 기록
4. 결정 변경 시 기존 문서를 삭제하지 않고 새 ADR에서 대체 관계 표시

새 문서는 [`0000-template.md`](0000-template.md)를 복사해 작성합니다.
