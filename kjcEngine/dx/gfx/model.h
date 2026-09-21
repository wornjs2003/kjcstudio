// FBX 를 읽어 GPU 가 쓸 수 있는 모양으로 바꾼다.
//
// 읽는 일은 ufbx 가 한다 (third_party/ufbx.h · MIT).
// Blender 와 Godot 이 자기 FBX 임포터를 이것으로 바꿨을 만큼 정확하고,
// 소스가 한 파일이라 빌드에 얹기만 하면 된다.

#pragma once

#include <windows.h>
#include <d3d11.h>
#include <DirectXMath.h>
#include <vector>

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

    // 이 정점 둘레가 오목한지 볼록한지. 이웃 정점이 법선 쪽으로 몰려 있으면
    // 양수(오목 — 콧방울 옆·입꼬리·주름), 반대로 퍼져 있으면 음수(볼록).
    // 모델을 읽을 때 한 번만 재 두면 실시간 비용이 없다.
    // 마모셋에서 Cavity 라고 부르는 그것이다
    float cav;

    // 이 정점에 주변 빛이 얼마나 드나. 1 = 훤히 열림, 0 = 꽉 막힘.
    // 정점에서 사방으로 광선을 쏴 제 메시에 막히는 비율을 센다.
    // Cavity 가 바로 옆만 보는 것과 달리 이쪽은 형상 전체를 본다 —
    // 턱 아래 · 귀 뒤 · 목처럼 멀리 있는 것에 가려지는 자리를 잡는다
    float ao;
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

    // AO 를 다시 구우려면 정점과 삼각형을 CPU 쪽에도 들고 있어야 한다.
    // 이 모델 기준 약 1MB — GPU 로 올린 뒤 버리면 다시 굽지 못한다
    std::vector<Vertex>   verts;
    std::vector<uint32_t> idx;
    float targetHeight  = 2.0f;   // 맞춰 놓은 높이. 광선 길이를 여기 견준다
    float aoRadius      = 0.18f;  // 광선을 이 높이의 몇 배까지 쏘나

    void Release() {
        if (ib) { ib->Release(); ib = nullptr; }
        if (vb) { vb->Release(); vb = nullptr; }
        indexCount = 0;
    }
};

// 한 씬에서 나온 메시들을 같은 자리에 놓으려면 변환이 하나여야 한다.
// 얼굴을 먼저 읽어 이것을 받아 두고, 나머지는 그것을 그대로 쓴다 —
// 메시마다 따로 가운데를 맞추면 눈썹이 코앞에 떠 버린다
struct Align {
    float scale = 1.0f;
    DirectX::XMFLOAT3 sub = { 0.0f, 0.0f, 0.0f };   // 좌표에서 빼는 값
    bool  valid = false;                            // false 면 이번에 정한다
};

// FBX 를 읽어 정점·인덱스 버퍼를 만든다.
//
//   targetHeight   이 높이가 되도록 크기를 맞춘다. 바닥(y=0)에 세우고
//                  가로 한가운데를 원점에 둔다
//   실패하면       false 를 돌리고 err 에 이유를 적는다
//   radial         ao 자리에 「메시 한가운데에서 얼마나 바깥인가」를 넣는다
//                  (0 = 한가운데, 1 = 가장 바깥). 헤어에서 안쪽 가닥을
//                  가려내는 데 쓴다 — 광선을 쏘는 것보다 훨씬 싸다
//   bakeAO         정점마다 광선을 쏴 가림 정도를 굽는다. 정점이 많으면
//                  몇 분씩 걸리므로, 털 가닥처럼 얻는 것이 적은 메시는 끈다
//   align          nullptr 이 아니면 — valid 일 때 그 변환을 쓰고,
//                  아닐 때는 이번에 정한 값을 채워 돌려준다
bool LoadFBX(ID3D11Device* dev, const char* path, float targetHeight,
             Model& out, char* err, size_t errSize,
             bool bakeAO = true, Align* align = nullptr, bool radial = false);

// 버텍스 AO 를 다른 범위로 다시 굽고 GPU 버퍼를 갈아끼운다.
// 정점 수에 비례해 시간이 걸리므로 (이 모델은 몇 초) 값을 바꿀 때마다가 아니라
// 다 정한 뒤 한 번만 부른다
void RebakeAO(ID3D11DeviceContext* ctx, Model& m, float radiusScale);
