// 이미지 파일을 읽어 GPU 텍스처로 만든다.
//
// 읽는 일은 stb_image 가 한다 (third_party/stb_image.h · 퍼블릭 도메인).
// JPG · PNG · TGA · HDR 을 다 읽어서, 재권님 텍스처(JPG)와
// 나중에 쓸 환경맵(HDR)을 같은 길로 다룰 수 있다.

#pragma once

#include <windows.h>
#include <d3d11.h>

struct Texture {
    ID3D11ShaderResourceView* srv = nullptr;
    int width = 0, height = 0;

    void Release() {
        if (srv) { srv->Release(); srv = nullptr; }
    }
};

// 이미지를 읽어 셰이더가 쓸 수 있는 텍스처로 만든다.
//
//   srgb   색으로 쓰는 그림(albedo)은 true.
//          숫자로 쓰는 그림(노말·거칠기)은 false — 아래 설명 참조
//   실패하면 false 를 돌리고 err 에 이유를 적는다
//
// sRGB 를 가르는 이유 — 사진이나 색 텍스처는 눈에 맞춰 밝기가 굽어 있다.
// GPU 에게 sRGB 라고 알려주면 읽을 때 그 굽은 것을 펴 준다. 반면 노말맵의
// 값은 색이 아니라 방향 숫자라서, 펴 버리면 방향이 틀어진다
bool LoadTexture(ID3D11Device* dev, ID3D11DeviceContext* ctx,
                 const char* path, bool srgb,
                 Texture& out, char* err, size_t errSize);
