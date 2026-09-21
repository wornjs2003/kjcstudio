// 셰이더 조절 창.
//
// 그리는 창 위에 겹치지 않고 따로 뜬다. 체크박스와 입력 칸이라
// 값을 눈으로 보고 직접 쳐 넣을 수 있다 — 키를 연타해 0.002 를 0.005 로
// 만들던 것을 대신한다.
//
// Shift+F5 로 열고 닫는다.

#pragma once

#include <windows.h>

// 엔진이 들고 있는 값들을 한 묶음으로 오간다.
// 창은 이 구조만 알고 엔진 내부는 모른다
struct ShaderSettings {
    // 켜고 끄기
    bool  skin      = true;    // 피부 산란 (그늘 경계를 감싸는 쪽)
    bool  micro     = true;    // 미세 결
    bool  ssao      = true;
    bool  cavity    = true;
    bool  rim       = true;
    bool  vao       = true;    // 버텍스 AO
    bool  sssBlur   = true;    // 피부 번짐
    bool  fog       = false;   // 깊이 어둡게
    bool  ibl       = true;    // 환경광
    // 아래 셋은 끄고 켜며 무엇이 어디까지 하고 있는지 가려낸다
    bool  diffuse   = true;    // 끄면 피부색이 걷히고 회색이 된다
    bool  normalMap = true;    // 끄면 면 방향이 메시 그대로가 된다
    bool  specular  = true;    // 끄면 번들거림이 사라진다

    // 값
    float microTile   = 70.0f;
    float ssaoRadius  = 0.03f;   // m
    float ssaoPower   = 1.0f;
    float cavityPower = 2.5f;
    float rimPower    = 0.7f;
    float vaoPower    = 1.0f;
    float vaoRadius   = 0.18f;   // 모델 높이의 몇 배
    float sssWidthMm  = 2.0f;    // mm
    float fogDepth    = 0.12f;   // m
    float envPower    = 1.0f;
    float shadowRange = 1.2f;    // m
    float sunYawDeg   = 77.0f;
    float sunHeightDeg= 33.0f;
    float exposure    = 0.46f;   // 화면 전체 밝기
    float sunIntensity= 0.70f;   // 태양 세기. 환경광과 균형을 잡는다
    float background  = 1.0f;    // 배경 밝기. 노출과 따로 논다
};

// 창이 무언가를 시켰을 때 엔진이 받는 쪽.
// 창은 화면을 직접 건드리지 않고 이 셋만 부른다
struct PanelHost {
    void (*Apply)(const ShaderSettings&) = nullptr;  // 값이 바뀌었다
    void (*Save)()                       = nullptr;  // 저장 단추
    void (*Rebake)()                     = nullptr;  // 버텍스 AO 다시 굽기
};

// 창을 만든다(아직 띄우지는 않는다). 한 번만 부른다
bool PanelCreate(HINSTANCE inst, HWND owner, const PanelHost& host,
                 const ShaderSettings& init);

// 열고 닫기. Shift+F5 가 부른다
void PanelToggle();

// 엔진 쪽에서 값이 바뀌었을 때(키로 조절했을 때) 칸에 되비춘다
void PanelRefresh(const ShaderSettings& s);

void PanelDestroy();
