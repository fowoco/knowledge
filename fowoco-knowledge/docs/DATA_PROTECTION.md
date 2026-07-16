# LLM 전송 경계와 데이터 보호

## 원칙

FOWOCO는 원본 여권·외국인등록증·근로계약서 파일을 LLM에 직접 전달하지 않습니다. OCR 또는
업무 DB에서 필요한 필드만 구조화하고, 해당 Workflow의 필수·선택 Slot만 남긴 뒤 식별자를
마스킹합니다.

```text
보호 DB의 원본 문서
  -> OCR·필드 추출
  -> 내부 worker_id와 문서 ID 연결
  -> Workflow Slot 허용목록 적용
  -> 실명·등록번호·전화번호·이메일 마스킹
  -> 최소 Payload만 LLM 전달
  -> 처리 결과와 마스킹 이력 감사로그
```

## 구현 범위

| 구분 | MVP 처리 |
| --- | --- |
| 권한 | `ADMIN`, `HR_MANAGER`, `HR_OPERATOR`, `WORKER_LINK` 역할 분리 |
| 전송 | HTTPS/TLS 사용을 인프라 정책으로 고정 |
| 저장 | 민감 원본은 보호 DB·오브젝트 스토리지에 암호화 저장 |
| LLM 입력 | Workflow 허용 Slot만 전송, 원본 문서와 직접식별자 제거 |
| 마스킹 해제 | HR 관리자만 사유를 남기고 조회, 감사로그 필수 |
| 학습 로그 | 마스킹된 수정 전·후 문장과 오류코드만 저장 |

MVP는 더미 데이터를 사용하므로 완전한 규제 대응을 주장하지 않습니다. 대신 실제 데이터로
전환할 때 필요한 접근경계와 전송 최소화가 코드에 반영됐음을 보여줍니다.

## 실행

```bash
.venv/bin/python -m fowoco_knowledge sanitize-llm-payload \
  WF-DOC-001 fowoco-knowledge/examples/llm_payload_with_pii.json
```

출력에는 LLM으로 보낼 `payload`와 제거·마스킹된 항목을 설명하는 `redactions`가 함께 나옵니다.
실제 값은 감사로그에 남기지 않고 필드 경로와 마스킹 유형만 기록합니다.
