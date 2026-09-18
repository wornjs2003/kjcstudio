// kjcEngine — DirectX 11 판.
//
//   kjcEngine/dx/build.bat   으로 빌드하고 run.bat 으로 띄운다
//
// 파이썬 2D 판(kjcEngine/main.py)과 같은 것을 3D 로 옮겼다.
//   흰 정육면체 하나가 회색 바닥판 위에 서 있고,
//   바닥을 클릭하면 그 자리로 미끄러지듯 이동해 도착하면 멈춘다.
//   가운데 단추를 누른 채 끌면 카메라가 돈다.
//   태양 하나가 빛을 던지고, 정육면체가 바닥에 그림자를 드리운다.
//
// 그리는 일을 두 번에 나눠서 한다 (다중 패스).
//   1패스  태양 자리에서 장면을 그려 「빛이 어디까지 닿는지」를 깊이로 기록한다
//   2패스  화면에 그리면서 1패스 결과를 참고해 그늘인지 판정한다
// 이 뼈대는 나중에 반사·안개 같은 것을 붙일 때 그대로 쓴다.
//
// 1단계다. 여기까지가 「그리는 부분」이고, 나중에 파이썬에서 부를 수 있게
// 껍데기를 씌우면 2단계가 된다. 이 파일의 구조는 그대로 남는다.

#include <windows.h>
#include <d3d11.h>
#include <d3dcompiler.h>
#include <DirectXMath.h>
#include <cstdlib>
#include <ctime>
#include <cstdio>

#include "model.h"      // Vertex 구조와 FBX 읽기
#include "texture.h"    // 이미지 → GPU 텍스처

#pragma comment(lib, "d3d11.lib")
#pragma comment(lib, "d3dcompiler.lib")
#pragma comment(lib, "dxgi.lib")

using namespace DirectX;

// ─── 색 ────────────────────────────────────────────────────────────────
// 값은 여기 한 곳에만 둔다. 파이썬 2D 판과 같은 값을 썼다 — 나란히 놓고
// 볼 때 같은 물건으로 보이게 하려는 것이다.
//
// 미정: 배경색은 룰이 없어 판단으로 둔 자리다. CLAUDE.md 는
//    「검은 배경 사용 금지」인데 그것은 웹 사이트 테마 룰이고, 게임 창이
//    거기 해당하는지는 정해지지 않았다. 밝게 하면 흰 정육면체가 묻힌다.
//    재권님이 정하시면 이 주석과 함께 지운다.
// ⚠ 이 값은 선형이다. 화면에 보이는 #22262b 를 편 것 —
//    PBR 계산은 선형에서 하고, 화면에 낼 때 GPU 가 다시 굽는다
static const float BG[4]      = { 0.0159f, 0.0194f, 0.0243f, 1.0f }; // #22262b 배경 — 미정
static const float CUBE_C[4]  = { 1.000f, 1.000f, 1.000f, 1.0f };  // #ffffff 정육면체 — 지시: 흰색
static const float PLATE_C[4] = { 0.306f, 0.349f, 0.408f, 1.0f };  // #4e5968 바닥판 — 지시: 회색

static const float TRI_C[4]   = { 0.92f, 0.24f, 0.28f, 1.0f };     // 세모 — 지시: 빨간색

// 축 색 — X 빨강 · Y 초록 · Z 파랑.
// 3D 도구가 다 같이 쓰는 관례라 테마 색이 아니라 데이터에 가깝다.
// 테마를 바꿔도 X 축은 빨강이어야 한다 (CLAUDE.md 「데이터로서의 색」)
static const float AXIS_X[4]  = { 0.94f, 0.27f, 0.32f, 1.0f };
static const float AXIS_Y[4]  = { 0.31f, 0.85f, 0.40f, 1.0f };
static const float AXIS_Z[4]  = { 0.25f, 0.58f, 0.96f, 1.0f };

// ─── 태양 ──────────────────────────────────────────────────────────────
// 빛이 「오는 쪽」을 가리키는 방향이다. 태양은 아주 멀어서 빛줄기가
// 평행하게 오므로 자리가 아니라 방향 하나로 적는다.
//
//    y 를 키우면      한낮에 가까워진다 (그림자가 짧아진다)
//    y 를 줄이면      해질녘에 가까워진다 (그림자가 길어진다)
//    x, z 를 바꾸면   해가 뜬 방향이 바뀐다
static const XMFLOAT3 SUN     = { 0.45f, 0.90f, -0.35f };
static const float    AMBIENT = 0.22f;   // 그늘의 밝기. 0 이면 새까맣게 죽는다

// ─── 그림자 ────────────────────────────────────────────────────────────
static const UINT  SHADOW_SIZE  = 2048;   // 깊이 기록장의 한 변. 클수록 곱지만 무겁다
static const float SHADOW_RANGE = 24.0f;  // 태양이 훑는 범위. 바닥판(10)보다 넉넉히
static const float SHADOW_BIAS  = 0.0018f;// 자기 그림자 줄무늬를 막는 여유값

// ─── 모델 ──────────────────────────────────────────────────────────────
// 정육면체 자리에 이 FBX 를 세운다.
//
// 경로를 여기 박아 둔 것은 1단계라서다. 다른 PC 에서는 안 열리므로
// 나중에 설정 파일이나 명령줄 인자로 뺀다
static const char* MODEL_PATH =
    "C:\\Users\\9800X3D\\Desktop\\Work_01\\2025_10\\head\\femaleHead\\head"
    "\\Assets\\Meshes\\Femalehead_0003_01.fbx";
static const float MODEL_H = 2.0f;  // 이 높이로 맞춘다. 판(10)의 5분의 1

// 텍스처. FBX 안의 재질은 옛 파일 하나만 가리키고 있어서 여기서 직접 잇는다 —
// 재권님이 2K 로 줄여 두신 것들이다
static const char* TEX_DIR =
    "C:\\Users\\9800X3D\\Desktop\\Work_01\\2025_10\\head\\femaleHead\\head\\Assets\\Textures\\";
static const char* TEX_ALBEDO = "Face_Albedo.jpg";
static const char* TEX_NORMAL = "Face_Normal.jpg";
static const char* TEX_ROUGH  = "Face_Roughness.jpg";
static const char* TEX_SPEC   = "Face_Specular.jpg";

// ─── 크기와 속도 ───────────────────────────────────────────────────────
// 2D 판의 비율(네모 10 : 판 100)을 그대로 옮겼다
static const int   WIN_W = 960, WIN_H = 640;
static const float PLATE = 10.0f;   // 바닥판 한 변 — 정육면체의 10배
static const float SPEED = 4.0f;    // 초당 움직이는 거리
static const float ORBIT = 0.008f;  // 마우스 1픽셀을 끌 때 카메라가 도는 각도(라디안)

// 휠 줌. 곱하기로 움직여서 가까이서는 잘게, 멀리서는 큼직하게 바뀐다 —
// 더하기로 하면 붙었을 때 한 칸이 너무 크다
static const float ZOOM_STEP = 1.12f;
static const float ZOOM_MIN  = 0.8f;
static const float ZOOM_MAX  = 30.0f;
static const float TURN  = 9.0f;    // 정면을 트는 빠르기 (초당 라디안)

// ─── 세모 ──────────────────────────────────────────────────────────────
static const int   TRI_N     = 2;     // 화면에 늘 있어야 하는 개수 — 지시: 2개
static const float TRI_SIZE  = 1.0f;  // 네모와 비슷한 크기 — 지시
static const float TRI_GAP   = 1.8f;  // 네모·다른 세모에서 이만큼은 떨어져 난다
static const float REACH     = 1.2f;  // 이만큼 가까워지면 닿은 것으로 본다
static const float BORN_WAIT = 1.0f;  // 사라지고 나서 새로 나기까지 — 지시: 1초

// 닿으면 네모가 한 번 뛴다. 이 뜀이 끝나는 순간 세모가 사라진다 —
// 지시로 「1초 기다렸다 사라진다」를 걷어내고 이 동작으로 바꿨다
static const float HOP_TIME   = 0.347f; // 뛰어올랐다 내려오기까지 — 지시로 0.52 에서 1.5배 빠르게
static const float HOP_HEIGHT = 0.75f;  // 뛰어오르는 높이 — 지시: 「살짝」
static const float HOP_WOBBLE = 0.13f;  // 뛰는 동안 X·Z 로 떠는 폭

// 가만히 있지 않고 조금씩 옮겨 다닌다
static const float DRIFT_MIN   = 1.0f;  // 다음 걸음까지 기다리는 시간 — 지시: 1~2초
static const float DRIFT_MAX   = 2.0f;
static const float DRIFT_STEP  = 1.2f;  // 한 걸음에 옮기는 거리 — 지시: 「약간씩」
static const float DRIFT_SPEED = 1.5f;  // 옮겨가는 빠르기 (초당). 네모보다 느리다

// ─── 세모가 사라질 때의 여운 ───────────────────────────────────────────
static const float SHAKE_TIME = 0.32f;  // 흔들리는 시간
static const float SHAKE_AMP  = 0.16f;  // 흔들리는 폭 — 지시: 「약간」
static const float FLASH_TIME = 0.28f;  // 밝아졌다 돌아오기까지
static const float FLASH_MAX  = 0.34f;  // 가장 밝을 때 흰색에 얼마나 가까운가 (0~1)
static const float AXIS_SELF  = 1.3f;   // 정육면체에 붙어 함께 도는 축의 길이
static const UINT  GIZMO_PX   = 130;    // 오른쪽 위 방향 표시기의 한 변 (픽셀)
static const UINT  GIZMO_PAD  = 12;     // 창 모서리에서 띄우는 간격
static const float GIZMO_VIEW = 3.0f;   // 표시기가 담아내는 범위. 글자까지 들어가야 한다
static const float LABEL_AT   = 1.20f;  // 축 끝에서 글자가 놓이는 자리
static const float LABEL_SIZE = 0.28f;  // 글자 크기

// ─── 셰이더 (HLSL) ─────────────────────────────────────────────────────
// 그래픽카드가 직접 돌리는 코드다. 정점을 화면 자리로 옮기는 것(VS)과
// 픽셀 색을 정하는 것(PS) 둘로 나뉜다.
static const char* HLSL = R"(
cbuffer CB : register(b0) {
    float4x4 wvp;         // 월드-뷰-투영을 한 번에 곱해둔 행렬
    float4x4 world;       // 월드 변환만 — 법선과 그림자 좌표에 쓴다
    float4x4 lightVP;     // 태양 시점의 뷰x투영
    float4   color;
    float4   sun;         // xyz = 태양 방향, w = 번쩍임 세기 (0 이면 평소)
    float4   shadowParam; // x = 기록장 한 칸의 크기, y = 여유값, z = 그늘 밝기,
                          // w = 그리는 방식 (아래 PS 참조)
    float4   camPos;      // xyz = 카메라 자리
    float4   nrmFlip;     // xyz = 노말맵 채널별 부호 (X · Y · Z 키로 바뀐다)
};

Texture2D              shadowMap : register(t0);
Texture2D              albedoMap : register(t1);
Texture2D              normalMap : register(t2);
Texture2D              roughMap  : register(t3);
Texture2D              specMap   : register(t4);
SamplerComparisonState shadowSmp : register(s0);
SamplerState           texSmp    : register(s1);

struct VSIn  {
    float3 pos : POSITION;
    float3 nrm : NORMAL;
    float4 tan : TANGENT;
    float2 uv  : TEXCOORD0;
};
struct VSOut {
    float4 pos  : SV_POSITION;
    float3 nrm  : NORMAL;
    float3 tan  : TANGENT;     // 면 위의 가로 방향
    float3 bit  : BINORMAL;    // 면 위의 세로 방향
    float4 lpos : TEXCOORD0;   // 태양 시점에서 이 점이 어디에 있나
    float2 uv   : TEXCOORD1;
    float3 wpos : TEXCOORD2;   // 월드 자리 — 보는 방향을 구하는 데 쓴다
};

// ── 1패스 — 태양 자리에서 깊이만 기록한다. 색을 안 쓰므로 PS 가 없다
float4 VS_Depth(VSIn i) : SV_POSITION {
    return mul(float4(i.pos, 1.0), wvp);
}

// ── 2패스 — 화면에 그린다
VSOut VS(VSIn i) {
    VSOut o;
    float4 wp = mul(float4(i.pos, 1.0), world);
    o.pos  = mul(float4(i.pos, 1.0), wvp);
    o.nrm  = mul(i.nrm, (float3x3)world);
    o.tan  = mul(i.tan.xyz, (float3x3)world);
    // 세로 방향은 두 축의 외적으로 그때그때 구한다. 정점에 담아 나르는 것보다
    // 자리를 덜 쓰고, w 의 부호가 거울로 뒤집힌 자리를 바로잡는다
    o.bit  = cross(o.nrm, o.tan) * i.tan.w;
    o.lpos = mul(wp, lightVP);
    o.uv   = i.uv;
    o.wpos = wp.xyz;
    return o;
}

// ─── PBR 조각들 ────────────────────────────────────────────────────────
// 표면을 「아주 작은 거울들이 제각각 기울어 깔린 면」으로 본다.
// 거칠수록 기울기가 흩어져 반사가 퍼지고, 매끈할수록 한 점에 모인다
static const float PI = 3.14159265;

// 그 작은 거울들이 얼마나 한 방향을 보고 있나 (GGX 분포)
float D_GGX(float NoH, float a) {
    float a2 = a * a;
    float d  = NoH * NoH * (a2 - 1.0) + 1.0;
    return a2 / max(PI * d * d, 1e-7);
}

// 거울들이 서로를 가려 빛이 못 오가는 정도 (Smith)
float V_Smith(float NoV, float NoL, float a) {
    float a2 = a * a;
    float gv = NoL * sqrt(NoV * NoV * (1.0 - a2) + a2);
    float gl = NoV * sqrt(NoL * NoL * (1.0 - a2) + a2);
    return 0.5 / max(gv + gl, 1e-5);
}

// 비스듬히 볼수록 반사가 세진다 (프레넬). 물 위를 멀리 볼 때 하늘이
// 비치는 것과 같은 현상이다
float3 F_Schlick(float3 f0, float VoH) {
    return f0 + (1.0 - f0) * pow(1.0 - VoH, 5.0);
}

// 코드에 적힌 단색은 화면에서 보이는 값(sRGB)이다. 계산은 선형에서 해야
// 맞으므로 펴 준다. 텍스처는 GPU 가 읽을 때 이미 펴 준다
float3 ToLinear(float3 c) { return pow(max(c, 0.0), 2.2); }

// 밝은 쪽이 하얗게 날아가지 않게 눌러 준다 (ACES 근사)
float3 Tonemap(float3 x) {
    return saturate((x * (2.51 * x + 0.03)) / (x * (2.43 * x + 0.59) + 0.14));
}

float4 PS(VSOut i) : SV_TARGET {
    // shadowParam.w 가 그리는 방식을 가른다
    //   0  빛을 받는 단색    바닥판 · 세모
    //   1  빛 없는 단색      축 · 글자 — 조명을 먹이면 무슨 색인지 헷갈린다
    //   2  빛을 받는 텍스처  모델
    float mode = shadowParam.w;

    if (mode > 0.5 && mode < 1.5)
        return float4(lerp(ToLinear(color.rgb), float3(1,1,1), sun.w), 1.0);

    float3 base = (mode > 1.5) ? albedoMap.Sample(texSmp, i.uv).rgb
                               : ToLinear(color.rgb);
    float3 N = normalize(i.nrm);

    // 거칠기와 반사색. 텍스처가 없는 것(판·세모)은 적당한 값으로 둔다
    float  rough = 0.6;
    float3 f0    = 0.04;          // 금속이 아닌 것의 기본 반사율

    if (mode > 1.5) {
        // 노말맵은 0~1 로 저장돼 있어 -1~1 로 편다
        float3 nm = normalMap.Sample(texSmp, i.uv).rgb * 2.0 - 1.0;

        // 채널마다 부호를 먹인다. 노말맵에는 여러 방식이 있어서
        // (OpenGL 은 초록이 위, DirectX 는 아래) 눈으로 맞춘다 — X · Y · Z 키
        nm *= nrmFlip.xyz;

        // 면 위의 가로·세로·법선 축에 얹어 월드 방향으로 옮긴다
        N = normalize(nm.x * normalize(i.tan)
                    + nm.y * normalize(i.bit)
                    + nm.z * N);

        rough = roughMap.Sample(texSmp, i.uv).r;
        f0    = specMap.Sample(texSmp, i.uv).rgb;
    }
    // 완전히 매끈하면 반사가 한 점에 몰려 깜빡인다. 바닥을 조금 깔아둔다
    rough = clamp(rough, 0.05, 1.0);
    float a = rough * rough;

    float3 L = normalize(sun.xyz);
    float3 V = normalize(camPos.xyz - i.wpos);
    float3 H = normalize(V + L);

    float NoL = saturate(dot(N, L));
    float NoV = saturate(dot(N, V)) + 1e-5;
    float NoH = saturate(dot(N, H));
    float VoH = saturate(dot(V, H));

    // ── 그림자 ──
    // 태양 시점 좌표를 기록장 위의 자리로 바꾼다.
    // y 를 뒤집는 것은 화면 좌표가 위에서 아래로 늘기 때문이다
    float3 p  = i.lpos.xyz / i.lpos.w;
    float2 uv = float2(p.x * 0.5 + 0.5, -p.y * 0.5 + 0.5);

    float lit = 1.0;
    bool inside = uv.x >= 0.0 && uv.x <= 1.0 && uv.y >= 0.0 && uv.y <= 1.0 && p.z <= 1.0;
    if (inside) {
        // 3x3 으로 아홉 번 재서 평균을 낸다. 한 번만 재면 그림자 끝이
        // 톱니처럼 각져 보인다 (PCF)
        float sum = 0.0;
        [unroll]
        for (int y = -1; y <= 1; ++y) {
            [unroll]
            for (int x = -1; x <= 1; ++x) {
                float2 o = float2(x, y) * shadowParam.x;
                sum += shadowMap.SampleCmpLevelZero(shadowSmp, uv + o, p.z - shadowParam.y);
            }
        }
        lit = sum / 9.0;
    }

    // ── 태양빛 ──
    float3 F    = F_Schlick(f0, VoH);
    float3 spec = D_GGX(NoH, a) * V_Smith(NoV, NoL, a) * F;
    // 반사로 튕겨나간 만큼은 속으로 안 들어간다 — 그만큼 확산에서 뺀다
    float3 diff = base * (1.0 - F) / PI;

    // PI 를 곱하는 것은 태양 세기를 그만큼으로 잡았기 때문이다.
    // 이렇게 두면 확산 항이 base * NoL 이 되어 눈에 익은 밝기가 나온다
    float3 col = (diff + spec) * NoL * lit * PI;

    // 그늘에서도 완전히 죽지 않게 바닥을 깔아둔다
    col += base * shadowParam.z;

    col = Tonemap(col);

    // 세모가 사라진 순간 화면 전체를 흰색 쪽으로 당긴다. 곧 0 으로 돌아온다
    return float4(lerp(col, float3(1,1,1), sun.w), 1.0);
}
)";

// Vertex 는 model.h 에 있다 — FBX 에서 읽은 것과 여기서 만든 것이
// 같은 모양이어야 하나의 입력 레이아웃으로 그릴 수 있다
struct CB {
    XMMATRIX wvp;
    XMMATRIX world;
    XMMATRIX lightVP;
    XMFLOAT4 color;
    XMFLOAT4 sun;
    XMFLOAT4 shadowParam;
    XMFLOAT4 camPos;      // HLSL 쪽 cbuffer 와 순서·자리가 정확히 같아야 한다
    XMFLOAT4 nrmFlip;
};

// ─── 전역 ──────────────────────────────────────────────────────────────
static ID3D11Device*            g_dev       = nullptr;
static ID3D11DeviceContext*     g_ctx       = nullptr;
static IDXGISwapChain*          g_swap      = nullptr;
static ID3D11RenderTargetView*  g_rtv       = nullptr;
static ID3D11DepthStencilView*  g_dsv       = nullptr;
static ID3D11VertexShader*      g_vs        = nullptr;
static ID3D11VertexShader*      g_vsDepth   = nullptr;
static ID3D11PixelShader*       g_ps        = nullptr;
static ID3D11InputLayout*       g_layout    = nullptr;
static ID3D11Buffer*            g_cb        = nullptr;
static ID3D11Buffer*            g_plateVB   = nullptr;
static Model                    g_head;        // FBX 에서 읽은 모델
static Texture                  g_albedo;      // 얼굴 색 텍스처
static Texture                  g_normal;      // 얼굴 노말맵
static Texture                  g_rough;       // 거칠기
static Texture                  g_spec;        // 반사색 (스페큘러 워크플로)

// 노말맵의 채널별 부호. X · Y · Z 키로 하나씩 뒤집는다.
// 만든 도구마다 축을 잡는 방식이 달라 문서만 봐서는 알 수 없다 —
// 화면을 보며 맞추는 것이 가장 빠르고, 지금 상태는 창 제목에 적힌다
static XMFLOAT3 g_nFlip = XMFLOAT3(1.0f, -1.0f, 1.0f);
static HWND     g_hwnd  = nullptr;
static ID3D11SamplerState*      g_texSmp = nullptr;
static ID3D11Buffer*            g_axisVB    = nullptr;
static ID3D11Buffer*            g_labelVB   = nullptr;
static ID3D11Buffer*            g_triVB     = nullptr;

// 그림자용
static ID3D11DepthStencilView*   g_shadowDSV = nullptr;
static ID3D11ShaderResourceView* g_shadowSRV = nullptr;
static ID3D11SamplerState*       g_shadowSmp = nullptr;
static ID3D11RasterizerState*    g_rsShadow  = nullptr;
static ID3D11RasterizerState*    g_rsNormal  = nullptr;

static XMMATRIX g_view, g_proj, g_lightVP;
static XMFLOAT3 g_camPos;      // 지금 카메라가 있는 자리. PBR 계산에 넘긴다

// ─── 카메라 ────────────────────────────────────────────────────────────
// 바라보는 점(원점)을 중심으로 구면 위를 돈다. 가운데 단추를 누른 채 끌면
// yaw(좌우)와 pitch(위아래)가 바뀐다. 거리는 그대로라 물체에서 멀어지지 않는다
static float g_yaw   = XM_PI;      // 좌우 각도 — 처음에는 -Z 쪽에서 본다
static float g_pitch = 0.686f;     // 위아래 각도 — 약 39도 위에서 내려다본다
static float g_dist  = 5.5f;       // 바라보는 점에서 떨어진 거리. 휠로 바뀐다
static float g_lookY = 1.0f;       // 바라보는 높이 — 얼굴 한가운데(모델 높이의 절반)
static bool  g_drag  = false;      // 가운데 단추를 누르고 있나
static POINT g_last  = {};         // 직전 마우스 자리

// 정육면체가 지금 있는 자리와 가야 할 자리. 판 위(y = 한 변의 절반)에 선다
static float g_x = 0.0f, g_z = 0.0f;
static float g_tx = 0.0f, g_tz = 0.0f;

// 정육면체가 바라보는 쪽. 제 몸의 +Z 가 정면이고, 이 각도만큼 돌아 있다.
// 정육면체는 어느 쪽에서 봐도 똑같이 생겨서, 붙어 있는 축으로만 방향이 보인다
static float g_facing = 0.0f;

// ─── 세모들 ────────────────────────────────────────────────────────────
struct Tri {
    float x, z;        // 지금 자리
    float tx, tz;      // 옮겨가는 중인 자리
    bool  alive;
    float wait;        // 사라진 뒤 다시 나기까지 남은 시간
    float drift;       // 다음 걸음을 고르기까지 남은 시간
};
static Tri   g_tri[TRI_N] = {};
static int   g_chase = -1;     // 지금 쫓고 있는 세모 번호. 없으면 -1
static float g_hop   = 0.0f;   // 뜀이 시작된 뒤 흐른 시간. 0 이면 안 뛰는 중

// 세모가 사라진 순간에 켜지고, 시간이 가면서 잦아든다
static float g_shake = 0.0f;   // 흔들림에 남은 시간
static float g_flash = 0.0f;   // 번쩍임에 남은 시간
static float g_glow  = 0.0f;   // 이 프레임의 밝아진 정도 (0~1). 셰이더로 넘어간다

static float Rand01() { return rand() / (float)RAND_MAX; }

// 회색 판 안에서 자리를 하나 고른다. 네모와도, 다른 세모와도 떨어뜨린다
static void SpawnTri(int i) {
    const float half = PLATE * 0.5f - TRI_SIZE;   // 판 밖으로 삐져나가지 않게

    for (int attempt = 0; attempt < 200; ++attempt) {
        float x = (Rand01() * 2.0f - 1.0f) * half;
        float z = (Rand01() * 2.0f - 1.0f) * half;

        float dxc = x - g_x, dzc = z - g_z;
        if (sqrtf(dxc * dxc + dzc * dzc) < TRI_GAP) continue;   // 네모와 겹친다

        bool clash = false;
        for (int j = 0; j < TRI_N; ++j) {
            if (j == i || !g_tri[j].alive) continue;
            float dx = x - g_tri[j].x, dz = z - g_tri[j].z;
            if (sqrtf(dx * dx + dz * dz) < TRI_GAP) { clash = true; break; }
        }
        if (clash) continue;

        g_tri[i].x = g_tri[i].tx = x;
        g_tri[i].z = g_tri[i].tz = z;
        g_tri[i].alive = true;
        g_tri[i].drift = DRIFT_MIN + Rand01() * (DRIFT_MAX - DRIFT_MIN);
        return;
    }

    // 200번을 고르고도 빈자리가 없으면 판이 꽉 찬 것이다. 겹치게 두느니
    // 조금 더 기다렸다 다시 고른다 — 네모가 움직이면 자리가 난다
    g_tri[i].wait = 0.2f;
}

// 제자리 둘레에서 한 걸음 갈 자리를 고른다. 판 밖으로는 나가지 않는다
static void PickDrift(int i) {
    const float half = PLATE * 0.5f - TRI_SIZE;

    for (int attempt = 0; attempt < 40; ++attempt) {
        float ang = Rand01() * XM_2PI;
        float len = DRIFT_STEP * (0.35f + Rand01() * 0.65f);   // 너무 안 움직이지 않게
        float x = g_tri[i].x + cosf(ang) * len;
        float z = g_tri[i].z + sinf(ang) * len;

        if (x < -half || x > half || z < -half || z > half) continue;   // 판 밖이다

        // 지금보다 네모에 가까워지는 걸음은 버린다 — 지시: 「네모에게 가까이
        // 다가가진 않는다」. 절대 거리로 막지 않는 것은, 그러면 네모가 올 때마다
        // 물러나는 셈이 되어 영영 못 잡기 때문이다. 스스로 다가가지만 않는다
        float nowX = g_tri[i].x - g_x, nowZ = g_tri[i].z - g_z;
        float newX = x - g_x,          newZ = z - g_z;
        if (sqrtf(newX * newX + newZ * newZ) < sqrtf(nowX * nowX + nowZ * nowZ))
            continue;

        bool clash = false;
        for (int j = 0; j < TRI_N; ++j) {
            if (j == i || !g_tri[j].alive) continue;
            float dx = x - g_tri[j].x, dz = z - g_tri[j].z;
            if (sqrtf(dx * dx + dz * dz) < TRI_GAP) { clash = true; break; }
        }
        if (clash) continue;

        g_tri[i].tx = x;
        g_tri[i].tz = z;
        g_tri[i].drift = DRIFT_MIN + Rand01() * (DRIFT_MAX - DRIFT_MIN);
        return;
    }

    // 갈 곳이 없으면 제자리에 두고 곧 다시 고른다
    g_tri[i].tx = g_tri[i].x;
    g_tri[i].tz = g_tri[i].z;
    g_tri[i].drift = 0.3f;
}

// 살아 있는 세모를 제 목표 쪽으로 옮기고, 때가 되면 다음 걸음을 고른다.
// 네모와의 거리는 보지 않는다 — 다가갈 때마다 밀려나면 영영 못 잡는다
static void UpdateTris(float dt) {
    for (int i = 0; i < TRI_N; ++i) {
        if (!g_tri[i].alive) continue;

        float dx = g_tri[i].tx - g_tri[i].x;
        float dz = g_tri[i].tz - g_tri[i].z;
        float d  = sqrtf(dx * dx + dz * dz);
        float s  = DRIFT_SPEED * dt;
        if (d <= s) {
            g_tri[i].x = g_tri[i].tx;
            g_tri[i].z = g_tri[i].tz;
        } else {
            g_tri[i].x += dx / d * s;
            g_tri[i].z += dz / d * s;
        }

        g_tri[i].drift -= dt;
        if (g_tri[i].drift <= 0.0f) PickDrift(i);
    }
}

// 축 세 개를 선으로. 원점에서 각 방향으로 길이 1 만큼 뻗는다.
// 법선은 안 쓴다 — 축은 빛 계산을 건너뛴다
static void BuildAxes(Vertex* v) {
    const XMFLOAT3 o = { 0, 0, 0 };
    v[0] = { o, o };  v[1] = { { 1, 0, 0 }, o };   // X
    v[2] = { o, o };  v[3] = { { 0, 1, 0 }, o };   // Y
    v[4] = { o, o };  v[5] = { { 0, 0, 1 }, o };   // Z
}

// 삼각뿔 — 밑면이 정삼각형이고 꼭대기가 하나. 옆면 셋에 밑면 하나,
// 면마다 법선이 달라야 해서 꼭짓점을 공유하지 않고 12개를 둔다
static void BuildTri(Vertex* v) {
    const float r = TRI_SIZE * 0.62f;   // 밑면 반지름
    const float h = TRI_SIZE;           // 높이

    XMFLOAT3 b[3];
    for (int i = 0; i < 3; ++i) {
        float a = XM_2PI * i / 3.0f + XM_PIDIV2;   // 꼭짓점 하나를 +Z 쪽으로
        b[i] = { r * cosf(a), 0.0f, r * sinf(a) };
    }
    const XMFLOAT3 top = { 0.0f, h, 0.0f };

    int n = 0;
    auto face = [&](const XMFLOAT3& p0, const XMFLOAT3& p1, const XMFLOAT3& p2) {
        XMVECTOR a = XMLoadFloat3(&p0), b1 = XMLoadFloat3(&p1), c = XMLoadFloat3(&p2);
        XMVECTOR nv = XMVector3Normalize(
            XMVector3Cross(XMVectorSubtract(b1, a), XMVectorSubtract(c, a)));
        XMFLOAT3 nf;
        XMStoreFloat3(&nf, nv);
        v[n++] = { p0, nf };
        v[n++] = { p1, nf };
        v[n++] = { p2, nf };
    };

    face(b[0], top, b[1]);      // 옆면 셋
    face(b[1], top, b[2]);
    face(b[2], top, b[0]);
    face(b[0], b[1], b[2]);     // 밑면 — 법선이 아래를 향하도록 이 순서다
}

// 글자 X · Y · Z 를 선으로 그린다. 폰트를 쓰려면 DirectWrite 를 얹어야 하는데
// 글자 셋에는 과하다. XY 평면에 눕혀 두고, 쓸 때 카메라를 향하도록 돌린다
//
//   X  정점 0~3   (선 2개)
//   Y  정점 4~9   (선 3개)
//   Z  정점 10~15 (선 3개)
static void BuildLabels(Vertex* v) {
    const XMFLOAT3 o = { 0, 0, 0 };
    int n = 0;
    auto L = [&](float x1, float y1, float x2, float y2) {
        v[n++] = { { x1, y1, 0.0f }, o };
        v[n++] = { { x2, y2, 0.0f }, o };
    };
    L(-0.5f, -0.5f,  0.5f,  0.5f);   // X — 대각선 둘
    L(-0.5f,  0.5f,  0.5f, -0.5f);

    L(-0.5f,  0.5f,  0.0f,  0.0f);   // Y — 위 두 갈래와
    L( 0.5f,  0.5f,  0.0f,  0.0f);
    L( 0.0f,  0.0f,  0.0f, -0.5f);   //     아래 기둥

    L(-0.5f,  0.5f,  0.5f,  0.5f);   // Z — 위 가로,
    L( 0.5f,  0.5f, -0.5f, -0.5f);   //     대각선,
    L(-0.5f, -0.5f,  0.5f, -0.5f);   //     아래 가로
}

static void BuildPlate(Vertex* v) {
    const float h = PLATE * 0.5f;
    const XMFLOAT3 up = { 0, 1, 0 };
    v[0] = { {-h, 0.0f, -h}, up };
    v[1] = { {-h, 0.0f,  h}, up };
    v[2] = { { h, 0.0f,  h}, up };
    v[3] = { {-h, 0.0f, -h}, up };
    v[4] = { { h, 0.0f,  h}, up };
    v[5] = { { h, 0.0f, -h}, up };
}

// ─── 각도에서 카메라 자리를 다시 구한다 ────────────────────────────────
// 각도가 바뀔 때마다 이것을 부른다. 레이 피킹도 이 행렬을 쓰므로,
// 화면을 돌린 뒤 클릭해도 바닥의 제자리를 집는다
static void UpdateView() {
    float cp = cosf(g_pitch), sp = sinf(g_pitch);
    // 원점이 아니라 얼굴 높이를 바라본다. 발치를 보면 얼굴이 화면 위에 걸린다
    XMVECTOR eye = XMVectorSet(g_dist * cp * sinf(g_yaw),
                               g_dist * sp + g_lookY,
                               g_dist * cp * cosf(g_yaw), 0.0f);
    XMVECTOR at = XMVectorSet(0.0f, g_lookY, 0.0f, 0.0f);

    // 세모가 사라진 직후에는 카메라를 잔떨림만큼 옮긴다. 보는 점까지 같이
    // 옮겨야 화면이 통째로 떨린다 — 눈만 흔들면 빙 도는 모양이 된다
    if (g_shake > 0.0f) {
        float k = g_shake / SHAKE_TIME;          // 1 에서 0 으로
        float a = SHAKE_AMP * k * k;             // 제곱이라 뒤로 갈수록 빨리 잦아든다
        XMVECTOR off = XMVectorSet((Rand01() * 2.0f - 1.0f) * a,
                                   (Rand01() * 2.0f - 1.0f) * a,
                                   (Rand01() * 2.0f - 1.0f) * a, 0.0f);
        eye = XMVectorAdd(eye, off);
        at  = XMVectorAdd(at,  off);
    }

    g_view = XMMatrixLookAtLH(eye, at, XMVectorSet(0.0f, 1.0f, 0.0f, 0.0f));
    XMStoreFloat3(&g_camPos, eye);
}

// ─── 태양 시점의 행렬을 구한다 ─────────────────────────────────────────
// 태양은 아주 멀어서 빛이 평행하게 온다. 그래서 원근이 아니라 직교로 본다 —
// 원근으로 보면 멀리 있는 것이 작아져서 그림자 크기가 틀어진다
static void BuildLightMatrix() {
    XMVECTOR dir = XMVector3Normalize(XMLoadFloat3(&SUN));
    XMVECTOR eye = XMVectorScale(dir, SHADOW_RANGE);   // 그 방향으로 물러선 자리

    // 위쪽 축이 시선과 나란하면 행렬이 무너진다. 태양이 거의 머리 위면 다른 축을 쓴다
    XMVECTOR up = (fabsf(XMVectorGetY(dir)) > 0.99f)
                ? XMVectorSet(0.0f, 0.0f, 1.0f, 0.0f)
                : XMVectorSet(0.0f, 1.0f, 0.0f, 0.0f);

    XMMATRIX v = XMMatrixLookAtLH(eye, XMVectorSet(0.0f, 0.0f, 0.0f, 0.0f), up);
    XMMATRIX p = XMMatrixOrthographicLH(SHADOW_RANGE, SHADOW_RANGE,
                                        0.1f, SHADOW_RANGE * 2.5f);
    g_lightVP = XMMatrixMultiply(v, p);
}

// ─── 클릭한 화면 자리를 바닥(y=0) 위의 한 점으로 바꾼다 ────────────────
// 화면은 2D 인데 세상은 3D 라, 눈에서 클릭 지점을 지나는 직선을 쏘아
// 그것이 바닥면과 만나는 자리를 찾는다. 이것을 레이 피킹이라 한다
static bool PickFloor(int mx, int my, float& outX, float& outZ) {
    float ndcX = (2.0f * mx / WIN_W) - 1.0f;
    float ndcY = 1.0f - (2.0f * my / WIN_H);

    XMMATRIX inv = XMMatrixInverse(nullptr, XMMatrixMultiply(g_view, g_proj));
    XMVECTOR a = XMVector3TransformCoord(XMVectorSet(ndcX, ndcY, 0.0f, 1.0f), inv);
    XMVECTOR b = XMVector3TransformCoord(XMVectorSet(ndcX, ndcY, 1.0f, 1.0f), inv);
    XMVECTOR dir = XMVector3Normalize(XMVectorSubtract(b, a));

    float ay = XMVectorGetY(a), dy = XMVectorGetY(dir);
    if (fabsf(dy) < 1e-6f) return false;      // 직선이 바닥과 나란하다 — 안 만난다
    float t = -ay / dy;
    if (t < 0.0f) return false;               // 뒤쪽에서 만난다 — 화면 밖이다

    outX = XMVectorGetX(a) + XMVectorGetX(dir) * t;
    outZ = XMVectorGetZ(a) + XMVectorGetZ(dir) * t;
    return true;
}

// ─── 한 물체 그리기 ────────────────────────────────────────────────────
// depthPass 면 태양 시점으로, 아니면 카메라 시점으로 옮긴다
// idxFmt 는 인덱스 한 칸의 크기다. 여기서 만든 작은 도형은 16비트면 넉넉하지만,
// FBX 모델은 정점이 6만 5천을 넘을 수 있어 32비트를 쓴다
static void DrawOne(ID3D11Buffer* vb, ID3D11Buffer* ib, UINT count,
                    XMMATRIX world, const float rgba[4], bool depthPass,
                    DXGI_FORMAT idxFmt = DXGI_FORMAT_R16_UINT, float mode = 0.0f) {
    UINT stride = sizeof(Vertex), offset = 0;
    g_ctx->IASetVertexBuffers(0, 1, &vb, &stride, &offset);

    CB cb;
    cb.wvp = depthPass ? XMMatrixTranspose(world * g_lightVP)
                       : XMMatrixTranspose(world * g_view * g_proj);
    cb.world       = XMMatrixTranspose(world);
    cb.lightVP     = XMMatrixTranspose(g_lightVP);
    cb.color       = XMFLOAT4(rgba[0], rgba[1], rgba[2], rgba[3]);
    cb.sun         = XMFLOAT4(SUN.x, SUN.y, SUN.z, g_glow);
    cb.shadowParam = XMFLOAT4(1.0f / SHADOW_SIZE, SHADOW_BIAS, AMBIENT, mode);
    cb.camPos      = XMFLOAT4(g_camPos.x, g_camPos.y, g_camPos.z, 0.0f);
    cb.nrmFlip     = XMFLOAT4(g_nFlip.x, g_nFlip.y, g_nFlip.z, 0.0f);
    g_ctx->UpdateSubresource(g_cb, 0, nullptr, &cb, 0, 0);

    if (ib) {
        g_ctx->IASetIndexBuffer(ib, idxFmt, 0);
        g_ctx->DrawIndexed(count, 0, 0);
    } else {
        g_ctx->Draw(count, 0);
    }
}

// ─── 축 세 개 그리기 ───────────────────────────────────────────────────
// viewProj 를 따로 받는다. 오른쪽 위 표시기는 본 화면과 다른 시점을 쓰기 때문이다
static void DrawAxes(XMMATRIX world, XMMATRIX viewProj) {
    UINT stride = sizeof(Vertex), offset = 0;
    g_ctx->IASetVertexBuffers(0, 1, &g_axisVB, &stride, &offset);
    g_ctx->IASetPrimitiveTopology(D3D11_PRIMITIVE_TOPOLOGY_LINELIST);

    const float* c[3] = { AXIS_X, AXIS_Y, AXIS_Z };
    for (UINT i = 0; i < 3; ++i) {
        CB cb;
        cb.wvp         = XMMatrixTranspose(world * viewProj);
        cb.world       = XMMatrixTranspose(world);
        cb.lightVP     = XMMatrixTranspose(g_lightVP);
        cb.color       = XMFLOAT4(c[i][0], c[i][1], c[i][2], 1.0f);
        cb.sun         = XMFLOAT4(SUN.x, SUN.y, SUN.z, g_glow);
        cb.shadowParam = XMFLOAT4(1.0f / SHADOW_SIZE, SHADOW_BIAS, AMBIENT,
                                  1.0f);   // 1 = 빛 계산을 건너뛴다
        cb.camPos      = XMFLOAT4(g_camPos.x, g_camPos.y, g_camPos.z, 0.0f);
    cb.nrmFlip     = XMFLOAT4(g_nFlip.x, g_nFlip.y, g_nFlip.z, 0.0f);
        g_ctx->UpdateSubresource(g_cb, 0, nullptr, &cb, 0, 0);
        g_ctx->Draw(2, i * 2);             // 축 하나가 정점 두 개다
    }

    g_ctx->IASetPrimitiveTopology(D3D11_PRIMITIVE_TOPOLOGY_TRIANGLELIST);
}

// ─── 축 끝에 X · Y · Z 글자를 붙인다 ───────────────────────────────────
// billboard 는 카메라 쪽을 향하게 돌리는 행렬이다. 이게 없으면 글자가
// 눕거나 뒤집혀서 못 읽는다
static void DrawLabels(XMMATRIX viewProj, XMMATRIX billboard) {
    UINT stride = sizeof(Vertex), offset = 0;
    g_ctx->IASetVertexBuffers(0, 1, &g_labelVB, &stride, &offset);
    g_ctx->IASetPrimitiveTopology(D3D11_PRIMITIVE_TOPOLOGY_LINELIST);

    struct Label { XMFLOAT3 at; const float* color; UINT start, count; };
    const Label L[3] = {
        { { LABEL_AT, 0.0f, 0.0f }, AXIS_X,  0, 4 },
        { { 0.0f, LABEL_AT, 0.0f }, AXIS_Y,  4, 6 },
        { { 0.0f, 0.0f, LABEL_AT }, AXIS_Z, 10, 6 },
    };

    for (int i = 0; i < 3; ++i) {
        XMMATRIX w = XMMatrixScaling(LABEL_SIZE, LABEL_SIZE, LABEL_SIZE)
                   * billboard
                   * XMMatrixTranslation(L[i].at.x, L[i].at.y, L[i].at.z);
        CB cb;
        cb.wvp         = XMMatrixTranspose(w * viewProj);
        cb.world       = XMMatrixTranspose(w);
        cb.lightVP     = XMMatrixTranspose(g_lightVP);
        cb.color       = XMFLOAT4(L[i].color[0], L[i].color[1], L[i].color[2], 1.0f);
        cb.sun         = XMFLOAT4(SUN.x, SUN.y, SUN.z, g_glow);
        cb.shadowParam = XMFLOAT4(1.0f / SHADOW_SIZE, SHADOW_BIAS, AMBIENT, 1.0f);
        cb.camPos      = XMFLOAT4(g_camPos.x, g_camPos.y, g_camPos.z, 0.0f);
    cb.nrmFlip     = XMFLOAT4(g_nFlip.x, g_nFlip.y, g_nFlip.z, 0.0f);
        g_ctx->UpdateSubresource(g_cb, 0, nullptr, &cb, 0, 0);
        g_ctx->Draw(L[i].count, L[i].start);
    }

    g_ctx->IASetPrimitiveTopology(D3D11_PRIMITIVE_TOPOLOGY_TRIANGLELIST);
}

// 바닥판과 정육면체를 한 번에 그린다. 두 패스가 같은 장면을 그려야 하므로
// 한 곳에 모아 둔다 — 한쪽에만 물체를 더하면 그림자가 어긋난다
static void DrawScene(bool depthPass) {
    // 뛰는 중이면 그만큼 떠오르고 좌우로 떤다.
    // 4t(1-t) 는 t 가 0 과 1 에서 0, 한가운데서 1 이 되는 포물선이라
    // 뛰어올랐다 제자리로 내려오는 모양이 저절로 나온다
    float cx = g_x, cy = 0.0f, cz = g_z;   // 모델은 발치가 y=0 이라 띄우지 않는다
    if (g_hop > 0.0f) {
        float t = g_hop / HOP_TIME;
        if (t > 1.0f) t = 1.0f;
        cy += HOP_HEIGHT * 4.0f * t * (1.0f - t);
        // 주기를 4번과 3번으로 어긋나게 둬서 같은 자리를 되풀이하지 않게 한다
        cx += HOP_WOBBLE * sinf(t * XM_2PI * 4.0f);
        cz += HOP_WOBBLE * cosf(t * XM_2PI * 3.0f);
    }

    // 정면이 향한 쪽으로 돌려 세운 다음 제자리로 옮긴다. 순서가 반대면
    // 원점을 중심으로 빙 도는 모양이 된다
    XMMATRIX cubeWorld = XMMatrixRotationY(g_facing)
                       * XMMatrixTranslation(cx, cy, cz);

    DrawOne(g_plateVB, nullptr, 6, XMMatrixIdentity(), PLATE_C, depthPass);
    // 모델은 정점이 많아 32비트 인덱스를 쓰고, 색은 텍스처에서 읽는다(모드 2)
    DrawOne(g_head.vb, g_head.ib, g_head.indexCount, cubeWorld, CUBE_C, depthPass,
            DXGI_FORMAT_R32_UINT, 2.0f);

    for (int i = 0; i < TRI_N; ++i) {
        if (!g_tri[i].alive) continue;
        DrawOne(g_triVB, nullptr, 12,
                XMMatrixTranslation(g_tri[i].x, 0.0f, g_tri[i].z), TRI_C, depthPass);
    }

    // 정육면체가 어디를 보는지 알려주는 축. 그림자 기록에는 넣지 않는다 —
    // 선이라 그림자가 실오라기처럼 지고, 방향 표시지 물체가 아니다
    if (!depthPass)
        DrawAxes(XMMatrixScaling(AXIS_SELF, AXIS_SELF, AXIS_SELF) * cubeWorld,
                 g_view * g_proj);
}

// 시작하다 막혔을 때 알린다. 창으로 띄우는 것만으로는 놓칠 수 있어서
// (백그라운드로 돌리면 안 보인다) 실행 파일 옆에 글로도 남긴다
static void Fail(HWND hwnd, const char* msg) {
    FILE* f = nullptr;
    if (fopen_s(&f, "kjcEngine-error.txt", "w") == 0 && f) {
        fputs(msg, f);
        fclose(f);
    }
    MessageBoxA(hwnd, msg, "kjcEngine", MB_OK | MB_ICONERROR);
}

// 지금 상태를 창 제목에 적는다. 노말맵 부호는 눈으로 확인할 방법이 없어서
// 어딘가에 보여야 한다 — 안 그러면 눌러 놓고도 어느 쪽인지 헷갈린다
static void UpdateTitle() {
    if (!g_hwnd) return;
    char t[256];
    wsprintfA(t, "kjcEngine - DirectX 11   |   %u verts, %u tris   |   normal  X%c Y%c Z%c",
              (unsigned)g_head.outVertices, (unsigned)(g_head.indexCount / 3),
              g_nFlip.x < 0.0f ? '-' : '+',
              g_nFlip.y < 0.0f ? '-' : '+',
              g_nFlip.z < 0.0f ? '-' : '+');
    SetWindowTextA(g_hwnd, t);
}

// 카메라를 당기고 민다. 휠과 [ ] 키가 같이 쓴다
static void Zoom(float factor) {
    g_dist *= factor;
    if (g_dist < ZOOM_MIN) g_dist = ZOOM_MIN;
    if (g_dist > ZOOM_MAX) g_dist = ZOOM_MAX;
}

static LRESULT CALLBACK WndProc(HWND hwnd, UINT msg, WPARAM wp, LPARAM lp) {
    switch (msg) {
    case WM_LBUTTONDOWN: {
        float fx, fz;
        if (!PickFloor((int)(short)LOWORD(lp), (int)(short)HIWORD(lp), fx, fz))
            return 0;

        // 짚은 자리가 어느 세모 위라면 그 세모를 쫓는다.
        // 바닥을 짚었으면 그냥 그 자리로 간다
        int   hit  = -1;
        float best = TRI_SIZE;
        for (int i = 0; i < TRI_N; ++i) {
            if (!g_tri[i].alive) continue;
            float dx = fx - g_tri[i].x, dz = fz - g_tri[i].z;
            float d  = sqrtf(dx * dx + dz * dz);
            if (d < best) { best = d; hit = i; }
        }

        g_chase = hit;
        g_hop   = 0.0f;
        if (hit >= 0) { g_tx = g_tri[hit].x; g_tz = g_tri[hit].z; }
        else          { g_tx = fx;           g_tz = fz;           }
        return 0;
    }

    case WM_MBUTTONDOWN:
        g_drag   = true;
        g_last.x = (int)(short)LOWORD(lp);
        g_last.y = (int)(short)HIWORD(lp);
        SetCapture(hwnd);          // 끌다가 창 밖으로 나가도 계속 따라간다
        return 0;

    case WM_MBUTTONUP:
        g_drag = false;
        ReleaseCapture();
        return 0;

    case WM_MOUSEMOVE: {
        if (!g_drag) return 0;
        int mx = (int)(short)LOWORD(lp), my = (int)(short)HIWORD(lp);
        g_yaw   += (mx - g_last.x) * ORBIT;
        g_pitch += (my - g_last.y) * ORBIT;
        // 위아래로 넘어가지 않게 막는다. 0도면 바닥이 선으로 보이고,
        // 90도를 넘기면 화면이 뒤집힌다
        if (g_pitch < 0.05f) g_pitch = 0.05f;
        if (g_pitch > 1.50f) g_pitch = 1.50f;
        g_last.x = mx;
        g_last.y = my;
        return 0;
    }

    case WM_MOUSEWHEEL:
        Zoom(GET_WHEEL_DELTA_WPARAM(wp) > 0 ? 1.0f / ZOOM_STEP : ZOOM_STEP);
        return 0;

    case WM_KEYDOWN:
        // 누르고 있으면 저절로 되풀이되므로 따로 처리할 것이 없다
        switch (wp) {
        case VK_ESCAPE: PostQuitMessage(0);        break;
        case VK_OEM_6:  Zoom(1.0f / ZOOM_STEP);    break;   // ]  확대
        case VK_OEM_4:  Zoom(ZOOM_STEP);           break;   // [  축소
        // 노말맵 채널을 하나씩 뒤집는다. 지금 상태는 창 제목에 나온다
        case 'X': g_nFlip.x = -g_nFlip.x; UpdateTitle(); break;
        case 'Y': g_nFlip.y = -g_nFlip.y; UpdateTitle(); break;
        case 'Z': g_nFlip.z = -g_nFlip.z; UpdateTitle(); break;
        }
        return 0;

    case WM_DESTROY:
        PostQuitMessage(0);
        return 0;
    }
    return DefWindowProc(hwnd, msg, wp, lp);
}

int WINAPI WinMain(HINSTANCE hInst, HINSTANCE, LPSTR, int) {
    WNDCLASSEX wc = { sizeof(wc) };
    wc.lpfnWndProc   = WndProc;
    wc.hInstance     = hInst;
    wc.hCursor       = LoadCursor(nullptr, IDC_ARROW);
    wc.lpszClassName = "kjcEngineDX";
    RegisterClassEx(&wc);

    RECT r = { 0, 0, WIN_W, WIN_H };
    DWORD style = WS_OVERLAPPEDWINDOW & ~WS_THICKFRAME & ~WS_MAXIMIZEBOX;
    AdjustWindowRect(&r, style, FALSE);
    const int winW = r.right - r.left, winH = r.bottom - r.top;

    // 마우스 커서가 있는 모니터 한가운데에 놓는다. CW_USEDEFAULT 로 두면
    // Windows 가 알아서 고르는데, 화면이 여럿이면 보고 있지 않은 쪽에 뜬다.
    // 작업 영역(rcWork)을 쓰므로 작업 표시줄에 가리지 않는다
    POINT cur;
    GetCursorPos(&cur);
    MONITORINFO mi = { sizeof(mi) };
    GetMonitorInfo(MonitorFromPoint(cur, MONITOR_DEFAULTTONEAREST), &mi);
    int wx = mi.rcWork.left + ((mi.rcWork.right  - mi.rcWork.left) - winW) / 2;
    int wy = mi.rcWork.top  + ((mi.rcWork.bottom - mi.rcWork.top)  - winH) / 2;

    HWND hwnd = CreateWindow("kjcEngineDX", "kjcEngine - DirectX 11", style,
                             wx, wy, winW, winH,
                             nullptr, nullptr, hInst, nullptr);

    // ── DX11 준비 ──
    DXGI_SWAP_CHAIN_DESC sd = {};
    sd.BufferCount       = 2;
    sd.BufferDesc.Width  = WIN_W;
    sd.BufferDesc.Height = WIN_H;
    sd.BufferDesc.Format = DXGI_FORMAT_R8G8B8A8_UNORM;
    sd.BufferUsage       = DXGI_USAGE_RENDER_TARGET_OUTPUT;
    sd.OutputWindow      = hwnd;
    sd.SampleDesc.Count  = 4;           // 계단 현상을 줄인다 (4배 다중표본)
    sd.Windowed          = TRUE;
    sd.SwapEffect        = DXGI_SWAP_EFFECT_DISCARD;

    if (FAILED(D3D11CreateDeviceAndSwapChain(
            nullptr, D3D_DRIVER_TYPE_HARDWARE, nullptr, 0, nullptr, 0,
            D3D11_SDK_VERSION, &sd, &g_swap, &g_dev, nullptr, &g_ctx))) {
        Fail(hwnd, "DirectX 11 device creation failed.");
        return 1;
    }

    // 화면에 낼 때 GPU 가 선형 → sRGB 로 구워 주게 한다. 이게 없으면
    // 계산은 선형인데 화면은 sRGB 로 읽어서 전체가 어둡고 탁해진다
    ID3D11Texture2D* back = nullptr;
    g_swap->GetBuffer(0, __uuidof(ID3D11Texture2D), (void**)&back);
    D3D11_RENDER_TARGET_VIEW_DESC rtvd = {};
    rtvd.Format        = DXGI_FORMAT_R8G8B8A8_UNORM_SRGB;
    rtvd.ViewDimension = D3D11_RTV_DIMENSION_TEXTURE2DMS;   // 다중표본을 쓰므로
    g_dev->CreateRenderTargetView(back, &rtvd, &g_rtv);
    back->Release();

    // 깊이 버퍼 — 앞의 물체가 뒤를 가리게 한다. 없으면 나중에 그린 것이 위에 온다
    D3D11_TEXTURE2D_DESC dd = {};
    dd.Width            = WIN_W;
    dd.Height           = WIN_H;
    dd.MipLevels        = 1;
    dd.ArraySize        = 1;
    dd.Format           = DXGI_FORMAT_D24_UNORM_S8_UINT;
    dd.SampleDesc.Count = 4;            // 스왑체인과 같아야 한다
    dd.Usage            = D3D11_USAGE_DEFAULT;
    dd.BindFlags        = D3D11_BIND_DEPTH_STENCIL;
    ID3D11Texture2D* depth = nullptr;
    g_dev->CreateTexture2D(&dd, nullptr, &depth);
    g_dev->CreateDepthStencilView(depth, nullptr, &g_dsv);
    depth->Release();

    // ── 그림자 기록장 ──
    // 깊이로 쓰면서 나중에 셰이더가 읽어야 해서, 형식을 TYPELESS 로 두고
    // 쓸 때(DSV)와 읽을 때(SRV) 각각 다른 형식으로 본다
    D3D11_TEXTURE2D_DESC sdesc = {};
    sdesc.Width            = SHADOW_SIZE;
    sdesc.Height           = SHADOW_SIZE;
    sdesc.MipLevels        = 1;
    sdesc.ArraySize        = 1;
    sdesc.Format           = DXGI_FORMAT_R32_TYPELESS;
    sdesc.SampleDesc.Count = 1;         // 기록장에는 다중표본을 쓰지 않는다
    sdesc.Usage            = D3D11_USAGE_DEFAULT;
    sdesc.BindFlags        = D3D11_BIND_DEPTH_STENCIL | D3D11_BIND_SHADER_RESOURCE;
    ID3D11Texture2D* shadowTex = nullptr;
    g_dev->CreateTexture2D(&sdesc, nullptr, &shadowTex);

    D3D11_DEPTH_STENCIL_VIEW_DESC sdv = {};
    sdv.Format        = DXGI_FORMAT_D32_FLOAT;
    sdv.ViewDimension = D3D11_DSV_DIMENSION_TEXTURE2D;
    g_dev->CreateDepthStencilView(shadowTex, &sdv, &g_shadowDSV);

    D3D11_SHADER_RESOURCE_VIEW_DESC ssv = {};
    ssv.Format                    = DXGI_FORMAT_R32_FLOAT;
    ssv.ViewDimension             = D3D11_SRV_DIMENSION_TEXTURE2D;
    ssv.Texture2D.MipLevels       = 1;
    g_dev->CreateShaderResourceView(shadowTex, &ssv, &g_shadowSRV);
    shadowTex->Release();

    // 비교 표본기 — 「이 픽셀이 기록장에 적힌 깊이보다 앞이냐」를 물어보면
    // 0(그늘) 또는 1(양지)로 답한다. 주변 값까지 섞어줘서 가장자리가 부드럽다
    D3D11_SAMPLER_DESC smp = {};
    smp.Filter         = D3D11_FILTER_COMPARISON_MIN_MAG_LINEAR_MIP_POINT;
    smp.AddressU       = D3D11_TEXTURE_ADDRESS_BORDER;
    smp.AddressV       = D3D11_TEXTURE_ADDRESS_BORDER;
    smp.AddressW       = D3D11_TEXTURE_ADDRESS_BORDER;
    smp.BorderColor[0] = smp.BorderColor[1] =
    smp.BorderColor[2] = smp.BorderColor[3] = 1.0f;   // 기록장 밖은 양지로 본다
    smp.ComparisonFunc = D3D11_COMPARISON_LESS_EQUAL;
    g_dev->CreateSamplerState(&smp, &g_shadowSmp);

    // 색 텍스처용 표본기. 이방성 필터를 쓰면 비스듬히 보이는 면이 덜 뭉갠다
    D3D11_SAMPLER_DESC ts = {};
    ts.Filter         = D3D11_FILTER_ANISOTROPIC;
    ts.MaxAnisotropy  = 8;
    ts.AddressU = ts.AddressV = ts.AddressW = D3D11_TEXTURE_ADDRESS_WRAP;
    ts.MaxLOD         = D3D11_FLOAT32_MAX;
    g_dev->CreateSamplerState(&ts, &g_texSmp);

    // 그림자를 그릴 때만 깊이를 살짝 밀어낸다. 이게 없으면 평평한 면이
    // 자기 자신을 가려서 줄무늬(섀도 애크니)가 생긴다
    D3D11_RASTERIZER_DESC rd = {};
    rd.FillMode              = D3D11_FILL_SOLID;
    rd.CullMode              = D3D11_CULL_BACK;
    rd.DepthClipEnable       = TRUE;
    g_dev->CreateRasterizerState(&rd, &g_rsNormal);
    rd.DepthBias             = 2500;
    rd.SlopeScaledDepthBias  = 2.5f;
    rd.DepthBiasClamp        = 0.0f;
    g_dev->CreateRasterizerState(&rd, &g_rsShadow);

    // ── 셰이더 ──
    ID3DBlob *vsb = nullptr, *vsdb = nullptr, *psb = nullptr, *err = nullptr;
    auto compile = [&](const char* entry, const char* target, ID3DBlob** out) -> bool {
        if (SUCCEEDED(D3DCompile(HLSL, strlen(HLSL), nullptr, nullptr, nullptr,
                                 entry, target, 0, 0, out, &err)))
            return true;
        Fail(hwnd, err ? (char*)err->GetBufferPointer() : "shader compile failed");
        return false;
    };
    if (!compile("VS",       "vs_5_0", &vsb))  return 1;
    if (!compile("VS_Depth", "vs_5_0", &vsdb)) return 1;
    if (!compile("PS",       "ps_5_0", &psb))  return 1;

    g_dev->CreateVertexShader(vsb->GetBufferPointer(),  vsb->GetBufferSize(),  nullptr, &g_vs);
    g_dev->CreateVertexShader(vsdb->GetBufferPointer(), vsdb->GetBufferSize(), nullptr, &g_vsDepth);
    g_dev->CreatePixelShader (psb->GetBufferPointer(),  psb->GetBufferSize(),  nullptr, &g_ps);

    // 자리(offset)는 Vertex 구조와 정확히 맞아야 한다 — 어긋나면 화면이
    // 조용히 이상해지고 오류는 안 난다
    D3D11_INPUT_ELEMENT_DESC il[] = {
        { "POSITION", 0, DXGI_FORMAT_R32G32B32_FLOAT,    0,  0, D3D11_INPUT_PER_VERTEX_DATA, 0 },
        { "NORMAL",   0, DXGI_FORMAT_R32G32B32_FLOAT,    0, 12, D3D11_INPUT_PER_VERTEX_DATA, 0 },
        { "TANGENT",  0, DXGI_FORMAT_R32G32B32A32_FLOAT, 0, 24, D3D11_INPUT_PER_VERTEX_DATA, 0 },
        { "TEXCOORD", 0, DXGI_FORMAT_R32G32_FLOAT,       0, 40, D3D11_INPUT_PER_VERTEX_DATA, 0 },
    };
    g_dev->CreateInputLayout(il, 4, vsb->GetBufferPointer(), vsb->GetBufferSize(), &g_layout);
    vsb->Release();
    vsdb->Release();
    psb->Release();

    // ── 정점 · 인덱스 · 상수 버퍼 ──
    Vertex plateV[6];
    BuildPlate(plateV);
    Vertex axisV[6];
    BuildAxes(axisV);
    Vertex labelV[16];
    BuildLabels(labelV);
    Vertex triV[12];
    BuildTri(triV);

    auto makeBuf = [&](const void* data, UINT bytes, UINT bind) {
        D3D11_BUFFER_DESC bd = {};
        bd.Usage     = D3D11_USAGE_DEFAULT;
        bd.ByteWidth = bytes;
        bd.BindFlags = bind;
        D3D11_SUBRESOURCE_DATA sr = { data, 0, 0 };
        ID3D11Buffer* b = nullptr;
        g_dev->CreateBuffer(&bd, &sr, &b);
        return b;
    };
    g_plateVB = makeBuf(plateV, sizeof(plateV), D3D11_BIND_VERTEX_BUFFER);
    g_axisVB  = makeBuf(axisV,  sizeof(axisV),  D3D11_BIND_VERTEX_BUFFER);
    g_labelVB = makeBuf(labelV, sizeof(labelV), D3D11_BIND_VERTEX_BUFFER);
    g_triVB   = makeBuf(triV,   sizeof(triV),   D3D11_BIND_VERTEX_BUFFER);

    // ── FBX 모델 ──
    // 여기서 막히면 화면에 아무것도 없이 검게만 보인다. 이유를 띄우고 끝낸다
    char loadErr[1024] = {};
    if (!LoadFBX(g_dev, MODEL_PATH, MODEL_H, g_head, loadErr, sizeof(loadErr))) {
        Fail(hwnd, loadErr);
        return 1;
    }
    // ── 텍스처 ──
    // albedo 는 색이므로 sRGB 로 읽는다 (texture.h 의 설명 참조)
    char texPath[512];
    auto loadTex = [&](const char* name, bool srgb, Texture& t) -> bool {
        lstrcpyA(texPath, TEX_DIR);
        lstrcatA(texPath, name);
        if (LoadTexture(g_dev, g_ctx, texPath, srgb, t, loadErr, sizeof(loadErr)))
            return true;
        Fail(hwnd, loadErr);
        return false;
    };
    if (!loadTex(TEX_ALBEDO, true,  g_albedo)) return 1;   // 색이므로 sRGB
    if (!loadTex(TEX_NORMAL, false, g_normal)) return 1;   // 방향 숫자라 그대로
    if (!loadTex(TEX_ROUGH,  false, g_rough))  return 1;   // 거칠기도 숫자
    if (!loadTex(TEX_SPEC,   true,  g_spec))   return 1;   // 반사색이라 sRGB

    // 제대로 들어왔는지, 노말맵 부호가 지금 어느 쪽인지 창 제목에서 보이게 한다
    g_hwnd = hwnd;
    UpdateTitle();

    // 세모를 처음 뿌린다. 매번 다른 자리에 나게 씨앗을 시간으로 준다
    srand((unsigned)time(nullptr));
    for (int i = 0; i < TRI_N; ++i) SpawnTri(i);

    D3D11_BUFFER_DESC cbd = {};
    cbd.Usage     = D3D11_USAGE_DEFAULT;
    cbd.ByteWidth = sizeof(CB);
    cbd.BindFlags = D3D11_BIND_CONSTANT_BUFFER;
    g_dev->CreateBuffer(&cbd, nullptr, &g_cb);

    // ── 카메라와 태양 ──
    UpdateView();
    BuildLightMatrix();
    g_proj = XMMatrixPerspectiveFovLH(XM_PIDIV4, (float)WIN_W / WIN_H, 0.1f, 200.0f);

    D3D11_VIEWPORT viewMain   = { 0, 0, (float)WIN_W, (float)WIN_H, 0.0f, 1.0f };
    D3D11_VIEWPORT viewShadow = { 0, 0, (float)SHADOW_SIZE, (float)SHADOW_SIZE, 0.0f, 1.0f };
    D3D11_VIEWPORT viewGizmo  = { (float)(WIN_W - GIZMO_PX - GIZMO_PAD), (float)GIZMO_PAD,
                                  (float)GIZMO_PX, (float)GIZMO_PX, 0.0f, 1.0f };

    ShowWindow(hwnd, SW_SHOW);

    // ── 돌린다 ──
    LARGE_INTEGER freq, prev;
    QueryPerformanceFrequency(&freq);
    QueryPerformanceCounter(&prev);

    MSG msg = {};
    while (msg.message != WM_QUIT) {
        if (PeekMessage(&msg, nullptr, 0, 0, PM_REMOVE)) {
            TranslateMessage(&msg);
            DispatchMessage(&msg);
            continue;
        }

        LARGE_INTEGER now;
        QueryPerformanceCounter(&now);
        float dt = float(now.QuadPart - prev.QuadPart) / freq.QuadPart;
        prev = now;
        if (dt > 0.1f) dt = 0.1f;          // 창을 끌 때 한 번에 튀지 않게

        // 여운을 잦아들게 한다. 번쩍임은 켜진 순간이 가장 밝고 곧 0 으로 돌아온다
        if (g_shake > 0.0f) g_shake -= dt;
        if (g_flash > 0.0f) g_flash -= dt;
        g_glow = (g_flash > 0.0f) ? FLASH_MAX * (g_flash / FLASH_TIME) : 0.0f;

        // ── 세모들이 조금씩 옮겨 다닌다 ──
        UpdateTris(dt);

        // ── 쫓는 중이면 목표를 다시 겨눈다 ──
        // 세모가 옮겨 다니므로 매 프레임 자리를 고쳐 잡는다.
        // 이미 닿아 있으면 그 자리에 서서 셈을 이어간다
        if (g_chase >= 0 && g_tri[g_chase].alive) {
            float ex = g_x - g_tri[g_chase].x, ez = g_z - g_tri[g_chase].z;
            if (sqrtf(ex * ex + ez * ez) <= REACH) {
                g_tx = g_x;                    // 닿았으니 더 다가가지 않는다
                g_tz = g_z;
                g_hop += dt;                   // 뛰기 시작한다
                if (g_hop >= HOP_TIME) {       // 내려앉는 순간 세모가 사라진다
                    g_tri[g_chase].alive = false;
                    g_tri[g_chase].wait  = BORN_WAIT;
                    g_chase = -1;
                    g_hop   = 0.0f;
                    g_shake = SHAKE_TIME;      // 사라지는 순간의 여운
                    g_flash = FLASH_TIME;
                }
            } else {
                g_tx  = g_tri[g_chase].x;      // 옮겨간 자리로 다시 겨눈다
                g_tz  = g_tri[g_chase].z;
                g_hop = 0.0f;                  // 멀어졌으면 뜀을 물린다
            }
        } else {
            g_chase = -1;                      // 쫓던 것이 없어졌다
            g_hop   = 0.0f;
        }

        // 목표를 향해 한 걸음. 남은 거리가 한 걸음보다 짧으면 딱 붙이고 멈춘다 —
        // 이 처리가 없으면 목표를 지나쳤다 돌아오길 되풀이하며 떤다
        float dx = g_tx - g_x, dz = g_tz - g_z;
        float dist = sqrtf(dx * dx + dz * dz);
        float step = SPEED * dt;
        if (dist <= step) {
            g_x = g_tx;
            g_z = g_tz;
        } else {
            g_x += dx / dist * step;
            g_z += dz / dist * step;
        }

        // 가는 쪽으로 정면을 튼다. 한 번에 홱 돌지 않고 조금씩 돌린다
        if (dist > 0.001f) {
            float want = atan2f(dx, dz);        // 제 몸의 +Z 가 정면이다
            float diff = want - g_facing;
            // 가까운 쪽으로 돈다. 350도를 도는 대신 반대로 10도만 돌게 한다
            while (diff >  XM_PI) diff -= XM_2PI;
            while (diff < -XM_PI) diff += XM_2PI;
            float turn = TURN * dt;
            if (fabsf(diff) <= turn) g_facing = want;
            else                     g_facing += (diff > 0.0f ? turn : -turn);
        }

        // ── 사라진 자리에 새로 난다 ──
        for (int i = 0; i < TRI_N; ++i) {
            if (g_tri[i].alive) continue;
            g_tri[i].wait -= dt;
            if (g_tri[i].wait <= 0.0f) SpawnTri(i);
        }

        UpdateView();              // 끌어서 바뀐 각도를 이 프레임에 반영한다

        g_ctx->IASetInputLayout(g_layout);
        g_ctx->IASetPrimitiveTopology(D3D11_PRIMITIVE_TOPOLOGY_TRIANGLELIST);
        g_ctx->VSSetConstantBuffers(0, 1, &g_cb);
        g_ctx->PSSetConstantBuffers(0, 1, &g_cb);

        // ── 1패스 — 태양 자리에서 깊이만 기록한다 ──
        // 지난 프레임에 읽던 것을 떼어낸다. 같은 그림을 쓰면서 동시에
        // 그릴 수는 없어서, 안 떼면 이번 기록이 통째로 무시된다
        ID3D11ShaderResourceView* none[5] = {};
        g_ctx->PSSetShaderResources(0, 5, none);

        g_ctx->OMSetRenderTargets(0, nullptr, g_shadowDSV);
        g_ctx->ClearDepthStencilView(g_shadowDSV, D3D11_CLEAR_DEPTH, 1.0f, 0);
        g_ctx->RSSetViewports(1, &viewShadow);
        g_ctx->RSSetState(g_rsShadow);
        g_ctx->VSSetShader(g_vsDepth, nullptr, 0);
        g_ctx->PSSetShader(nullptr, nullptr, 0);      // 색은 안 쓴다
        DrawScene(true);

        // ── 2패스 — 화면에 그리면서 그늘을 판정한다 ──
        // 바탕도 함께 밝아져야 화면 전체가 번쩍인 것으로 보인다.
        // 물체만 밝히면 어두운 바탕이 그대로라 어색하다
        const float bg[4] = { BG[0] + (1.0f - BG[0]) * g_glow,
                              BG[1] + (1.0f - BG[1]) * g_glow,
                              BG[2] + (1.0f - BG[2]) * g_glow, 1.0f };
        g_ctx->OMSetRenderTargets(1, &g_rtv, g_dsv);
        g_ctx->ClearRenderTargetView(g_rtv, bg);
        g_ctx->ClearDepthStencilView(g_dsv, D3D11_CLEAR_DEPTH, 1.0f, 0);
        g_ctx->RSSetViewports(1, &viewMain);
        g_ctx->RSSetState(g_rsNormal);
        g_ctx->VSSetShader(g_vs, nullptr, 0);
        g_ctx->PSSetShader(g_ps, nullptr, 0);
        ID3D11ShaderResourceView* srvs[5] = { g_shadowSRV, g_albedo.srv, g_normal.srv,
                                             g_rough.srv, g_spec.srv };
        ID3D11SamplerState*       smps[2] = { g_shadowSmp, g_texSmp };
        g_ctx->PSSetShaderResources(0, 5, srvs);
        g_ctx->PSSetSamplers(0, 2, smps);
        DrawScene(false);

        // ── 3패스 — 오른쪽 위 방향 표시기 ──
        // 카메라와 같은 각도에서 보되 자리는 고정이라, 화면을 돌리면
        // 이것도 같이 돈다. 깊이를 지우고 그려서 물체에 가리지 않는다
        g_ctx->RSSetViewports(1, &viewGizmo);
        g_ctx->ClearDepthStencilView(g_dsv, D3D11_CLEAR_DEPTH, 1.0f, 0);
        float gcp = cosf(g_pitch), gsp = sinf(g_pitch);
        XMMATRIX gv = XMMatrixLookAtLH(
            XMVectorSet(3.0f * gcp * sinf(g_yaw), 3.0f * gsp, 3.0f * gcp * cosf(g_yaw), 0.0f),
            XMVectorSet(0.0f, 0.0f, 0.0f, 0.0f),
            XMVectorSet(0.0f, 1.0f, 0.0f, 0.0f));
        // 원근이 아니라 직교로 본다 — 원근이면 카메라 쪽으로 온 축만 굵어 보인다
        XMMATRIX gp = XMMatrixOrthographicLH(GIZMO_VIEW, GIZMO_VIEW, 0.1f, 10.0f);
        DrawAxes(XMMatrixIdentity(), gv * gp);

        // 글자가 카메라를 향하게 돌리는 행렬. 뷰 행렬을 되돌리면 카메라의
        // 자세가 나오는데, 자리는 필요 없고 방향만 쓰므로 평행이동을 지운다
        XMMATRIX bill = XMMatrixInverse(nullptr, gv);
        bill.r[3] = XMVectorSet(0.0f, 0.0f, 0.0f, 1.0f);
        DrawLabels(gv * gp, bill);

        g_swap->Present(1, 0);
    }

    // ── 정리 ──
    if (g_rsNormal)  g_rsNormal->Release();
    if (g_rsShadow)  g_rsShadow->Release();
    if (g_shadowSmp) g_shadowSmp->Release();
    if (g_shadowSRV) g_shadowSRV->Release();
    if (g_shadowDSV) g_shadowDSV->Release();
    if (g_triVB)     g_triVB->Release();
    if (g_labelVB)   g_labelVB->Release();
    if (g_axisVB)    g_axisVB->Release();
    if (g_plateVB)   g_plateVB->Release();
    g_head.Release();
    g_albedo.Release();
    g_normal.Release();
    g_rough.Release();
    g_spec.Release();
    if (g_texSmp) g_texSmp->Release();
    if (g_cb)        g_cb->Release();
    if (g_layout)    g_layout->Release();
    if (g_ps)        g_ps->Release();
    if (g_vsDepth)   g_vsDepth->Release();
    if (g_vs)        g_vs->Release();
    if (g_dsv)       g_dsv->Release();
    if (g_rtv)       g_rtv->Release();
    if (g_swap)      g_swap->Release();
    if (g_ctx)       g_ctx->Release();
    if (g_dev)       g_dev->Release();
    return 0;
}
