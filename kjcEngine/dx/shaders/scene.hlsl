// 이 파일은 kjcEngine 이 시작할 때 읽어 컴파일한다.
// 고치고 F5 를 누르면 다시 읽으므로, 빌드하지 않고 화면으로 확인할 수 있다.

#include "surface.hlsl"

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
    o.cav  = i.cav;
    o.vao  = i.vao;
    return o;
}

PSOut PS(VSOut i) {
    PSOut o;
    // shadowParam.w 가 그리는 방식을 가른다
    //   0  빛을 받는 단색    바닥판 · 세모
    //   1  빛 없는 단색      축 · 글자 — 조명을 먹이면 무슨 색인지 헷갈린다
    //   2  빛을 받는 텍스처  모델
    float mode = shadowParam.w;

    if (mode > 0.5 && mode < 1.5) {
        o.color = float4(lerp(ToLinear(color.rgb), float3(1,1,1), sun.w), 1.0);
        o.diff  = 0.0;
        return o;
    }

    float3 base = (mode > 1.5) ? albedoMap.Sample(texSmp, i.uv).rgb
                               : ToLinear(color.rgb);

    // 디퓨즈를 끄면 피부색이 걷히고 형태와 빛만 남는다.
    // 노말·반사·그림자는 그대로 두므로, 텍스처 무늬에 가려 안 보이던
    // 음영이 드러난다. sRGB 0.5 를 선형으로 옮긴 값이다
    if (screen.z < 0.5) base = 0.2140;
    float3 N = normalize(i.nrm);

    // 거칠기와 반사색. 텍스처가 없는 것(판·세모)은 적당한 값으로 둔다
    float  rough = 0.6;
    float3 f0    = 0.04;          // 금속이 아닌 것의 기본 반사율

    if (mode > 1.5) {
      // 노말맵을 끄면 아래를 통째로 건너뛴다 — 면 방향이 메시 그대로가 되어
      // 「이 굴곡이 모델의 것인가 텍스처의 것인가」 를 가려낼 수 있다
      if (screen.w > 0.5) {
        // 노말맵은 0~1 로 저장돼 있어 -1~1 로 편다
        float3 nm = normalMap.Sample(texSmp, i.uv).rgb * 2.0 - 1.0;

        // 채널마다 부호를 먹인다. 노말맵에는 여러 방식이 있어서
        // (OpenGL 은 초록이 위, DirectX 는 아래) 눈으로 맞춘다 — X · Y · Z 키
        nm *= nrmFlip.xyz;

        // 모공·잔주름. UV 를 여러 배로 늘려 촘촘히 깔고, 마스크가
        // 자리마다 세기를 정한다 (이마·볼은 세게, 입술은 약하게)
        float3 mn = microMap.Sample(texSmp, i.uv * envParam.w).rgb * 2.0 - 1.0;
        mn *= nrmFlip.xyz;
        float  mk = maskMap.Sample(texSmp, i.uv).r * camPos.w;
        mn.xy *= mk;
        nm = CombineNormals(nm, mn);

        // 면 위의 가로·세로·법선 축에 얹어 월드 방향으로 옮긴다
        N = normalize(nm.x * normalize(i.tan)
                    + nm.y * normalize(i.bit)
                    + nm.z * N);
      }

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

    // ── 피부 산란 ──
    // 살은 빛을 표면에서 다 튕겨내지 않는다. 얼마쯤 속으로 들어갔다가
    // 조금 떨어진 자리로 다시 나온다. 그래서 빛과 그늘의 경계가 칼같이
    // 떨어지지 않고 번지며, 살 속을 지나는 동안 붉게 물든다.
    //
    // 채널마다 감싸는 정도를 달리해 그 번짐을 흉내 낸다 —
    // 빨강이 가장 깊이 들어가고 파랑이 가장 얕다
    float  scat    = (mode > 1.5) ? scatterMap.Sample(texSmp, i.uv).r : 0.0;
    float3 wrap    = float3(0.45, 0.24, 0.13) * scat * nrmFlip.w;
    float3 wrapNoL = saturate((NoL + wrap) / (1.0 + wrap));

    // 확산은 감싼 값으로, 반사는 원래 값으로 셈한다.
    // 반사는 표면에서 바로 튕기는 것이라 속으로 들어가지 않는다.
    // PI 를 곱하는 것은 태양 세기를 그만큼으로 잡았기 때문이다 —
    // 이렇게 두면 확산 항이 base * NoL 이 되어 눈에 익은 밝기가 나온다
    float  sunI = toneParam.y;
    float3 dCol = diff * wrapNoL * lit * PI * sunI;  // 속으로 들어간 몫 — 이것만 번진다
    float3 sCol = spec * NoL     * lit * PI * sunI * toneParam.w;  // 표면에서 튕긴 몫

    // ── 환경광 ──
    // 환경맵이 있으면 사방에서 오는 빛을 그대로 읽는다. 없으면 하늘빛과
    // 땅빛 두 색을 섞어 흉내 낸다 — 그것도 없으면 얼굴이 납작해진다
    float  up  = N.y * 0.5 + 0.5;
    float3 amb = lerp(groundCol.rgb, skyCol.rgb, up);
    if (envParam.z > 0.5)
        // 구워 둔 것은 사방에서 들어온 빛을 그대로 더한 값이다.
        // 확산 반사는 그것을 반구로 고루 흩뿌리므로 PI 로 나눠야 한다 —
        // 안 나누면 PI 배 밝아져 얼굴이 하얗게 날아간다
        amb = irrMap.SampleLevel(texSmp, N, 0).rgb * envParam.x / PI;

    // 구석진 곳은 주변 빛이 덜 드니 SSAO 로 그만큼 깎는다
    float ao = 1.0;
    if (ssaoParam.w > 0.5)
        ao = aoTex.SampleLevel(pointSmp, i.pos.xy / screen.xy, 0).r;

    // 오목한 자리는 주변 빛이 덜 든다. 곡률이 양수일수록 파인 곳이다 —
    // SSAO 가 반경이 커서 놓치는 작은 주름을 이쪽이 잡는다
    float cav = saturate(1.0 - max(i.cav, 0.0) * skyCol.w);

    // 형상 전체에 가려지는 정도. 굽는 쪽이라 화면 밖의 것에 가려지는 것도 센다
    float vao = lerp(1.0, saturate(i.vao), rimCol.w);

    dCol += base * amb * ao * cav * vao;

    // ── 환경 반사 ──
    // 주변이 표면에 비친다. 거칠수록 뿌옇게 보이므로 거칠기에 맞는 밉을 읽는다.
    // 이것이 없으면 금속이나 젖은 표면이 제 모습을 못 낸다
    if (envParam.z > 0.5 && toneParam.w > 0.5) {
        float3 R    = reflect(-V, N);
        float  mip  = rough * (envParam.y - 1.0);
        float3 pref = prefMap.SampleLevel(texSmp, R, mip).rgb * envParam.x;
        // 가려진 자리는 비칠 것도 덜 들어온다
        sCol += pref * EnvBRDFApprox(f0, rough, NoV) * ao * vao;
    }

    // ── Rim ──
    // 뒤쪽에서 비쳐 윤곽을 띄운다. 태양 반대편에서 조금 위로 잡고,
    // 보는 방향과 면이 나란할수록(가장자리일수록) 세게 먹인다
    float3 rimDir = normalize(float3(-L.x, 0.35, -L.z));
    float  rimNoL = saturate(dot(N, rimDir));
    float  rimF   = pow(1.0 - NoV, 3.0);
    sCol += rimCol.rgb * rimF * rimNoL * groundCol.w;

    // 세모가 사라진 순간 화면 전체를 흰색 쪽으로 당긴다. 곧 0 으로 돌아온다.
    // 톤매핑은 하지 않는다 — 번지게 한 뒤 맨 끝에서 한 번에 한다
    // 카메라에서 멀수록 어둡게. 모델에만 건다 — 판이나 세모까지 걸면
    // 공간이 묻혀서 앞뒤 입체감이 아니라 그냥 어두운 화면이 된다
    float fogT = 0.0;
    if (mode > 1.5 && fogParam.z > 0.5) {
        float dist = length(camPos.xyz - i.wpos);
        fogT = saturate((dist - fogParam.x) / max(fogParam.y - fogParam.x, 1e-4));
    }
    // 확산에도 같이 먹여야 번짐이 어긋나지 않는다
    dCol = lerp(dCol, fogCol.rgb, fogT);
    sCol = lerp(sCol, 0.0,        fogT);

    float3 col = dCol + sCol;
    o.color = float4(lerp(col, float3(1,1,1), sun.w), 1.0);
    // 모델만 번지게 한다. 바닥판이나 세모가 번지면 이상하다
    o.diff  = float4((mode > 1.5) ? dCol : float3(0,0,0), 1.0);
    return o;
}


// ─── 깊이·법선 그리기 (SSAO 재료) ──────────────────────────────────────

GBufOut VS_GBuf(VSIn i) {
    GBufOut o;
    float4 wp = mul(float4(i.pos, 1.0), world);
    o.pos  = mul(float4(i.pos, 1.0), wvp);
    o.vpos = mul(wp, view).xyz;
    o.vnrm = mul(mul(i.nrm, (float3x3)world), (float3x3)view);
    return o;
}


GBufTargets PS_GBuf(GBufOut i) {
    GBufTargets o;
    o.p = float4(i.vpos, 1.0);
    o.n = float4(normalize(i.vnrm), 0.0);
    return o;
}

// ② 화면을 덮는 삼각형 하나. 정점 버퍼 없이 번호만으로 만든다 —
