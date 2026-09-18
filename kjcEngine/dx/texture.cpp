#include "texture.h"

#define STB_IMAGE_IMPLEMENTATION
#define STBI_NO_PSD
#define STBI_NO_GIF
#define STBI_NO_PIC
#define STBI_NO_PNM
#include "third_party/stb_image.h"

#include <cstdio>

bool LoadTexture(ID3D11Device* dev, ID3D11DeviceContext* ctx,
                 const char* path, bool srgb,
                 Texture& out, char* err, size_t errSize) {
    int w = 0, h = 0, comp = 0;
    // 채널이 몇 개든 4개(RGBA)로 맞춰 받는다. GPU 텍스처 형식이 하나로 고정돼
    // 뒤쪽 코드가 갈라지지 않는다
    unsigned char* pixels = stbi_load(path, &w, &h, &comp, 4);
    if (!pixels) {
        snprintf(err, errSize, "Image read failed:\n%s\n\n%s", path, stbi_failure_reason());
        return false;
    }

    // 밉맵을 쓴다. 멀리 있는 면이 한 픽셀에 여러 텍셀을 담게 되는데,
    // 밉맵이 없으면 그 자리가 지글거린다
    D3D11_TEXTURE2D_DESC td = {};
    td.Width          = w;
    td.Height         = h;
    td.MipLevels      = 0;               // 0 = 끝까지 만든다
    td.ArraySize      = 1;
    td.Format         = srgb ? DXGI_FORMAT_R8G8B8A8_UNORM_SRGB
                             : DXGI_FORMAT_R8G8B8A8_UNORM;
    td.SampleDesc.Count = 1;
    td.Usage          = D3D11_USAGE_DEFAULT;
    td.BindFlags      = D3D11_BIND_SHADER_RESOURCE | D3D11_BIND_RENDER_TARGET;
    td.MiscFlags      = D3D11_RESOURCE_MISC_GENERATE_MIPS;

    ID3D11Texture2D* tex = nullptr;
    if (FAILED(dev->CreateTexture2D(&td, nullptr, &tex))) {
        snprintf(err, errSize, "CreateTexture2D failed (%dx%d):\n%s", w, h, path);
        stbi_image_free(pixels);
        return false;
    }

    // 맨 위 단계에만 그림을 넣고, 나머지 단계는 GPU 가 줄여서 채우게 한다
    ctx->UpdateSubresource(tex, 0, nullptr, pixels, w * 4, 0);
    stbi_image_free(pixels);

    D3D11_SHADER_RESOURCE_VIEW_DESC sd = {};
    sd.Format                    = td.Format;
    sd.ViewDimension             = D3D11_SRV_DIMENSION_TEXTURE2D;
    sd.Texture2D.MipLevels       = (UINT)-1;      // 있는 단계를 전부 쓴다
    if (FAILED(dev->CreateShaderResourceView(tex, &sd, &out.srv))) {
        snprintf(err, errSize, "CreateShaderResourceView failed:\n%s", path);
        tex->Release();
        return false;
    }
    tex->Release();

    ctx->GenerateMips(out.srv);
    out.width  = w;
    out.height = h;
    return true;
}
