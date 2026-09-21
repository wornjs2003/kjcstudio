// 배경 오브젝트 — 놓여 있기만 한 것.
//
// 플레이어·몬스터와 달리 스스로 움직이지 않고, 터레인과 달리 부딪히지도
// 않는다. 그냥 거기 서서 화면을 채운다.
//
//   Player   입력을 받는다        Monster  스스로 움직인다
//   Terrain  부딪힌다             Prop     아무것도 안 한다
//
// 그래서 다루기가 가장 쉽다 — 자리와 메시만 있으면 된다.
// 나중에 FBX 를 주면 아래 목록에 한 줄 더하면 그대로 얹힌다.

#pragma once

#include <windows.h>
#include <d3d11.h>
#include <DirectXMath.h>

// 놓을 것들을 마련한다. 메시를 못 읽은 것은 조용히 건너뛴다 —
// 배경이 하나 빠졌다고 게임이 멈출 이유가 없다
bool PropInit(ID3D11Device* dev);

int  PropCount();

// 그리는 데 필요한 것. 그리는 일 자체는 밖에서 한다
ID3D11Buffer*     PropVB(int i);
UINT              PropVertexCount(int i);
DirectX::XMMATRIX PropWorld(int i);
const float*      PropColor(int i);

void PropShutdown();
