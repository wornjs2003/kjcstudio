// 환경맵 조명 (IBL — Image Based Lighting).
//
// 주변 풍경이 물체에 비치게 한다. 지금까지는 그늘을 「하늘빛·땅빛 두 색」으로
// 채웠는데, 그 자리에 실제 환경을 넣는 것이다. 마모셋 씬의 Sky Light 가
// 하는 일이 이것이다.
//
// HDR 한 장에서 세 가지를 굽는다.
//
//   환경 큐브맵    배경으로 그리고, 아래 둘을 굽는 재료가 된다
//   Irradiance     사방에서 오는 빛을 뭉뚱그린 것. 확산(피부 밑색)에 쓴다
//   Prefiltered    거칠기별로 흐려 놓은 것. 반사에 쓴다
//
// 굽는 일은 CPU 에서 한다. GPU 로 하면 렌더 타겟과 셰이더가 줄줄이 붙는데,
// 모델을 읽을 때 한 번만 하는 계산이라 그럴 값이 없다.

#pragma once

#include <windows.h>
#include <d3d11.h>

struct Environment {
    ID3D11ShaderResourceView* skySRV    = nullptr;  // 배경으로 그릴 것
    ID3D11ShaderResourceView* irrSRV    = nullptr;  // 확산용
    ID3D11ShaderResourceView* specSRV   = nullptr;  // 반사용 (밉마다 거칠기가 다르다)
    UINT specMips = 1;

    void Release() {
        if (specSRV) { specSRV->Release(); specSRV = nullptr; }
        if (irrSRV)  { irrSRV->Release();  irrSRV  = nullptr; }
        if (skySRV)  { skySRV->Release();  skySRV  = nullptr; }
    }
};

// .hdr 을 읽어 위 셋을 만든다. 몇 초 걸린다.
// 실패하면 false 를 돌리고 err 에 이유를 적는다
bool LoadEnvironment(ID3D11Device* dev, const char* hdrPath,
                     Environment& out, char* err, size_t errSize);
