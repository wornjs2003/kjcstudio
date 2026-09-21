// 몬스터 — 화면에 늘 정해진 수만큼 떠 있는 빨간 세모.
//
// 스스로 나고, 조금씩 떠돌고, 플레이어가 닿으면 사라지고, 잠시 뒤 다시 난다.
// 플레이어와 달리 입력을 받지 않는다.
//
// 이 파일은 **자리와 때만** 다룬다. 메시를 만들고 그리는 것은 밖에서 한다 —
// 그래야 게임 규칙이 렌더링 코드에 묶이지 않는다.

#pragma once

// 화면에 늘 있어야 하는 개수
int MonsterCount();

// 크기. 판 가장자리를 넘지 않게 자리를 고를 때 쓴다
float MonsterSize();

// 플레이어가 이만큼 안에 들면 닿은 것으로 본다
float MonsterReach();

// 판 위에 처음 흩어 놓는다. halfExtent 는 판 반쪽 길이(m)
void MonsterInit(float halfExtent, float playerX, float playerZ);

// 한 프레임 굴린다 — 살아 있는 것은 옮기고, 죽은 것은 다시 날 때를 센다.
//
// 플레이어 자리를 받는 것은 두 가지 때문이다.
//   날 때    플레이어 바로 옆에 나지 않게 떨어뜨린다
//   걸을 때  플레이어 쪽으로 다가가는 걸음은 버린다
void MonsterUpdate(float dt, float halfExtent, float playerX, float playerZ);

bool MonsterAlive(int i);
void MonsterAt(int i, float& x, float& z);

// 닿아서 사라진다. 잠시 뒤 저절로 다시 난다
void MonsterKill(int i);

// 그 자리에서 가장 가까운 것을 고른다. 없으면 -1.
// 플레이어가 바닥을 눌렀을 때 무엇을 쫓을지 정하는 데 쓴다
int MonsterNearest(float x, float z, float within);
