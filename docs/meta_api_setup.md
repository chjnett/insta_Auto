# 메타(Instagram Graph) API 설정 가이드

> 작성일: 2026-07-22
> 상태: **아직 진행 전 — 참고용 문서.** DESIGN.md 기준 메타 API 자동 발행은 후순위(섹션 7 TODO 마지막 항목, 섹션 4.8)이며, 현재 파이프라인은 `output/ready_to_publish/`에 영상을 쌓는 것까지만 자동화하고 실제 업로드는 사람이 수동으로 진행한다. 이 문서는 나중에 `08_meta_publish.py`를 구현할 때 참고할 절차를 미리 정리해둔 것이다.
>
> 아래 내용은 Meta 공식 문서(developers.facebook.com)가 아니라 2026년 기준 서드파티 개발자 가이드 블로그들을 웹서치로 종합한 것이다. 실제 앱 심사를 제출하기 직전에는 반드시 Meta 공식 문서로 세부 항목(권한 이름, 요율 공식 등)을 재확인할 것.

---

## 1. 전체 흐름 요약

```
인스타 계정을 프로페셔널로 전환
        ↓
페이스북 페이지와 연결
        ↓
Meta for Developers에서 Business 앱 생성
        ↓
Instagram Graph API 제품 추가 + OAuth 권한 설정
        ↓
(개발 모드로 테스터 계정 대상 자체 테스트)
        ↓
앱 심사(App Review) 제출 → 통과
        ↓
Live 모드 전환
        ↓
Content Publishing API로 실제 발행 자동화
```

전체 소요 기간(계정 세팅 → 개발 → 심사 통과 → Live 전환): **약 4~6주** (심사 자체는 2~4주).

---

## 2. 계정 세팅

### 2.1 프로페셔널 계정 전환 (필수)
- **2026년 기준, 일반(개인) 인스타그램 계정은 어떤 공식 API로도 접근이 불가능하다.**
- 인스타그램 앱 → 설정 → 계정 → **프로페셔널 계정으로 전환**
- "비즈니스" 또는 "크리에이터" 중 선택 (릴스 자동 발행 목적이면 "비즈니스" 권장)

### 2.2 페이스북 페이지 연결 (필수)
- Instagram Graph API는 **반드시 연결된 페이스북 페이지**가 있어야 동작한다. Instagram 계정 단독으로는 API 접근 자체가 불가능하다.
- 경로: 인스타그램 앱 → 설정 → 계정 → **연결된 계정 → Facebook**
- 페이스북 페이지가 없다면 먼저 새로 생성해야 한다.

---

## 3. Meta 개발자 앱 생성

1. [developers.facebook.com](https://developers.facebook.com) 에서 Meta 개발자 계정 생성 (또는 기존 페이스북 계정으로 로그인)
2. **"앱 만들기"** → 앱 유형은 반드시 **비즈니스(Business)** 선택
3. 생성된 앱 대시보드에서 다음 제품을 추가:
   - **Instagram Graph API**
   - (필요 시) **Instagram Content Publishing API**

---

## 4. 권한(Permissions) 및 OAuth 설정

- 인증 방식: **Facebook Login을 통한 OAuth 2.0**, authorization code flow 구현 필요

### 4.1 발행 자동화에 필요한 핵심 권한
| 권한 | 용도 |
|---|---|
| `instagram_basic` | 계정 기본 정보 조회 |
| `instagram_business_content_publish` | 콘텐츠 발행 (구 `instagram_content_publish`에서 명칭이 바뀐 것으로 보임 — 실제 심사 화면에서 정확한 최신 명칭 재확인 필요) |
| `pages_show_list` | 연결된 페이지 목록 조회 |
| `pages_read_engagement` | 페이지 참여 데이터 조회 |

### 4.2 개발 모드 제약
- 앱 심사를 통과하기 전에는 **개발 모드**로만 동작하며, 앱 대시보드에 **테스터로 직접 등록한 계정**만 API 호출 대상이 될 수 있다.
- 우리 계정(발행 주체 계정)을 테스터로 등록해두면 심사 전에도 미리 API 호출 테스트가 가능하다.

---

## 5. 앱 심사 (App Review)

- 요청한 각 권한(`instagram_business_content_publish` 등)에 대해 **사용 목적 설명 + 실제 동작 화면 녹화(스크린캐스트) 시연**을 제출해야 한다.
- 심사 기간: **약 2~4주**
- **팁**: 파이프라인이 실제로 몇 편 이상 안정적으로 돌아가서 보여줄 콘텐츠가 쌓인 뒤에 심사를 제출하는 것이 통과율에 유리하다 (시연 영상에 실제 동작하는 파이프라인이 나와야 설득력이 있음).
- 심사 통과 후 앱을 **Live 모드**로 전환해야 실제 서비스(테스터 계정 외 사용)가 가능하다.

---

## 6. 실제 발행 API 사용법 (`08_meta_publish.py` 구현 시 참고)

Content Publishing은 **2단계 Graph API 호출**로 이루어진다:

1. **미디어 컨테이너 생성**
   ```
   POST /{ig-user-id}/media
   ```
   - 영상/이미지는 **로컬 파일 직접 업로드가 아니라, 공개적으로 접근 가능한 URL**을 파라미터로 넘겨야 한다.
   - 즉 `output/ready_to_publish/`의 mp4를 어딘가 공개 호스팅(예: 임시 클라우드 스토리지, S3 등)에 올려서 URL을 확보하는 단계가 먼저 필요함 — 현재 파이프라인엔 없는 신규 컴포넌트.

2. **컨테이너 발행**
   ```
   POST /{ig-user-id}/media_publish
   ```

---

## 7. 비용 및 사용량 제한 (Rate Limit)

- API 호출 자체는 **무료** (호출당 과금 없음)
- Rate limit은 계정의 **최근 24시간 노출수(impressions)에 비례**하는 공식으로 계산됨 (기본 시간당 약 200회 + 노출수 기반 가산). 예: 전날 노출수가 1,000이면 다음 24시간 동안 최대 약 480만 회 호출 가능(서드파티 가이드 기준 수치, 정확도 낮을 수 있음).
- 직접 과금은 없지만 **사업자 인증(business verification)**, 심사 준비에 드는 시간·인력 비용은 별도로 감안해야 한다.

---

## 8. 최적화 팁 (서드파티 가이드 종합)

- **Field selection**: 필요한 필드만 명시적으로 요청해서 응답 크기/처리 비용 절감
- **캐싱**: 적절한 TTL로 응답 캐싱
- **배치 요청(batch requests)**: 여러 호출을 묶어서 처리
- **커서 기반 페이지네이션**: 목록 조회 시 offset 대신 cursor 사용
- **웹훅(webhooks)**: 실시간 갱신이 필요한 경우 폴링 대신 웹훅 사용

---

## 9. 지금 당장 할 일 vs 나중에 할 일

| 지금 (준비 단계) | 나중에 (파이프라인 안정화 후) |
|---|---|
| 인스타 계정 프로페셔널 전환 | 앱 심사 제출 |
| 페이스북 페이지 연결 | 심사 통과 후 Live 모드 전환 |
| Meta 개발자 앱 생성 + 제품 추가 | `08_meta_publish.py` 구현 (컨테이너 생성 → 발행 로직) |
| 테스터 계정 등록 후 자체 API 테스트 | 영상 공개 호스팅 방식 결정 (URL 확보 방법) |

---

## 출처

- [How to Use Instagram Graph API in 2026](https://apidog.com/blog/how-to-use-instagram-graph-api/)
- [Instagram Graph API: Complete Developer Guide for 2026](https://elfsight.com/blog/instagram-graph-api-complete-developer-guide-for-2026/)
- [Instagram API Integration Guide 2026: Setup, OAuth, Rate Limits & Key Challenges | Phyllo](https://www.getphyllo.com/post/instagram-api-integration-101-for-developers-of-the-creator-economy)
- [Instagram Graph API 2026: Dev Questions Meta's Docs Leave Open](https://zernio.com/blog/instagram-graph-api)
- [Instagram API in 2026: every option, free or paid, explained](https://zernio.com/blog/instagram-api)
