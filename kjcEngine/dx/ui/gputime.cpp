#include "ui/gputime.h"

namespace {

const int MAX_MARKS  = 24;
const int FRAMES     = 3;     // 이만큼 늦게 읽는다. GPU 를 세우지 않으려면 필요하다

struct FrameQ {
    ID3D11Query*   disjoint = nullptr;
    ID3D11Query*   ts[MAX_MARKS + 1] = {};   // 시작 한 번 + 마크마다 하나
    int            count = 0;
    const wchar_t* names[MAX_MARKS] = {};
    bool           pending = false;          // 거둘 것이 들어 있나
};

ID3D11Device*        g_dev = nullptr;
ID3D11DeviceContext* g_ctx = nullptr;
FrameQ g_q[FRAMES];
int    g_cur = 0;

// 거둔 값
int            g_n = 0;
const wchar_t* g_names[MAX_MARKS] = {};
float          g_ms[MAX_MARKS] = {};
float          g_total = 0.0f;

} // namespace

bool GpuTimeInit(ID3D11Device* dev, ID3D11DeviceContext* ctx) {
    g_dev = dev; g_ctx = ctx;

    D3D11_QUERY_DESC dj = { D3D11_QUERY_TIMESTAMP_DISJOINT, 0 };
    D3D11_QUERY_DESC tq = { D3D11_QUERY_TIMESTAMP,          0 };
    for (int f = 0; f < FRAMES; ++f) {
        if (FAILED(dev->CreateQuery(&dj, &g_q[f].disjoint))) return false;
        for (int i = 0; i <= MAX_MARKS; ++i)
            if (FAILED(dev->CreateQuery(&tq, &g_q[f].ts[i]))) return false;
    }
    return true;
}

void GpuTimeBeginFrame() {
    if (!g_ctx) return;
    FrameQ& q = g_q[g_cur];
    q.count = 0;
    g_ctx->Begin(q.disjoint);
    g_ctx->End(q.ts[0]);          // 프레임이 시작된 시각
}

void GpuTimeMark(const wchar_t* name) {
    if (!g_ctx) return;
    FrameQ& q = g_q[g_cur];
    if (q.count >= MAX_MARKS) return;
    q.names[q.count] = name;
    g_ctx->End(q.ts[q.count + 1]);
    ++q.count;
}

void GpuTimeEndFrame() {
    if (!g_ctx) return;
    FrameQ& q = g_q[g_cur];
    g_ctx->End(q.disjoint);
    q.pending = true;

    // 가장 오래된 것을 거둔다. 그쯤이면 GPU 가 지나갔다
    g_cur = (g_cur + 1) % FRAMES;
    FrameQ& old = g_q[g_cur];
    if (!old.pending) return;

    D3D11_QUERY_DATA_TIMESTAMP_DISJOINT dj = {};
    if (g_ctx->GetData(old.disjoint, &dj, sizeof(dj), 0) != S_OK) return;
    old.pending = false;
    // Disjoint 는 재는 동안 GPU 시계가 흔들렸다는 뜻이다. 그 프레임은 버린다
    if (dj.Disjoint || dj.Frequency == 0) return;

    UINT64 prev = 0;
    if (g_ctx->GetData(old.ts[0], &prev, sizeof(prev), 0) != S_OK) return;

    // 먼저 전부 읽어 본다. 한 자리라도 어그러지면 그 프레임은 통째로 버린다 —
    // 반쯤 섞으면 터무니없는 값이 평균에 남아 오래 간다
    UINT64 t[MAX_MARKS] = {};
    for (int i = 0; i < old.count; ++i)
        if (g_ctx->GetData(old.ts[i + 1], &t[i], sizeof(UINT64), 0) != S_OK) return;

    float ms[MAX_MARKS] = {};
    float total = 0.0f;
    for (int i = 0; i < old.count; ++i) {
        // 뒤 시각이 앞보다 이르면 뺄셈이 한 바퀴 돌아 거대한 값이 된다.
        // GPU 가 순서를 바꿔 실행하거나 쿼리가 덜 여물면 그렇게 나온다
        if (t[i] < prev) return;
        ms[i] = (float)((double)(t[i] - prev) * 1000.0 / (double)dj.Frequency);
        if (ms[i] > 1000.0f) return;       // 한 패스에 1초는 잰 것이 아니다
        prev = t[i];
        total += ms[i];
    }

    static bool first = true;
    for (int i = 0; i < old.count; ++i) {
        g_names[i] = old.names[i];
        // 한 장씩은 심하게 튄다. 천천히 따라가게 두어야 읽을 수 있다.
        // 다만 첫 값은 그대로 받는다 — 0 에서 기어오르면 한참 틀린 값을 보인다
        g_ms[i] = first ? ms[i] : g_ms[i] + (ms[i] - g_ms[i]) * 0.1f;
        if (i + 1 > g_n) g_n = i + 1;
    }
    g_total = first ? total : g_total + (total - g_total) * 0.1f;
    first = false;
}

int            GpuTimeCount()      { return g_n; }
const wchar_t* GpuTimeName(int i)  { return (i >= 0 && i < g_n) ? g_names[i] : L""; }
float          GpuTimeMs(int i)    { return (i >= 0 && i < g_n) ? g_ms[i] : 0.0f; }
float          GpuTimeTotalMs()    { return g_total; }

void GpuTimeShutdown() {
    for (int f = 0; f < FRAMES; ++f) {
        if (g_q[f].disjoint) { g_q[f].disjoint->Release(); g_q[f].disjoint = nullptr; }
        for (int i = 0; i <= MAX_MARKS; ++i)
            if (g_q[f].ts[i]) { g_q[f].ts[i]->Release(); g_q[f].ts[i] = nullptr; }
    }
    g_n = 0;
    g_ctx = nullptr;
}
