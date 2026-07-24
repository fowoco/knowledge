
### Intent 분류 규칙 정의서


#### 1. Intent 정의 (7개)

→ workflow yaml 파일 기준에 맞췄습니다.

| **Intent Code** | **적용 업무** |
| --- | --- |
| WORK_INSTRUCTION | 작업 지시, 근무 일정 변경, 현장 행동 안내 |
| DOCUMENT_REQUEST | 여권/등록증/계약서/증명서 등 특정 서류를 받아내거나 제출을 추적하는 것 자체가 지금 할 일인 경우 |
| PAYROLL_EXPLANATION | 급여, 수당 , 공제 내역, 출퇴근/근태 관련 설명 및 문의 |
| WORKER_ONBOARDING | 신규 입사자 등록, 보험 최초 가입, 초기 프로필 생성 (이미 첨부된 서류 기반 처리) |
| EMPLOYMENT_CHANGE | 퇴사, 무단결근/연락두절, 사업장 변경, 휴가 등 재직 상태 변동 이벤트의 확인 및 신고 |
| EXPIRY_RENEWAL | 근로계약/체류기간/고용허가기간 등의 만료 임박,연장,갱신 절차 |
| OUT_OF_SCOPE | 위 6개 어디에도 해당하지 않는 요청 (생산/영업 등 HR 범주 밖, 잡담 등 ) |

#### 2. 핵심 분류 원칙

1. **“최종 목적”이 아니라 “지금 요청된 행위” 기준**
    
    발화문에서 결과적으로 무엇에 쓰이는지가 아니라, 이 문장이 지금 당장 실행을 요구하는 행위를 기준으로 인텐트를 정한다.
    
    > 예시 ) “여권 사본 받아줘 ”
    > 
    > 
    > → 여권 사본을 요청하는 이유가 나중에 체류 연장에 쓰일 것이라도 지금 발화에 따라 DOCUMENT_REQUEST
    > 
    
2. **여러** **Intent  처리 기준**
    
    b-1. 한 발화문 내에 여러 Intent가 있다면 함께 붙인다.
    
    b-2. 발화문에 “~를 받아서/제출받아/요청해” 등 서류를 확보하는 행위 자체를 명시적으로 지시하는 표현이 있으면, 그 업무의 최종 목적이 무엇이든 DOCUMENT_REQUEST를 별도 인텐트로 함께 붙인다.
    
    - 서류가 이미 첨부되어 있거나 시스템에 존재한다고 발화문 내에 명시되어 있다면  DOCUMENT_REQUEST 붙이지 않음
    - 발화문에 “진행해줘/준비해줘/설명해줘” 처럼 목적 업무만 지시되고 서류 확보 표현이 없으면 DOCUMENT_REQUEST  붙이지 않음 (서류 확보는 각 워크 플로우 내부 스텝에서 자체적 처리)
    - 서류 확보 표현이 명시적으로 있으면 목적 업무 인텐트와 함께 DOCUMENT_REQUEST 동반
    
    > 예시) "첨부한 계약서로 등록 초안 만들어줘” : 서류 확보 표현 X (이미 첨부)
    > 
    > 
    > → WORKER_ONBOARDING
    > 
    > 예시) "여권이랑 계약서 먼저 받아서 올려주세요, 등록해야 해요” : 서류 확보 표현 O
    > 
    > → DOCUMENT_REQUEST, WORKER_ONBOARDING
    > 
    > 예시) "계약 만료 다가오니 재계약 준비 진행해줘” : 서류 확보 표현 X
    > 
    > → EXPIRY_RENEWAL
    > 
    > 예시) "재계약 준비하면서 서명본도 받아서 첨부해줘” : 서류 확보 표현 O
    > 
    > → EXPIRY_RENEWAL, DOCUMENT_REQUEST
    > 
    
3. **서류의 실제 존재 여부는 Intent Agent의 판단 범위가 아니다.**
    
    오직 발화문의 표현만 보고 판단한다. 그 서류가 실제로 회사 시스템에 있는지, 근로자가 아직 제출하지 않았는지 등의 실물 확인은 후속 에이전트 (Slot/Ambiguit Agent)의 역할
    
4. **Multi Intent의 순서 배치**
    
    한 문장에서 인텐트가 2개 이상 나올 경우,  발화문에 언급된 순서대로 배치한다. 이 순서는 업무상 선후관계를 부여하지 않는다. (workflow yaml 파일의 역할)
    
5. **OUT_OF_SCOPE는 다른 인텐트와 공존 불가하다.**
    
    OUT_OF_SCOPE으로 판단되면 그 값 하나만 있어야한다.
    

#### 3. 경계 케이스 (클로드가 잘 헷갈린 케이스 정리)

| **헷갈리는 쌍** | **구분 기준**  |
| --- | --- |
| **DOCUMENT_REQUEST** & **WORKER_ONBOARDING** | 서류가 이미 발화문 내에 주어졌는가? → YES : **WORKER_ONBOARDING**만
서류 확보 지시가 발화문에 명시 되어 있는가? 
→ YES : **DOCUMENT_REQUEST** 함께 표기 |
| **DOCUMENT_REQUEST** &
**EXPIRY_RENEWAL** | “준비해줘/진행해줘”만 있으면 **EXPIRY_RENEWAL** 단독 
”받아줘” 와 같은 표현이 명시되어 있으면 **DOCUMENT_REQUEST** 함께 표기 |
| **DOCUMENT_REQUEST** & 
**PAYROLL_EXPLANATION** | “명세서”와 같은 서류가 이미 있다고 언급되면 **PAYROLL_EXPLANATION** 단독
서류 확보 지시가 들어가면 **DOCUMENT_REQUEST** 함께 표기 |
| **EMPLOYMENT_CHANGE** &
**WORK_INSTRUCTION** | 재직 상태 자체의 변동(퇴사,결근,연락두절 등)이면 **EMPLOYMENT_CHANGE**
근무 배치,일정 변경 지시 등이면 **WORK_INSTRUCTION**
둘 다 명시되어 있으면 함께 표기 |
| **EMPLOYMENT_CHANGE** &
**EXPIRY_RENEWAL** | 재직 상태 자체가 변동 된 사건 ( 퇴사, 결근 ) 이면 **EMPLOYMENT_CHANGE** 
계약/체류/허가의 만료 갱신 절차이면**EXPIRY_RENEWAL** 
둘 다 명시되어 있으면 함께 표기 |




### Intent 데이터 정의서


### 1. A.X 학습/평가용 데이터 스키마

```json
{
  "id": "hr_train_00147",
  "hr_input": "재계약 준비하면서 서명본도 받아서 첨부해줘",
  "intents": [
    {"intent": "EXPIRY_RENEWAL", "evidence": "재계약 준비하면서"},
    {"intent": "DOCUMENT_REQUEST", "evidence": "서명본도 받아서 첨부"}
  ],
  "source": "manual",
  "split": "for_test"
}
```

| **필드** | **타입** | **설명** |
| --- | --- | --- |
| id | string | 고유 ID |
| hr_input | string | HR 담당자 원문 발화 |
| intents | list[object] | 정답 Intent (1개 이상) |
| intents[].intent | string | 7개 intent코드 중 1 |
| intents[].evidence | string | null | 원문에서 그대로 가져온 부분 문자열 (OUT_OF_SCOPE의 경우 null) |
| source | string | manual (사람 생성) | auto ( AI생성 ) |
| split | string | for_test  | for_train |

### 2.  A.X 모델 출력 스키마

```json
{
  "intents": [
    {"intent": "EXPIRY_RENEWAL","evidence": "재계약 준비하면서"},
    {"intent": "DOCUMENT_REQUEST","evidence": "서명본도 받아서 첨부"}
  ]
}
```

| **필드** | **설명** |
| --- | --- |
| intents[].intent | 7개 intent코드 중 1 |
| intents[].evidence | 원문에서 그대로 가져온 부분 문자열 (OUT_OF_SCOPE의 경우 null) |

### 2 -1 .  최종 출력 스키마 → 모델 출력에 규칙기반으로 감싸기

```json
{
  "request_id": "req_20260724141530_0042",
  "hr_input": "재계약 준비하면서 서명본도 받아서 첨부해줘",
  "intents": [
    {"intent": "EXPIRY_RENEWAL", "evidence": "재계약 준비하면서"},
    {"intent": "DOCUMENT_REQUEST", "evidence": "서명본도 받아서 첨부"}
  ],
  "status": "CONFIRMED",
  "meta": {
    "model": "A.X-4.0-Light",
    "timestamp": "2026-07-24T14:15:30+09:00"
  }
}
```

| **필드** | **설명** |
| --- | --- |
| request_id | req_YYYYMMDDHHMMSS_CODE |
| hr_input | 입력 원문 |
| intents[].intent | 7개 intent코드 중 1 |
| intents[].evidence | 원문에서 그대로 가져온 부분 문자열 (OUT_OF_SCOPE의 경우 null) |
| status | 규칙 기반 검증 결과 |
| meta.model | 모델명 |
| meta.timestamp | 생성 시각 |

