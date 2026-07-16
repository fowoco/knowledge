# 외부 데이터 수집 판단

## 바로 적재한 자료

| 출처 | 처리 결과 | 이유 |
| --- | --- | --- |
| [고용허가제 민원서식별 필요서류](https://www.data.go.kr/data/15153513/fileData.do) | 원본 187행 중 제조업·전업종 122행 정규화 | 이용범위 제한 없음, 서류 Workflow에 직접 사용 |
| [EPS 허용 세부업종·사업내용](https://www.data.go.kr/data/15153406/fileData.do) | 원본 847행 중 제조업 569행 정규화 | 이용범위 제한 없음, 업종 표준화에 직접 사용 |

## 링크 조회만 유지한 자료

| 출처 | 현재 결정 | 이유 |
| --- | --- | --- |
| [EPS 용어사전](https://mainevent.eps.go.kr/eo/VocaDicLstR.eo) | `LINK_ONLY` | 76개 용어는 확인했으나 재배포 조건과 정의의 현행성 검토 필요 |
| [EPS 외국어 문장 DB](https://eps.hrdkorea.or.kr/e9/user/language/language.do?method=languageSearch&searchLanguage=01) | `LINK_ONLY` | 검색 활용은 가능하지만 전체 크롤링·재배포 조건이 불명확 |
| [국가법령정보 Open API](https://open.law.go.kr/LSO/openApi/guideList.do) | `DEFERRED` | 키 발급 후 조문·시행일 버전 관리가 필요하며 MVP는 선별 링크로 충분 |
| [특일 정보 Open API](https://www.data.go.kr/data/15012690/openapi.do) | `DEFERRED` | 영업일 계산 구현 시 필요하지만 현재 핵심 데이터보다 우선순위가 낮음 |

## 모델팀 후보로만 유지한 자료

| 출처 | 결정 | 이유 |
| --- | --- | --- |
| AIHub 민원 업무 자동화 | 직접 적재 보류 | HR Intent와 라벨 의미가 달라 정답 라벨로 전이할 수 없음 |
| AIHub 시간표현 데이터 | 모델팀 후보 | 날짜 추출 사전학습에는 유용하나 기준일 정규화는 별도 구현 필요 |
| KLUE NER | 모델팀 후보 | 한국어 NER Baseline에는 유용하지만 FOWOCO 서류명·급여 Slot 자체 라벨 필요 |

공개된 행 수가 많다는 이유로 데이터를 추가하지 않습니다. `Workflow에 직접 연결되는가`,
`이용조건이 명확한가`, `현행성을 검증할 수 있는가`, `모델 정답 라벨과 의미가 같은가`를 모두
통과한 자료만 정규화 스냅샷으로 커밋합니다.
