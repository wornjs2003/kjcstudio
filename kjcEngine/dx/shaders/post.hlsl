// 이 파일은 kjcEngine 이 시작할 때 읽어 컴파일한다.
// 고치고 F5 를 누르면 다시 읽으므로, 빌드하지 않고 화면으로 확인할 수 있다.

#include "surface.hlsl"


FullOut VS_Full(uint id : SV_VertexID) {
    FullOut o;
    o.uv  = float2((id << 1) & 2, id & 2);
    o.pos = float4(o.uv * float2(2.0, -2.0) + float2(-1.0, 1.0), 0.0, 1.0);
    return o;
}

// 픽셀마다 커널을 조금씩 돌려 쓴다. 안 돌리면 같은 무늬가 화면에 깔린다
float Hash(float2 p) {
    return frac(sin(dot(p, float2(127.1, 311.7))) * 43758.5453);
}

// 반구 안에 흩어 둔 표본 방향. 가까운 쪽을 촘촘히 잡아 가까운 가림이
// 더 세게 먹게 한다
static const int SSAO_N = 16;
static const float3 KERNEL[SSAO_N] = {
    float3( 0.538,  0.191,  0.462), float3(-0.278,  0.433,  0.208),
    float3( 0.116, -0.548,  0.331), float3(-0.462, -0.157,  0.671),
    float3( 0.724,  0.310,  0.118), float3(-0.115,  0.712,  0.386),
    float3( 0.293, -0.246,  0.845), float3(-0.634,  0.318,  0.402),
    float3( 0.052,  0.107,  0.238), float3(-0.183, -0.092,  0.161),
    float3( 0.216,  0.174,  0.093), float3(-0.079,  0.245,  0.297),
    float3( 0.402, -0.486,  0.527), float3(-0.551, -0.372,  0.288),
    float3( 0.148,  0.639,  0.611), float3(-0.324, -0.601,  0.455),
};

float4 PS_SSAO(FullOut i) : SV_TARGET {
    float3 P = posTex.SampleLevel(pointSmp, i.uv, 0).xyz;
    float3 N = normalize(nrmTex.SampleLevel(pointSmp, i.uv, 0).xyz);

    // 아무것도 안 그려진 자리(배경)는 가림이 없다
    if (P.z <= 0.0001) return 1.0;

    float ang = Hash(i.uv * screen.xy) * 6.2831853;
    float cs = cos(ang), sn = sin(ang);

    float occ = 0.0;
    [unroll]
    for (int k = 0; k < SSAO_N; ++k) {
        float3 s = KERNEL[k];
        s.xy = float2(s.x * cs - s.y * sn, s.x * sn + s.y * cs);   // 돌린다
        if (dot(s, N) < 0.0) s = -s;                               // 면 바깥쪽으로

        float3 sp = P + s * ssaoParam.x;

        // 그 자리를 화면으로 되돌려 실제로 무엇이 그려져 있는지 본다
        float4 clip = mul(float4(sp, 1.0), proj);
        if (clip.w <= 0.0) continue;
        float2 suv = clip.xy / clip.w * float2(0.5, -0.5) + 0.5;
        if (suv.x < 0.0 || suv.x > 1.0 || suv.y < 0.0 || suv.y > 1.0) continue;

        float sz = posTex.SampleLevel(pointSmp, suv, 0).z;
        if (sz <= 0.0001) continue;

        // 거기 있는 것이 표본보다 앞이면 가려진 것이다.
        // 다만 너무 멀리 있는 것에 가려지는 것으로 치면 그림자처럼 번져서,
        // 반경 밖은 세기를 떨어뜨린다
        float range = saturate(ssaoParam.x / max(abs(P.z - sz), 1e-4));
        occ += (sz < sp.z - ssaoParam.z ? 1.0 : 0.0) * range;
    }

    float ao = 1.0 - (occ / SSAO_N) * ssaoParam.y;
    return saturate(ao);
}

// 배경으로 환경을 그린다. 화면 픽셀에서 바라보는 방향을 되찾아 큐브맵을 읽는다
PSOut PS_Sky(FullOut i) {
    float2 ndc = i.uv * float2(2.0, -2.0) + float2(-1.0, 1.0);
    float4 a = mul(float4(ndc, 0.0, 1.0), invVP);
    float4 b = mul(float4(ndc, 1.0, 1.0), invVP);
    float3 dir = normalize(b.xyz / b.w - a.xyz / a.w);
    PSOut o;
    // 톤매핑은 맨 끝에서 한다
    // 배경은 환경광 세기와 노출에서 떼어 놓았다. 그 둘은 모델을 보려고
    // 만지는 값인데, 따라 움직이면 뒤에 걸어 둔 사진까지 같이 바뀐다.
    // 톤매핑이 노출을 곱하므로 여기서 미리 나눠 상쇄한다
    float3 sky = skyMap.SampleLevel(texSmp, dir, 0).rgb;
    o.color = float4(sky * toneParam.z / max(toneParam.x, 1e-4), 1.0);
    o.diff  = 0.0;   // 배경은 번지지 않는다
    return o;
}

// ─── 피부 번짐 ────────────────────────────────────────────────────────
// 확산만 가로로 한 번, 세로로 한 번 흐린다. 두 번에 나누면 계산이
// 크게 줄어서 「분리 가능(separable)」이라 부른다.
//
// 채널마다 퍼지는 폭이 다르다 — 빨강이 살을 가장 깊이 지나므로
// 넓게 번지고, 그래서 그늘 경계가 붉게 물든다
static const float3 SSS_SIGMA = float3(1.00, 0.38, 0.22);
static const int    SSS_TAPS  = 9;

float4 PS_SSSBlur(FullOut i) : SV_TARGET {
    float2 step = sssParam.zw * sssParam.x;
    float3 sum = 0.0, wsum = 0.0;
    [unroll]
    for (int k = -SSS_TAPS; k <= SSS_TAPS; ++k) {
        float  t = (float)k / SSS_TAPS;
        float3 c = diffTex.SampleLevel(pointSmp, i.uv + step * t, 0).rgb;
        float3 w = exp(-(t * t) / (2.0 * SSS_SIGMA * SSS_SIGMA));
        sum  += c * w;
        wsum += w;
    }
    return float4(sum / max(wsum, 1e-4), 1.0);
}

// 다시 합친다. 원래 확산을 빼고 번진 확산을 넣는다 —
// 반사는 건드리지 않으므로 하이라이트가 그대로 살아 있다
float4 PS_Combine(FullOut i) : SV_TARGET {
    float3 scene = sceneTex.SampleLevel(pointSmp, i.uv, 0).rgb;
    float3 d     = diffTex.SampleLevel(pointSmp, i.uv, 0).rgb;
    float3 b     = blurTex.SampleLevel(pointSmp, i.uv, 0).rgb;
    float3 col   = scene - d + lerp(d, b, sssParam.y);
    return float4(Tonemap(col), 1.0);
}

// ③ 흐리게. 몇 군데만 찔러 본 값이라 그대로 두면 지글거린다
// 가림 값을 문지른다. 가로 한 번, 세로 한 번으로 나눈다 —
// 5x5 를 한 번에 하면 스물다섯 번 읽지만 나누면 열 번이면 같은 결과가 난다.
// 텍스처 크기는 직접 물어본다. 가림은 화면의 절반 크기라 screen 을 쓰면 어긋난다
float4 BlurAxis(float2 uv, float2 dir) {
    float w, h;
    aoTex.GetDimensions(w, h);
    float2 step = dir / float2(w, h);

    float sum = 0.0;
    [unroll]
    for (int k = -2; k <= 2; ++k)
        sum += aoTex.SampleLevel(pointSmp, uv + step * k, 0).r;
    return sum / 5.0;
}

float4 PS_BlurH(FullOut i) : SV_TARGET { return BlurAxis(i.uv, float2(1.0, 0.0)); }
float4 PS_BlurV(FullOut i) : SV_TARGET { return BlurAxis(i.uv, float2(0.0, 1.0)); }

// ─── 오버드로를 색으로 ─────────────────────────────────────────────────
// 몇 번 그려졌는지를 색으로 읽게 한다. 숫자를 보기 전에 어디가 겹쳤는지
// 한눈에 들어와야 해서, 적은 쪽은 차갑고 많은 쪽은 뜨겁게 간다
float4 PS_ShowOver(FullOut i) : SV_Target {
    float n = overTex.SampleLevel(pointSmp, i.uv, 0).r;
    if (n < 0.5) return float4(0.02, 0.02, 0.03, 1.0);    // 아무것도 안 그려진 자리

    float3 c;
    if      (n < 1.5) c = float3(0.10, 0.20, 0.55);   // 1겹 — 낭비 없음
    else if (n < 2.5) c = float3(0.10, 0.45, 0.75);   // 2
    else if (n < 3.5) c = float3(0.15, 0.65, 0.45);   // 3
    else if (n < 5.5) c = float3(0.75, 0.80, 0.20);   // 4~5
    else if (n < 8.5) c = float3(0.95, 0.55, 0.15);   // 6~8
    else              c = float3(0.95, 0.15, 0.15);   // 9겹 이상
    return float4(c, 1.0);
}
