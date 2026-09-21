#include "model.h"
#include "third_party/ufbx.h"

#include <vector>
#include <cstdio>
#include <cfloat>

using namespace DirectX;

static XMFLOAT3 F3(ufbx_vec3 v) { return XMFLOAT3((float)v.x, (float)v.y, (float)v.z); }
static XMFLOAT2 F2(ufbx_vec2 v) { return XMFLOAT2((float)v.x, (float)v.y); }

// ─── 버텍스 AO ─────────────────────────────────────────────────────────
// 정점마다 사방으로 광선을 쏴서 제 메시에 몇 개나 막히는지 센다.
// 마모셋에서 AO 를 굽는 것과 같은 방식이고, 모델을 읽을 때 한 번만 한다.

// 광선이 삼각형을 뚫는지 본다 (Möller–Trumbore).
// 나눗셈을 한 번만 쓰고 미리 자르는 검사가 많아 이 계열에서 가장 빠른 축이다
static bool RayTri(const XMFLOAT3& o, const XMFLOAT3& d,
                   const XMFLOAT3& a, const XMFLOAT3& b, const XMFLOAT3& c,
                   float maxT) {
    const float EPS = 1e-7f;
    float e1x = b.x - a.x, e1y = b.y - a.y, e1z = b.z - a.z;
    float e2x = c.x - a.x, e2y = c.y - a.y, e2z = c.z - a.z;

    float px = d.y * e2z - d.z * e2y;
    float py = d.z * e2x - d.x * e2z;
    float pz = d.x * e2y - d.y * e2x;
    float det = e1x * px + e1y * py + e1z * pz;
    if (fabsf(det) < EPS) return false;          // 광선이 삼각형과 나란하다

    float inv = 1.0f / det;
    float tx = o.x - a.x, ty = o.y - a.y, tz = o.z - a.z;
    float u = (tx * px + ty * py + tz * pz) * inv;
    if (u < 0.0f || u > 1.0f) return false;

    float qx = ty * e1z - tz * e1y;
    float qy = tz * e1x - tx * e1z;
    float qz = tx * e1y - ty * e1x;
    float v = (d.x * qx + d.y * qy + d.z * qz) * inv;
    if (v < 0.0f || u + v > 1.0f) return false;

    float t = (e2x * qx + e2y * qy + e2z * qz) * inv;
    return t > 1e-4f && t < maxT;
}

// 삼각형을 격자 칸에 나눠 담는다. 광선이 지나는 칸의 것만 보면 되므로
// 24,820개를 매번 다 훑지 않아도 된다
struct Grid {
    XMFLOAT3 lo{};
    float    cell = 1.0f;
    int      nx = 1, ny = 1, nz = 1;
    std::vector<std::vector<uint32_t>> bin;   // 칸마다 삼각형 번호

    int Index(int x, int y, int z) const { return (z * ny + y) * nx + x; }

    void Clamp(int& x, int& y, int& z) const {
        x = x < 0 ? 0 : (x >= nx ? nx - 1 : x);
        y = y < 0 ? 0 : (y >= ny ? ny - 1 : y);
        z = z < 0 ? 0 : (z >= nz ? nz - 1 : z);
    }
};

static void ComputeVertexAO(std::vector<Vertex>& v,
                            const std::vector<uint32_t>& idx,
                            float modelHeight, float radiusScale) {
    const size_t nv = v.size();
    const size_t nt = idx.size() / 3;
    if (nt == 0) return;

    // 얼마나 멀리까지 보고 가림으로 칠지. 모델 높이에 견주어 잡는다.
    // 길수록 어두워지는 자리가 넓어지고 전체도 조금 어두워진다 —
    // 멀리 있는 것에 막힐 확률이 함께 올라가기 때문이다
    const float RAY_LEN = modelHeight * radiusScale;
    const int   RAYS    = 16;

    // ── 격자를 만든다 ──
    XMFLOAT3 lo(FLT_MAX, FLT_MAX, FLT_MAX), hi(-FLT_MAX, -FLT_MAX, -FLT_MAX);
    for (const Vertex& x : v) {
        lo.x = min(lo.x, x.pos.x); hi.x = max(hi.x, x.pos.x);
        lo.y = min(lo.y, x.pos.y); hi.y = max(hi.y, x.pos.y);
        lo.z = min(lo.z, x.pos.z); hi.z = max(hi.z, x.pos.z);
    }

    Grid g;
    g.lo = XMFLOAT3(lo.x - 1e-3f, lo.y - 1e-3f, lo.z - 1e-3f);
    float span = max(max(hi.x - lo.x, hi.y - lo.y), hi.z - lo.z);
    g.cell = span / 40.0f;                       // 한 변을 마흔 칸으로
    if (g.cell < 1e-5f) g.cell = 1e-5f;
    g.nx = (int)((hi.x - g.lo.x) / g.cell) + 2;
    g.ny = (int)((hi.y - g.lo.y) / g.cell) + 2;
    g.nz = (int)((hi.z - g.lo.z) / g.cell) + 2;
    g.bin.resize((size_t)g.nx * g.ny * g.nz);

    for (size_t t = 0; t < nt; ++t) {
        const XMFLOAT3& a = v[idx[t * 3 + 0]].pos;
        const XMFLOAT3& b = v[idx[t * 3 + 1]].pos;
        const XMFLOAT3& c = v[idx[t * 3 + 2]].pos;
        int x0 = (int)((min(min(a.x, b.x), c.x) - g.lo.x) / g.cell);
        int x1 = (int)((max(max(a.x, b.x), c.x) - g.lo.x) / g.cell);
        int y0 = (int)((min(min(a.y, b.y), c.y) - g.lo.y) / g.cell);
        int y1 = (int)((max(max(a.y, b.y), c.y) - g.lo.y) / g.cell);
        int z0 = (int)((min(min(a.z, b.z), c.z) - g.lo.z) / g.cell);
        int z1 = (int)((max(max(a.z, b.z), c.z) - g.lo.z) / g.cell);
        g.Clamp(x0, y0, z0);
        g.Clamp(x1, y1, z1);
        for (int z = z0; z <= z1; ++z)
            for (int y = y0; y <= y1; ++y)
                for (int x = x0; x <= x1; ++x)
                    g.bin[g.Index(x, y, z)].push_back((uint32_t)t);
    }

    // ── 정점마다 광선을 쏜다 ──
    // 같은 삼각형을 여러 칸에서 다시 보지 않도록 마지막에 본 광선 번호를 남긴다
    std::vector<uint32_t> seen(nt, 0xFFFFFFFFu);
    uint32_t stamp = 0;

    for (size_t i = 0; i < nv; ++i) {
        const XMFLOAT3& p = v[i].pos;
        XMVECTOR N = XMVector3Normalize(XMLoadFloat3(&v[i].nrm));

        // 법선을 축으로 하는 좌표계를 만든다
        XMVECTOR up = (fabsf(XMVectorGetY(N)) > 0.99f)
                    ? XMVectorSet(1, 0, 0, 0) : XMVectorSet(0, 1, 0, 0);
        XMVECTOR T = XMVector3Normalize(XMVector3Cross(up, N));
        XMVECTOR B = XMVector3Cross(N, T);

        int blocked = 0;
        for (int r = 0; r < RAYS; ++r) {
            // 반구에 코사인 분포로 흩는다. 법선 쪽을 촘촘히 잡는 것이
            // 실제 빛이 드는 비율과 맞는다
            float u1 = (r + 0.5f) / RAYS;
            float u2 = fmodf(r * 0.618033989f, 1.0f);   // 황금비로 고르게 흩는다
            float rr = sqrtf(u1);
            float ph = 6.2831853f * u2;
            float dx = rr * cosf(ph), dy = rr * sinf(ph);
            float dz = sqrtf(max(0.0f, 1.0f - u1));

            XMVECTOR dv = XMVectorAdd(XMVectorAdd(XMVectorScale(T, dx),
                                                  XMVectorScale(B, dy)),
                                      XMVectorScale(N, dz));
            XMFLOAT3 d;
            XMStoreFloat3(&d, XMVector3Normalize(dv));

            // 제 면에 바로 닿지 않게 살짝 띄워서 쏜다
            XMFLOAT3 o(p.x + d.x * 1e-4f, p.y + d.y * 1e-4f, p.z + d.z * 1e-4f);

            ++stamp;
            bool hit = false;

            // 광선을 따라가며 지나는 칸의 삼각형만 본다.
            // 칸보다 촘촘히 짚으므로 건너뛰는 칸이 없다
            int steps = (int)(RAY_LEN / g.cell) + 2;
            for (int s = 0; s <= steps && !hit; ++s) {
                float tt = RAY_LEN * s / steps;
                int cx = (int)((o.x + d.x * tt - g.lo.x) / g.cell);
                int cy = (int)((o.y + d.y * tt - g.lo.y) / g.cell);
                int cz = (int)((o.z + d.z * tt - g.lo.z) / g.cell);
                if (cx < 0 || cy < 0 || cz < 0 || cx >= g.nx || cy >= g.ny || cz >= g.nz)
                    break;                        // 모델 밖으로 나갔다

                for (uint32_t t : g.bin[g.Index(cx, cy, cz)]) {
                    if (seen[t] == stamp) continue;
                    seen[t] = stamp;
                    if (RayTri(o, d, v[idx[t * 3]].pos, v[idx[t * 3 + 1]].pos,
                               v[idx[t * 3 + 2]].pos, RAY_LEN)) {
                        hit = true;
                        break;
                    }
                }
            }
            if (hit) ++blocked;
        }

        v[i].ao = 1.0f - (float)blocked / RAYS;
    }
}

bool LoadFBX(ID3D11Device* dev, const char* path, float targetHeight,
             Model& out, char* err, size_t errSize,
             bool bakeAO, Align* align, bool radial) {
    ufbx_load_opts opts = {};
    // DirectX 는 왼손 좌표계에 Y 가 위다. FBX 는 만든 도구마다 축이 달라서
    // 여기서 한 번에 맞춰 둔다 — 안 맞추면 모델이 눕거나 뒤집혀 들어온다
    opts.target_axes        = ufbx_axes_left_handed_y_up;
    opts.target_unit_meters = 1.0f;
    opts.generate_missing_normals = true;   // 법선이 없으면 만들어 준다

    ufbx_error e;
    ufbx_scene* scene = ufbx_load_file(path, &opts, &e);
    if (!scene) {
        snprintf(err, errSize, "FBX read failed:\n%s\n\n%s", path, e.description.data);
        return false;
    }
    if (scene->meshes.count == 0) {
        snprintf(err, errSize, "No mesh in:\n%s", path);
        ufbx_free_scene(scene);
        return false;
    }

    // ── 면을 삼각형으로 펼친다 ──
    // FBX 의 면은 꼭짓점이 셋이 아닐 수 있고(사각형·다각형), 위치·법선·UV 가
    // 각자 다른 인덱스를 쓴다. 그래서 일단 삼각형 꼭짓점마다 값을 직접 뽑아
    // 평탄한 배열로 만든 다음, 겹치는 것을 합쳐 인덱스를 다시 만든다
    std::vector<Vertex> flat;
    std::vector<uint32_t> tri;

    for (size_t mi = 0; mi < scene->meshes.count; ++mi) {
        ufbx_mesh* mesh = scene->meshes.data[mi];
        tri.resize(mesh->max_face_triangles * 3);

        for (size_t fi = 0; fi < mesh->num_faces; ++fi) {
            ufbx_face face = mesh->faces.data[fi];
            size_t n = ufbx_triangulate_face(tri.data(), tri.size(), mesh, face);

            for (size_t k = 0; k < n * 3; ++k) {
                uint32_t ix = tri[k];
                Vertex v;
                v.pos = F3(ufbx_get_vertex_vec3(&mesh->vertex_position, ix));
                v.nrm = mesh->vertex_normal.exists
                      ? F3(ufbx_get_vertex_vec3(&mesh->vertex_normal, ix))
                      : XMFLOAT3(0, 1, 0);
                v.uv  = mesh->vertex_uv.exists
                      ? F2(ufbx_get_vertex_vec2(&mesh->vertex_uv, ix))
                      : XMFLOAT2(0, 0);
                // 세로를 뒤집는다. FBX 의 UV 는 아래에서 위로 올라가는데
                // DirectX 텍스처는 위에서 아래로 내려간다. 안 뒤집으면
                // 얼굴이 아래위로 뒤집혀 붙는다
                v.uv.y = 1.0f - v.uv.y;
                flat.push_back(v);
            }
        }
    }
    ufbx_free_scene(scene);

    if (flat.empty()) {
        snprintf(err, errSize, "Mesh has no triangles:\n%s", path);
        return false;
    }
    out.srcVertices = flat.size();

    // ── 크기와 자리를 맞춘다 ──
    // 원본이 센티미터로 만들어졌는지 미터인지, 원점이 어디인지 알 수 없다.
    // 재서 맞추면 어떤 모델이 와도 화면 한가운데 제대로 선다
    XMFLOAT3 lo(FLT_MAX, FLT_MAX, FLT_MAX), hi(-FLT_MAX, -FLT_MAX, -FLT_MAX);
    for (const Vertex& v : flat) {
        lo.x = min(lo.x, v.pos.x); hi.x = max(hi.x, v.pos.x);
        lo.y = min(lo.y, v.pos.y); hi.y = max(hi.y, v.pos.y);
        lo.z = min(lo.z, v.pos.z); hi.z = max(hi.z, v.pos.z);
    }
    out.rawHeight = hi.y - lo.y;
    // targetHeight 가 0 이하면 원본 크기를 그대로 쓴다.
    // ufbx 에 미터로 읽으라고 시켰으므로 그 값이 곧 실제 치수다 —
    // 억지로 키우면 1 단위가 무엇인지 알 수 없게 되고,
    // 피부 산란 같은 물리 값을 실제 수치로 넣을 수 없다
    out.scale = (targetHeight > 0.0f && out.rawHeight > 1e-6f)
              ? (targetHeight / out.rawHeight) : 1.0f;

    float cx = (lo.x + hi.x) * 0.5f, cz = (lo.z + hi.z) * 0.5f, by = lo.y;

    // 앞서 정해 둔 변환이 있으면 그것을 쓴다. 메시마다 제 가운데를 찾으면
    // 눈썹은 눈썹의 한가운데, 얼굴은 얼굴의 한가운데로 가서 서로 어긋난다
    if (align && align->valid) {
        out.scale = align->scale;
        cx = align->sub.x; by = align->sub.y; cz = align->sub.z;
    } else if (align) {
        align->scale = out.scale;
        align->sub   = DirectX::XMFLOAT3(cx, by, cz);
        align->valid = true;
    }

    for (Vertex& v : flat) {
        v.pos.x = (v.pos.x - cx) * out.scale;   // 가로는 한가운데로
        v.pos.y = (v.pos.y - by) * out.scale;   // 발치가 y=0 에 오게
        v.pos.z = (v.pos.z - cz) * out.scale;
    }

    // ── 겹치는 정점을 합친다 ──
    // 위에서 꼭짓점마다 값을 뽑았으므로 같은 자리가 여러 번 들어 있다.
    // 합치면 정점 수가 크게 줄어 GPU 가 덜 일한다
    std::vector<uint32_t> indices(flat.size());
    ufbx_vertex_stream stream = { flat.data(), flat.size(), sizeof(Vertex) };
    ufbx_error ge;
    size_t nv = ufbx_generate_indices(&stream, 1, indices.data(), indices.size(), nullptr, &ge);
    if (nv == 0) {
        snprintf(err, errSize, "Index generation failed:\n%s", ge.description.data);
        return false;
    }
    out.outVertices  = nv;
    out.indexCount   = (UINT)indices.size();
    out.targetHeight = targetHeight;

    // ── 탄젠트를 만든다 ──
    // FBX 에 탄젠트가 없어서(이 파일은 tangent=0 이었다) 직접 구한다.
    // 삼각형마다 「UV 가 가로로 한 칸 갈 때 공간에서 어느 쪽으로 가는가」를
    // 풀어서 얻고, 정점마다 이웃한 삼각형 것을 모아 평균 낸다 —
    // 면 단위로 두면 삼각형 경계가 각져 보인다
    {
        std::vector<XMFLOAT3> tanAcc(nv, XMFLOAT3(0, 0, 0));
        std::vector<XMFLOAT3> bitAcc(nv, XMFLOAT3(0, 0, 0));

        for (size_t i = 0; i + 2 < indices.size(); i += 3) {
            uint32_t ia = indices[i], ib = indices[i + 1], ic = indices[i + 2];
            const Vertex& a = flat[ia];
            const Vertex& b = flat[ib];
            const Vertex& c = flat[ic];

            float e1x = b.pos.x - a.pos.x, e1y = b.pos.y - a.pos.y, e1z = b.pos.z - a.pos.z;
            float e2x = c.pos.x - a.pos.x, e2y = c.pos.y - a.pos.y, e2z = c.pos.z - a.pos.z;
            float du1 = b.uv.x - a.uv.x, dv1 = b.uv.y - a.uv.y;
            float du2 = c.uv.x - a.uv.x, dv2 = c.uv.y - a.uv.y;

            float det = du1 * dv2 - du2 * dv1;
            if (fabsf(det) < 1e-12f) continue;   // UV 가 한 점에 뭉친 삼각형
            float r = 1.0f / det;

            XMFLOAT3 t((e1x * dv2 - e2x * dv1) * r,
                       (e1y * dv2 - e2y * dv1) * r,
                       (e1z * dv2 - e2z * dv1) * r);
            XMFLOAT3 bt((e2x * du1 - e1x * du2) * r,
                        (e2y * du1 - e1y * du2) * r,
                        (e2z * du1 - e1z * du2) * r);

            for (uint32_t ix : { ia, ib, ic }) {
                tanAcc[ix].x += t.x;  tanAcc[ix].y += t.y;  tanAcc[ix].z += t.z;
                bitAcc[ix].x += bt.x; bitAcc[ix].y += bt.y; bitAcc[ix].z += bt.z;
            }
        }

        for (size_t i = 0; i < nv; ++i) {
            XMVECTOR n = XMLoadFloat3(&flat[i].nrm);
            XMVECTOR t = XMLoadFloat3(&tanAcc[i]);

            // 탄젠트가 전혀 안 모인 자리(UV 가 없는 정점)는 아무 가로축이나 준다
            if (XMVectorGetX(XMVector3LengthSq(t)) < 1e-16f)
                t = XMVectorSet(1, 0, 0, 0);

            // 법선에 붙어 있는 성분을 빼서 직각으로 세운다 (그람-슈미트)
            t = XMVector3Normalize(XMVectorSubtract(t, XMVectorScale(n, XMVectorGetX(XMVector3Dot(n, t)))));
            if (XMVectorGetX(XMVector3LengthSq(t)) < 1e-16f)
                t = XMVectorSet(1, 0, 0, 0);

            // 세로축이 뒤집힌 자리인지 본다. 거울처럼 쓴 UV 에서 생긴다
            XMVECTOR expect = XMVector3Cross(n, t);
            float w = (XMVectorGetX(XMVector3Dot(expect, XMLoadFloat3(&bitAcc[i]))) < 0.0f)
                    ? -1.0f : 1.0f;

            XMFLOAT3 t3;
            XMStoreFloat3(&t3, t);
            flat[i].tan = XMFLOAT4(t3.x, t3.y, t3.z, w);
        }
    }

    // ── 곡률(Cavity)을 잰다 ──
    // 정점마다 이웃으로 가는 방향과 제 법선을 내적해 평균 낸다.
    // 이웃이 법선 쪽에 있으면 안으로 파인 자리, 반대면 튀어나온 자리다.
    // SSAO 가 반경이 커서 놓치는 작은 주름을 이쪽이 잡는다
    {
        std::vector<float> sum(nv, 0.0f);
        std::vector<int>   cnt(nv, 0);

        auto edge = [&](uint32_t a, uint32_t b) {
            float dx = flat[b].pos.x - flat[a].pos.x;
            float dy = flat[b].pos.y - flat[a].pos.y;
            float dz = flat[b].pos.z - flat[a].pos.z;
            float len = sqrtf(dx * dx + dy * dy + dz * dz);
            if (len < 1e-9f) return;
            dx /= len; dy /= len; dz /= len;
            const XMFLOAT3& n = flat[a].nrm;
            sum[a] += dx * n.x + dy * n.y + dz * n.z;
            cnt[a] += 1;
        };

        for (size_t i = 0; i + 2 < indices.size(); i += 3) {
            uint32_t a = indices[i], b = indices[i + 1], c = indices[i + 2];
            edge(a, b); edge(b, a);
            edge(b, c); edge(c, b);
            edge(c, a); edge(a, c);
        }

        for (size_t i = 0; i < nv; ++i)
            flat[i].cav = cnt[i] ? (sum[i] / cnt[i]) : 0.0f;
    }

    // ── 버텍스 AO 를 굽는다 ──
    // 여기서 시간이 걸린다. 정점 수와 삼각형 수에 따라 1~3초 정도다
    // 털 가닥처럼 정점이 많고 얻는 것이 적은 메시는 굽지 않는다.
    // 안 구우면 ao 가 1(훤히 열림)로 남아 아무 영향도 주지 않는다
    if (bakeAO) {
        ComputeVertexAO(flat, indices, targetHeight, out.aoRadius);
    } else if (radial) {
        // 한가운데에서 얼마나 바깥인가. 헤어는 안쪽 가닥이 바깥 가닥에
        // 완전히 덮이는데, 광선을 쏴 가리려면 정점이 팔만이라 몇십 초가 든다.
        // 머리 모양은 덩어리에 가까워 한가운데에서 잰 거리로도 충분히 갈린다
        DirectX::XMFLOAT3 c(0.0f, 0.0f, 0.0f);
        for (const Vertex& v : flat) { c.x += v.pos.x; c.y += v.pos.y; c.z += v.pos.z; }
        float inv = flat.empty() ? 0.0f : 1.0f / (float)flat.size();
        c.x *= inv; c.y *= inv; c.z *= inv;

        float maxR = 1e-6f;
        for (const Vertex& v : flat) {
            float dx = v.pos.x - c.x, dy = v.pos.y - c.y, dz = v.pos.z - c.z;
            float d = sqrtf(dx * dx + dy * dy + dz * dz);
            if (d > maxR) maxR = d;
        }
        for (Vertex& v : flat) {
            float dx = v.pos.x - c.x, dy = v.pos.y - c.y, dz = v.pos.z - c.z;
            v.ao = sqrtf(dx * dx + dy * dy + dz * dz) / maxR;   // 0 = 한가운데
        }
    } else {
        for (Vertex& v : flat) v.ao = 1.0f;
    }

    // ── GPU 로 올린다 ──
    D3D11_BUFFER_DESC bd = {};
    D3D11_SUBRESOURCE_DATA sr = {};

    bd.Usage     = D3D11_USAGE_DEFAULT;
    bd.ByteWidth = (UINT)(nv * sizeof(Vertex));
    bd.BindFlags = D3D11_BIND_VERTEX_BUFFER;
    sr.pSysMem   = flat.data();
    if (FAILED(dev->CreateBuffer(&bd, &sr, &out.vb))) {
        snprintf(err, errSize, "Vertex buffer creation failed");
        return false;
    }

    // 정점이 6만 5천을 넘으면 16비트 인덱스로는 못 가리킨다. 32비트를 쓴다
    bd.ByteWidth = (UINT)(indices.size() * sizeof(uint32_t));
    bd.BindFlags = D3D11_BIND_INDEX_BUFFER;
    sr.pSysMem   = indices.data();
    if (FAILED(dev->CreateBuffer(&bd, &sr, &out.ib))) {
        snprintf(err, errSize, "Index buffer creation failed");
        out.Release();
        return false;
    }

    // 다시 구울 때 쓸 사본. 합쳐진 뒤의 정점만 남기면 된다
    flat.resize(nv);
    out.verts = std::move(flat);
    out.idx   = std::move(indices);
    return true;
}

void RebakeAO(ID3D11DeviceContext* ctx, Model& m, float radiusScale) {
    if (m.verts.empty() || !m.vb) return;
    ComputeVertexAO(m.verts, m.idx, m.targetHeight, radiusScale);
    ctx->UpdateSubresource(m.vb, 0, nullptr, m.verts.data(), 0, 0);
    m.aoRadius = radiusScale;
}
