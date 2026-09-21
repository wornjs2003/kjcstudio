// 플레이어 — 재권님이 조작하는 것.
//
// 바닥을 누르면 그리로 걸어가고, 몬스터를 누르면 쫓아가 닿는 순간 한 번 뛴다.
// 뜀이 끝나면 그 몬스터가 사라진다. 화살표로는 제자리에서 돈다.
//
// **메시는 이 파일이 들고 있지 않다.** 얼굴·눈썹·속눈썹·눈알 둘·헤어가
// 한 덩어리로 움직이는데, 그것을 읽고 그리는 것은 렌더링 쪽 일이다.
// 여기는 「어디에 서서 어느 쪽을 보고 있나」만 안다.

#pragma once

#include <DirectXMath.h>

void PlayerInit();

// 한 프레임 굴린다. 걸어가고, 방향을 틀고, 닿았으면 뛴다.
//
// 이번 프레임에 **잡은 몬스터 번호**를 돌려준다 (없으면 -1).
// 화면이 흔들리고 번쩍이는 것은 그것을 받은 쪽이 켠다 — 그건 연출이지
// 게임 규칙이 아니라서 여기 두지 않는다
int PlayerUpdate(float dt);

// 바닥의 한 점으로 간다
void PlayerMoveTo(float x, float z);

// 그 몬스터를 쫓는다. -1 이면 쫓기를 그만둔다
void PlayerChase(int monster);
int  PlayerChasing();

// 제자리에서 돌린다 (라디안). 화살표 한 번에 부르는 값이다
void PlayerTurn(float radians);

void  PlayerAt(float& x, float& z);
float PlayerFacing();

// 바닥에서 띄운 높이. 붙여 두면 발치가 판에 파묻힌다
float PlayerLift();

// 지금 놓인 자리와 방향을 행렬로. 뛰는 중이면 그만큼 올라가 있다.
//
// **그리는 쪽과 그림자 쪽이 같은 값을 써야 한다** — 한 치라도 어긋나면
// 「깊이가 같을 때만」 판정이 빗나가 헤어가 사라진다
DirectX::XMMATRIX PlayerWorld();
