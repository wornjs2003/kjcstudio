#include "ibl.h"

// 구현부는 texture.cpp 에 있다. 여기서는 선언만 가져온다
#include "third_party/stb_image.h"

#include <DirectXMath.h>
#include <DirectXPackedVector.h>   // 반정밀도 변환
#include <vector>
#include <cmath>
#include <cstdio>

using namespace DirectX;
using namespace DirectX::PackedVector;

namespace {

const float PI = 3.14159265358979f;

// 굽는 크기. 키우면 곱지만 굽는 시간이 제곱으로 는다
const UINT SKY_SIZE  = 512;   // 배경으로 보이는 것
const UINT IRR_SIZE  = 32;    // 확산 — 어차피 뭉개는 것이라 작아도 된다
const UINT SPEC_SIZE = 128;   // 반사 — 밉마다 거칠기가 다르다
const UINT SPEC_MIPS = 5;

struct RGB { float r, g, b; };

// ── 큐브맵의 한 면에서 바깥을 가리키는 방향 ──
// DirectX 큐브맵의 면 순서는 +X, -X, +Y, -Y, +Z, -Z 다.
// u, v 는 -1~1 이고 v 는 아래로 간다
XMFLOAT3 FaceDir(int face, float u, float v) {
    switch (face) {
    case 0: return XMFLOAT3( 1.0f,   -v,   -u);   // +X
    case 1: return XMFLOAT3(-1.0f,   -v,    u);   // -X
    case 2: return XMFLOAT3(    u, 1.0f,    v);   // +Y
    case 3: return XMFLOAT3(    u,-1.0f,   -v);   // -Y
    case 4: return XMFLOAT3(    u,   -v, 1.0f);   // +Z
    default:return XMFLOAT3(   -u,   -v,-1.0f);   // -Z
    }
}

XMFLOAT3 Norm(XMFLOAT3 d) {
    float L = sqrtf(d.x * d.x + d.y * d.y + d.z * d.z);
    if (L < 1e-9f) return XMFLOAT3(0, 1, 0);
    return XMFLOAT3(d.x / L, d.y / L, d.z / L);
}

// ── 가로로 펼친 HDR(equirectangular)에서 방향으로 읽는다 ──
// 위아래가 극, 좌우가 한 바퀴다. 방향을 각도로 바꿔 그 자리를 집는다
struct Equirect {
    std::vector<RGB> px;
    int w = 0, h = 0;

    RGB Sample(const XMFLOAT3& d) const {
        float phi   = atan2f(d.z, d.x);                       // -PI ~ PI
        float theta = acosf(d.y < -1.0f ? -1.0f : (d.y > 1.0f ? 1.0f : d.y));
        float u = phi * (0.5f / PI) + 0.5f;
        float v = theta * (1.0f / PI);

        int x = (int)(u * w);
        int y = (int)(v * h);
        if (x < 0) x = 0; else if (x >= w) x = w - 1;
        if (y < 0) y = 0; else if (y >= h) y = h - 1;
        return px[(size_t)y * w + x];
    }
};

// ── 큐브맵 한 벌 (밉 하나) ──
struct CubeLevel {
    std::vector<RGB> face[6];
    UINT size = 0;

    void Alloc(UINT s) {
        size = s;
        for (int f = 0; f < 6; ++f) face[f].assign((size_t)s * s, RGB{0, 0, 0});
    }

    RGB Sample(const XMFLOAT3& dir) const {
        // 어느 면인지는 절댓값이 가장 큰 축이 정한다
        float ax = fabsf(dir.x), ay = fabsf(dir.y), az = fabsf(dir.z);
        int f; float u, v, m;
        if (ax >= ay && ax >= az) {
            m = ax;
            if (dir.x > 0) { f = 0; u = -dir.z / m; v = -dir.y / m; }
            else           { f = 1; u =  dir.z / m; v = -dir.y / m; }
        } else if (ay >= az) {
            m = ay;
            if (dir.y > 0) { f = 2; u =  dir.x / m; v =  dir.z / m; }
            else           { f = 3; u =  dir.x / m; v = -dir.z / m; }
        } else {
            m = az;
            if (dir.z > 0) { f = 4; u =  dir.x / m; v = -dir.y / m; }
            else           { f = 5; u = -dir.x / m; v = -dir.y / m; }
        }
        int x = (int)((u * 0.5f + 0.5f) * size);
        int y = (int)((v * 0.5f + 0.5f) * size);
        if (x < 0) x = 0; else if (x >= (int)size) x = size - 1;
        if (y < 0) y = 0; else if (y >= (int)size) y = size - 1;
        return face[f][(size_t)y * size + x];
    }
};

// ── 확산용으로 뭉갠다 ──
// 한 방향에서 볼 때 반구 전체에서 들어오는 빛을 코사인으로 가중해 더한다.
// 결과가 아주 부드러워서 32 픽셀이면 넉넉하다
void BakeIrradiance(const CubeLevel& src, CubeLevel& dst) {
    dst.Alloc(IRR_SIZE);

    const int NPHI = 64, NTHETA = 16;
    const float dPhi   = 2.0f * PI / NPHI;
    const float dTheta = 0.5f * PI / NTHETA;

    for (int f = 0; f < 6; ++f) {
        for (UINT y = 0; y < IRR_SIZE; ++y) {
            for (UINT x = 0; x < IRR_SIZE; ++x) {
                float u = (x + 0.5f) / IRR_SIZE * 2.0f - 1.0f;
                float v = (y + 0.5f) / IRR_SIZE * 2.0f - 1.0f;
                XMFLOAT3 N = Norm(FaceDir(f, u, v));

                // N 을 축으로 하는 좌표계
                XMFLOAT3 up = (fabsf(N.y) > 0.99f) ? XMFLOAT3(1, 0, 0) : XMFLOAT3(0, 1, 0);
                XMVECTOR nv = XMLoadFloat3(&N);
                XMVECTOR tv = XMVector3Normalize(XMVector3Cross(XMLoadFloat3(&up), nv));
                XMVECTOR bv = XMVector3Cross(nv, tv);
                XMFLOAT3 T, B;
                XMStoreFloat3(&T, tv);
                XMStoreFloat3(&B, bv);

                RGB sum{0, 0, 0};
                for (int ip = 0; ip < NPHI; ++ip) {
                    float phi = ip * dPhi;
                    float cp = cosf(phi), sp = sinf(phi);
                    for (int it = 0; it < NTHETA; ++it) {
                        float th = (it + 0.5f) * dTheta;
                        float st = sinf(th), ct = cosf(th);

                        XMFLOAT3 d(
                            st * cp * T.x + st * sp * B.x + ct * N.x,
                            st * cp * T.y + st * sp * B.y + ct * N.y,
                            st * cp * T.z + st * sp * B.z + ct * N.z);
                        RGB c = src.Sample(d);
                        // 코사인(ct)으로 가중하고, 극 쪽이 촘촘해지는 것을 st 로 바로잡는다
                        float w = ct * st;
                        sum.r += c.r * w;
                        sum.g += c.g * w;
                        sum.b += c.b * w;
                    }
                }
                float k = PI * dPhi * dTheta / PI;   // 적분을 마무리하는 상수
                dst.face[f][(size_t)y * IRR_SIZE + x] = { sum.r * k, sum.g * k, sum.b * k };
            }
        }
    }
}

// GGX 로 흩어지는 방향을 고른다. 거칠수록 넓게 퍼진다
XMFLOAT3 ImportanceGGX(float u1, float u2, const XMFLOAT3& N, float rough) {
    float a = rough * rough;
    float phi = 2.0f * PI * u1;
    float ct = sqrtf((1.0f - u2) / (1.0f + (a * a - 1.0f) * u2));
    float st = sqrtf(1.0f - ct * ct);

    XMFLOAT3 up = (fabsf(N.y) > 0.99f) ? XMFLOAT3(1, 0, 0) : XMFLOAT3(0, 1, 0);
    XMVECTOR nv = XMLoadFloat3(&N);
    XMVECTOR tv = XMVector3Normalize(XMVector3Cross(XMLoadFloat3(&up), nv));
    XMVECTOR bv = XMVector3Cross(nv, tv);
    XMFLOAT3 T, B;
    XMStoreFloat3(&T, tv);
    XMStoreFloat3(&B, bv);

    return Norm(XMFLOAT3(
        st * cosf(phi) * T.x + st * sinf(phi) * B.x + ct * N.x,
        st * cosf(phi) * T.y + st * sinf(phi) * B.y + ct * N.y,
        st * cosf(phi) * T.z + st * sinf(phi) * B.z + ct * N.z));
}

// ── 반사용으로 거칠기별로 흐린다 ──
// 밉 0 은 거울처럼 또렷하고, 아래로 갈수록 뿌옇다.
// 셰이더는 거칠기에 맞는 밉을 골라 읽는다
void BakeSpecular(const CubeLevel& src, std::vector<CubeLevel>& dst) {
    dst.resize(SPEC_MIPS);

    for (UINT mip = 0; mip < SPEC_MIPS; ++mip) {
        UINT size = SPEC_SIZE >> mip;
        if (size < 1) size = 1;
        dst[mip].Alloc(size);

        float rough = (float)mip / (SPEC_MIPS - 1);
        int samples = (mip == 0) ? 1 : 64;

        for (int f = 0; f < 6; ++f) {
            for (UINT y = 0; y < size; ++y) {
                for (UINT x = 0; x < size; ++x) {
                    float u = (x + 0.5f) / size * 2.0f - 1.0f;
                    float v = (y + 0.5f) / size * 2.0f - 1.0f;
                    XMFLOAT3 N = Norm(FaceDir(f, u, v));

                    if (mip == 0) {                      // 또렷한 그대로
                        dst[mip].face[f][(size_t)y * size + x] = src.Sample(N);
                        continue;
                    }

                    RGB sum{0, 0, 0};
                    float wsum = 0.0f;
                    for (int s = 0; s < samples; ++s) {
                        float u1 = (s + 0.5f) / samples;
                        float u2 = fmodf(s * 0.618033989f, 1.0f);   // 황금비로 고르게
                        XMFLOAT3 H = ImportanceGGX(u1, u2, N, rough);
                        float NoH = N.x * H.x + N.y * H.y + N.z * H.z;
                        // 보는 방향을 N 으로 잡았을 때의 반사 방향
                        XMFLOAT3 L = Norm(XMFLOAT3(2.0f * NoH * H.x - N.x,
                                                   2.0f * NoH * H.y - N.y,
                                                   2.0f * NoH * H.z - N.z));
                        float NoL = N.x * L.x + N.y * L.y + N.z * L.z;
                        if (NoL <= 0.0f) continue;
                        RGB c = src.Sample(L);
                        sum.r += c.r * NoL;
                        sum.g += c.g * NoL;
                        sum.b += c.b * NoL;
                        wsum += NoL;
                    }
                    if (wsum < 1e-6f) wsum = 1.0f;
                    dst[mip].face[f][(size_t)y * size + x] =
                        { sum.r / wsum, sum.g / wsum, sum.b / wsum };
                }
            }
        }
    }
}

// float RGB 를 반정밀도(16비트)로 줄여 GPU 에 올린다.
// 32비트로 두면 자리를 네 배 먹는데 눈으로는 차이를 못 본다
void ToHalf4(const std::vector<RGB>& src, std::vector<uint16_t>& dst) {
    dst.resize(src.size() * 4);
    std::vector<float> tmp(src.size() * 4);
    for (size_t i = 0; i < src.size(); ++i) {
        tmp[i * 4 + 0] = src[i].r;
        tmp[i * 4 + 1] = src[i].g;
        tmp[i * 4 + 2] = src[i].b;
        tmp[i * 4 + 3] = 1.0f;
    }
    XMConvertFloatToHalfStream(dst.data(), sizeof(uint16_t),
                               tmp.data(), sizeof(float), tmp.size());
}

// 큐브맵 텍스처를 만들어 올린다. 밉이 여럿이면 levels 에 차례로 담아 넘긴다
ID3D11ShaderResourceView* MakeCube(ID3D11Device* dev,
                                   const std::vector<CubeLevel>& levels) {
    const UINT mips = (UINT)levels.size();

    D3D11_TEXTURE2D_DESC td = {};
    td.Width            = levels[0].size;
    td.Height           = levels[0].size;
    td.MipLevels        = mips;
    td.ArraySize        = 6;
    td.Format           = DXGI_FORMAT_R16G16B16A16_FLOAT;
    td.SampleDesc.Count = 1;
    td.Usage            = D3D11_USAGE_IMMUTABLE;
    td.BindFlags        = D3D11_BIND_SHADER_RESOURCE;
    td.MiscFlags        = D3D11_RESOURCE_MISC_TEXTURECUBE;

    // 면과 밉마다 자료를 하나씩 넘긴다. 순서는 면 → 밉이다
    std::vector<std::vector<uint16_t>> blobs((size_t)6 * mips);
    std::vector<D3D11_SUBRESOURCE_DATA> sub((size_t)6 * mips);
    for (UINT f = 0; f < 6; ++f) {
        for (UINT m = 0; m < mips; ++m) {
            size_t k = (size_t)f * mips + m;
            ToHalf4(levels[m].face[f], blobs[k]);
            sub[k].pSysMem          = blobs[k].data();
            sub[k].SysMemPitch      = levels[m].size * 4 * sizeof(uint16_t);
            sub[k].SysMemSlicePitch = 0;
        }
    }

    ID3D11Texture2D* tex = nullptr;
    if (FAILED(dev->CreateTexture2D(&td, sub.data(), &tex))) return nullptr;

    D3D11_SHADER_RESOURCE_VIEW_DESC sd = {};
    sd.Format                  = td.Format;
    sd.ViewDimension           = D3D11_SRV_DIMENSION_TEXTURECUBE;
    sd.TextureCube.MipLevels   = mips;
    ID3D11ShaderResourceView* srv = nullptr;
    dev->CreateShaderResourceView(tex, &sd, &srv);
    tex->Release();
    return srv;
}

} // namespace

bool LoadEnvironment(ID3D11Device* dev, const char* hdrPath,
                     Environment& out, char* err, size_t errSize) {
    // ── HDR 을 읽는다 ──
    int w = 0, h = 0, comp = 0;
    float* raw = stbi_loadf(hdrPath, &w, &h, &comp, 3);
    if (!raw) {
        snprintf(err, errSize, "HDR read failed:\n%s\n\n%s", hdrPath, stbi_failure_reason());
        return false;
    }

    Equirect eq;
    eq.w = w;
    eq.h = h;
    eq.px.resize((size_t)w * h);
    for (size_t i = 0; i < eq.px.size(); ++i)
        eq.px[i] = { raw[i * 3], raw[i * 3 + 1], raw[i * 3 + 2] };
    stbi_image_free(raw);

    // ── 가로로 펼친 것을 큐브로 옮긴다 ──
    CubeLevel sky;
    sky.Alloc(SKY_SIZE);
    for (int f = 0; f < 6; ++f) {
        for (UINT y = 0; y < SKY_SIZE; ++y) {
            for (UINT x = 0; x < SKY_SIZE; ++x) {
                float u = (x + 0.5f) / SKY_SIZE * 2.0f - 1.0f;
                float v = (y + 0.5f) / SKY_SIZE * 2.0f - 1.0f;
                sky.face[f][(size_t)y * SKY_SIZE + x] = eq.Sample(Norm(FaceDir(f, u, v)));
            }
        }
    }

    CubeLevel irr;
    BakeIrradiance(sky, irr);

    std::vector<CubeLevel> spec;
    BakeSpecular(sky, spec);

    // ── GPU 로 올린다 ──
    std::vector<CubeLevel> one{ sky };
    out.skySRV  = MakeCube(dev, one);
    std::vector<CubeLevel> oneIrr{ irr };
    out.irrSRV  = MakeCube(dev, oneIrr);
    out.specSRV = MakeCube(dev, spec);
    out.specMips = SPEC_MIPS;

    if (!out.skySRV || !out.irrSRV || !out.specSRV) {
        snprintf(err, errSize, "Cubemap creation failed:\n%s", hdrPath);
        out.Release();
        return false;
    }
    return true;
}
