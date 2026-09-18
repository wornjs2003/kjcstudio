// FBX 를 읽어 GPU 가 쓸 수 있는 모양으로 바꾼다.
//
// 읽는 일은 ufbx 가 한다 (third_party/ufbx.h · MIT).
// Blender 와 Godot 이 자기 FBX 임포터를 이것으로 바꿨을 만큼 정확하고,
// 소스가 한 파일이라 빌드에 얹기만 하면 된다.

#pragma once

#include <windows.h>
#include <d3d11.h>
#include <DirectXMath.h>

// 화면에 그리는 모든 것이 쓰는 정점 모양.
// uv 는 지금(1단계)은 안 쓰지만 자리를 미리 비워 둔다 — 2단계에서 텍스처를
// 붙일 때 이 구조가 바뀌면 큐브·판·세모·축을 전부 고쳐야 하기 때문이다
struct Vertex {
    DirectX::XMFLOAT3 pos;
    DirectX::XMFLOAT3 nrm;
    // xyz = 탄젠트(가로 방향), w = 세로 방향의 부호.
    // 노말맵은 「면을 기준으로 한 방향」으로 적혀 있어서, 그것을 월드 방향으로
    // 옮기려면 면 위의 가로·세로 축이 필요하다. 그 가로축이 탄젠트다.
    // w 가 있는 이유는 UV 를 거울처럼 뒤집어 쓴 자리 때문이다 — 그런 곳은
    // 세로축이 반대로 뒤집힌다
    DirectX::XMFLOAT4 tan;
    DirectX::XMFLOAT2 uv;
};

struct Model {
    ID3D11Buffer* vb    = nullptr;
    ID3D11Buffer* ib    = nullptr;
    UINT indexCount     = 0;

    // 읽어들인 뒤 잰 값. 원본이 어떤 크기로 만들어졌든 화면에 맞추려고 쓴다
    float rawHeight     = 0.0f;   // 원래 높이 (모델 단위)
    float scale         = 1.0f;   // 적용한 배율
    size_t srcVertices  = 0;      // 삼각형으로 펼친 뒤의 정점 수
    size_t outVertices  = 0;      // 겹치는 것을 합친 뒤의 정점 수

    void Release() {
        if (ib) { ib->Release(); ib = nullptr; }
        if (vb) { vb->Release(); vb = nullptr; }
        indexCount = 0;
    }
};

// FBX 를 읽어 정점·인덱스 버퍼를 만든다.
//
//   targetHeight   이 높이가 되도록 크기를 맞춘다. 바닥(y=0)에 세우고
//                  가로 한가운데를 원점에 둔다
//   실패하면       false 를 돌리고 err 에 이유를 적는다
bool LoadFBX(ID3D11Device* dev, const char* path, float targetHeight,
             Model& out, char* err, size_t errSize);
