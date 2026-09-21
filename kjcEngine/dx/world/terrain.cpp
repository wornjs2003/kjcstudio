#include "world/terrain.h"
#include "gfx/model.h"       // Vertex — 화면에 그리는 모든 것이 쓰는 정점 모양

namespace {

const float PLATE   = 2.0f;   // 바닥판 한 변 — 2 m
const float COLOR[4] = { 0.306f, 0.349f, 0.408f, 1.0f };   // #4e5968 — 지시: 회색

ID3D11Buffer* g_vb = nullptr;

} // namespace

float TerrainSize() { return PLATE; }
float TerrainHalf() { return PLATE * 0.5f; }

float TerrainHeightAt(float, float) {
    // 지금은 평평하다. 높낮이가 생기면 여기만 고치면 되고,
    // 물어보는 쪽(몬스터·플레이어)은 그대로 둔다
    return 0.0f;
}

bool TerrainInit(ID3D11Device* dev) {
    const float h = PLATE * 0.5f;
    const DirectX::XMFLOAT3 up = { 0, 1, 0 };
    Vertex v[6] = {};
    v[0] = { {-h, 0.0f, -h}, up };
    v[1] = { {-h, 0.0f,  h}, up };
    v[2] = { { h, 0.0f,  h}, up };
    v[3] = { {-h, 0.0f, -h}, up };
    v[4] = { { h, 0.0f,  h}, up };
    v[5] = { { h, 0.0f, -h}, up };

    D3D11_BUFFER_DESC bd = {};
    bd.Usage     = D3D11_USAGE_DEFAULT;
    bd.ByteWidth = sizeof(v);
    bd.BindFlags = D3D11_BIND_VERTEX_BUFFER;
    D3D11_SUBRESOURCE_DATA sr = { v, 0, 0 };
    return SUCCEEDED(dev->CreateBuffer(&bd, &sr, &g_vb));
}

ID3D11Buffer* TerrainVB()          { return g_vb; }
UINT          TerrainVertexCount() { return 6; }
const float*  TerrainColor()       { return COLOR; }

void TerrainShutdown() {
    if (g_vb) { g_vb->Release(); g_vb = nullptr; }
}
