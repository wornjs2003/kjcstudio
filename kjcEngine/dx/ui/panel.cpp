#include "ui/panel.h"

#include <commctrl.h>
#include <cstdio>
#include <cstdlib>
#include <cwchar>

#pragma comment(lib, "comctl32.lib")

namespace {

// ─── 창에 놓는 것들 ────────────────────────────────────────────────────
// 줄마다 체크박스 하나와 「이름 · 칸 · 슬라이더」 묶음이 하나둘 온다.
// 번호로 구분한다
enum {
    ID_APPLY = 100, ID_SAVE, ID_REBAKE,
    ID_CHK_FIRST = 200,      // 체크박스
    ID_EDT_FIRST = 300,      // 입력 칸
    ID_SLD_FIRST = 400,      // 슬라이더
};

const int CHK_N = 12;
const int EDT_N = 16;

// 슬라이더는 정수만 다룬다. 0~SLD_STEPS 를 아래 범위로 펴서 쓴다
const int SLD_STEPS = 1000;

HWND g_panel = nullptr;
HWND g_chk[CHK_N] = {};
HWND g_edt[EDT_N] = {};
HWND g_sld[EDT_N] = {};
PanelHost       g_host;
ShaderSettings  g_cur;
bool g_filling = false;      // 되비추는 중에는 바뀜을 무시한다

// 체크박스가 어느 값을 가리키나
bool* ChkTarget(ShaderSettings& s, int i) {
    switch (i) {
    case 0: return &s.skin;    case 1: return &s.micro;   case 2: return &s.ssao;
    case 3: return &s.cavity;  case 4: return &s.rim;     case 5: return &s.vao;
    case 6: return &s.sssBlur; case 7: return &s.fog;     case 8: return &s.ibl;
    case 9: return &s.diffuse; case 10: return &s.normalMap;
    default: return &s.specular;
    }
}

float* EdtTarget(ShaderSettings& s, int i) {
    switch (i) {
    case 0:  return &s.microTile;   case 1:  return &s.ssaoRadius;
    case 2:  return &s.ssaoPower;   case 3:  return &s.cavityPower;
    case 4:  return &s.rimPower;    case 5:  return &s.vaoPower;
    case 6:  return &s.vaoRadius;   case 7:  return &s.sssWidthMm;
    case 8:  return &s.fogDepth;    case 9:  return &s.envPower;
    case 10: return &s.shadowRange; case 11: return &s.sunYawDeg;
    case 12: return &s.sunHeightDeg; case 13: return &s.exposure;
    case 14: return &s.sunIntensity;
    default: return &s.background;
    }
}

// 슬라이더가 움직일 수 있는 범위. 칸에 직접 치면 이 밖의 값도 넣을 수 있고,
// 그때 슬라이더는 끝에 붙는다
struct Range { float lo, hi; };
const Range RANGE[EDT_N] = {
    { 1.0f,    200.0f },   //  0 Detail Normal · Tile
    { 0.005f,    0.30f },  //  1 SSAO · Radius (m)
    { 0.0f,      3.0f },   //  2 SSAO · Intensity
    { 0.0f,      6.0f },   //  3 Cavity · Intensity
    { 0.0f,      3.0f },   //  4 Rim Light · Intensity
    { 0.0f,      3.0f },   //  5 Vertex AO · Intensity
    { 0.02f,     1.00f },  //  6 Vertex AO · Radius
    { 0.1f,     10.0f },   //  7 SSS Blur · Width (mm)
    { 0.01f,     1.00f },  //  8 Depth Darkening · Depth (m)
    { 0.0f,      4.0f },   //  9 IBL · Intensity
    { 0.3f,      8.0f },   // 10 Shadow Range (m)
    { -180.0f, 180.0f },   // 11 Sun · Yaw
    { 5.0f,     88.0f },   // 12 Sun · Pitch
    { 0.1f,      4.0f },   // 13 Exposure
    { 0.0f,      3.0f },   // 14 Sun · Intensity
    { 0.0f,      4.0f },   // 15 Background
};

void FormatValue(wchar_t* buf, size_t n, float v) {
    // 자릿수를 값에 맞춘다. 0.030 을 0 으로 보여주면 고칠 수가 없다
    if (v >= 100.0f || v <= -100.0f)    swprintf(buf, n, L"%.0f", v);
    else if (v >= 10.0f || v <= -10.0f) swprintf(buf, n, L"%.1f", v);
    else                                swprintf(buf, n, L"%.3f", v);
}

void SetSlider(int i, float v) {
    if (!g_sld[i]) return;
    const Range& r = RANGE[i];
    float t = (v - r.lo) / (r.hi - r.lo);
    if (t < 0.0f) t = 0.0f;
    if (t > 1.0f) t = 1.0f;
    SendMessageW(g_sld[i], TBM_SETPOS, TRUE, (LPARAM)(int)(t * SLD_STEPS + 0.5f));
}

// 칸에서 숫자를 읽어 온다. 빈 칸이나 글자는 무시하고 있던 값을 지킨다
void ReadEdits() {
    wchar_t buf[64];
    for (int i = 0; i < EDT_N; ++i) {
        if (!g_edt[i]) continue;
        GetWindowTextW(g_edt[i], buf, 64);
        wchar_t* end = nullptr;
        double v = wcstod(buf, &end);
        if (end != buf) *EdtTarget(g_cur, i) = (float)v;
    }
    for (int i = 0; i < CHK_N; ++i)
        *ChkTarget(g_cur, i) = (SendMessageW(g_chk[i], BM_GETCHECK, 0, 0) == BST_CHECKED);
}

void WriteEdits(const ShaderSettings& s) {
    g_filling = true;
    ShaderSettings t = s;
    wchar_t buf[64];
    for (int i = 0; i < EDT_N; ++i) {
        if (!g_edt[i]) continue;
        float v = *EdtTarget(t, i);
        FormatValue(buf, 64, v);
        SetWindowTextW(g_edt[i], buf);
        SetSlider(i, v);
    }
    for (int i = 0; i < CHK_N; ++i)
        SendMessageW(g_chk[i], BM_SETCHECK,
                     *ChkTarget(t, i) ? BST_CHECKED : BST_UNCHECKED, 0);
    g_filling = false;
}

LRESULT CALLBACK PanelProc(HWND h, UINT m, WPARAM w, LPARAM l) {
    switch (m) {
    // ── 슬라이더를 밀었다 ──
    // 칸의 숫자를 따라 고치고 바로 화면에 먹인다. 칸에 쓰는 동안에는
    // g_filling 을 세워 EN_CHANGE 가 같은 일을 되풀이하지 않게 한다
    case WM_HSCROLL: {
        HWND from = (HWND)l;
        for (int i = 0; i < EDT_N; ++i) {
            if (g_sld[i] != from) continue;
            int pos = (int)SendMessageW(from, TBM_GETPOS, 0, 0);
            const Range& r = RANGE[i];
            float v = r.lo + (r.hi - r.lo) * ((float)pos / SLD_STEPS);
            *EdtTarget(g_cur, i) = v;

            wchar_t buf[64];
            FormatValue(buf, 64, v);
            g_filling = true;
            SetWindowTextW(g_edt[i], buf);
            g_filling = false;

            if (g_host.Apply) g_host.Apply(g_cur);
            return 0;
        }
        return 0;
    }

    case WM_COMMAND: {
        int id = LOWORD(w);
        if (g_filling) return 0;

        if (id == ID_SAVE) {
            ReadEdits();
            if (g_host.Apply) g_host.Apply(g_cur);
            if (g_host.Save)  g_host.Save();
            return 0;
        }
        if (id == ID_REBAKE) {
            ReadEdits();
            if (g_host.Apply)  g_host.Apply(g_cur);
            if (g_host.Rebake) g_host.Rebake();
            return 0;
        }
        // 체크박스를 누르거나 칸에서 값을 고치면 곧바로 화면에 먹인다 —
        // Apply 를 따로 누르게 하면 바꿔 보는 맛이 죽는다
        if (id == ID_APPLY ||
            (id >= ID_CHK_FIRST && id < ID_CHK_FIRST + CHK_N) ||
            (id >= ID_EDT_FIRST && id < ID_EDT_FIRST + EDT_N && HIWORD(w) == EN_CHANGE)) {
            ReadEdits();
            // 숫자를 직접 쳤으면 슬라이더도 그 자리로 옮긴다.
            // TBM_SETPOS 는 WM_HSCROLL 을 안 보내므로 되돌아오지 않는다
            if (id >= ID_EDT_FIRST) {
                g_filling = true;
                int i = id - ID_EDT_FIRST;
                SetSlider(i, *EdtTarget(g_cur, i));
                g_filling = false;
            }
            if (g_host.Apply) g_host.Apply(g_cur);
        }
        return 0;
    }
    case WM_CLOSE:                 // X 를 눌러도 없애지 않고 숨긴다
        ShowWindow(h, SW_HIDE);
        return 0;
    }
    return DefWindowProcW(h, m, w, l);
}

// 한 줄에 놓이는 것. -1 이면 그 자리에는 아무것도 두지 않는다
struct Row { const wchar_t* name; int chk; const wchar_t* l1; int e1;
             const wchar_t* l2; int e2; };

const Row ROWS[] = {
    { L"Subsurface Scattering", 0, nullptr,      -1, nullptr,      -1 },
    { L"Detail Normal",         1, L"Tile",       0, nullptr,      -1 },
    { L"SSAO",                  2, L"Radius m",   1, L"Intensity",  2 },
    { L"Cavity",                3, L"Intensity",  3, nullptr,      -1 },
    { L"Rim Light",             4, L"Intensity",  4, nullptr,      -1 },
    { L"Vertex AO",             5, L"Intensity",  5, L"Radius",     6 },
    { L"SSS Blur",              6, L"Width mm",   7, nullptr,      -1 },
    { L"Depth Darkening",       7, L"Depth m",    8, nullptr,      -1 },
    { L"IBL",                   8, L"Intensity",  9, nullptr,      -1 },
    { L"Diffuse",               9, nullptr,      -1, nullptr,      -1 },
    { L"Normal Map",           10, nullptr,      -1, nullptr,      -1 },
    { L"Specular",             11, nullptr,      -1, nullptr,      -1 },
    { L"Shadow Range",         -1, L"m",         10, nullptr,      -1 },
    { L"Sun",                  -1, L"Yaw",       11, L"Pitch",     12 },
    { L"",                     -1, L"Intensity", 14, nullptr,      -1 },
    { L"Exposure",             -1, L"",          13, L"Background", 15 },
};

// 가로 자리. 한 묶음은 「이름 · 칸 · 슬라이더」다
const int X_CHK = 12,  W_CHK = 152;
const int X_LB1 = 168, W_LB  = 68;
const int X_ED1 = 242, W_ED  = 60;
const int X_SL1 = 308, W_SL  = 140;
const int X_LB2 = 458;
const int X_ED2 = 532;
const int X_SL2 = 598;
const int PANEL_W = X_SL2 + W_SL + 12;

} // namespace

bool PanelCreate(HINSTANCE inst, HWND owner, const PanelHost& host,
                 const ShaderSettings& init) {
    g_host = host;
    g_cur  = init;

    INITCOMMONCONTROLSEX icc = { sizeof(icc), ICC_BAR_CLASSES };  // 슬라이더
    InitCommonControlsEx(&icc);

    WNDCLASSW wc = {};
    wc.lpfnWndProc   = PanelProc;
    wc.hInstance     = inst;
    wc.hCursor       = LoadCursor(nullptr, IDC_ARROW);
    wc.hbrBackground = (HBRUSH)(COLOR_BTNFACE + 1);
    wc.lpszClassName = L"kjcEnginePanel";
    RegisterClassW(&wc);

    const int ROW_H = 30, TOP = 12;
    const int nRows = (int)(sizeof(ROWS) / sizeof(ROWS[0]));
    const int H = TOP + nRows * ROW_H + 60;

    RECT r = { 0, 0, PANEL_W, H };
    AdjustWindowRect(&r, WS_OVERLAPPEDWINDOW & ~WS_THICKFRAME & ~WS_MAXIMIZEBOX, FALSE);

    // 그리는 창을 가리지 않게 그 오른쪽에 붙인다. 화면 밖으로 나가면 왼쪽으로
    int px = CW_USEDEFAULT, py = CW_USEDEFAULT;
    RECT ow;
    if (owner && GetWindowRect(owner, &ow)) {
        int panelW = r.right - r.left;
        px = ow.right + 8;
        py = ow.top;
        if (px + panelW > GetSystemMetrics(SM_CXVIRTUALSCREEN)) px = ow.left - panelW - 8;
    }

    g_panel = CreateWindowW(L"kjcEnginePanel", L"kjcEngine · Shaders",
                            WS_OVERLAPPEDWINDOW & ~WS_THICKFRAME & ~WS_MAXIMIZEBOX,
                            px, py,
                            r.right - r.left, r.bottom - r.top,
                            owner, nullptr, inst, nullptr);
    if (!g_panel) return false;

    // 창 글꼴을 컨트롤에도 입힌다. 안 하면 옛 시스템 글꼴로 나온다
    HFONT font = (HFONT)GetStockObject(DEFAULT_GUI_FONT);
    NONCLIENTMETRICSW ncm = { sizeof(ncm) };
    if (SystemParametersInfoW(SPI_GETNONCLIENTMETRICS, sizeof(ncm), &ncm, 0))
        font = CreateFontIndirectW(&ncm.lfMessageFont);

    auto put = [&](const wchar_t* cls, const wchar_t* text, DWORD style,
                   int x, int y, int w, int h, int id) -> HWND {
        HWND c = CreateWindowW(cls, text, WS_CHILD | WS_VISIBLE | style,
                               x, y, w, h, g_panel, (HMENU)(INT_PTR)id, inst, nullptr);
        SendMessageW(c, WM_SETFONT, (WPARAM)font, TRUE);
        return c;
    };

    // 「이름 · 칸 · 슬라이더」 한 묶음
    auto putField = [&](const wchar_t* label, int idx,
                        int xLabel, int xEdit, int xSlider, int y) {
        put(L"STATIC", label, SS_RIGHT, xLabel, y + 5, W_LB, 20, -1);
        g_edt[idx] = put(L"EDIT", L"", WS_BORDER | ES_RIGHT | ES_AUTOHSCROLL,
                         xEdit, y + 2, W_ED, 22, ID_EDT_FIRST + idx);
        g_sld[idx] = put(TRACKBAR_CLASSW, L"", TBS_HORZ | TBS_NOTICKS,
                         xSlider, y + 2, W_SL, 24, ID_SLD_FIRST + idx);
        SendMessageW(g_sld[idx], TBM_SETRANGE, TRUE, MAKELPARAM(0, SLD_STEPS));
    };

    for (int i = 0; i < nRows; ++i) {
        const Row& row = ROWS[i];
        int y = TOP + i * ROW_H;

        if (row.chk >= 0)
            g_chk[row.chk] = put(L"BUTTON", row.name, BS_AUTOCHECKBOX,
                                 X_CHK, y + 2, W_CHK, 22, ID_CHK_FIRST + row.chk);
        else
            put(L"STATIC", row.name, 0, X_CHK + 18, y + 5, W_CHK, 20, -1);

        if (row.e1 >= 0) putField(row.l1, row.e1, X_LB1, X_ED1, X_SL1, y);
        if (row.e2 >= 0) putField(row.l2, row.e2, X_LB2, X_ED2, X_SL2, y);
    }

    // 버텍스 AO 의 범위는 다시 구워야 바뀐다. 그래서 단추가 따로 있다
    int by = TOP + nRows * ROW_H + 12;
    put(L"BUTTON", L"Bake AO", BS_PUSHBUTTON, X_ED1,      by, 100, 26, ID_REBAKE);
    put(L"BUTTON", L"Apply",   BS_PUSHBUTTON, X_ED2 - 8,  by, 100, 26, ID_APPLY);
    put(L"BUTTON", L"Save",    BS_PUSHBUTTON, X_SL2 + 40, by, 100, 26, ID_SAVE);

    WriteEdits(g_cur);
    return true;
}

void PanelToggle() {
    if (!g_panel) return;
    if (IsWindowVisible(g_panel)) {
        ShowWindow(g_panel, SW_HIDE);
    } else {
        ShowWindow(g_panel, SW_SHOW);
        SetForegroundWindow(g_panel);
    }
}

void PanelRefresh(const ShaderSettings& s) {
    if (!g_panel) return;
    g_cur = s;
    WriteEdits(g_cur);
}

void PanelDestroy() {
    if (g_panel) { DestroyWindow(g_panel); g_panel = nullptr; }
}
