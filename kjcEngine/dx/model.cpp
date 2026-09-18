#include "model.h"
#include "third_party/ufbx.h"

#include <vector>
#include <cstdio>
#include <cfloat>

using namespace DirectX;

static XMFLOAT3 F3(ufbx_vec3 v) { return XMFLOAT3((float)v.x, (float)v.y, (float)v.z); }
static XMFLOAT2 F2(ufbx_vec2 v) { return XMFLOAT2((float)v.x, (float)v.y); }

bool LoadFBX(ID3D11Device* dev, const char* path, float targetHeight,
             Model& out, char* err, size_t errSize) {
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
    out.scale = (out.rawHeight > 1e-6f) ? (targetHeight / out.rawHeight) : 1.0f;

    float cx = (lo.x + hi.x) * 0.5f, cz = (lo.z + hi.z) * 0.5f;
    for (Vertex& v : flat) {
        v.pos.x = (v.pos.x - cx) * out.scale;   // 가로는 한가운데로
        v.pos.y = (v.pos.y - lo.y) * out.scale; // 발치가 y=0 에 오게
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
    out.outVertices = nv;
    out.indexCount  = (UINT)indices.size();

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

    return true;
}
