#include "world/player.h"
#include "world/monster.h"

#include <cmath>

using namespace DirectX;

namespace {

const float SPEED = 0.8f;    // 초당 0.8 m — 걷는 빠르기쯤
const float TURN  = 9.0f;    // 정면을 트는 빠르기 (초당 라디안)
const float LIFT  = 0.1f;    // 바닥에서 띄우는 높이

// 닿으면 한 번 뛴다. 이 뜀이 끝나는 순간 몬스터가 사라진다 —
// 지시로 「1초 기다렸다 사라진다」를 걷어내고 이 동작으로 바꿨다
const float HOP_TIME   = 0.347f; // 뛰어올랐다 내려오기까지 — 지시로 0.52 에서 1.5배 빠르게
const float HOP_HEIGHT = 0.10f;  // 10 cm 뛴다
const float HOP_WOBBLE = 0.02f;  // 뛰는 동안 2 cm 떤다

const float PI_F  = 3.14159265358979f;
const float TWO_PI = PI_F * 2.0f;

float g_x = 0.0f, g_z = 0.0f;      // 지금 자리
float g_tx = 0.0f, g_tz = 0.0f;    // 가려는 자리
float g_facing = 0.0f;             // 정면이 향한 쪽
int   g_chase  = -1;               // 쫓고 있는 몬스터. 없으면 -1
float g_hop    = 0.0f;             // 뜀이 시작된 뒤 흐른 시간. 0 이면 안 뛰는 중

} // namespace

void PlayerInit() {
    g_x = g_z = g_tx = g_tz = 0.0f;
    g_facing = 0.0f;
    g_chase  = -1;
    g_hop    = 0.0f;
}

void PlayerMoveTo(float x, float z) {
    g_tx = x; g_tz = z;
    g_chase = -1;
    g_hop   = 0.0f;
}

void PlayerChase(int monster) {
    g_chase = monster;
    g_hop   = 0.0f;
    if (monster >= 0) MonsterAt(monster, g_tx, g_tz);
}

int   PlayerChasing()  { return g_chase; }
float PlayerFacing()   { return g_facing; }
float PlayerLift()     { return LIFT; }

void PlayerTurn(float radians) { g_facing += radians; }

void PlayerAt(float& x, float& z) { x = g_x; z = g_z; }

int PlayerUpdate(float dt) {
    int killed = -1;

    // ── 쫓는 중이면 목표를 다시 겨눈다 ──
    // 몬스터가 옮겨 다니므로 매 프레임 자리를 고쳐 잡는다.
    // 이미 닿아 있으면 그 자리에 서서 셈을 이어간다
    if (g_chase >= 0 && MonsterAlive(g_chase)) {
        float mx, mz;
        MonsterAt(g_chase, mx, mz);
        float ex = g_x - mx, ez = g_z - mz;
        if (sqrtf(ex * ex + ez * ez) <= MonsterReach()) {
            g_tx = g_x;                    // 닿았으니 더 다가가지 않는다
            g_tz = g_z;
            g_hop += dt;                   // 뛰기 시작한다
            if (g_hop >= HOP_TIME) {       // 내려앉는 순간 몬스터가 사라진다
                killed = g_chase;
                MonsterKill(g_chase);
                g_chase = -1;
                g_hop   = 0.0f;
            }
        } else {
            g_tx  = mx;                    // 옮겨간 자리로 다시 겨눈다
            g_tz  = mz;
            g_hop = 0.0f;                  // 멀어졌으면 뜀을 물린다
        }
    } else {
        g_chase = -1;                      // 쫓던 것이 없어졌다
        g_hop   = 0.0f;
    }

    // ── 목표를 향해 한 걸음 ──
    // 남은 거리가 한 걸음보다 짧으면 딱 붙이고 멈춘다 — 이 처리가 없으면
    // 목표를 지나쳤다 돌아오길 되풀이하며 떤다
    float dx = g_tx - g_x, dz = g_tz - g_z;
    float dist = sqrtf(dx * dx + dz * dz);
    float step = SPEED * dt;
    if (dist <= step) {
        g_x = g_tx;
        g_z = g_tz;
    } else {
        g_x += dx / dist * step;
        g_z += dz / dist * step;
    }

    // 가는 쪽으로 정면을 튼다. 한 번에 홱 돌지 않고 조금씩 돌린다
    if (dist > 0.001f) {
        float want = atan2f(dx, dz);        // 제 몸의 +Z 가 정면이다
        float diff = want - g_facing;
        // 가까운 쪽으로 돈다. 350도를 도는 대신 반대로 10도만 돌게 한다
        while (diff >  PI_F) diff -= TWO_PI;
        while (diff < -PI_F) diff += TWO_PI;
        float turn = TURN * dt;
        if (fabsf(diff) <= turn) g_facing = want;
        else                     g_facing += (diff > 0.0f ? turn : -turn);
    }

    return killed;
}

XMMATRIX PlayerWorld() {
    float cx = g_x, cy = LIFT, cz = g_z;
    if (g_hop > 0.0f) {
        float t = g_hop / HOP_TIME;
        if (t > 1.0f) t = 1.0f;
        cy += HOP_HEIGHT * 4.0f * t * (1.0f - t);
        // 주기를 4번과 3번으로 어긋나게 둬서 같은 자리를 되풀이하지 않게 한다
        cx += HOP_WOBBLE * sinf(t * TWO_PI * 4.0f);
        cz += HOP_WOBBLE * cosf(t * TWO_PI * 3.0f);
    }
    // 정면이 향한 쪽으로 돌려 세운 다음 제자리로 옮긴다. 순서가 반대면
    // 원점을 중심으로 빙 도는 모양이 된다
    return XMMatrixRotationY(g_facing) * XMMatrixTranslation(cx, cy, cz);
}
