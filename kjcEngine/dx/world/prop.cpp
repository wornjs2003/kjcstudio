#include "world/prop.h"
#include "world/terrain.h"
#include "gfx/model.h"

#include <cmath>

using namespace DirectX;

namespace {

// 놓을 것 하나하나. 지금은 코드로 만드는 상자뿐이라 크기와 자리만 있다.
// FBX 를 읽게 되면 여기에 파일 이름이 붙는다
struct Prop {
    float x, z;        // 어디에
    float yaw;         // 어느 쪽을 보게
    float w, h, d;     // 크기 (m)
    float color[4];
    ID3D11Buffer* vb;
};

// 판 가장자리에 기둥 둘. 배경이 비어 있으면 움직임이 얼마나 되는지
// 가늠이 안 돼서, 서 있는 것을 놓아 둔다
Prop g_props[] = {
    { -0.85f,  0.85f, 0.0f, 0.10f, 0.45f, 0.10f, { 0.38f, 0.40f, 0.44f, 1.0f }, nullptr },
    {  0.85f, -0.85f, 0.6f, 0.10f, 0.30f, 0.10f, { 0.38f, 0.40f, 0.44f, 1.0f }, nullptr },
};
const int N = (int)(sizeof(g_props) / sizeof(g_props[0]));

// 상자 하나를 정점 36개로. 면마다 법선이 달라야 해서 꼭짓점을 공유하지 않는다
void BuildBox(Vertex* v, float w, float h, float d) {
    const float x = w * 0.5f, z = d * 0.5f;
    struct Face { XMFLOAT3 a, b, c, dd; XMFLOAT3 n; };
    const Face f[6] = {
        { {-x,0,-z},{-x,h,-z},{ x,h,-z},{ x,0,-z}, { 0, 0,-1} },   // 앞
        { { x,0, z},{ x,h, z},{-x,h, z},{-x,0, z}, { 0, 0, 1} },   // 뒤
        { {-x,0, z},{-x,h, z},{-x,h,-z},{-x,0,-z}, {-1, 0, 0} },   // 왼
        { { x,0,-z},{ x,h,-z},{ x,h, z},{ x,0, z}, { 1, 0, 0} },   // 오른
        { {-x,h,-z},{-x,h, z},{ x,h, z},{ x,h,-z}, { 0, 1, 0} },   // 위
        { {-x,0, z},{-x,0,-z},{ x,0,-z},{ x,0, z}, { 0,-1, 0} },   // 아래
    };
    int n = 0;
    for (const Face& q : f) {
        v[n++] = { q.a, q.n };  v[n++] = { q.b, q.n };  v[n++] = { q.c, q.n };
        v[n++] = { q.a, q.n };  v[n++] = { q.c, q.n };  v[n++] = { q.dd, q.n };
    }
}

} // namespace

bool PropInit(ID3D11Device* dev) {
    for (Prop& p : g_props) {
        Vertex v[36] = {};
        BuildBox(v, p.w, p.h, p.d);

        D3D11_BUFFER_DESC bd = {};
        bd.Usage     = D3D11_USAGE_DEFAULT;
        bd.ByteWidth = sizeof(v);
        bd.BindFlags = D3D11_BIND_VERTEX_BUFFER;
        D3D11_SUBRESOURCE_DATA sr = { v, 0, 0 };
        if (FAILED(dev->CreateBuffer(&bd, &sr, &p.vb))) p.vb = nullptr;
    }
    return true;      // 하나쯤 못 만들어도 게임은 돈다
}

int PropCount() { return N; }

ID3D11Buffer* PropVB(int i)          { return (i >= 0 && i < N) ? g_props[i].vb : nullptr; }
UINT          PropVertexCount(int i) { return 36; }
const float*  PropColor(int i)       { return g_props[i].color; }

XMMATRIX PropWorld(int i) {
    const Prop& p = g_props[i];
    // 바닥 높이를 물어본다. 터레인에 높낮이가 생기면 저절로 따라 올라간다
    float y = TerrainHeightAt(p.x, p.z);
    return XMMatrixRotationY(p.yaw) * XMMatrixTranslation(p.x, y, p.z);
}

void PropShutdown() {
    for (Prop& p : g_props)
        if (p.vb) { p.vb->Release(); p.vb = nullptr; }
}
