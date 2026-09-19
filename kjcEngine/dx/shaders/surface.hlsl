// 이 파일은 kjcEngine 이 시작할 때 읽어 컴파일한다.
// 고치고 F5 를 누르면 다시 읽으므로, 빌드하지 않고 화면으로 확인할 수 있다.

#include "common.hlsl"

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

// 세로 성분은 곱한다 (whiteout 방식)
float3 CombineNormals(float3 big, float3 fine) {
    return normalize(float3(big.xy + fine.xy, big.z * fine.z));
}

// 미세 결을 몇 배로 촘촘히 깔 것인가. 창에서 바꾸므로 상수 버퍼로 온다

// 반사에서 프레넬과 가림을 한꺼번에 어림잡는다.
// 보통은 2차원 표를 구워 쓰는데, 이 식이 그것을 거의 그대로 흉내 낸다
float3 EnvBRDFApprox(float3 f0, float rough, float NoV) {
    const float4 c0 = float4(-1.0, -0.0275, -0.572,  0.022);
    const float4 c1 = float4( 1.0,  0.0425,  1.040, -0.040);
    float4 r = rough * c0 + c1;
    float a004 = min(r.x * r.x, exp2(-9.28 * NoV)) * r.x + r.y;
    float2 AB  = float2(-1.04, 1.04) * a004 + r.zw;
    return f0 * AB.x + AB.y;
}

