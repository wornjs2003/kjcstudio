// 화면에 글자를 쓴다.
//
// 이 엔진에는 글자를 그릴 수단이 선분뿐이었다 — 축 끝의 X·Y·Z 와 상태
// 표시 S·M·O 세 글자가 전부였고, 숫자도 한글도 그릴 수가 없었다.
// 값을 화면에 보여주려 할 때마다 그 벽에 부딪혀서 한 번에 깔아 둔다.
//
// 방식은 비트맵 아틀라스다. 글자 모양을 GDI 로 한 장의 회색 텍스처에
// 구워 두고, 그릴 때는 글자마다 사각형 하나씩 찍는다.
//
//   Direct2D/DirectWrite  정석이지만 스왑체인을 D2D 와 나눠 쓰도록
//                         다시 만들어야 해서 지금 구조를 크게 건드린다
//   비트맵 아틀라스       D3D11 만으로 끝난다. 이쪽을 골랐다
//
// 한글은 미리 굽지 않는다. **처음 보는 글자를 만나면 그때 굽는다** —
// 유니코드를 전부 구우면 낭비고, 쓸 글자를 목록으로 적어 두면 문구를
// 바꿀 때마다 그 목록을 따라 고쳐야 한다.

#pragma once

#include <windows.h>
#include <d3d11.h>

// 글꼴을 준비한다. pixelHeight 는 화면 픽셀 기준 높이다.
// 실패하면 false 를 돌리고 err 에 이유를 적는다
bool FontInit(ID3D11Device* dev, ID3D11DeviceContext* ctx,
              const wchar_t* face, int pixelHeight, char* err, size_t errSize);

// 한 프레임의 글자를 모으기 시작한다. 화면 크기를 픽셀로 준다
void FontBegin(int screenW, int screenH);

// 글자를 쌓는다. x·y 는 왼쪽 위 기준 픽셀 자리.
// 여기서 그리지 않는다 — FontEnd 가 모아서 한 번에 낸다
void FontDraw(float x, float y, const wchar_t* text, const float rgba[4]);

// 바탕을 한 칸 깐다. 밝은 화면 위에서 글자가 묻히는 것을 막는다
void FontRect(float x, float y, float w, float h, const float rgba[4]);

// 쌓아 둔 것을 한 번에 그린다. 글자마다 그리면 그것이 도리어 비용이 된다
void FontEnd();

// 재어 보기. 칸을 잡거나 오른쪽 맞춤에 쓴다
float FontWidth(const wchar_t* text);
float FontLineHeight();

void FontShutdown();
