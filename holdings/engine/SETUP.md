# KJC Engine 개발 환경 설정 가이드 (macOS)

## 0. 전제
- 맥 환경(Intel 또는 Apple Silicon 모두 가능, Apple Silicon 권장)
- macOS 13 이상 권장
- 저장 공간 최소 100GB 여유(Unreal 설치만 50GB 내외)
- 인터넷 회선

---

## Phase 1 환경 (Unreal 중심)

### 1. Epic Games Launcher 설치
1. https://www.unrealengine.com/download 에서 Epic Games Launcher 다운로드
2. Epic Games 계정 생성 또는 로그인
3. Launcher 실행 → Unreal Engine 탭 → 라이브러리 → "Engine Versions" 옆 + 버튼
4. 최신 안정 버전(5.4 또는 5.5) 선택 → 설치
5. 설치 중 옵션: "Engine Source", "Starter Content", "Templates and Feature Packs" 체크

### 2. Xcode 및 Command Line Tools
Unreal에서 C++ 빌드를 하려면 필요합니다. 현 시점에는 HLSL/머티리얼 위주라 최소 설치여도 됩니다.

```
xcode-select --install
```

혹은 App Store에서 Xcode 설치(용량 큼).

### 3. Perforce 또는 Git LFS (선택)
장기 상업 프로젝트면 버전 관리가 필수입니다.
- 단기: Git + Git LFS (무료, 용량 작음)
- 장기/팀: Perforce Helix Core (에픽 권장, 무료 5인까지)

Git LFS 설치:
```
brew install git-lfs
git lfs install
```

### 4. 보조 툴
- **Visual Studio Code**: 코드/셰이더 편집 (https://code.visualstudio.com)
  - 확장: C/C++ · HLSL Tools for Visual Studio · Unreal Engine Shader Linter
- **RenderDoc**: 프레임 디버깅 (https://renderdoc.org)
- **Substance Designer · Painter**: 머티리얼 오서링 (재권님은 이미 숙련)
- **DaVinci Resolve**: 쇼케이스 영상 편집 (무료 버전)

---

## Phase 2 환경 (자체 엔진 · Week 8부터 병행 설치)

### 1. Homebrew
없으면 설치합니다.

```
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

### 2. 필수 CLI 도구
```
brew install cmake ninja git git-lfs python@3.12
```

### 3. 라이브러리 (CMake FetchContent 또는 vcpkg로 가져올 예정)
직접 brew 설치하지 않고 프로젝트 내 빌드 시스템이 가져오도록 합니다. 참고용:
- GLFW · GLAD · GLM
- Assimp (모델 로더)
- Dear ImGui (에디터 GUI)
- EnTT (ECS)
- stb_image (이미지 로더)

### 4. IDE
- **CLion**: JetBrains, 학생/오픈소스 무료 · 유료 라이선스 있음 (1순위 추천)
- **VS Code + CMake Tools 확장**: 무료 · 가벼움
- **Xcode**: 맥 네이티브이지만 CMake 프로젝트와 잘 안 맞음 (비추천)

### 5. Vulkan (나중 Phase 2 후반용, 지금은 불필요)
```
brew install molten-vk
# Vulkan SDK는 LunarG에서 직접 다운로드
# https://vulkan.lunarg.com/sdk/home#mac
```

---

## 설치 확인 체크리스트

### Phase 1 완료 조건
- [ ] Epic Games Launcher 로그인 완료
- [ ] Unreal Engine 5.x 설치 완료
- [ ] Unreal Engine 실행 → 빈 프로젝트 "Third Person" 템플릿 생성 · 실행까지 성공
- [ ] Xcode Command Line Tools 설치(`xcode-select -p` 결과가 경로 출력)
- [ ] VS Code 설치

### Phase 2 완료 조건 (Week 8 이후)
- [ ] Homebrew 설치 (`brew --version` 작동)
- [ ] CMake 설치 (`cmake --version` 3.26 이상)
- [ ] Ninja 설치 (`ninja --version`)
- [ ] Git LFS 설치 (`git lfs version`)
- [ ] CLion 또는 VS Code CMake Tools 확장 설치
- [ ] 빈 C++ "Hello World" CMake 프로젝트 빌드·실행 성공

---

## 문제 발생 시
- 에러 메시지 그대로 Claude에게 전달하시면 해결책을 찾아드립니다.
- macOS 버전, Apple Silicon 여부, 설치 시도한 명령을 함께 알려주세요.
