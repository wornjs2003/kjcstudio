# Week 1 — 환경 구축 + 첫 커스텀 셰이더

## 이번 주 목표
1. Unreal Engine 5.x 설치 및 KJCEngine 프로젝트 초기화
2. 룩 디벨롭 전용 레벨 구성 (중립 조명 + 캘리브레이션 지오메트리)
3. 첫 커스텀 머티리얼 작성: 기본 PBR + 림 라이트 튜닝
4. 결과물 스크린샷 1장 (1920×1080 이상)

---

## 세부 작업

### 1. 프로젝트 생성 (재권님)
- Unreal Launcher → 라이브러리 → UE5.x 실행
- 새 프로젝트 → Games → **Blank** 템플릿
- 설정:
  - C++ 또는 Blueprint: **Blueprint** (초기는 BP만으로 충분)
  - Quality Preset: **Maximum Quality**
  - Starter Content: **체크 해제** (KJC만의 라이브러리 만들 예정이라)
  - Raytracing: **체크 해제** (나중에 필요 시 켜기)
- 프로젝트 이름: `KJCEngineShowcase`
- 저장 위치: `~/Desktop/KJCEngine/phase1_unreal/`

### 2. 프로젝트 폴더 정리 (재권님)
콘텐츠 브라우저에서 아래 폴더 구조로 재정리합니다.
```
/Content/
  /KJC/
    /Materials/       # 커스텀 머티리얼
    /MaterialFunctions/  # MF_KJC_*
    /Textures/        # 공용 텍스처
    /Meshes/          # 공용 스태틱 메시
    /Levels/          # KJC 레벨
    /LookDev/         # 룩 디브 에셋
```

### 3. 룩 디브 레벨 구성 (재권님 + Claude)
**레벨 파일명**: `L_KJC_LookDev_Neutral.umap`

구성 요소:
- **라이팅**: Directional Light 1개 (Intensity 10 lux, 중립 4500K)
- **환경**: Sky Atmosphere + Sky Light (HDRI 대신 Sky Atmosphere 기반)
- **포그**: Exponential Height Fog (Fog Density 0.02, Fog Height Falloff 0.2)
- **포스트프로세스 볼륨**: Unbound, Auto Exposure OFF (Manual EV 1.0 고정)
- **지오메트리** (같은 머티리얼 적용하여 비교):
  - 스탠다드 구 (Shader Ball 대체, 반지름 50cm)
  - 큐브 100cm
  - 실린더 100cm
  - 평면 바닥 4m×4m
  - 선택: 맥베스 컬러 체커 이미지 평면 (컬러 캘리브레이션용)

### 4. 첫 커스텀 머티리얼 (Claude가 노드 그래프 설명 + 재권님이 Unreal에서 작성)
**머티리얼명**: `M_KJC_BasePBR_RimLit`

파라미터:
- Base Color (Vector Parameter)
- Roughness (Scalar 0~1)
- Metallic (Scalar 0~1)
- Normal (Texture Sample, 기본 플랫 노멀)
- Rim Color (Vector)
- Rim Power (Scalar 1~8, 기본 4)
- Rim Intensity (Scalar 0~3, 기본 1)

림 라이트 수식:
```
Fresnel = pow(1 - saturate(dot(N, V)), RimPower)
Emissive = RimColor * RimIntensity * Fresnel
```

이 머티리얼의 인스턴스를 3개 만들고 지오메트리에 적용합니다.
- MI_KJC_Rim_Warm (RimColor: 따뜻한 오렌지)
- MI_KJC_Rim_Cool (RimColor: 차가운 블루)
- MI_KJC_Rim_Neutral (RimColor: 화이트, Intensity 낮음)

### 5. 결과물 촬영 (재권님)
카메라 세팅:
- Cine Camera Actor 1대
- Focal Length 50mm
- 구도: 구·큐브·실린더가 한 프레임에 들어오도록
- Frame: 1920×1080 또는 3840×2160

HighResShot 명령으로 스크린샷 저장:
- Console: `HighResShot 1920x1080`
- 저장 위치: `Saved/Screenshots/`

### 6. 결과 문서화
`docs/progress/week_01.md` 파일에 다음 기록:
- 완성된 스크린샷 (이미지 임베드)
- 사용한 머티리얼 인스턴스별 설명
- 다음 주 개선할 점(있다면)

---

## 체크리스트

- [ ] SETUP.md 따라 Unreal 설치 완료
- [ ] KJCEngineShowcase 프로젝트 생성 완료
- [ ] Content/KJC/ 폴더 구조 생성
- [ ] L_KJC_LookDev_Neutral 레벨 구성
- [ ] M_KJC_BasePBR_RimLit 머티리얼 작성
- [ ] 머티리얼 인스턴스 3종 생성 및 적용
- [ ] 1920×1080 스크린샷 촬영
- [ ] week_01.md 진행 기록 작성

---

## Claude가 준비할 것
- 머티리얼 노드 그래프 상세 다이어그램(텍스트 설명)
- 림 라이트 수식 해설 (왜 이렇게 계산하는지, 다른 변형)
- HDRI 기반 확장 방안 (Week 3에 다룰 예정)

## 재권님이 고민해볼 것
- KJC의 "중립 조명"을 어떻게 정의할까?
  - 붉은사막에서 쓰던 캘리브레이션 조명과 동일하게? 더 중립적으로?
- 기본 톤매퍼: ACES 그대로 쓸까, 건드릴까?
- 쇼케이스 씬의 전반적 아트 톤: 사실주의 / 스타일라이즈드 / 시네마틱 어느 쪽인가?

이 질문들에 답을 주시면 Week 3~4 가이드가 훨씬 선명해집니다.
