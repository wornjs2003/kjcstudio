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
#include "ibl.h"        // 환경맵 조명
#include "panel.h"      // 셰이더 조절 창

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

// 화면 왼쪽 위 상태 표시. 켜진 것은 밝게, 꺼진 것은 바탕에 잠기게 둔다
static const float STAT_ON[4]  = { 0.40f, 0.92f, 0.50f, 1.0f };
static const float STAT_OFF[4] = { 0.26f, 0.28f, 0.31f, 1.0f };

// ─── 태양 ──────────────────────────────────────────────────────────────
// 빛이 「오는 쪽」을 가리키는 방향이다. 태양은 아주 멀어서 빛줄기가
// 평행하게 오므로 자리가 아니라 방향 하나로 적는다.
//
//    y 를 키우면      한낮에 가까워진다 (그림자가 짧아진다)
//    y 를 줄이면      해질녘에 가까워진다 (그림자가 길어진다)
//    x, z 를 바꾸면   해가 뜬 방향이 바뀐다
// 태양은 각도로 들고 있다가 방향으로 바꿔 쓴다. 화살표 키로 돌릴 수 있어서
// 얼굴에 그림자를 지웠다 넣었다 하며 견줄 수 있다.
//
//   머리 위에 가까울수록   얼굴이 고르게 밝고 명암이 옅다
//   옆으로 눕힐수록       코 그림자가 볼에 지고 한쪽이 그늘진다
static float    g_sunYaw   = 1.35f;   // 좌우 (라디안)
static float    g_sunPitch = 0.58f;   // 위아래 — 약 33도
static XMFLOAT3 SUN        = { 0.82f, 0.55f, 0.19f };   // 위 각도에서 나온 값
static const float    AMBIENT = 0.22f;   // 그늘의 밝기. 0 이면 새까맣게 죽는다

// ─── 하늘빛과 땅빛 ─────────────────────────────────────────────────────
// 그늘을 자리마다 같은 밝기로 채우면 얼굴이 납작해진다. 위에서 오는 빛과
// 아래에서 오는 빛을 나누면 그것만으로 입체가 선다 — 환경광의 가장 단순한 꼴이다.
// 값은 선형이다 (화면에 보이는 값이 아니다)
static const float SKY_RGB[3]    = { 0.30f, 0.34f, 0.42f };  // 위 — 조금 푸르다
static const float GROUND_RGB[3] = { 0.09f, 0.08f, 0.07f };  // 아래 — 어둡고 누렇다

// 마모셋 씬의 Rim 에 해당한다. 뒤에서 비쳐 윤곽을 띄운다
static const float RIM_RGB[3] = { 0.55f, 0.58f, 0.66f };
static float g_rim = 0.7f;      // 세기. R 키로 껐다 켠다

// 곡률(Cavity) 세기. 오목한 자리를 얼마나 어둡게 할지. C 키로 껐다 켠다.
// 정점 곡률은 -1~1 인데 실제로는 ±0.2 안쪽에 몰려 있어 크게 곱해 준다
static float g_cav = 2.5f;

// 버텍스 AO — 그림자의 진하기와 지는 넓이.
//   진하기(g_vao)   화면에서 곱하는 값이라 키를 누르는 즉시 바뀐다
//   넓이(g_vaoR)    정점에 구워 넣은 값이라 B 키로 다시 구워야 바뀐다
static float g_vao  = 1.0f;    // 0 ~ 2.0   G · H 키
static float g_vaoR = 0.18f;   // 모델 높이의 몇 배까지 광선을 쏘나. , · . 키

// ─── 그림자 ────────────────────────────────────────────────────────────
// 기록장이 덮는 범위를 좁히고 크기를 키워 텍셀을 촘촘히 한다.
// 콧구멍처럼 작은 틈에 지는 그림자는 텍셀이 몇 개 안 되면 뭉개져 사라진다.
//
//   범위 24 · 크기 2048  →  텍셀 하나가 0.0117   콧구멍(0.05)이 4텍셀
//   범위  8 · 크기 4096  →  텍셀 하나가 0.0020   콧구멍이 25텍셀
//
// 대신 판(10) 바깥은 그림자를 못 받는다. 얼굴이 주인공이라 그쪽에 몰아준다 —
// 둘 다 챙기려면 먼 곳용과 가까운 곳용 기록장을 따로 둬야 한다(캐스케이드)
static const UINT  SHADOW_SIZE  = 4096;
static float SHADOW_RANGE = 1.2f;   // 1.2 m 를 덮는다. 9 · 0 키로 바꾼다
static const float SHADOW_BIAS  = 0.0010f;

// ─── 모델 ──────────────────────────────────────────────────────────────
// 정육면체 자리에 이 FBX 를 세운다.
//
// 경로를 여기 박아 둔 것은 1단계라서다. 다른 PC 에서는 안 열리므로
// 나중에 설정 파일이나 명령줄 인자로 뺀다
static const char* MESH_DIR =
    "C:\\Users\\9800X3D\\Desktop\\Work_01\\2025_10\\head\\femaleHead\\head"
    "/";
static const char* MODEL_FILE = "Assets/Meshes/Femalehead_0003_01.fbx";

// 얼굴에 얹어 함께 그리는 메시들.
// 마모셋 머티리얼이 텍스처 없이 단색(Color)만 쓰고 있어 색을 여기 적는다 —
// 털은 가닥 하나하나가 실제 지오메트리라 무늬가 필요 없다.
// 없는 파일은 조용히 건너뛴다. 눈알·헤어가 오면 여기 한 줄 더한다
struct Extra {
    const char* file;
    float       color[4];    // sRGB. 마모셋의 선형 값을 옮긴 것이다
    float       mode;        // 0 = 단색, 3 = 눈알 (제 텍스처를 쓴다)
    Model       model;
};
static Extra g_extra[] = {
    { "Brows_02.fbx",  { 0.309f, 0.254f, 0.254f, 1.0f }, 0.0f },   // 눈썹
    { "Lashes_02.fbx", { 0.309f, 0.254f, 0.254f, 1.0f }, 0.0f },   // 속눈썹

    // 눈알과 헤어. 텍스처를 붙이기 전이라 중성 회색으로 둔다
    { "eyeboll_left.fbx",  { 1.0f, 1.0f, 1.0f, 1.0f }, 3.0f },   // 텍스처를 쓴다
    { "eyeboll_right.fbx", { 1.0f, 1.0f, 1.0f, 1.0f }, 3.0f },
    { "hair.fbx",          { 1.0f, 1.0f, 1.0f, 1.0f }, 4.0f },   // 텍스처 + 알파

    // 눈알 위에 씌우는 물기막은 아직 뺀다 — 반투명으로 그릴 줄 몰라서,
    // 넣으면 불투명한 막이 눈알을 덮어 버린다
    // { "Eye Wet_02.fbx", { 0.700f, 0.700f, 0.720f, 1.0f } },
};
// 0 이면 원본 크기 그대로. FBX 를 미터로 읽었으므로 이 모델은 0.34m 다.
// 이렇게 두어야 1 단위 = 1 미터가 되고, 아래 값들이 실제 치수가 된다
static const float MODEL_H = 0.0f;
// 바닥에 딱 붙이면 발치가 판에 파묻혀 어디까지가 모델인지 안 보인다
static const float MODEL_LIFT = 0.1f;
// ← → 한 번에 도는 각도. 15도
static const float TURN_STEP  = 15.0f * 3.14159265f / 180.0f;

// 텍스처. FBX 안의 재질은 옛 파일 하나만 가리키고 있어서 여기서 직접 잇는다 —
// 재권님이 2K 로 줄여 두신 것들이다
static const char* TEX_DIR =
    "C:\\Users\\9800X3D\\Desktop\\Work_01\\2025_10\\head\\femaleHead\\head\\Assets\\Textures\\";
static const char* TEX_ALBEDO = "Face_Albedo.jpg";
static const char* TEX_NORMAL = "Face_Normal.jpg";
static const char* TEX_ROUGH  = "Face_Roughness.jpg";
static const char* TEX_SPEC   = "Face_Specular.jpg";
// 눈알. 거칠기·산란 맵은 마모셋 머티리얼에도 nil 이라 상수로 간다
static const char* EYE_ALBEDO = "Eyes_Balls_Diffuse.jpg";
static const char* EYE_NORMAL = "Eyes_Balls_Normals.jpg";
static const char* EYE_SPEC   = "Eyes_Balls_Spec.jpg";
// 헤어. 알베도의 알파가 가닥 모양을 오려 낸다
static const char* HAIR_ALBEDO = "Hair_Colour_Opacity.tga";
static const char* HAIR_NORMAL = "Hair_Normal.tga";
static const char* HAIR_SPEC   = "Hair_Specular.tga";
static const char* TEX_SCAT   = "Face_Scatter map.jpg";
static const char* TEX_MICRO  = "Face_Micro Normal.jpg";
static const char* TEX_MASK   = "Face_Details_Mask.jpg";

// ─── 환경맵 ────────────────────────────────────────────────────────────
// Poly Haven 에서 받은 CC0 HDR 들. [ ] 가 아니라 E 키로 돌려 가며 본다 —
// 무엇을 고르느냐로 인상이 통째로 달라져서 견줄 수 있어야 한다
static const char* HDRI_DIR = "../assets/hdri/";
static const char* HDRI[] = {
    "brown_photostudio_02.hdr",   // 따뜻한 스튜디오
    "studio_small_03.hdr",        // 밝고 고른 조명
    "blue_photo_studio.hdr",      // 차가운 쪽
};
static const int HDRI_N = 3;

// ─── 크기와 속도 ───────────────────────────────────────────────────────
// 여기서부터 모든 길이는 미터다. 머리가 0.34m 라는 것을 기준으로 잡았다
static const int   WIN_W = 1920, WIN_H = 1280;
static const float PLATE = 2.0f;    // 바닥판 한 변 — 2 m
static const float SPEED = 0.8f;    // 초당 0.8 m — 걷는 빠르기쯤
static const float ORBIT = 0.008f;  // 마우스 1픽셀을 끌 때 카메라가 도는 각도(라디안)

// 휠 줌. 곱하기로 움직여서 가까이서는 잘게, 멀리서는 큼직하게 바뀐다 —
// 더하기로 하면 붙었을 때 한 칸이 너무 크다
static const float ZOOM_STEP = 1.12f;
static const float ZOOM_MIN  = 0.12f;
static const float ZOOM_MAX  = 6.0f;
static const float TURN  = 9.0f;    // 정면을 트는 빠르기 (초당 라디안)

// ─── 세모 ──────────────────────────────────────────────────────────────
static const int   TRI_N     = 2;     // 화면에 늘 있어야 하는 개수 — 지시: 2개
static const float TRI_SIZE  = 0.12f; // 12 cm
static const float TRI_GAP   = 0.25f; // 25 cm 는 떨어져 난다
static const float REACH     = 0.20f; // 20 cm 안에 들면 닿은 것으로 본다
static const float BORN_WAIT = 1.0f;  // 사라지고 나서 새로 나기까지 — 지시: 1초

// 닿으면 네모가 한 번 뛴다. 이 뜀이 끝나는 순간 세모가 사라진다 —
// 지시로 「1초 기다렸다 사라진다」를 걷어내고 이 동작으로 바꿨다
static const float HOP_TIME   = 0.347f; // 뛰어올랐다 내려오기까지 — 지시로 0.52 에서 1.5배 빠르게
static const float HOP_HEIGHT = 0.10f;  // 10 cm 뛴다
static const float HOP_WOBBLE = 0.02f;  // 뛰는 동안 2 cm 떤다

// 가만히 있지 않고 조금씩 옮겨 다닌다
static const float DRIFT_MIN   = 1.0f;  // 다음 걸음까지 기다리는 시간 — 지시: 1~2초
static const float DRIFT_MAX   = 2.0f;
static const float DRIFT_STEP  = 0.15f; // 한 걸음에 15 cm
static const float DRIFT_SPEED = 0.3f;  // 초당 30 cm. 네모보다 느리다

// ─── 세모가 사라질 때의 여운 ───────────────────────────────────────────
static const float SHAKE_TIME = 0.32f;  // 흔들리는 시간
static const float SHAKE_AMP  = 0.02f;  // 2 cm 흔들린다
static const float FLASH_TIME = 0.28f;  // 밝아졌다 돌아오기까지
static const float FLASH_MAX  = 0.34f;  // 가장 밝을 때 흰색에 얼마나 가까운가 (0~1)
static const float AXIS_SELF  = 0.15f;  // 모델에 붙어 함께 도는 축 — 15 cm
static const UINT  GIZMO_PX   = 190;    // 오른쪽 위 방향 표시기의 한 변 (픽셀)
static const UINT  GIZMO_PAD  = 18;     // 창 모서리에서 띄우는 간격
static const float GIZMO_VIEW = 3.0f;   // 표시기가 담아내는 범위. 글자까지 들어가야 한다
static const float LABEL_AT   = 1.20f;  // 축 끝에서 글자가 놓이는 자리
static const float LABEL_SIZE = 0.28f;  // 글자 크기

// ─── 셰이더 ────────────────────────────────────────────────────────────
// 셰이더는 shaders/ 아래 파일로 있다. 전에는 이 자리에 문자열로 박혀
// 있었는데, 그러면 이런 것들이 걸렸다.
//
//   편집기가 HLSL 로 못 본다
//   리터럴 길이 한계에 걸려 내용과 상관없는 자리에서 잘린다
//   오류가 Shader@0x00007FF...(38,14) 로만 나와 어디인지 알 수 없다
//   C++ 설정값이 문자열 안에 잘못 들어가도 아무도 못 잡는다 (실제로 그랬다)
//
// 파일로 두면 넷 다 풀리고, 고친 뒤 F5 로 다시 읽을 수 있다
static const wchar_t* SH_SCENE = L"shaders/scene.hlsl";   // 물체를 그리는 것
static const wchar_t* SH_POST  = L"shaders/post.hlsl";    // 화면을 덮고 처리하는 것

// Vertex 는 model.h 에 있다 — FBX 에서 읽은 것과 여기서 만든 것이
// 같은 모양이어야 하나의 입력 레이아웃으로 그릴 수 있다
struct CB {
    XMMATRIX wvp;
    XMMATRIX world;
    XMMATRIX lightVP;
    XMMATRIX view;
    XMMATRIX proj;
    XMFLOAT4 color;
    XMFLOAT4 sun;
    XMFLOAT4 shadowParam;
    XMFLOAT4 camPos;      // HLSL 쪽 cbuffer 와 순서·자리가 정확히 같아야 한다
    XMFLOAT4 nrmFlip;
    XMFLOAT4 ssaoParam;
    XMFLOAT4 screen;
    XMFLOAT4 skyCol;
    XMFLOAT4 groundCol;
    XMFLOAT4 rimCol;
    XMFLOAT4 fogParam;
    XMFLOAT4 fogCol;
    XMFLOAT4 sssParam;
    XMFLOAT4 envParam;
    XMMATRIX invVP;
    XMFLOAT4 toneParam;
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
static Texture                  g_scatter;     // 빛이 살 속으로 얼마나 들어가나
static Texture                  g_micro;       // 모공·잔주름 같은 미세 결
static Texture                  g_mask;
static Texture                  g_eyeAlbedo, g_eyeNormal, g_eyeSpec;
static Texture                  g_hairAlbedo, g_hairNormal, g_hairSpec;        // 그 결을 어디에 얼마나 얹을지
static Environment              g_env;         // 환경맵에서 구운 것 셋
static int                      g_envIdx = 0;  // 지금 쓰는 HDR
static float                    g_envOn  = 1.0f;
static float                    g_envPow = 1.0f;   // 환경광 세기

// 노말맵의 채널별 부호. X · Y · Z 키로 하나씩 뒤집는다.
// 만든 도구마다 축을 잡는 방식이 달라 문서만 봐서는 알 수 없다 —
// 화면을 보며 맞추는 것이 가장 빠르고, 지금 상태는 창 제목에 적힌다
static XMFLOAT3 g_nFlip = XMFLOAT3(1.0f, -1.0f, 1.0f);
static HWND     g_hwnd  = nullptr;

// 피부 산란의 세기. S 키로 껐다 켰다 하며 견준다
static float    g_skin  = 1.0f;

// 미세 결의 세기. 지시로 기본이 켜짐이고, M 키로 견준다
static float    g_micTo = 1.0f;
// 미세 결을 몇 배로 촘촘히 깔 것인가. 셰이더에 박혀 있던 것을 여기로 옮겼다 —
// 창에서 값을 고칠 수 있으려면 상수 버퍼를 타고 가야 한다
static float    g_micTile = 70.0f;

// ─── 피부 번짐 (Separable SSS) ─────────────────────────────────────────
// 살 속으로 들어간 빛은 조금 떨어진 자리로 나온다. 그 번짐을 화면에서
// 흉내 낸다. 가로로 한 번, 세로로 한 번 흐리면 되므로 「분리 가능」이라 부른다.
//
// 번지게 하는 것은 확산뿐이다. 반사까지 번지면 하이라이트가 뭉개져
// 피부가 밀랍처럼 보인다 — 그래서 둘을 따로 담는다.
//
// 빨강이 가장 깊이 들어가고 파랑이 가장 얕다. 그래서 그늘 경계가 붉어진다
static const float SSS_RGB[3] = { 1.00f, 0.38f, 0.22f };
// 번지는 폭을 실제 길이(미터)로 잡는다. 화면 비율로 두면 줌할 때마다
// 번짐이 달라져 값이 의미를 잃는다. 피부 속 산란은 실제로 1~3 mm 다
static float g_sssWidth = 0.002f;   // 2 mm
static float g_sssOn    = 1.0f;
// 아래 셋은 끄고 켜며 무엇이 어디까지 하고 있는지 가려낸다
static float g_diffOn   = 1.0f;   // 끄면 피부색이 걷히고 회색이 된다
static float g_nrmOn    = 1.0f;   // 끄면 면 방향이 메시 그대로가 된다
static float g_specOn   = 1.0f;   // 끄면 번들거림이 사라진다
static float g_expo     = 0.46f;  // 노출 — 화면 전체 밝기
static float g_sunI     = 0.70f;  // 태양 세기. 환경광과 균형을 잡는다
static float g_bgPow    = 1.0f;   // 배경 밝기. 1 이면 환경맵 그대로   // Gray Diffuse — 피부색을 걷어내고 형태만 본다

// ─── 깊이 어둡게 (Fog) ─────────────────────────────────────────────────
// 카메라에서 멀어질수록 어둡게 해서 모델 자체의 앞뒤를 드러낸다.
// 얼굴에만 건다 — 판이나 배경까지 걸면 공간이 묻힌다.
//
// 시작·끝을 절대 거리로 두면 줌할 때마다 어긋난다. 카메라 거리를 기준으로
// 앞뒤 얼마인지로 잡아 두면 당겨도 밀어도 그대로 따라온다
static const float FOG_RGB[3] = { 0.015f, 0.016f, 0.020f };   // 섞을 색 (선형)
static float g_fogNear = -0.03f;   // 카메라 거리 기준 — 3 cm 앞부터 그대로
static float g_fogFar  =  0.12f;   // 12 cm 뒤면 온전히 섞인다. 얼굴 두께만큼이다
static float g_fogOn   =  0.0f;    // 8 키로 켠다. 기본은 꺼짐

// ─── SSAO ──────────────────────────────────────────────────────────────
// 구석진 곳이 얼마나 막혀 있는지 화면을 보고 어림잡아 어둡게 한다.
// 값은 눈으로 맞추는 것이라 키로 조절한다 — 빌드를 되풀이하지 않으려는 것이다
static const UINT  SSAO_DIV    = 1;      // 1 = 화면과 같은 크기
static float g_aoRadius = 0.03f;         // 3 cm 둘레를 본다
static float g_aoPower  = 1.0f;          // 어둡게 하는 세기
static float g_aoBias   = 0.002f;        // 2 mm 여유
static float g_aoOn     = 1.0f;
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

// SSAO 용. 화면과 같은 크기로 두되 다중표본은 쓰지 않는다 —
// 가림을 어림잡는 데는 한 겹이면 넉넉하고, 표본이 여럿이면 읽기가 번거롭다
static ID3D11RenderTargetView*   g_posRTV    = nullptr;
static ID3D11ShaderResourceView* g_posSRV    = nullptr;
static ID3D11RenderTargetView*   g_nrmRTV    = nullptr;
static ID3D11ShaderResourceView* g_nrmSRV    = nullptr;
static ID3D11DepthStencilView*   g_gbufDSV   = nullptr;
static ID3D11RenderTargetView*   g_aoRTV     = nullptr;
static ID3D11ShaderResourceView* g_aoSRV     = nullptr;
static ID3D11RenderTargetView*   g_aoBlurRTV = nullptr;
static ID3D11ShaderResourceView* g_aoBlurSRV = nullptr;
static ID3D11SamplerState*       g_pointSmp  = nullptr;

static ID3D11VertexShader*       g_vsGBuf    = nullptr;
static ID3D11PixelShader*        g_psGBuf    = nullptr;
static ID3D11VertexShader*       g_vsFull    = nullptr;
static ID3D11PixelShader*        g_psSSAO    = nullptr;
static ID3D11PixelShader*        g_psBlur    = nullptr;
static ID3D11PixelShader*        g_psSky     = nullptr;
// 배경을 그릴 때는 깊이를 보지도 쓰지도 않는다. 화면을 덮는 삼각형이
// 깊이를 써 버리면 그 뒤에 그리는 물체가 가려진다
static ID3D11DepthStencilState*  g_dsNoDepth = nullptr;

// 피부 번짐용. 그림을 화면에 바로 그리지 않고 여기 담았다가,
// 확산만 번지게 한 뒤 합쳐서 내보낸다
static ID3D11RenderTargetView*   g_sceneRTV  = nullptr;   // 색 전부 (다중표본)
static ID3D11RenderTargetView*   g_diffRTV   = nullptr;   // 확산만 (다중표본)
static ID3D11Texture2D*          g_sceneMS   = nullptr;
static ID3D11Texture2D*          g_diffMS    = nullptr;
static ID3D11Texture2D*          g_sceneRes  = nullptr;   // 한 겹으로 푼 것
static ID3D11Texture2D*          g_diffRes   = nullptr;
static ID3D11ShaderResourceView* g_sceneSRV  = nullptr;
static ID3D11ShaderResourceView* g_diffSRV   = nullptr;
static ID3D11RenderTargetView*   g_blurRTV[2] = { nullptr, nullptr };
static ID3D11ShaderResourceView* g_blurSRV[2] = { nullptr, nullptr };
static ID3D11PixelShader*        g_psSSSBlur = nullptr;
static ID3D11PixelShader*        g_psCombine = nullptr;

// 깊이·법선을 그릴 때는 축을 빼야 한다. 선이라 그 둘레가 괜히 어두워진다
static bool g_wantAxes = true;

static XMMATRIX g_view, g_proj, g_lightVP;
static XMFLOAT3 g_camPos;      // 지금 카메라가 있는 자리. PBR 계산에 넘긴다

// ─── 카메라 ────────────────────────────────────────────────────────────
// 바라보는 점(원점)을 중심으로 구면 위를 돈다. 가운데 단추를 누른 채 끌면
// yaw(좌우)와 pitch(위아래)가 바뀐다. 거리는 그대로라 물체에서 멀어지지 않는다
static float g_yaw   = 0.55f;      // 좌우 각도 — 얼굴 3/4 쪽. 전에는 뒤통수였다
static float g_pitch = 0.18f;      // 위아래 각도 — 눈높이에 가깝게
static float g_dist  = 0.55f;      // 55 cm 앞에서 본다. 휠로 바뀐다
static float g_lookY = 0.26f;      // 26 cm — 눈께
// 바라보는 지점을 옆으로도 옮긴다 (WASD). 이것이 없으면 물체가 화면
// 한쪽으로 치우쳤을 때 가운데로 되돌릴 방법이 없다
static float g_lookX = 0.0f, g_lookZ = 0.0f;
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
//   S  정점 16~25 (선 5개)   화면 왼쪽 위 상태 표시에 쓴다
//   M  정점 26~33 (선 4개)
//   O  정점 34~41 (선 4개)
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

    L( 0.5f,  0.5f, -0.5f,  0.5f);   // S — 위 가로에서 시작해
    L(-0.5f,  0.5f, -0.5f,  0.0f);   //     왼쪽으로 내려와
    L(-0.5f,  0.0f,  0.5f,  0.0f);   //     가운데를 건너
    L( 0.5f,  0.0f,  0.5f, -0.5f);   //     오른쪽으로 내려가
    L( 0.5f, -0.5f, -0.5f, -0.5f);   //     아래 가로

    L(-0.5f, -0.5f, -0.5f,  0.5f);   // M — 왼쪽 기둥
    L(-0.5f,  0.5f,  0.0f,  0.0f);   //     가운데로 내려오는 사선 둘
    L( 0.0f,  0.0f,  0.5f,  0.5f);
    L( 0.5f,  0.5f,  0.5f, -0.5f);   //     오른쪽 기둥

    L(-0.4f,  0.5f,  0.4f,  0.5f);   // O — 네모로 그린다. 선이라 동그라미는
    L( 0.4f,  0.5f,  0.4f, -0.5f);   //     각이 지고 정점만 는다
    L( 0.4f, -0.5f, -0.4f, -0.5f);
    L(-0.4f, -0.5f, -0.4f,  0.5f);
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
    XMVECTOR eye = XMVectorSet(g_lookX + g_dist * cp * sinf(g_yaw),
                               g_lookY + g_dist * sp,
                               g_lookZ + g_dist * cp * cosf(g_yaw), 0.0f);
    XMVECTOR at = XMVectorSet(g_lookX, g_lookY, g_lookZ, 0.0f);

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

// 각도에서 태양 방향을 다시 구하고, 그림자 행렬도 함께 고쳐 잡는다
static void BuildLightMatrix();
static void UpdateSun() {
    float cp = cosf(g_sunPitch);
    SUN = XMFLOAT3(cp * sinf(g_sunYaw), sinf(g_sunPitch), cp * cosf(g_sunYaw));
    BuildLightMatrix();
}

// ─── 태양 시점의 행렬을 구한다 ─────────────────────────────────────────
// 태양은 아주 멀어서 빛이 평행하게 온다. 그래서 원근이 아니라 직교로 본다 —
// 원근으로 보면 멀리 있는 것이 작아져서 그림자 크기가 틀어진다
static void BuildLightMatrix() {
    XMVECTOR dir = XMVector3Normalize(XMLoadFloat3(&SUN));

    // 기록장이 담는 자리를 모델에 맞춰 옮긴다. 원점에 고정해 두면
    // 모델이 조금만 걸어가도 범위(SHADOW_RANGE) 밖으로 나가 그림자가 끊긴다.
    // 폭이 1.2m 이라 0.6m 만 벗어나도 그렇게 된다
    XMVECTOR at  = XMVectorSet(g_x, MODEL_LIFT, g_z, 0.0f);
    XMVECTOR eye = XMVectorAdd(at, XMVectorScale(dir, SHADOW_RANGE));

    // 위쪽 축이 시선과 나란하면 행렬이 무너진다. 태양이 거의 머리 위면 다른 축을 쓴다
    XMVECTOR up = (fabsf(XMVectorGetY(dir)) > 0.99f)
                ? XMVectorSet(0.0f, 0.0f, 1.0f, 0.0f)
                : XMVectorSet(0.0f, 1.0f, 0.0f, 0.0f);

    XMMATRIX v = XMMatrixLookAtLH(eye, at, up);
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
static void UpdateTitle();   // 아래에 있다
static void SaveView();

// ─── 조절 창과 주고받기 ────────────────────────────────────────────────
// 창은 엔진 내부를 모르고 ShaderSettings 한 묶음만 안다.
// 여기서 그것을 엔진 변수로 풀고, 반대로도 담는다
static ShaderSettings g_set;

static void SettingsFromEngine() {
    g_set.skin    = g_skin  > 0.5f;
    g_set.micro   = g_micTo > 0.5f;
    g_set.ssao    = g_aoOn  > 0.5f;
    g_set.cavity  = g_cav   > 0.05f;
    g_set.rim     = g_rim   > 0.05f;
    g_set.vao     = g_vao   > 0.05f;
    g_set.sssBlur = g_sssOn > 0.5f;
    g_set.fog     = g_fogOn > 0.5f;
    g_set.ibl     = g_envOn > 0.5f;
    g_set.diffuse   = g_diffOn > 0.5f;
    g_set.normalMap = g_nrmOn  > 0.5f;
    g_set.specular  = g_specOn > 0.5f;

    g_set.microTile    = g_micTile;
    g_set.ssaoRadius   = g_aoRadius;
    g_set.ssaoPower    = g_aoPower;
    if (g_set.cavity) g_set.cavityPower = g_cav;   // 꺼져 있으면 0 이라 덮지 않는다
    if (g_set.rim)    g_set.rimPower    = g_rim;
    if (g_set.vao)    g_set.vaoPower    = g_vao;
    g_set.vaoRadius    = g_vaoR;
    g_set.sssWidthMm   = g_sssWidth * 1000.0f;
    g_set.fogDepth     = g_fogFar;
    g_set.envPower     = g_envPow;
    g_set.shadowRange  = SHADOW_RANGE;
    g_set.sunYawDeg    = g_sunYaw   * 57.29578f;
    g_set.sunHeightDeg = g_sunPitch * 57.29578f;
    g_set.exposure     = g_expo;
    g_set.sunIntensity = g_sunI;
    g_set.background   = g_bgPow;
}

static bool g_fromPanel = false;   // 창이 부른 것이면 칸을 되쓰지 않는다

static void ApplySettings(const ShaderSettings& s) {
    g_fromPanel = true;
    g_set = s;
    g_skin  = s.skin    ? 1.0f : 0.0f;
    g_micTo = s.micro   ? 1.0f : 0.0f;
    g_aoOn  = s.ssao    ? 1.0f : 0.0f;
    g_sssOn = s.sssBlur ? 1.0f : 0.0f;
    g_fogOn = s.fog     ? 1.0f : 0.0f;
    g_envOn = s.ibl     ? 1.0f : 0.0f;
    g_diffOn = s.diffuse   ? 1.0f : 0.0f;
    g_nrmOn  = s.normalMap ? 1.0f : 0.0f;
    g_specOn = s.specular  ? 1.0f : 0.0f;
    // 이 셋은 켜고 끄기와 세기가 한 값에 묶여 있다. 끄면 0 이 되고,
    // 다시 켜면 창이 들고 있던 세기로 돌아온다
    g_cav = s.cavity ? s.cavityPower : 0.0f;
    g_rim = s.rim    ? s.rimPower    : 0.0f;
    g_vao = s.vao    ? s.vaoPower    : 0.0f;

    g_micTile  = s.microTile;
    g_aoRadius = s.ssaoRadius;
    g_aoPower  = s.ssaoPower;
    g_vaoR     = s.vaoRadius;
    g_sssWidth = s.sssWidthMm * 0.001f;
    g_fogFar   = s.fogDepth;
    g_envPow   = s.envPower;

    SHADOW_RANGE = s.shadowRange;
    g_sunYaw     = s.sunYawDeg    * 0.01745329f;
    g_sunPitch   = s.sunHeightDeg * 0.01745329f;
    g_expo       = s.exposure;
    g_sunI       = s.sunIntensity;
    g_bgPow      = s.background;
    UpdateSun();          // 태양 방향과 그림자 행렬을 함께 고쳐 잡는다
    UpdateTitle();
    g_fromPanel = false;
}

static const char* SET_FILE = "kjcEngine-shader.txt";

static void SaveSettings() {
    SaveView();                       // 보던 자리도 함께 담는다
    FILE* f = nullptr;
    if (fopen_s(&f, SET_FILE, "w") != 0 || !f) return;
    const ShaderSettings& s = g_set;
    fprintf(f, "%d %d %d %d %d %d %d %d %d %d %d %d\n",
            s.skin, s.micro, s.ssao, s.cavity, s.rim, s.vao, s.sssBlur, s.fog,
            s.ibl, s.diffuse, s.normalMap, s.specular);
    fprintf(f, "%g %g %g %g %g %g %g %g %g %g %g %g %g %g %g %g\n",
            s.microTile, s.ssaoRadius, s.ssaoPower, s.cavityPower, s.rimPower,
            s.vaoPower, s.vaoRadius, s.sssWidthMm, s.fogDepth, s.envPower,
            s.shadowRange, s.sunYawDeg, s.sunHeightDeg, s.exposure, s.sunIntensity,
            s.background);
    fclose(f);
    if (g_hwnd) SetWindowTextW(g_hwnd, L"kjcEngine   |   값을 담았습니다");
}

static void LoadSettings() {
    FILE* f = nullptr;
    if (fopen_s(&f, SET_FILE, "r") != 0 || !f) return;   // 없으면 기본값
    int b[12] = {};
    float v[16] = {};
    if (fscanf_s(f, "%d %d %d %d %d %d %d %d %d %d %d %d",
                 &b[0],&b[1],&b[2],&b[3],&b[4],&b[5],&b[6],&b[7],&b[8],
                 &b[9],&b[10],&b[11]) == 12 &&
        fscanf_s(f, "%f %f %f %f %f %f %f %f %f %f %f %f %f %f %f %f",
                 &v[0],&v[1],&v[2],&v[3],&v[4],&v[5],&v[6],&v[7],
                 &v[8],&v[9],&v[10],&v[11],&v[12],&v[13],&v[14],&v[15]) == 16) {
        ShaderSettings s;
        s.skin=b[0]; s.micro=b[1]; s.ssao=b[2]; s.cavity=b[3]; s.rim=b[4];
        s.vao=b[5];  s.sssBlur=b[6]; s.fog=b[7]; s.ibl=b[8];
        s.diffuse=b[9]; s.normalMap=b[10]; s.specular=b[11];
        s.microTile=v[0]; s.ssaoRadius=v[1]; s.ssaoPower=v[2]; s.cavityPower=v[3];
        s.rimPower=v[4];  s.vaoPower=v[5];   s.vaoRadius=v[6]; s.sssWidthMm=v[7];
        s.fogDepth=v[8];  s.envPower=v[9];   s.shadowRange=v[10];
        s.sunYawDeg=v[11]; s.sunHeightDeg=v[12];
        s.exposure=v[13];  s.sunIntensity=v[14]; s.background=v[15];
        ApplySettings(s);
    }
    fclose(f);
}

static void RebakeNow() {
    if (g_hwnd) SetWindowTextW(g_hwnd, L"kjcEngine   |   버텍스 AO 굽는 중...");
    RebakeAO(g_ctx, g_head, g_vaoR);
    UpdateTitle();
}

// ─── 상수 버퍼 채우기 ──────────────────────────────────────────────────
// 네 곳에서 같은 것을 손으로 되풀이하다 빠뜨린 자리가 생겼다.
// 초기화 없는 지역 변수라 빠진 칸에는 쓰레기 값이 실려 GPU 로 갔다 —
// 화면이 멀쩡해 보여도 우연이었다. 한곳에 모아 그 일이 다시 없게 한다
static void SetCB(XMMATRIX world, XMMATRIX viewProj,
                  const float rgba[4], float mode) {
    CB cb = {};
    cb.wvp         = XMMatrixTranspose(world * viewProj);
    cb.world       = XMMatrixTranspose(world);
    cb.lightVP     = XMMatrixTranspose(g_lightVP);
    cb.view        = XMMatrixTranspose(g_view);
    cb.proj        = XMMatrixTranspose(g_proj);
    cb.invVP       = XMMatrixTranspose(
                         XMMatrixInverse(nullptr, XMMatrixMultiply(g_view, g_proj)));
    cb.color       = XMFLOAT4(rgba[0], rgba[1], rgba[2], rgba[3]);
    cb.sun         = XMFLOAT4(SUN.x, SUN.y, SUN.z, g_glow);
    cb.shadowParam = XMFLOAT4(1.0f / SHADOW_SIZE, SHADOW_BIAS, AMBIENT, mode);
    cb.camPos      = XMFLOAT4(g_camPos.x, g_camPos.y, g_camPos.z, g_micTo);
    cb.nrmFlip     = XMFLOAT4(g_nFlip.x, g_nFlip.y, g_nFlip.z, g_skin);
    cb.ssaoParam   = XMFLOAT4(g_aoRadius, g_aoPower, g_aoBias, g_aoOn);
    cb.screen      = XMFLOAT4((float)WIN_W, (float)WIN_H, g_diffOn, g_nrmOn);
    cb.toneParam   = XMFLOAT4(g_expo, g_sunI, g_bgPow, g_specOn);
    cb.skyCol      = XMFLOAT4(SKY_RGB[0], SKY_RGB[1], SKY_RGB[2], g_cav);
    cb.groundCol   = XMFLOAT4(GROUND_RGB[0], GROUND_RGB[1], GROUND_RGB[2], g_rim);
    cb.rimCol      = XMFLOAT4(RIM_RGB[0], RIM_RGB[1], RIM_RGB[2], g_vao);
    cb.fogParam    = XMFLOAT4(g_dist + g_fogNear, g_dist + g_fogFar, g_fogOn, 0.0f);
    cb.fogCol      = XMFLOAT4(FOG_RGB[0], FOG_RGB[1], FOG_RGB[2], 0.0f);
    cb.sssParam    = XMFLOAT4(0.0f, g_sssOn, 0.0f, 0.0f);   // 폭·방향은 번짐 패스에서
    cb.envParam    = XMFLOAT4(g_envPow, (float)g_env.specMips, g_envOn, g_micTile);
    g_ctx->UpdateSubresource(g_cb, 0, nullptr, &cb, 0, 0);
}

// idxFmt 는 인덱스 한 칸의 크기다. 여기서 만든 작은 도형은 16비트면 넉넉하지만,
// FBX 모델은 정점이 6만 5천을 넘을 수 있어 32비트를 쓴다
static void DrawOne(ID3D11Buffer* vb, ID3D11Buffer* ib, UINT count,
                    XMMATRIX world, const float rgba[4], bool depthPass,
                    DXGI_FORMAT idxFmt = DXGI_FORMAT_R16_UINT, float mode = 0.0f) {
    UINT stride = sizeof(Vertex), offset = 0;
    g_ctx->IASetVertexBuffers(0, 1, &vb, &stride, &offset);

    SetCB(world, depthPass ? g_lightVP : XMMatrixMultiply(g_view, g_proj),
          rgba, mode);

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
        SetCB(world, viewProj, c[i], 1.0f);
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
        SetCB(w, viewProj, L[i].color, 1.0f);
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
    float cx = g_x, cy = MODEL_LIFT, cz = g_z;   // 판에서 살짝 띄운다
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
    // 눈썹·속눈썹·헤어는 텍스처가 없어 단색(모드 0)으로 간다.
    // 눈알(모드 3)만 제 텍스처가 있어 그 세 장을 잠깐 갈아 끼운다
    for (Extra& e : g_extra) {
        if (!e.model.indexCount) continue;
        float mode = e.mode;
        // 제 텍스처가 있는 것만 그 모드로 간다. 없으면 회색으로 떨어뜨린다
        Texture* set = nullptr;
        if      (mode > 3.5f) set = g_hairAlbedo.srv ? &g_hairAlbedo : nullptr;
        else if (mode > 2.5f) set = g_eyeAlbedo.srv  ? &g_eyeAlbedo  : nullptr;

        bool swap = (set != nullptr) && !depthPass;
        if (swap) {
            bool hair = (mode > 3.5f);
            ID3D11ShaderResourceView* t[2] = {
                hair ? g_hairAlbedo.srv : g_eyeAlbedo.srv,
                hair ? g_hairNormal.srv : g_eyeNormal.srv };
            g_ctx->PSSetShaderResources(1, 2, t);
            ID3D11ShaderResourceView* sp = hair ? g_hairSpec.srv : g_eyeSpec.srv;
            g_ctx->PSSetShaderResources(4, 1, &sp);
        } else if (mode > 2.5f) {
            mode = 0.0f;               // 텍스처가 없으면 회색으로 그린다
        }

        DrawOne(e.model.vb, e.model.ib, e.model.indexCount, cubeWorld,
                e.color, depthPass, DXGI_FORMAT_R32_UINT, mode);

        if (swap) {                    // 얼굴 것으로 돌려 놓는다
            ID3D11ShaderResourceView* t[2] = { g_albedo.srv, g_normal.srv };
            g_ctx->PSSetShaderResources(1, 2, t);
            g_ctx->PSSetShaderResources(4, 1, &g_spec.srv);
        }
    }

    for (int i = 0; i < TRI_N; ++i) {
        if (!g_tri[i].alive) continue;
        DrawOne(g_triVB, nullptr, 12,
                XMMatrixTranslation(g_tri[i].x, 0.0f, g_tri[i].z), TRI_C, depthPass);
    }

    // 정육면체가 어디를 보는지 알려주는 축. 그림자 기록과 깊이·법선 패스에는
    // 넣지 않는다 — 선이라 그림자가 실오라기처럼 지고, 방향 표시지 물체가 아니다
    if (!depthPass && g_wantAxes)
        DrawAxes(XMMatrixScaling(AXIS_SELF, AXIS_SELF, AXIS_SELF) * cubeWorld,
                 g_view * g_proj);
}

// ─── 보던 자리를 기억한다 ──────────────────────────────────────────────
// 빌드할 때마다 창이 닫혀 각도를 다시 맞춰야 하는 것을 없앤다.
// K 로 담고, 켤 때 저절로 꺼내 쓴다
static const char* VIEW_FILE = "kjcEngine-view.txt";

static void SaveView() {
    FILE* f = nullptr;
    if (fopen_s(&f, VIEW_FILE, "w") != 0 || !f) return;
    fprintf(f, "%g %g %g %g %g %g %g %g\n",
            g_yaw, g_pitch, g_dist, g_lookX, g_lookY, g_lookZ,
            g_sunYaw, g_sunPitch);
    fclose(f);
}

static void LoadView() {
    FILE* f = nullptr;
    if (fopen_s(&f, VIEW_FILE, "r") != 0 || !f) return;   // 없으면 기본값 그대로
    float a, b, c, d, e, g, h, i;
    if (fscanf_s(f, "%f %f %f %f %f %f %f %f", &a, &b, &c, &d, &e, &g, &h, &i) == 8) {
        g_yaw = a; g_pitch = b; g_dist = c;
        g_lookX = d; g_lookY = e; g_lookZ = g;
        g_sunYaw = h; g_sunPitch = i;
    }
    fclose(f);
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

// ─── 셰이더 만들기 ─────────────────────────────────────────────────────
// 파일에서 읽어 컴파일하고 갈아끼운다. F5 로 다시 부를 수 있다.
// 컴파일을 전부 마친 뒤에 교체하므로, 하나라도 틀리면 돌고 있던 것이 그대로
// 남는다 — 오타 하나에 화면이 까맣게 되지 않는다
static bool BuildShaders(HWND hwnd) {
    struct Job { const wchar_t* file; const char* entry; const char* target; ID3DBlob** out; };

    ID3DBlob *bVS = nullptr, *bVSD = nullptr, *bPS = nullptr, *bGV = nullptr,
             *bGP = nullptr, *bFV = nullptr, *bAO = nullptr, *bBL = nullptr,
             *bSK = nullptr, *bSB = nullptr, *bCM = nullptr;

    const Job jobs[] = {
        { SH_SCENE, "VS",         "vs_5_0", &bVS  },
        { SH_SCENE, "VS_Depth",   "vs_5_0", &bVSD },
        { SH_SCENE, "PS",         "ps_5_0", &bPS  },
        { SH_SCENE, "VS_GBuf",    "vs_5_0", &bGV  },
        { SH_SCENE, "PS_GBuf",    "ps_5_0", &bGP  },
        { SH_POST,  "VS_Full",    "vs_5_0", &bFV  },
        { SH_POST,  "PS_SSAO",    "ps_5_0", &bAO  },
        { SH_POST,  "PS_Blur",    "ps_5_0", &bBL  },
        { SH_POST,  "PS_Sky",     "ps_5_0", &bSK  },
        { SH_POST,  "PS_SSSBlur", "ps_5_0", &bSB  },
        { SH_POST,  "PS_Combine", "ps_5_0", &bCM  },
    };

    for (const Job& j : jobs) {
        ID3DBlob* e = nullptr;
        // D3D_COMPILE_STANDARD_FILE_INCLUDE 를 주면 #include 가 그 파일 옆에서 찾아진다
        HRESULT hr = D3DCompileFromFile(j.file, nullptr, D3D_COMPILE_STANDARD_FILE_INCLUDE,
                                        j.entry, j.target, 0, 0, j.out, &e);
        if (FAILED(hr)) {
            char msg[2048];
            if (e) {
                snprintf(msg, sizeof(msg), "%s", (const char*)e->GetBufferPointer());
                e->Release();
            } else {
                snprintf(msg, sizeof(msg), "shader file not found or unreadable:\n%ls\n(entry %s)",
                         j.file, j.entry);
            }
            Fail(hwnd, msg);
            for (const Job& k : jobs) if (*k.out) { (*k.out)->Release(); *k.out = nullptr; }
            return false;
        }
        if (e) e->Release();
    }

    // 여기까지 왔으면 전부 성공이다. 이제 갈아끼운다
    ID3D11DeviceChild* old[] = { g_vs, g_vsDepth, g_ps, g_vsGBuf, g_psGBuf,
                                 g_vsFull, g_psSSAO, g_psBlur, g_psSky,
                                 g_psSSSBlur, g_psCombine, g_layout };
    for (ID3D11DeviceChild* o : old) if (o) o->Release();

    g_dev->CreateVertexShader(bVS ->GetBufferPointer(), bVS ->GetBufferSize(), nullptr, &g_vs);
    g_dev->CreateVertexShader(bVSD->GetBufferPointer(), bVSD->GetBufferSize(), nullptr, &g_vsDepth);
    g_dev->CreatePixelShader (bPS ->GetBufferPointer(), bPS ->GetBufferSize(), nullptr, &g_ps);
    g_dev->CreateVertexShader(bGV ->GetBufferPointer(), bGV ->GetBufferSize(), nullptr, &g_vsGBuf);
    g_dev->CreatePixelShader (bGP ->GetBufferPointer(), bGP ->GetBufferSize(), nullptr, &g_psGBuf);
    g_dev->CreateVertexShader(bFV ->GetBufferPointer(), bFV ->GetBufferSize(), nullptr, &g_vsFull);
    g_dev->CreatePixelShader (bAO ->GetBufferPointer(), bAO ->GetBufferSize(), nullptr, &g_psSSAO);
    g_dev->CreatePixelShader (bBL ->GetBufferPointer(), bBL ->GetBufferSize(), nullptr, &g_psBlur);
    g_dev->CreatePixelShader (bSK ->GetBufferPointer(), bSK ->GetBufferSize(), nullptr, &g_psSky);
    g_dev->CreatePixelShader (bSB ->GetBufferPointer(), bSB ->GetBufferSize(), nullptr, &g_psSSSBlur);
    g_dev->CreatePixelShader (bCM ->GetBufferPointer(), bCM ->GetBufferSize(), nullptr, &g_psCombine);

    // 자리(offset)는 Vertex 구조와 정확히 맞아야 한다 — 어긋나면 화면이
    // 조용히 이상해지고 오류는 안 난다
    D3D11_INPUT_ELEMENT_DESC il[] = {
        { "POSITION", 0, DXGI_FORMAT_R32G32B32_FLOAT,    0,  0, D3D11_INPUT_PER_VERTEX_DATA, 0 },
        { "NORMAL",   0, DXGI_FORMAT_R32G32B32_FLOAT,    0, 12, D3D11_INPUT_PER_VERTEX_DATA, 0 },
        { "TANGENT",  0, DXGI_FORMAT_R32G32B32A32_FLOAT, 0, 24, D3D11_INPUT_PER_VERTEX_DATA, 0 },
        { "TEXCOORD", 0, DXGI_FORMAT_R32G32_FLOAT,       0, 40, D3D11_INPUT_PER_VERTEX_DATA, 0 },
        { "TEXCOORD", 1, DXGI_FORMAT_R32_FLOAT,          0, 48, D3D11_INPUT_PER_VERTEX_DATA, 0 },
        { "TEXCOORD", 2, DXGI_FORMAT_R32_FLOAT,          0, 52, D3D11_INPUT_PER_VERTEX_DATA, 0 },
    };
    g_dev->CreateInputLayout(il, 6, bVS->GetBufferPointer(), bVS->GetBufferSize(), &g_layout);

    for (const Job& j : jobs) (*j.out)->Release();
    return true;
}

// 지금 상태를 창 제목에 적는다. 노말맵 부호는 눈으로 확인할 방법이 없어서
// 어딘가에 보여야 한다 — 안 그러면 눌러 놓고도 어느 쪽인지 헷갈린다
static void UpdateTitle() {
    if (!g_fromPanel) { SettingsFromEngine(); PanelRefresh(g_set); }

    if (!g_hwnd) return;
    char t[256];
    wsprintfA(t, "kjcEngine   |   normal X%c Y%c Z%c   |   skin %s  micro %s  sss %s w%dmm  fog %s f%d.%02d"
                 "   |   ao %s  env %s   |   vao %d.%d r%d.%02d%s   |   shadow %d (texel .%04d)   |   sun %d/%d",
              g_nFlip.x < 0.0f ? '-' : '+',
              g_nFlip.y < 0.0f ? '-' : '+',
              g_nFlip.z < 0.0f ? '-' : '+',
              g_skin  > 0.5f ? "on" : "off",
              g_micTo > 0.5f ? "on" : "off",
              g_sssOn > 0.5f ? "on" : "off",
              (int)(g_sssWidth * 1000.0f + 0.5f),
              g_fogOn > 0.5f ? "on" : "off",
              (int)g_fogFar, (int)(g_fogFar * 100.0f) % 100,
              g_aoOn  > 0.5f ? "on" : "off",
              (g_envOn > 0.5f && g_env.skySRV) ? "on" : "off",
              (int)g_vao, (int)(g_vao * 10.0f) % 10,
              (int)g_vaoR, (int)(g_vaoR * 100.0f) % 100,
              // 구워진 값과 지금 고른 값이 다르면 알린다. B 를 눌러야 반영된다
              (fabsf(g_vaoR - g_head.aoRadius) > 1e-4f) ? " [B]" : "",
              (int)SHADOW_RANGE,
              (int)(SHADOW_RANGE / SHADOW_SIZE * 10000.0f),
              (int)(g_sunYaw   * 57.2958f),   // 라디안을 도로
              (int)(g_sunPitch * 57.2958f));
    SetWindowTextA(g_hwnd, t);
}

// 카메라를 당기고 민다. 휠과 [ ] 키가 같이 쓴다
static void Zoom(float factor) {
    g_dist *= factor;
    if (g_dist < ZOOM_MIN) g_dist = ZOOM_MIN;
    if (g_dist > ZOOM_MAX) g_dist = ZOOM_MAX;
}

// ─── 화면 왼쪽 위 상태 표시 ────────────────────────────────────────────
// 무엇이 켜져 있는지 보여준다. 창 제목에도 적지만 거기는 눈에 안 들어온다.
// 켜진 것은 밝게, 꺼진 것은 바탕에 잠기듯 어둡게 둔다
static void DrawStatus(XMMATRIX viewProj) {
    UINT stride = sizeof(Vertex), offset = 0;
    g_ctx->IASetVertexBuffers(0, 1, &g_labelVB, &stride, &offset);
    g_ctx->IASetPrimitiveTopology(D3D11_PRIMITIVE_TOPOLOGY_LINELIST);

    struct Item { float x; bool on; UINT start, count; };
    const Item items[3] = {
        { -1.3f, g_skin  > 0.5f, 16, 10 },   // S  피부 산란
        {  0.0f, g_micTo > 0.5f, 26,  8 },   // M  미세 결
        {  1.3f, g_aoOn  > 0.5f, 34,  8 },   // O  가림(SSAO)
    };

    for (int i = 0; i < 3; ++i) {
        const float* c = items[i].on ? STAT_ON : STAT_OFF;
        XMMATRIX w = XMMatrixScaling(0.8f, 0.8f, 0.8f)
                   * XMMatrixTranslation(items[i].x, 0.0f, 0.0f);
        SetCB(w, viewProj, c, 1.0f);
        g_ctx->Draw(items[i].count, items[i].start);
    }

    g_ctx->IASetPrimitiveTopology(D3D11_PRIMITIVE_TOPOLOGY_TRIANGLELIST);
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
        // F5        셰이더 파일을 다시 읽는다 (빌드 없이 반영된다)
        // Shift+F5  조절 창을 열고 닫는다
        case VK_F5:
            // 키를 누르고 있으면 WM_KEYDOWN 이 되풀이 들어온다.
            // 여는 것은 한 번만 — 안 그러면 열렸다 닫혔다 하다 끝난다
            if (lp & (1 << 30)) break;
            if (GetKeyState(VK_SHIFT) & 0x8000) {
                PanelToggle();
            } else if (BuildShaders(g_hwnd)) {
                SetWindowTextW(g_hwnd, L"kjcEngine   |   셰이더를 다시 읽었습니다");
            }
            break;
        case VK_OEM_6:  Zoom(1.0f / ZOOM_STEP);    break;   // ]  확대
        case VK_OEM_4:  Zoom(ZOOM_STEP);           break;   // [  축소
        // 노말맵 채널을 하나씩 뒤집는다. 지금 상태는 창 제목에 나온다
        case 'X': g_nFlip.x = -g_nFlip.x; UpdateTitle(); break;
        case 'Y': g_nFlip.y = -g_nFlip.y; UpdateTitle(); break;
        case 'Z': g_nFlip.z = -g_nFlip.z; UpdateTitle(); break;

        // 켜고 끄는 것은 숫자 키다. WASD 를 화면 옮기기에 내주었다
        case '1': g_skin  = (g_skin  > 0.5f)  ? 0.0f : 1.0f; UpdateTitle(); break;
        case '2': g_micTo = (g_micTo > 0.5f)  ? 0.0f : 1.0f; UpdateTitle(); break;
        case '3': g_aoOn  = (g_aoOn  > 0.5f)  ? 0.0f : 1.0f; UpdateTitle(); break;
        case '4': g_cav   = (g_cav   > 0.05f) ? 0.0f : 2.5f; UpdateTitle(); break;
        case '5': g_rim   = (g_rim   > 0.05f) ? 0.0f : 0.7f; UpdateTitle(); break;
        case '6': g_vao   = (g_vao   > 0.05f) ? 0.0f : 1.0f; UpdateTitle(); break;
        case '7': g_sssOn = (g_sssOn > 0.5f)  ? 0.0f : 1.0f; UpdateTitle(); break;
        case '8': g_fogOn = (g_fogOn > 0.5f)  ? 0.0f : 1.0f; UpdateTitle(); break;
        // 어두워지기 시작하는 곳과 다 어두워지는 곳
        case 'U': g_fogFar = max(g_fogNear + 0.05f, g_fogFar - 0.05f); UpdateTitle(); break;
        case 'I': g_fogFar = min(3.0f, g_fogFar + 0.05f); UpdateTitle(); break;
        // 번지는 폭. 넓히면 살이 두꺼워 보이고, 좁히면 표면에 가까워진다
        case 'J': g_sssWidth = max(0.0002f, g_sssWidth - 0.0005f); UpdateTitle(); break;
        case 'L': g_sssWidth = min(0.0200f, g_sssWidth + 0.0005f); UpdateTitle(); break;
        // 그림자 기록장이 덮는 범위. 좁힐수록 텍셀이 촘촘해져 작은 그림자가
        // 살아나지만, 그 밖은 그림자를 아예 못 받는다
        case '9': SHADOW_RANGE = max(0.3f,  SHADOW_RANGE - 0.2f);
                  BuildLightMatrix(); UpdateTitle(); break;
        case '0': SHADOW_RANGE = min(8.0f,  SHADOW_RANGE + 0.2f);
                  BuildLightMatrix(); UpdateTitle(); break;

        // WASD 로 화면을 옮긴다. 걸음 폭을 거리에 비례시켜서
        // 가까이 붙었을 때는 잘게, 멀리서는 큼직하게 움직인다
        case 'W': g_lookY += g_dist * 0.05f; break;
        case 'S': g_lookY -= g_dist * 0.05f; break;
        case 'A': { float st = g_dist * 0.05f;
                    g_lookX +=  cosf(g_yaw) * st;
                    g_lookZ += -sinf(g_yaw) * st; } break;
        case 'D': { float st = g_dist * 0.05f;
                    g_lookX += -cosf(g_yaw) * st;
                    g_lookZ +=  sinf(g_yaw) * st; } break;
        // 가운데로 되돌린다 — 옮기다 물체를 놓쳤을 때 쓴다
        case 'F': g_lookX = 0.0f; g_lookZ = 0.0f; g_lookY = 0.26f; break;
        // 지금 보고 있는 자리와 태양을 담아 둔다. 다음에 켜면 이대로 시작한다
        case 'K': SaveView(); SetWindowTextW(g_hwnd, L"kjcEngine   |   지금 자리를 담았습니다"); break;

        // 버텍스 AO — 진하기는 즉시, 넓이는 값만 바꾸고 B 로 굽는다
        case 'G': g_vao  = max(0.0f, g_vao - 0.1f);  UpdateTitle(); break;
        case 'H': g_vao  = min(2.0f, g_vao + 0.1f);  UpdateTitle(); break;
        case VK_OEM_COMMA:  g_vaoR = max(0.02f, g_vaoR - 0.02f); UpdateTitle(); break;
        case VK_OEM_PERIOD: g_vaoR = min(1.00f, g_vaoR + 0.02f); UpdateTitle(); break;
        case 'B': {
            // 굽는 동안 화면이 멈춘다. 무엇을 하고 있는지 제목에 알린다
            SetWindowTextW(g_hwnd, L"kjcEngine   |   버텍스 AO 굽는 중...");
            RebakeAO(g_ctx, g_head, g_vaoR);
            UpdateTitle();
        } break;
        // 태양 돌리기. 누르고 있으면 저절로 되풀이된다
        // ← → 는 모델을 돌린다. 태양 좌우는 조절 창의 Sun · Yaw 로 옮겼다
        case VK_LEFT:  g_facing -= TURN_STEP; break;
        case VK_RIGHT: g_facing += TURN_STEP; break;
        case VK_UP:    g_sunPitch = min(1.50f, g_sunPitch + 0.04f); UpdateSun(); UpdateTitle(); break;
        case VK_DOWN:  g_sunPitch = max(0.08f, g_sunPitch - 0.04f); UpdateSun(); UpdateTitle(); break;
        case VK_OEM_1:     g_aoRadius = max(0.02f, g_aoRadius - 0.02f); UpdateTitle(); break;
        case VK_OEM_7:     g_aoRadius = min(2.00f, g_aoRadius + 0.02f); UpdateTitle(); break;
        case VK_OEM_MINUS: g_aoPower  = max(0.00f, g_aoPower  - 0.10f); UpdateTitle(); break;
        case VK_OEM_PLUS:  g_aoPower  = min(3.00f, g_aoPower  + 0.10f); UpdateTitle(); break;
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
    // 화면 자체는 한 겹이다. 그림은 따로 둔 4배 다중표본 판에 그리고,
    // 번짐을 먹인 뒤 마지막에 풀어서 이리로 넘긴다
    sd.SampleDesc.Count  = 1;
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
    rtvd.ViewDimension = D3D11_RTV_DIMENSION_TEXTURE2D;
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

    // ── SSAO 가 쓰는 판들 ──
    // 화면과 같은 크기로 두되 다중표본은 쓰지 않는다. 가림을 어림잡는 데는
    // 한 겹이면 넉넉하고, 표본이 여럿이면 셰이더에서 읽기가 번거로워진다
    auto makeRT = [&](DXGI_FORMAT fmt, ID3D11RenderTargetView** rtv,
                      ID3D11ShaderResourceView** srv) {
        D3D11_TEXTURE2D_DESC rt = {};
        rt.Width            = WIN_W;
        rt.Height           = WIN_H;
        rt.MipLevels        = 1;
        rt.ArraySize        = 1;
        rt.Format           = fmt;
        rt.SampleDesc.Count = 1;
        rt.Usage            = D3D11_USAGE_DEFAULT;
        rt.BindFlags        = D3D11_BIND_RENDER_TARGET | D3D11_BIND_SHADER_RESOURCE;
        ID3D11Texture2D* t = nullptr;
        g_dev->CreateTexture2D(&rt, nullptr, &t);
        g_dev->CreateRenderTargetView(t, nullptr, rtv);
        g_dev->CreateShaderResourceView(t, nullptr, srv);
        t->Release();
    };
    // 자리와 법선은 소수점이 필요하고, 가림 정도는 0~1 한 칸이면 된다
    makeRT(DXGI_FORMAT_R16G16B16A16_FLOAT, &g_posRTV,    &g_posSRV);
    makeRT(DXGI_FORMAT_R16G16B16A16_FLOAT, &g_nrmRTV,    &g_nrmSRV);
    makeRT(DXGI_FORMAT_R8_UNORM,           &g_aoRTV,     &g_aoSRV);
    makeRT(DXGI_FORMAT_R8_UNORM,           &g_aoBlurRTV, &g_aoBlurSRV);

    D3D11_TEXTURE2D_DESC gd = {};
    gd.Width            = WIN_W;
    gd.Height           = WIN_H;
    gd.MipLevels        = 1;
    gd.ArraySize        = 1;
    gd.Format           = DXGI_FORMAT_D32_FLOAT;
    gd.SampleDesc.Count = 1;
    gd.Usage            = D3D11_USAGE_DEFAULT;
    gd.BindFlags        = D3D11_BIND_DEPTH_STENCIL;
    ID3D11Texture2D* gdt = nullptr;
    g_dev->CreateTexture2D(&gd, nullptr, &gdt);
    g_dev->CreateDepthStencilView(gdt, nullptr, &g_gbufDSV);
    gdt->Release();

    // 뭉개지 않고 그 자리 값을 그대로 읽는 표본기. 깊이와 법선을 섞으면
    // 없는 면이 생겨 가림이 엉뚱하게 계산된다
    D3D11_SAMPLER_DESC ps = {};
    ps.Filter   = D3D11_FILTER_MIN_MAG_MIP_POINT;
    ps.AddressU = ps.AddressV = ps.AddressW = D3D11_TEXTURE_ADDRESS_CLAMP;
    ps.MaxLOD   = D3D11_FLOAT32_MAX;
    g_dev->CreateSamplerState(&ps, &g_pointSmp);

    // ── 피부 번짐이 쓰는 판들 ──
    // 그림을 화면에 바로 그리지 않고 여기 담는다. 톤매핑 전 값이라
    // 소수점 형식이어야 한다 — 8비트로는 밝은 쪽이 잘려 번짐이 틀어진다
    auto makeMS = [&](ID3D11Texture2D** tex, ID3D11RenderTargetView** rtv) {
        D3D11_TEXTURE2D_DESC td = {};
        td.Width            = WIN_W;
        td.Height           = WIN_H;
        td.MipLevels        = 1;
        td.ArraySize        = 1;
        td.Format           = DXGI_FORMAT_R16G16B16A16_FLOAT;
        td.SampleDesc.Count = 4;              // 화면과 달리 여기는 네 겹이다
        td.Usage            = D3D11_USAGE_DEFAULT;
        td.BindFlags        = D3D11_BIND_RENDER_TARGET;
        g_dev->CreateTexture2D(&td, nullptr, tex);
        g_dev->CreateRenderTargetView(*tex, nullptr, rtv);
    };
    makeMS(&g_sceneMS, &g_sceneRTV);
    makeMS(&g_diffMS,  &g_diffRTV);

    // 네 겹을 한 겹으로 푼 것. 셰이더가 읽으려면 이 형태여야 한다
    auto makeRes = [&](ID3D11Texture2D** tex, ID3D11ShaderResourceView** srv) {
        D3D11_TEXTURE2D_DESC td = {};
        td.Width            = WIN_W;
        td.Height           = WIN_H;
        td.MipLevels        = 1;
        td.ArraySize        = 1;
        td.Format           = DXGI_FORMAT_R16G16B16A16_FLOAT;
        td.SampleDesc.Count = 1;
        td.Usage            = D3D11_USAGE_DEFAULT;
        td.BindFlags        = D3D11_BIND_SHADER_RESOURCE;
        g_dev->CreateTexture2D(&td, nullptr, tex);
        g_dev->CreateShaderResourceView(*tex, nullptr, srv);
    };
    makeRes(&g_sceneRes, &g_sceneSRV);
    makeRes(&g_diffRes,  &g_diffSRV);

    // 가로로 한 번, 세로로 한 번 흐릴 자리
    makeRT(DXGI_FORMAT_R16G16B16A16_FLOAT, &g_blurRTV[0], &g_blurSRV[0]);
    makeRT(DXGI_FORMAT_R16G16B16A16_FLOAT, &g_blurRTV[1], &g_blurSRV[1]);

    // 그림자를 그릴 때만 깊이를 살짝 밀어낸다. 이게 없으면 평평한 면이
    // 자기 자신을 가려서 줄무늬(섀도 애크니)가 생긴다
    D3D11_RASTERIZER_DESC rd = {};
    rd.FillMode              = D3D11_FILL_SOLID;
    rd.CullMode              = D3D11_CULL_BACK;
    rd.DepthClipEnable       = TRUE;
    g_dev->CreateRasterizerState(&rd, &g_rsNormal);
    // 여유값도 함께 줄인다. 크게 두면 경사가 급한 곳(콧구멍 안쪽)에서 특히
    // 많이 밀려나 그림자가 면에서 떨어진다
    rd.DepthBias             = 700;
    rd.SlopeScaledDepthBias  = 1.5f;
    rd.DepthBiasClamp        = 0.0f;
    g_dev->CreateRasterizerState(&rd, &g_rsShadow);

    // ── 셰이더 ──
    if (!BuildShaders(hwnd)) return 1;

    D3D11_DEPTH_STENCIL_DESC nod = {};
    nod.DepthEnable = FALSE;
    g_dev->CreateDepthStencilState(&nod, &g_dsNoDepth);

    // ── 정점 · 인덱스 · 상수 버퍼 ──
    Vertex plateV[6];
    BuildPlate(plateV);
    Vertex axisV[6];
    BuildAxes(axisV);
    Vertex labelV[42];
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
    char meshPath[640];
    auto meshAt = [&](const char* file) -> const char* {
        lstrcpyA(meshPath, MESH_DIR); lstrcatA(meshPath, file); return meshPath;
    };

    // 얼굴을 먼저 읽어 정렬을 정하고, 나머지가 그것을 그대로 쓴다
    Align align;
    g_head.aoRadius = g_vaoR;   // 처음 구울 때도 같은 값으로
    if (!LoadFBX(g_dev, meshAt(MODEL_FILE), MODEL_H, g_head,
                 loadErr, sizeof(loadErr), true, &align)) {
        Fail(hwnd, loadErr);
        return 1;
    }

    // 얹는 메시들. 버텍스 AO 는 굽지 않는다 — 털은 정점이 열 배가 넘는데
    // 가닥 사이가 다 뚫려 있어 구워도 거의 1 로 나온다
    for (Extra& e : g_extra) {
        char why[512] = {};
        if (!LoadFBX(g_dev, meshAt(e.file), MODEL_H, e.model,
                     why, sizeof(why), false, &align))
            e.model.indexCount = 0;   // 없으면 그냥 안 그린다
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
    if (!loadTex(TEX_SCAT,   false, g_scatter))return 1;   // 산란 세기, 숫자
    if (!loadTex(TEX_MICRO,  false, g_micro))  return 1;   // 노말이라 숫자
    if (!loadTex(TEX_MASK,   false, g_mask))   return 1;   // 마스크, 숫자
    // 눈알. 없으면 회색으로 그려지므로 실패해도 멈추지 않는다
    loadTex(EYE_ALBEDO, true,  g_eyeAlbedo);
    loadTex(EYE_NORMAL, false, g_eyeNormal);
    loadTex(EYE_SPEC,   true,  g_eyeSpec);
    loadTex(HAIR_ALBEDO, true,  g_hairAlbedo);
    loadTex(HAIR_NORMAL, false, g_hairNormal);
    loadTex(HAIR_SPEC,   true,  g_hairSpec);

    // ── 환경맵 ──
    // 굽는 데 몇 초 걸린다. 실패해도 멈추지는 않는다 — 하늘빛·땅빛 두 색으로
    // 물러서면 화면은 나오기 때문이다
    {
        char hp[512];
        lstrcpyA(hp, HDRI_DIR);
        lstrcatA(hp, HDRI[g_envIdx]);
        if (!LoadEnvironment(g_dev, hp, g_env, loadErr, sizeof(loadErr))) {
            g_envOn = 0.0f;
            FILE* lf = nullptr;
            if (fopen_s(&lf, "kjcEngine-error.txt", "w") == 0 && lf) {
                fputs(loadErr, lf);
                fclose(lf);
            }
        }
    }

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
    // ── 셰이더 조절 창 (Shift+F5) ──
    // 담아 둔 값이 있으면 그것으로 시작하고, 없으면 지금 값을 그대로 보여준다
    SettingsFromEngine();
    LoadSettings();
    SettingsFromEngine();
    PanelHost panelHost = { ApplySettings, SaveSettings, RebakeNow };
    PanelCreate(hInst, hwnd, panelHost, g_set);

    LoadView();          // 담아 둔 자리가 있으면 그대로 시작한다
    UpdateView();
    UpdateSun();
    g_proj = XMMatrixPerspectiveFovLH(XM_PIDIV4, (float)WIN_W / WIN_H, 0.1f, 200.0f);

    D3D11_VIEWPORT viewMain   = { 0, 0, (float)WIN_W, (float)WIN_H, 0.0f, 1.0f };
    D3D11_VIEWPORT viewShadow = { 0, 0, (float)SHADOW_SIZE, (float)SHADOW_SIZE, 0.0f, 1.0f };
    D3D11_VIEWPORT viewGizmo  = { (float)(WIN_W - GIZMO_PX - GIZMO_PAD), (float)GIZMO_PAD,
                                  (float)GIZMO_PX, (float)GIZMO_PX, 0.0f, 1.0f };
    D3D11_VIEWPORT viewStat   = { (float)GIZMO_PAD, (float)GIZMO_PAD,
                                  230.0f, 80.0f, 0.0f, 1.0f };

    ShowWindow(hwnd, SW_SHOW);
    PanelToggle();              // 조절 창도 함께 띄운다. Shift+F5 로 껐다 켠다
    SetForegroundWindow(hwnd);  // 키는 그리는 창이 받아야 한다

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

        // 모델이 걸어다니므로 기록장이 담는 자리도 따라 옮긴다.
        // 한 번만 잡아 두면 모델이 그 범위를 나가는 순간 그림자가 끊긴다
        BuildLightMatrix();

        // ── 1패스 — 태양 자리에서 깊이만 기록한다 ──
        // 지난 프레임에 읽던 것을 떼어낸다. 같은 그림을 쓰면서 동시에
        // 그릴 수는 없어서, 안 떼면 이번 기록이 통째로 무시된다
        ID3D11ShaderResourceView* none[11] = {};
        g_ctx->PSSetShaderResources(0, 11, none);

        g_ctx->OMSetRenderTargets(0, nullptr, g_shadowDSV);
        g_ctx->ClearDepthStencilView(g_shadowDSV, D3D11_CLEAR_DEPTH, 1.0f, 0);
        g_ctx->RSSetViewports(1, &viewShadow);
        g_ctx->RSSetState(g_rsShadow);
        g_ctx->VSSetShader(g_vsDepth, nullptr, 0);
        g_ctx->PSSetShader(nullptr, nullptr, 0);      // 색은 안 쓴다
        DrawScene(true);

        // ── 2~4패스 — SSAO ──
        // 켜져 있을 때만 돈다. 꺼 두면 세 패스를 통째로 건너뛴다
        if (g_aoOn > 0.5f) {
            // 2패스 — 깊이와 법선을 카메라 시점 기준으로 따로 그린다
            ID3D11RenderTargetView* gbuf[2] = { g_posRTV, g_nrmRTV };
            const float zero4[4] = { 0.0f, 0.0f, 0.0f, 0.0f };
            g_ctx->OMSetRenderTargets(2, gbuf, g_gbufDSV);
            g_ctx->ClearRenderTargetView(g_posRTV, zero4);
            g_ctx->ClearRenderTargetView(g_nrmRTV, zero4);
            g_ctx->ClearDepthStencilView(g_gbufDSV, D3D11_CLEAR_DEPTH, 1.0f, 0);
            g_ctx->RSSetViewports(1, &viewMain);
            g_ctx->RSSetState(g_rsNormal);
            g_ctx->VSSetShader(g_vsGBuf, nullptr, 0);
            g_ctx->PSSetShader(g_psGBuf, nullptr, 0);
            g_wantAxes = false;          // 선이라 그 둘레가 괜히 어두워진다
            DrawScene(false);
            g_wantAxes = true;

            // 3패스 — 픽셀마다 둘레를 찔러 보고 막힌 비율을 센다
            ID3D11ShaderResourceView* nul = nullptr;
            g_ctx->OMSetRenderTargets(1, &g_aoRTV, nullptr);
            g_ctx->PSSetShaderResources(8, 1, &g_posSRV);
            g_ctx->PSSetShaderResources(9, 1, &g_nrmSRV);
            g_ctx->PSSetSamplers(2, 1, &g_pointSmp);
            g_ctx->IASetInputLayout(nullptr);       // 정점 버퍼 없이 번호로 그린다
            g_ctx->IASetPrimitiveTopology(D3D11_PRIMITIVE_TOPOLOGY_TRIANGLELIST);
            g_ctx->VSSetShader(g_vsFull, nullptr, 0);
            g_ctx->PSSetShader(g_psSSAO, nullptr, 0);
            g_ctx->Draw(3, 0);

            // 4패스 — 흐리게. 몇 군데만 찔러 본 값이라 그대로 두면 지글거린다
            g_ctx->OMSetRenderTargets(1, &g_aoBlurRTV, nullptr);
            g_ctx->PSSetShaderResources(8, 1, &nul);   // 읽던 것을 떼어낸다
            g_ctx->PSSetShaderResources(9, 1, &nul);
            g_ctx->PSSetShaderResources(10, 1, &g_aoSRV);
            g_ctx->PSSetShader(g_psBlur, nullptr, 0);
            g_ctx->Draw(3, 0);

            g_ctx->PSSetShaderResources(10, 1, &nul);
            g_ctx->IASetInputLayout(g_layout);         // 본 렌더용으로 되돌린다
        }

        // ── 5패스 — 화면에 그리면서 그늘을 판정한다 ──
        // 바탕도 함께 밝아져야 화면 전체가 번쩍인 것으로 보인다.
        // 물체만 밝히면 어두운 바탕이 그대로라 어색하다
        const float bg[4] = { BG[0] + (1.0f - BG[0]) * g_glow,
                              BG[1] + (1.0f - BG[1]) * g_glow,
                              BG[2] + (1.0f - BG[2]) * g_glow, 1.0f };
        // 화면이 아니라 별도 판 둘에 그린다. 하나는 색 전부, 하나는 확산만.
        // 번지게 할 것이 확산뿐이라 갈라 두어야 한다
        ID3D11RenderTargetView* sceneRTs[2] = { g_sceneRTV, g_diffRTV };
        const float zeroRT[4] = { 0.0f, 0.0f, 0.0f, 0.0f };
        g_ctx->OMSetRenderTargets(2, sceneRTs, g_dsv);
        g_ctx->ClearRenderTargetView(g_diffRTV, zeroRT);
        g_ctx->ClearDepthStencilView(g_dsv, D3D11_CLEAR_DEPTH, 1.0f, 0);
        g_ctx->RSSetViewports(1, &viewMain);

        if (g_envOn > 0.5f && g_env.skySRV) {
            // 환경을 배경으로 깐다. 화면을 다 덮으므로 색을 따로 지우지 않는다.
            // DrawOne 을 거치지 않으니 상수 버퍼를 여기서 채워야 한다
            CB sky = {};
            sky.envParam = XMFLOAT4(g_envPow, (float)g_env.specMips, g_envOn, 0.0f);
            sky.invVP    = XMMatrixTranspose(
                XMMatrixInverse(nullptr, XMMatrixMultiply(g_view, g_proj)));
            // 빠뜨리면 노출이 0 이 되어 배경이 새까맣게 된다
            sky.toneParam = XMFLOAT4(g_expo, g_sunI, g_bgPow, g_specOn);
            g_ctx->UpdateSubresource(g_cb, 0, nullptr, &sky, 0, 0);

            g_ctx->OMSetDepthStencilState(g_dsNoDepth, 0);
            g_ctx->PSSetShaderResources(11, 1, &g_env.skySRV);
            g_ctx->PSSetSamplers(1, 1, &g_texSmp);
            g_ctx->IASetInputLayout(nullptr);
            g_ctx->IASetPrimitiveTopology(D3D11_PRIMITIVE_TOPOLOGY_TRIANGLELIST);
            g_ctx->VSSetShader(g_vsFull, nullptr, 0);
            g_ctx->PSSetShader(g_psSky, nullptr, 0);
            g_ctx->Draw(3, 0);
            g_ctx->OMSetDepthStencilState(nullptr, 0);
            g_ctx->IASetInputLayout(g_layout);
        } else {
            g_ctx->ClearRenderTargetView(g_sceneRTV, bg);
        }
        g_ctx->RSSetState(g_rsNormal);
        g_ctx->VSSetShader(g_vs, nullptr, 0);
        g_ctx->PSSetShader(g_ps, nullptr, 0);
        ID3D11ShaderResourceView* srvs[8] = { g_shadowSRV, g_albedo.srv, g_normal.srv,
                                             g_rough.srv, g_spec.srv, g_scatter.srv,
                                             g_micro.srv, g_mask.srv };
        ID3D11SamplerState*       smps[2] = { g_shadowSmp, g_texSmp };
        g_ctx->PSSetShaderResources(0, 8, srvs);
        g_ctx->PSSetShaderResources(10, 1, &g_aoBlurSRV);   // 흐려 둔 가림 정도
        if (g_env.skySRV) {
            ID3D11ShaderResourceView* envs[3] = { g_env.skySRV, g_env.irrSRV, g_env.specSRV };
            g_ctx->PSSetShaderResources(11, 3, envs);
        }
        g_ctx->PSSetSamplers(0, 2, smps);
        g_ctx->PSSetSamplers(2, 1, &g_pointSmp);
        DrawScene(false);

        // ── 6패스 — 오른쪽 위 방향 표시기 ──
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

        // ── 7패스 — 화면 왼쪽 위 상태 표시 ──
        // 정면에서 곧게 본다. 돌아가면 글자가 눕는다
        g_ctx->RSSetViewports(1, &viewStat);
        XMMATRIX sv = XMMatrixLookAtLH(XMVectorSet(0.0f, 0.0f, -2.0f, 0.0f),
                                       XMVectorSet(0.0f, 0.0f,  0.0f, 0.0f),
                                       XMVectorSet(0.0f, 1.0f,  0.0f, 0.0f));
        XMMATRIX spj = XMMatrixOrthographicLH(4.2f, 1.5f, 0.1f, 10.0f);   // 화면 위 표시 — 미터와 무관
        DrawStatus(sv * spj);

        // ── 8패스 — 네 겹을 한 겹으로 푼다 ──
        // 다중표본 판은 셰이더가 그대로 읽지 못한다
        ID3D11ShaderResourceView* nulSSS[3] = {};
        g_ctx->PSSetShaderResources(14, 3, nulSSS);
        g_ctx->OMSetRenderTargets(0, nullptr, nullptr);
        g_ctx->ResolveSubresource(g_sceneRes, 0, g_sceneMS, 0,
                                  DXGI_FORMAT_R16G16B16A16_FLOAT);
        g_ctx->ResolveSubresource(g_diffRes, 0, g_diffMS, 0,
                                  DXGI_FORMAT_R16G16B16A16_FLOAT);

        // ── 9·10패스 — 확산을 가로로 한 번, 세로로 한 번 번지게 한다 ──
        g_ctx->RSSetViewports(1, &viewMain);
        g_ctx->IASetInputLayout(nullptr);
        g_ctx->IASetPrimitiveTopology(D3D11_PRIMITIVE_TOPOLOGY_TRIANGLELIST);
        g_ctx->VSSetShader(g_vsFull, nullptr, 0);
        g_ctx->PSSetShader(g_psSSSBlur, nullptr, 0);
        g_ctx->PSSetSamplers(2, 1, &g_pointSmp);

        auto blurPass = [&](ID3D11RenderTargetView* rt,
                            ID3D11ShaderResourceView* src, float dx, float dy) {
            ID3D11ShaderResourceView* nul = nullptr;
            g_ctx->PSSetShaderResources(15, 1, &nul);   // 읽던 것을 떼어낸다
            g_ctx->OMSetRenderTargets(1, &rt, nullptr);
            CB cb = {};
            // 실제 길이를 화면 비율로 바꾼다.
            // 카메라 거리에서 화면 한 폭이 담는 실제 넓이로 나누면 된다
            // g_dist 는 카메라가 도는 반지름이지 모델까지의 거리가 아니다.
            // 모델이 옆으로 걸어가면 실제로는 더 먼데 그대로 쓰면
            // 화면에서 작아진 얼굴에 같은 폭을 발라 번짐이 과해진다
            float ex = g_camPos.x - g_x;
            float ey = g_camPos.y - MODEL_LIFT;
            float ez = g_camPos.z - g_z;
            float toModel = sqrtf(ex * ex + ey * ey + ez * ez);
            float viewM = 2.0f * max(toModel, 0.05f) * tanf(XM_PIDIV4 * 0.5f);
            float uvW   = g_sssWidth / max(viewM, 1e-4f);
            cb.sssParam = XMFLOAT4(uvW, g_sssOn, dx, dy);
            g_ctx->UpdateSubresource(g_cb, 0, nullptr, &cb, 0, 0);
            g_ctx->PSSetShaderResources(15, 1, &src);
            g_ctx->Draw(3, 0);
        };
        blurPass(g_blurRTV[0], g_diffSRV,     1.0f, 0.0f);   // 가로
        blurPass(g_blurRTV[1], g_blurSRV[0],  0.0f, 1.0f);   // 세로

        // ── 11패스 — 다시 합쳐 화면에 낸다 ──
        // 원래 확산을 빼고 번진 확산을 넣는다. 반사는 건드리지 않아
        // 하이라이트가 그대로 살아 있다. 톤매핑도 여기서 한 번에 한다
        ID3D11ShaderResourceView* nul1 = nullptr;
        g_ctx->PSSetShaderResources(15, 1, &nul1);
        g_ctx->OMSetRenderTargets(1, &g_rtv, nullptr);
        CB fin = {};
        fin.sssParam  = XMFLOAT4(g_sssWidth, g_sssOn, 0.0f, 0.0f);
        fin.toneParam = XMFLOAT4(g_expo, g_sunI, g_bgPow, g_specOn);
        g_ctx->UpdateSubresource(g_cb, 0, nullptr, &fin, 0, 0);
        ID3D11ShaderResourceView* comb[3] = { g_sceneSRV, g_diffSRV, g_blurSRV[1] };
        g_ctx->PSSetShaderResources(14, 3, comb);
        g_ctx->PSSetShader(g_psCombine, nullptr, 0);
        g_ctx->Draw(3, 0);
        g_ctx->PSSetShaderResources(14, 3, nulSSS);
        g_ctx->IASetInputLayout(g_layout);

        g_swap->Present(1, 0);
    }

    // ── 정리 ──
    g_env.Release();
    for (int i = 0; i < 2; ++i) {
        if (g_blurSRV[i]) g_blurSRV[i]->Release();
        if (g_blurRTV[i]) g_blurRTV[i]->Release();
    }
    if (g_diffSRV)   g_diffSRV->Release();
    if (g_sceneSRV)  g_sceneSRV->Release();
    if (g_diffRes)   g_diffRes->Release();
    if (g_sceneRes)  g_sceneRes->Release();
    if (g_diffRTV)   g_diffRTV->Release();
    if (g_sceneRTV)  g_sceneRTV->Release();
    if (g_diffMS)    g_diffMS->Release();
    if (g_sceneMS)   g_sceneMS->Release();
    if (g_dsNoDepth) g_dsNoDepth->Release();
    if (g_pointSmp)  g_pointSmp->Release();
    if (g_aoBlurSRV) g_aoBlurSRV->Release();
    if (g_aoBlurRTV) g_aoBlurRTV->Release();
    if (g_aoSRV)     g_aoSRV->Release();
    if (g_aoRTV)     g_aoRTV->Release();
    if (g_gbufDSV)   g_gbufDSV->Release();
    if (g_nrmSRV)    g_nrmSRV->Release();
    if (g_nrmRTV)    g_nrmRTV->Release();
    if (g_posSRV)    g_posSRV->Release();
    if (g_posRTV)    g_posRTV->Release();
    if (g_rsNormal)  g_rsNormal->Release();
    if (g_rsShadow)  g_rsShadow->Release();
    if (g_shadowSmp) g_shadowSmp->Release();
    if (g_shadowSRV) g_shadowSRV->Release();
    if (g_shadowDSV) g_shadowDSV->Release();
    PanelDestroy();
    if (g_triVB)     g_triVB->Release();
    if (g_labelVB)   g_labelVB->Release();
    if (g_axisVB)    g_axisVB->Release();
    if (g_plateVB)   g_plateVB->Release();
    g_head.Release();
    for (Extra& e : g_extra) e.model.Release();
    g_albedo.Release();
    g_normal.Release();
    g_rough.Release();
    g_spec.Release();
    g_scatter.Release();
    g_micro.Release();
    g_mask.Release();
    g_eyeAlbedo.Release(); g_eyeNormal.Release(); g_eyeSpec.Release();
    g_hairAlbedo.Release(); g_hairNormal.Release(); g_hairSpec.Release();
    if (g_texSmp) g_texSmp->Release();
    if (g_cb)        g_cb->Release();
    // 셰이더와 입력 레이아웃은 BuildShaders 가 만든 것이라 함께 놓는다
    ID3D11DeviceChild* sh[] = { g_vs, g_vsDepth, g_ps, g_vsGBuf, g_psGBuf,
                                g_vsFull, g_psSSAO, g_psBlur, g_psSky,
                                g_psSSSBlur, g_psCombine, g_layout };
    for (ID3D11DeviceChild* o : sh) if (o) o->Release();
    if (g_dsv)       g_dsv->Release();
    if (g_rtv)       g_rtv->Release();
    if (g_swap)      g_swap->Release();
    if (g_ctx)       g_ctx->Release();
    if (g_dev)       g_dev->Release();
    return 0;
}
