#include "world/monster.h"

#include <cmath>
#include <cstdlib>

namespace {

const int   TRI_N     = 2;     // 화면에 늘 있어야 하는 개수 — 지시: 2개
const float TRI_SIZE  = 0.12f; // 12 cm
const float TRI_GAP   = 0.25f; // 25 cm 는 떨어져 난다
const float REACH     = 0.20f; // 20 cm 안에 들면 닿은 것으로 본다
const float BORN_WAIT = 1.0f;  // 사라지고 나서 새로 나기까지 — 지시: 1초

// 가만히 있지 않고 조금씩 옮겨 다닌다
const float DRIFT_MIN   = 1.0f;  // 다음 걸음까지 기다리는 시간 — 지시: 1~2초
const float DRIFT_MAX   = 2.0f;
const float DRIFT_STEP  = 0.15f; // 한 걸음에 15 cm
const float DRIFT_SPEED = 0.3f;  // 초당 30 cm. 플레이어보다 느리다

const float TWO_PI = 6.28318530718f;

struct Tri {
    float x, z;        // 지금 자리
    float tx, tz;      // 옮겨가는 중인 자리
    bool  alive;
    float wait;        // 사라진 뒤 다시 나기까지 남은 시간
    float drift;       // 다음 걸음을 고르기까지 남은 시간
};

Tri g_tri[TRI_N] = {};

float Rand01() { return rand() / (float)RAND_MAX; }

// 판 안에서 자리를 하나 고른다. 플레이어와도, 다른 몬스터와도 떨어뜨린다
void Spawn(int i, float halfExtent, float px, float pz) {
    const float half = halfExtent - TRI_SIZE;   // 판 밖으로 삐져나가지 않게

    for (int attempt = 0; attempt < 200; ++attempt) {
        float x = (Rand01() * 2.0f - 1.0f) * half;
        float z = (Rand01() * 2.0f - 1.0f) * half;

        float dxc = x - px, dzc = z - pz;
        if (sqrtf(dxc * dxc + dzc * dzc) < TRI_GAP) continue;   // 플레이어와 겹친다

        bool clash = false;
        for (int j = 0; j < TRI_N; ++j) {
            if (j == i || !g_tri[j].alive) continue;
            float dx = x - g_tri[j].x, dz = z - g_tri[j].z;
            if (sqrtf(dx * dx + dz * dz) < TRI_GAP) { clash = true; break; }
        }
        if (clash) continue;

        g_tri[i].x = g_tri[i].tx = x;
        g_tri[i].z = g_tri[i].tz = z;
        g_tri[i].alive = true;
        g_tri[i].drift = DRIFT_MIN + Rand01() * (DRIFT_MAX - DRIFT_MIN);
        return;
    }

    // 200번을 고르고도 빈자리가 없으면 판이 꽉 찬 것이다. 겹치게 두느니
    // 조금 더 기다렸다 다시 고른다 — 플레이어가 움직이면 자리가 난다
    g_tri[i].wait = 0.2f;
}

// 제자리 둘레에서 한 걸음 갈 자리를 고른다. 판 밖으로는 나가지 않는다
void PickDrift(int i, float halfExtent, float px, float pz) {
    const float half = halfExtent - TRI_SIZE;

    for (int attempt = 0; attempt < 40; ++attempt) {
        float ang = Rand01() * TWO_PI;
        float len = DRIFT_STEP * (0.35f + Rand01() * 0.65f);   // 너무 안 움직이지 않게
        float x = g_tri[i].x + cosf(ang) * len;
        float z = g_tri[i].z + sinf(ang) * len;

        if (x < -half || x > half || z < -half || z > half) continue;   // 판 밖이다

        // 지금보다 플레이어에 가까워지는 걸음은 버린다 — 지시: 「가까이
        // 다가가진 않는다」. 절대 거리로 막지 않는 것은, 그러면 플레이어가 올 때마다
        // 물러나는 셈이 되어 영영 못 잡기 때문이다. 스스로 다가가지만 않는다
        float nowX = g_tri[i].x - px, nowZ = g_tri[i].z - pz;
        float newX = x - px,          newZ = z - pz;
        if (sqrtf(newX * newX + newZ * newZ) < sqrtf(nowX * nowX + nowZ * nowZ))
            continue;

        bool clash = false;
        for (int j = 0; j < TRI_N; ++j) {
            if (j == i || !g_tri[j].alive) continue;
            float dx = x - g_tri[j].x, dz = z - g_tri[j].z;
            if (sqrtf(dx * dx + dz * dz) < TRI_GAP) { clash = true; break; }
        }
        if (clash) continue;

        g_tri[i].tx = x;
        g_tri[i].tz = z;
        g_tri[i].drift = DRIFT_MIN + Rand01() * (DRIFT_MAX - DRIFT_MIN);
        return;
    }

    // 갈 곳이 없으면 제자리에 두고 곧 다시 고른다
    g_tri[i].tx = g_tri[i].x;
    g_tri[i].tz = g_tri[i].z;
    g_tri[i].drift = 0.3f;
}

} // namespace

int   MonsterCount() { return TRI_N; }
float MonsterSize()  { return TRI_SIZE; }
float MonsterReach() { return REACH; }

void MonsterInit(float halfExtent, float playerX, float playerZ) {
    for (int i = 0; i < TRI_N; ++i) Spawn(i, halfExtent, playerX, playerZ);
}

void MonsterUpdate(float dt, float halfExtent, float px, float pz) {
    for (int i = 0; i < TRI_N; ++i) {
        if (!g_tri[i].alive) {
            // 사라진 것은 때가 되면 다시 난다
            g_tri[i].wait -= dt;
            if (g_tri[i].wait <= 0.0f) Spawn(i, halfExtent, px, pz);
            continue;
        }

        float dx = g_tri[i].tx - g_tri[i].x;
        float dz = g_tri[i].tz - g_tri[i].z;
        float d  = sqrtf(dx * dx + dz * dz);
        float s  = DRIFT_SPEED * dt;
        if (d <= s) {
            g_tri[i].x = g_tri[i].tx;
            g_tri[i].z = g_tri[i].tz;
        } else {
            g_tri[i].x += dx / d * s;
            g_tri[i].z += dz / d * s;
        }

        g_tri[i].drift -= dt;
        if (g_tri[i].drift <= 0.0f) PickDrift(i, halfExtent, px, pz);
    }
}

bool MonsterAlive(int i) {
    return (i >= 0 && i < TRI_N) && g_tri[i].alive;
}

void MonsterAt(int i, float& x, float& z) {
    if (i < 0 || i >= TRI_N) { x = z = 0.0f; return; }
    x = g_tri[i].x;
    z = g_tri[i].z;
}

void MonsterKill(int i) {
    if (i < 0 || i >= TRI_N) return;
    g_tri[i].alive = false;
    g_tri[i].wait  = BORN_WAIT;
}

int MonsterNearest(float x, float z, float within) {
    int   best = -1;
    float bestD = within;
    for (int i = 0; i < TRI_N; ++i) {
        if (!g_tri[i].alive) continue;
        float dx = x - g_tri[i].x, dz = z - g_tri[i].z;
        float d = sqrtf(dx * dx + dz * dz);
        if (d < bestD) { bestD = d; best = i; }
    }
    return best;
}
