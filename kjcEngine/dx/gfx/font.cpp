#include "gfx/font.h"

#include <d3dcompiler.h>
#include <cstdio>
#include <vector>
#include <unordered_map>

#pragma comment(lib, "d3dcompiler.lib")
#pragma comment(lib, "gdi32.lib")

namespace {

// ─── 아틀라스 ──────────────────────────────────────────────────────────
// 글자 모양을 한 장에 모아 둔다. 넓게 잡아도 R8 이라 1MB 다
const int ATLAS = 1024;
const int PAD   = 1;          // 옆 글자가 새어 들어오지 않게 한 칸 띄운다

struct Glyph {
    float u0, v0, u1, v1;     // 아틀라스 안의 자리
    int   w, h;               // 그림 크기
    int   bx, by;             // 글자 상자 왼쪽 위에서 그림까지의 치우침
    int   adv;                // 다음 글자까지의 걸음
};

// 정점 하나. 자리는 화면 픽셀 그대로 넘긴다
struct TVert {
    float x, y;
    float u, v;
    float r, g, b, a;
};

ID3D11Device*        g_dev = nullptr;
ID3D11DeviceContext* g_ctx = nullptr;

ID3D11Texture2D*          g_tex    = nullptr;
ID3D11ShaderResourceView* g_srv    = nullptr;
ID3D11Buffer*             g_vb     = nullptr;
ID3D11Buffer*             g_cb     = nullptr;
ID3D11VertexShader*       g_vs     = nullptr;
ID3D11PixelShader*        g_ps     = nullptr;
ID3D11InputLayout*        g_layout = nullptr;
ID3D11SamplerState*       g_smp    = nullptr;
ID3D11BlendState*         g_blend  = nullptr;
ID3D11DepthStencilState*  g_noDepth = nullptr;
ID3D11RasterizerState*    g_rs     = nullptr;

HDC   g_gdiDC   = nullptr;
HFONT g_gdiFont = nullptr;
HFONT g_gdiOld  = nullptr;
int   g_ascent = 0, g_lineH = 0;

std::unordered_map<wchar_t, Glyph> g_glyphs;
int g_penX = PAD, g_penY = PAD, g_shelfH = 0;   // 아틀라스에 놓는 자리

std::vector<TVert> g_verts;
size_t g_vbCap = 0;
int    g_scrW = 1, g_scrH = 1;

// ─── 글자 하나를 구워 아틀라스에 넣는다 ────────────────────────────────
// GGO_GRAY8_BITMAP 은 0~64 단계의 덮임 정도를 준다. 행마다 4바이트로
// 맞춰져 있어서 그대로 읽으면 어긋난다
const Glyph* Bake(wchar_t ch) {
    auto it = g_glyphs.find(ch);
    if (it != g_glyphs.end()) return &it->second;
    if (!g_gdiDC) return nullptr;

    GLYPHMETRICS gm = {};
    MAT2 mat = { {0,1},{0,0},{0,0},{0,1} };      // 단위 행렬
    DWORD size = GetGlyphOutlineW(g_gdiDC, ch, GGO_GRAY8_BITMAP, &gm, 0, nullptr, &mat);
    if (size == GDI_ERROR) return nullptr;

    Glyph gl = {};
    gl.adv = gm.gmCellIncX;
    gl.bx  = gm.gmptGlyphOrigin.x;
    gl.by  = g_ascent - gm.gmptGlyphOrigin.y;

    if (size == 0) {                              // 공백처럼 그림이 없는 글자
        g_glyphs[ch] = gl;
        return &g_glyphs[ch];
    }

    std::vector<BYTE> buf(size);
    if (GetGlyphOutlineW(g_gdiDC, ch, GGO_GRAY8_BITMAP, &gm, size, buf.data(), &mat)
        == GDI_ERROR) return nullptr;

    int w = gm.gmBlackBoxX, h = gm.gmBlackBoxY;
    int pitch = (w + 3) & ~3;                     // 행이 4바이트로 맞춰져 있다

    // 아틀라스에 자리를 잡는다. 선반처럼 한 줄을 채우고 다음 줄로 내려간다
    if (g_penX + w + PAD > ATLAS) {
        g_penX = PAD;
        g_penY += g_shelfH + PAD;
        g_shelfH = 0;
    }
    if (g_penY + h + PAD > ATLAS) return nullptr; // 다 찼다. 드물게 일어난다
    if (h > g_shelfH) g_shelfH = h;

    // 0~64 를 0~255 로 편다
    std::vector<BYTE> pix((size_t)w * h);
    for (int y = 0; y < h; ++y)
        for (int x = 0; x < w; ++x) {
            BYTE v = buf[(size_t)y * pitch + x];
            pix[(size_t)y * w + x] = (BYTE)(v >= 64 ? 255 : v * 255 / 64);
        }

    D3D11_BOX box = { (UINT)g_penX, (UINT)g_penY, 0,
                      (UINT)(g_penX + w), (UINT)(g_penY + h), 1 };
    g_ctx->UpdateSubresource(g_tex, 0, &box, pix.data(), w, 0);

    gl.w  = w;  gl.h = h;
    gl.u0 = (float)g_penX / ATLAS;
    gl.v0 = (float)g_penY / ATLAS;
    gl.u1 = (float)(g_penX + w) / ATLAS;
    gl.v1 = (float)(g_penY + h) / ATLAS;
    g_penX += w + PAD;

    g_glyphs[ch] = gl;
    return &g_glyphs[ch];
}

void PushQuad(float x0, float y0, float x1, float y1,
              float u0, float v0, float u1, float v1, const float c[4]) {
    const float px[6] = { x0, x1, x0, x0, x1, x1 };
    const float py[6] = { y0, y0, y1, y1, y0, y1 };
    const float pu[6] = { u0, u1, u0, u0, u1, u1 };
    const float pv[6] = { v0, v0, v1, v1, v0, v1 };
    for (int i = 0; i < 6; ++i)
        g_verts.push_back({ px[i], py[i], pu[i], pv[i], c[0], c[1], c[2], c[3] });
}

} // namespace

bool FontInit(ID3D11Device* dev, ID3D11DeviceContext* ctx,
              const wchar_t* face, int pixelHeight, char* err, size_t errSize) {
    g_dev = dev; g_ctx = ctx;

    // ── GDI 쪽 ──
    g_gdiDC = CreateCompatibleDC(nullptr);
    if (!g_gdiDC) { snprintf(err, errSize, "CreateCompatibleDC failed"); return false; }

    // ANTIALIASED_QUALITY — ClearType 은 채널마다 값이 달라 회색 한 장에 못 담는다
    g_gdiFont = CreateFontW(-pixelHeight, 0, 0, 0, FW_NORMAL, FALSE, FALSE, FALSE,
                            DEFAULT_CHARSET, OUT_TT_PRECIS, CLIP_DEFAULT_PRECIS,
                            ANTIALIASED_QUALITY, DEFAULT_PITCH | FF_DONTCARE, face);
    if (!g_gdiFont) { snprintf(err, errSize, "CreateFontW failed"); return false; }
    g_gdiOld = (HFONT)SelectObject(g_gdiDC, g_gdiFont);

    TEXTMETRICW tm = {};
    GetTextMetricsW(g_gdiDC, &tm);
    g_ascent = tm.tmAscent;
    g_lineH  = tm.tmHeight + tm.tmExternalLeading;

    // ── 아틀라스 ──
    D3D11_TEXTURE2D_DESC td = {};
    td.Width = td.Height = ATLAS;
    td.MipLevels = td.ArraySize = 1;
    td.Format    = DXGI_FORMAT_R8_UNORM;
    td.SampleDesc.Count = 1;
    td.Usage     = D3D11_USAGE_DEFAULT;
    td.BindFlags = D3D11_BIND_SHADER_RESOURCE;
    std::vector<BYTE> zero((size_t)ATLAS * ATLAS, 0);
    D3D11_SUBRESOURCE_DATA sd = { zero.data(), ATLAS, 0 };
    if (FAILED(dev->CreateTexture2D(&td, &sd, &g_tex))) {
        snprintf(err, errSize, "atlas CreateTexture2D failed"); return false;
    }
    dev->CreateShaderResourceView(g_tex, nullptr, &g_srv);

    // ── 셰이더 ──
    // 제 것만 따로 컴파일한다. 다른 셰이더와 섞으면 F5 로 다시 읽을 때
    // 글자까지 함께 날아간다
    ID3DBlob *bv = nullptr, *bp = nullptr, *be = nullptr;
    const wchar_t* path = L"shaders/text.hlsl";
    if (FAILED(D3DCompileFromFile(path, nullptr, D3D_COMPILE_STANDARD_FILE_INCLUDE,
                                  "VS_Text", "vs_5_0", 0, 0, &bv, &be))) {
        snprintf(err, errSize, "text.hlsl VS:\n%s",
                 be ? (const char*)be->GetBufferPointer() : "not found");
        if (be) be->Release();
        return false;
    }
    if (FAILED(D3DCompileFromFile(path, nullptr, D3D_COMPILE_STANDARD_FILE_INCLUDE,
                                  "PS_Text", "ps_5_0", 0, 0, &bp, &be))) {
        snprintf(err, errSize, "text.hlsl PS:\n%s",
                 be ? (const char*)be->GetBufferPointer() : "not found");
        if (be) be->Release();
        bv->Release();
        return false;
    }
    dev->CreateVertexShader(bv->GetBufferPointer(), bv->GetBufferSize(), nullptr, &g_vs);
    dev->CreatePixelShader (bp->GetBufferPointer(), bp->GetBufferSize(), nullptr, &g_ps);

    const D3D11_INPUT_ELEMENT_DESC il[] = {
        { "POSITION", 0, DXGI_FORMAT_R32G32_FLOAT,       0,  0, D3D11_INPUT_PER_VERTEX_DATA, 0 },
        { "TEXCOORD", 0, DXGI_FORMAT_R32G32_FLOAT,       0,  8, D3D11_INPUT_PER_VERTEX_DATA, 0 },
        { "COLOR",    0, DXGI_FORMAT_R32G32B32A32_FLOAT, 0, 16, D3D11_INPUT_PER_VERTEX_DATA, 0 },
    };
    dev->CreateInputLayout(il, 3, bv->GetBufferPointer(), bv->GetBufferSize(), &g_layout);
    bv->Release(); bp->Release();

    // ── 상수 버퍼 ──
    D3D11_BUFFER_DESC cbd = {};
    cbd.Usage     = D3D11_USAGE_DEFAULT;
    cbd.ByteWidth = 16;
    cbd.BindFlags = D3D11_BIND_CONSTANT_BUFFER;
    dev->CreateBuffer(&cbd, nullptr, &g_cb);

    // ── 상태들 ──
    D3D11_SAMPLER_DESC smp = {};
    smp.Filter   = D3D11_FILTER_MIN_MAG_MIP_LINEAR;
    smp.AddressU = smp.AddressV = smp.AddressW = D3D11_TEXTURE_ADDRESS_CLAMP;
    dev->CreateSamplerState(&smp, &g_smp);

    D3D11_BLEND_DESC bd = {};
    bd.RenderTarget[0].BlendEnable    = TRUE;
    bd.RenderTarget[0].SrcBlend       = D3D11_BLEND_SRC_ALPHA;
    bd.RenderTarget[0].DestBlend      = D3D11_BLEND_INV_SRC_ALPHA;
    bd.RenderTarget[0].BlendOp        = D3D11_BLEND_OP_ADD;
    bd.RenderTarget[0].SrcBlendAlpha  = D3D11_BLEND_ONE;
    bd.RenderTarget[0].DestBlendAlpha = D3D11_BLEND_INV_SRC_ALPHA;
    bd.RenderTarget[0].BlendOpAlpha   = D3D11_BLEND_OP_ADD;
    bd.RenderTarget[0].RenderTargetWriteMask = D3D11_COLOR_WRITE_ENABLE_ALL;
    dev->CreateBlendState(&bd, &g_blend);

    D3D11_DEPTH_STENCIL_DESC dsd = {};
    dsd.DepthEnable = FALSE;
    dev->CreateDepthStencilState(&dsd, &g_noDepth);

    D3D11_RASTERIZER_DESC rd = {};
    rd.FillMode = D3D11_FILL_SOLID;
    rd.CullMode = D3D11_CULL_NONE;
    dev->CreateRasterizerState(&rd, &g_rs);

    return true;
}

void FontBegin(int screenW, int screenH) {
    g_scrW = screenW > 0 ? screenW : 1;
    g_scrH = screenH > 0 ? screenH : 1;
    g_verts.clear();
}

void FontRect(float x, float y, float w, float h, const float rgba[4]) {
    // uv 를 음수로 두면 셰이더가 아틀라스를 안 읽고 색만 낸다
    PushQuad(x, y, x + w, y + h, -1.0f, -1.0f, -1.0f, -1.0f, rgba);
}

void FontDraw(float x, float y, const wchar_t* text, const float rgba[4]) {
    if (!text) return;
    float pen = x;
    for (const wchar_t* p = text; *p; ++p) {
        if (*p == L'\n') { pen = x; y += (float)g_lineH; continue; }
        const Glyph* gl = Bake(*p);
        if (!gl) continue;
        if (gl->w > 0) {
            float x0 = pen + gl->bx, y0 = y + gl->by;
            PushQuad(x0, y0, x0 + gl->w, y0 + gl->h,
                     gl->u0, gl->v0, gl->u1, gl->v1, rgba);
        }
        pen += gl->adv;
    }
}

float FontWidth(const wchar_t* text) {
    if (!text) return 0.0f;
    float w = 0.0f, best = 0.0f;
    for (const wchar_t* p = text; *p; ++p) {
        if (*p == L'\n') { if (w > best) best = w; w = 0.0f; continue; }
        const Glyph* gl = Bake(*p);
        if (gl) w += gl->adv;
    }
    return w > best ? w : best;
}

float FontLineHeight() { return (float)g_lineH; }

void FontEnd() {
    if (g_verts.empty() || !g_vs) return;

    // 모인 만큼 담을 자리를 마련한다. 줄어들 때는 그대로 둔다
    if (g_verts.size() > g_vbCap) {
        if (g_vb) { g_vb->Release(); g_vb = nullptr; }
        g_vbCap = g_verts.size() + 512;
        D3D11_BUFFER_DESC bd = {};
        bd.Usage          = D3D11_USAGE_DYNAMIC;
        bd.ByteWidth      = (UINT)(sizeof(TVert) * g_vbCap);
        bd.BindFlags      = D3D11_BIND_VERTEX_BUFFER;
        bd.CPUAccessFlags = D3D11_CPU_ACCESS_WRITE;
        if (FAILED(g_dev->CreateBuffer(&bd, nullptr, &g_vb))) { g_vbCap = 0; return; }
    }

    D3D11_MAPPED_SUBRESOURCE m = {};
    if (FAILED(g_ctx->Map(g_vb, 0, D3D11_MAP_WRITE_DISCARD, 0, &m))) return;
    memcpy(m.pData, g_verts.data(), sizeof(TVert) * g_verts.size());
    g_ctx->Unmap(g_vb, 0);

    float scr[4] = { (float)g_scrW, (float)g_scrH, 0.0f, 0.0f };
    g_ctx->UpdateSubresource(g_cb, 0, nullptr, scr, 0, 0);

    UINT stride = sizeof(TVert), offset = 0;
    g_ctx->IASetInputLayout(g_layout);
    g_ctx->IASetVertexBuffers(0, 1, &g_vb, &stride, &offset);
    g_ctx->IASetPrimitiveTopology(D3D11_PRIMITIVE_TOPOLOGY_TRIANGLELIST);
    g_ctx->VSSetShader(g_vs, nullptr, 0);
    g_ctx->PSSetShader(g_ps, nullptr, 0);
    g_ctx->VSSetConstantBuffers(3, 1, &g_cb);
    g_ctx->PSSetShaderResources(20, 1, &g_srv);
    g_ctx->PSSetSamplers(5, 1, &g_smp);

    const float bf[4] = { 0, 0, 0, 0 };
    g_ctx->OMSetBlendState(g_blend, bf, 0xffffffff);
    g_ctx->OMSetDepthStencilState(g_noDepth, 0);
    g_ctx->RSSetState(g_rs);

    g_ctx->Draw((UINT)g_verts.size(), 0);

    // 다음 패스가 제 상태를 다시 잡을 수 있게 기본으로 돌려 놓는다
    g_ctx->OMSetBlendState(nullptr, bf, 0xffffffff);
    g_ctx->OMSetDepthStencilState(nullptr, 0);
    ID3D11ShaderResourceView* nul = nullptr;
    g_ctx->PSSetShaderResources(20, 1, &nul);

    g_verts.clear();
}

void FontShutdown() {
    if (g_rs)      { g_rs->Release();      g_rs = nullptr; }
    if (g_noDepth) { g_noDepth->Release(); g_noDepth = nullptr; }
    if (g_blend)   { g_blend->Release();   g_blend = nullptr; }
    if (g_smp)     { g_smp->Release();     g_smp = nullptr; }
    if (g_layout)  { g_layout->Release();  g_layout = nullptr; }
    if (g_ps)      { g_ps->Release();      g_ps = nullptr; }
    if (g_vs)      { g_vs->Release();      g_vs = nullptr; }
    if (g_cb)      { g_cb->Release();      g_cb = nullptr; }
    if (g_vb)      { g_vb->Release();      g_vb = nullptr; g_vbCap = 0; }
    if (g_srv)     { g_srv->Release();     g_srv = nullptr; }
    if (g_tex)     { g_tex->Release();     g_tex = nullptr; }

    if (g_gdiDC) {
        if (g_gdiOld) SelectObject(g_gdiDC, g_gdiOld);
        DeleteDC(g_gdiDC);
        g_gdiDC = nullptr;
    }
    if (g_gdiFont) { DeleteObject(g_gdiFont); g_gdiFont = nullptr; }
    g_glyphs.clear();
    g_penX = g_penY = PAD;
    g_shelfH = 0;
}
