// 터레인 — 모두가 올라서 있는 바닥.
//
// 안 움직이고, 그림자를 받고, 플레이어와 몬스터가 나갈 수 없는 경계다.
// 지금은 평평한 네모 한 장이지만 나중에 높낮이가 생길 자리다.
//
// 「몬스터가 판 밖으로 안 나간다」 같은 규칙이 여기 반경을 물어보고 정해진다 —
// 그래서 크기를 상수로 박지 않고 이쪽에 물어보게 둔다.

#pragma once

#include <windows.h>
#include <d3d11.h>

// 한 변의 길이 (m)
float TerrainSize();

// 한가운데에서 가장자리까지 (m). 판 밖으로 안 나가게 할 때 쓴다
float TerrainHalf();

// 바닥 높이. 지금은 어디서나 0 이지만, 높낮이가 생기면 자리를 받는 꼴이 된다
float TerrainHeightAt(float x, float z);

// 그릴 것을 마련한다. 실패하면 false
bool TerrainInit(ID3D11Device* dev);

// 그리는 데 필요한 것 — 정점 버퍼와 색.
// 그리는 일 자체는 밖에서 한다. 렌더링 방식을 터레인이 알 필요가 없다
ID3D11Buffer* TerrainVB();
UINT          TerrainVertexCount();
const float*  TerrainColor();

void TerrainShutdown();
