# 공식 데이터 적재 기준

## 목적

공공데이터를 모델 정답으로 오인하지 않고, Agent가 조회할 **업무 기준·업종 용어·출처**로
재현 가능하게 관리한다. 원본은 `local-data/`에 보관하고 검증된 제조업 정규화 결과만
저장소에 커밋한다.

## 데이터 스냅샷

| 출처 | 원본 | 제조업 정규화 | 실제 사용 |
| --- | ---: | ---: | --- |
| 고용허가제 민원서식별 업종별 필요서류 | 187건 | 122건 | 신청서별 서류 후보 조회 |
| EPS 허용 세부업종 및 사업내용 | 847건 | 569건 | 제조업 업종 표준화·검색 |

- 출처·버전·원본 SHA-256: `data/external/source_manifest.yaml`
- 정규화 결과·행 수·결과 SHA-256: `data/processed/manifest.yaml`
- 원본 이용조건: 공공데이터포털 표시 기준 `이용허락범위 제한 없음`

## 변환 규칙

### 필요서류

`해당업종`이 `전업종`이거나 제조업을 포함하는 행만 선택한다. 원본에
`제조업(필수)`가 표시된 경우에만 `REQUIRED`로 저장한다. 표시가 없는 행은 임의로
선택사항이라고 판단하지 않고 `OFFICIAL_CONFIRMATION_REQUIRED`로 저장한다.

### 세부업종

`대분류 업종명=제조업`인 행만 선택한다. 한국어 업종 분류와 영어 참고명만 저장한다.
다국어 열은 표본 확인 과정에서 한국어 사업내용과 의미가 맞지 않는 사례가 발견되어
MVP 번역 근거에서 제외한다.

> 이 847건은 Intent 학습 데이터가 아니다. 업종 검색·정규화용 사전이며 다국어 안내문은
> 검수된 별도 템플릿과 번역 계층을 사용한다.

## 재생성

```bash
# 인터넷에서 고정된 원본을 내려받고 SHA·행·컬럼 검증 후 재생성
.venv/bin/python -m fowoco_knowledge sync-official-data

# 이미 local-data/official에 원본이 있을 때
.venv/bin/python -m fowoco_knowledge sync-official-data --offline
```

원본 해시나 컬럼이 바뀌면 적재를 중단한다. 변경 내용을 사람이 확인한 뒤
`source_manifest.yaml`의 버전과 변환 규칙을 갱신해야 한다.

## Agent 조회 예시

```bash
.venv/bin/python -m fowoco_knowledge \
  list-required-documents "외국인 고용변동 등 신고" --json

.venv/bin/python -m fowoco_knowledge search-industries "금속가공제품" --limit 5
```
