// 패스마다 GPU 가 몇 ms 를 쓰는지 잰다.
//
// CPU 시계로는 못 잰다. GPU 는 명령을 받아 두고 나중에 실행해서,
// Draw 를 부른 시각은 실제로 그려진 시각이 아니다. 그래서 GPU 가 그
// 지점을 지날 때의 시각을 적게 하는 타임스탬프 쿼리를 쓴다.
//
// 결과는 두세 프레임 뒤에 나온다. 기다리면 GPU 를 세우는 셈이라 그
// 자체가 느려지므로, 쿼리를 여러 벌 돌려가며 늦게 읽는다.

#pragma once

#include <windows.h>
#include <d3d11.h>

bool GpuTimeInit(ID3D11Device* dev, ID3D11DeviceContext* ctx);

// 프레임 맨 앞에서 부른다
void GpuTimeBeginFrame();

// 패스가 끝나는 자리마다 부른다. 이름은 계속 살아 있는 문자열이어야 한다.
//
// **건너뛰는 패스에서도 불러야 한다.** 안 그러면 프레임마다 마크 수가
// 달라져 이름과 값이 어긋난다 — 건너뛴 패스는 0 으로 나오면 그만이다
void GpuTimeMark(const wchar_t* name);

// 프레임 맨 뒤에서 부른다. 여기서 지난 프레임 결과를 거둔다
void GpuTimeEndFrame();

// 거둔 값. 한 장씩은 심하게 튀므로 여러 장을 섞은 값이다
int            GpuTimeCount();
const wchar_t* GpuTimeName(int i);
float          GpuTimeMs(int i);
float          GpuTimeTotalMs();

void GpuTimeShutdown();
