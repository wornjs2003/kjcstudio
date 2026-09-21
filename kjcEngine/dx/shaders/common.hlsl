// 이 파일은 kjcEngine 이 시작할 때 읽어 컴파일한다.
// 고치고 F5 를 누르면 다시 읽으므로, 빌드하지 않고 화면으로 확인할 수 있다.
// 여기에는 「무엇이 있는가」만 둔다. 계산은 surface·scene·post 에 있다.

cbuffer CB : register(b0) {
    float4x4 wvp;         // 월드-뷰-투영을 한 번에 곱해둔 행렬
    float4x4 world;       // 월드 변환만 — 법선과 그림자 좌표에 쓴다
    float4x4 lightVP;     // 태양 시점의 뷰x투영
    float4x4 view;        // 카메라 시점으로 옮기는 행렬 — 깊이·법선 패스가 쓴다
    float4x4 proj;        // 투영 — SSAO 가 표본 자리를 화면으로 되돌릴 때 쓴다
    float4   color;
    float4   sun;         // xyz = 태양 방향, w = 번쩍임 세기 (0 이면 평소)
    float4   shadowParam; // x = 기록장 한 칸의 크기, y = 여유값, z = 그늘 밝기,
                          // w = 그리는 방식 (아래 PS 참조)
    float4   camPos;      // xyz = 카메라 자리, w = 미세 결 세기
    float4   nrmFlip;     // xyz = 노말맵 채널별 부호, w = 피부 산란 세기
    float4   ssaoParam;   // x = 반경, y = 세기, z = 여유값, w = 켜짐
    float4   screen;      // xy = 화면 크기 (픽셀),
                          // z = 디퓨즈 (0 이면 회색), w = 노말맵
    float4   skyCol;      // xyz = 위에서 오는 빛, w = Cavity 세기
    float4   groundCol;   // xyz = 아래에서 오는 빛, w = Rim 세기
    float4   rimCol;      // xyz = Rim 빛깔, w = 버텍스 AO 세기
    float4   fogParam;    // x = 시작 거리, y = 끝 거리, z = 켜짐
    float4   fogCol;      // xyz = 섞을 색
    float4   sssParam;    // x = 번지는 폭, y = 켜짐, zw = 번지는 방향
                          // (물체를 그릴 때는 z 가 헤어 안쪽을 걷어내는 선)
    float4   envParam;    // x = 환경광 세기, y = 반사 밉 개수, z = 켜짐,
                          // w = 미세 결 타일 수
    float4x4 invVP;       // 화면 픽셀에서 바라보는 방향을 되찾는 데 쓴다
    float4   toneParam;   // x = 노출, y = 태양 세기, z = 배경 밝기,
                          // w = 반사
};

Texture2D              shadowMap : register(t0);
Texture2D              albedoMap : register(t1);
Texture2D              normalMap : register(t2);
Texture2D              roughMap  : register(t3);
Texture2D              specMap   : register(t4);
Texture2D              scatterMap: register(t5);
Texture2D              microMap  : register(t6);
Texture2D              maskMap   : register(t7);
// SSAO 가 쓰는 것들 — 아래 SSAO 절 참조
Texture2D    posTex   : register(t8);   // 카메라 시점에서 본 자리
Texture2D    nrmTex   : register(t9);   // 카메라 시점에서 본 법선
Texture2D    aoTex    : register(t10);  // 막힌 정도
// 환경맵에서 구운 것들
TextureCube  skyMap   : register(t11);  // 배경
TextureCube  irrMap   : register(t12);  // 사방에서 오는 빛 (확산용)
TextureCube  prefMap  : register(t13);  // 거칠기별로 흐려 놓은 것 (반사용)
// 피부 번짐이 쓰는 것들
Texture2D    sceneTex : register(t14);  // 색 전부
Texture2D    diffTex  : register(t15);  // 확산만
Texture2D    blurTex  : register(t16);  // 번지게 한 확산
Texture2D    overTex  : register(t17);  // 몇 겹으로 그려졌나
SamplerState pointSmp : register(s2);   // 뭉개지 않고 그 자리 값을 그대로
SamplerComparisonState shadowSmp : register(s0);
SamplerState           texSmp    : register(s1);

struct VSIn  {
    float3 pos : POSITION;
    float3 nrm : NORMAL;
    float4 tan : TANGENT;
    float2 uv  : TEXCOORD0;
    float  cav : TEXCOORD1;
    float  vao : TEXCOORD2;
};
struct VSOut {
    float4 pos  : SV_POSITION;
    float3 nrm  : NORMAL;
    float3 tan  : TANGENT;     // 면 위의 가로 방향
    float3 bit  : BINORMAL;    // 면 위의 세로 방향
    float4 lpos : TEXCOORD0;   // 태양 시점에서 이 점이 어디에 있나
    float2 uv   : TEXCOORD1;
    float3 wpos : TEXCOORD2;   // 월드 자리 — 보는 방향을 구하는 데 쓴다
    float  cav  : TEXCOORD3;   // 이 자리가 얼마나 파였나
    float  vao  : TEXCOORD4;   // 형상 전체에 얼마나 가려지나
};

// 그리는 방식마다 내보내는 것이 다르다. 한곳에 모아 둔다
struct PSOut {
    float4 color : SV_TARGET0;   // 반사까지 합친 것
    float4 diff  : SV_TARGET1;   // 살 속으로 들어간 몫
};
struct GBufOut {
    float4 pos  : SV_POSITION;
    float3 vpos : TEXCOORD0;
    float3 vnrm : TEXCOORD1;
};
struct GBufTargets {
    float4 p : SV_TARGET0;
    float4 n : SV_TARGET1;
};
struct FullOut {
    float4 pos : SV_POSITION;
    float2 uv  : TEXCOORD0;
};

// 코드에 적힌 단색은 화면에서 보이는 값(sRGB)이다. 계산은 선형에서 해야
// 맞으므로 펴 준다. 텍스처는 GPU 가 읽을 때 이미 펴 준다
float3 ToLinear(float3 c) { return pow(max(c, 0.0), 2.2); }

// 밝은 쪽이 하얗게 날아가지 않게 눌러 준다 (ACES 근사)
float3 Tonemap(float3 x) {
    x *= toneParam.x;     // 노출 — 사진기의 조리개에 해당한다
    return saturate((x * (2.51 * x + 0.03)) / (x * (2.43 * x + 0.59) + 0.14));
}

// 큰 굴곡 위에 잔 결을 얹는다.
// 두 방향을 그냥 더하면 세기가 틀어져서, 가로 성분은 더하고
