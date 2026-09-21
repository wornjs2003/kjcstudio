// 화면에 글자를 찍는 셰이더.
//
// 다른 패스와 자리를 다투지 않도록 슬롯을 따로 쓴다 — 상수 b3, 텍스처 t20,
// 샘플러 s5. 겹치면 글자를 그리고 난 뒤 앞의 바인딩을 되돌려 놔야 한다.

cbuffer TextCB : register(b3) {
    float4 screen;        // xy = 화면 크기 (픽셀)
};

Texture2D    atlas : register(t20);   // 글자 모양. R8 — 얼마나 덮였나만 담는다
SamplerState smp   : register(s5);

struct VIn {
    float2 pos : POSITION;    // 화면 픽셀 자리
    float2 uv  : TEXCOORD;
    float4 col : COLOR;
};

struct VOut {
    float4 pos : SV_POSITION;
    float2 uv  : TEXCOORD;
    float4 col : COLOR;
};

VOut VS_Text(VIn i) {
    VOut o;
    // 픽셀 자리를 그대로 화면 좌표로 옮긴다. 3D 공간에 띄우면 흐려진다
    o.pos = float4(i.pos.x / screen.x *  2.0 - 1.0,
                   i.pos.y / screen.y * -2.0 + 1.0, 0.0, 1.0);
    o.uv  = i.uv;
    o.col = i.col;
    return o;
}

float4 PS_Text(VOut i) : SV_Target {
    // uv 가 음수면 글자가 아니라 바탕 칸이다. 아틀라스를 읽지 않는다
    float a = (i.uv.x < 0.0) ? 1.0 : atlas.Sample(smp, i.uv).r;
    return float4(i.col.rgb, i.col.a * a);
}
