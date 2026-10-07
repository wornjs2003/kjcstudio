// HBM 패키지 분해도(3D) — hbm3d.html 의 장면 · 부품 · 분해 슬라이더 (2026-10-06 · 시황분석)
// ⚠️ 아래 재질 색(기판 초록 · 금 · 실리콘 · 니켈 · 회로 무늬)은 실물 재질의 색이라 테마 변수가 아닌 **데이터**다
// (CLAUDE.md 「하드코딩 금지의 예외 — 테마 색과 데이터로서의 색」). 테마를 바꿔도 금은 금이다. 화면 글자 · 칸 색은 hbm3d.html 의 CSS 가 변수로 쓴다.
// 종목 · 등급(PARTS)은 시황분석 판단(2026-10-06 · 미확정 · 화면에 빨간 표시).
import * as THREE from 'three';
import {OrbitControls} from 'three/addons/controls/OrbitControls.js';
import {RoomEnvironment} from 'three/addons/environments/RoomEnvironment.js';
import {RoundedBoxGeometry} from 'three/addons/geometries/RoundedBoxGeometry.js';
import {CSS2DRenderer, CSS2DObject} from 'three/addons/renderers/CSS2DRenderer.js';

// ── 부품 정의 — 종목은 시황분석 판단(미확정) ─────────────────────────────
const G = {1:'대장주',2:'주도주',3:'소부장'};
const PARTS = {
  lid:   {name:'히트스프레더(리드)', desc:'니켈 도금 구리 뚜껑. 칩 열을 쿨러로 넘긴다. 국내 상장 대장주는 뚜렷하지 않다 — 열 인터페이스 · 방열 소재 쪽을 더 봐야 한다.',
          stocks:[[3,'—','열 소재 쪽은 미정']]},
  tim:   {name:'열 인터페이스(TIM)', desc:'리드와 칩 윗면 사이를 채우는 열전달 소재(그리스 · 인듐 · 금속 시트). 리드를 들어 올리면 아래에 얇은 막으로 보인다.',
          stocks:[[3,'—','국내 소재 대장주 미정']]},
  gpu:   {name:'GPU 다이(연산)', desc:'TSMC 4N 급 로직 다이. 설계는 엔비디아, 제조는 TSMC — 둘 다 해외. 국내는 직접 대장주가 없고 후공정 장비 · 테스트가 붙는다.',
          stocks:[[1,'NVIDIA(해외)','설계'],[2,'TSMC(해외)','파운드리'],[3,'리노공업 032500','테스트 소켓(판단)']]},
  hbm:   {name:'HBM — D램 12단 스택', desc:'D램 다이를 TSV 로 수직으로 쌓은 고대역폭 메모리. HBM3E 는 8단 · 12단, HBM4 는 12단 · 16단(SK하이닉스 핫칩스 2026). 12단으로 그렸다 — 전체 높이는 8단과 같게 다이를 얇게(삼성 12H 식).',
          stocks:[[1,'SK하이닉스 000660','HBM 1위'],[2,'삼성전자 005930','HBM3E·HBM4'],[3,'한미반도체 042700','TC 본더']]},
  ncf:   {name:'층간 충전재(NCF · MUF)', desc:'D램 층 사이 범프 둘레를 채우는 소재. 삼성은 필름(TC-NCF), SK하이닉스는 액상 몰드 언더필(MR-MUF). 「분해」 를 올리면 층 사이 얇은 막으로 보인다. 소재는 일본 쪽(나믹스 · 레조낙)이 크다.',
          stocks:[[1,'SK하이닉스 000660','MR-MUF'],[2,'삼성전자 005930','TC-NCF'],[3,'—','국내 소재 대장주 미정']]},
  tsv:   {name:'TSV · 마이크로 범프', desc:'D램 층을 관통하는 미세 전극과 층 사이의 범프. 「분해」 를 올리면 층 사이 범프가 보인다.',
          stocks:[[1,'한미반도체 042700','TC 본더'],[2,'한화세미텍(비상장)','본더'],[3,'이오테크닉스 039030','레이저'],[3,'피에스케이홀딩스 031980','범프 장비(판단)']]},
  base:  {name:'베이스 다이(로직)', desc:'HBM 스택 맨 아래 로직 다이. HBM4 부터 파운드리 공정(삼성 · TSMC)으로 만든다 — 메모리 회사와 파운드리의 접점.',
          stocks:[[1,'삼성전자 005930','파운드리+메모리'],[2,'TSMC(해외)','HBM4 베이스 다이'],[3,'—','미정']]},
  mold:  {name:'스택 몰드(EMC)', desc:'HBM 스택 둘레를 감싸 보호하는 에폭시 몰드. 반투명으로 그려 안의 층이 보이게 했다. 열이 빠져나가는 길이기도 해서 두께 · 소재가 HBM 발열의 변수다.',
          stocks:[[1,'—','소재는 해외(일본) 중심'],[3,'—','미정']]},
  uf:    {name:'언더필(다이 ↔ 인터포저 · 인터포저 ↔ 기판)', desc:'범프를 감싸 보호하고 열팽창 차이를 받아 주는 수지. GPU · HBM 아래와 인터포저 아래 두 자리에 들어간다. 얇은 막이라 분해를 올려야 보인다.',
          stocks:[[3,'—','국내 소재 대장주 미정']]},
  inter: {name:'실리콘 인터포저(2.5D)', desc:'GPU 와 HBM 을 잇는 실리콘 판(TSMC CoWoS-S). H100 이 이 식이고, B200 은 작은 실리콘 브리지 + 유기 인터포저(CoWoS-L)로 바뀐다 — 다음 세대는 L. 국내 직접 대장주는 없다 — 유리기판 · 하이브리드 본딩이 다음 자리.',
          stocks:[[1,'TSMC(해외)','CoWoS'],[2,'—','유리기판은 별도 지도'],[3,'하나마이크론 067310','패키징(판단)']]},
  c4:    {name:'C4 범프(인터포저 ↔ 기판)', desc:'인터포저 아래와 기판 사이의 범프. 마이크로 범프보다 크다(수십 µm). 조립 상태에서는 기판에 묻혀 안 보이고 분해를 올리면 인터포저 아래에 드러난다.',
          stocks:[[3,'덕산하이메탈 077360','솔더 소재(판단)'],[3,'—','미정']]},
  sub:   {name:'패키지 기판(FC-BGA)', desc:'인터포저 아래 유기 기판. 신호를 보드로 내린다. 국내 대장은 삼성전기.',
          stocks:[[1,'삼성전기 009150','FC-BGA'],[2,'LG이노텍 011070','FC-BGA 진입'],[3,'대덕전자 353200','기판'],[3,'심텍 222800','기판']]},
  stiff: {name:'스티프너 링', desc:'기판 둘레의 금속 테. 큰 기판이 휘는 것을 막고 리드가 그 위에 얹힌다. B300 부터 리드 없이 가는 설계가 나온다는 보도가 있다.',
          stocks:[[3,'—','미정']]},
  cap:   {name:'디커플링 캐패시터(MLCC)', desc:'기판 위 네 모서리의 작은 캐패시터. 전원 노이즈를 잡는다. 실제로는 기판 아래에도 붙는다. 국내 대장은 삼성전기(MLCC).',
          stocks:[[1,'삼성전기 009150','MLCC'],[3,'삼화콘덴서 001820','MLCC']]},
  ball:  {name:'솔더볼(BGA)', desc:'기판 아래 수천 개 주석 공. 보드와 붙는 자리.',
          stocks:[[1,'덕산하이메탈 077360','솔더볼'],[2,'MK전자 033160','본딩 와이어·솔더'],[3,'—','']]},
};

// ── 설명 칸 — 3D 가 없어도 돈다 (2026-10-07 재권님 「응」 · 창구 경유 · WebGL 실패 안내) ──
let onPick=null;   // 3D 가 떠 있으면 init3D 가 비추기(setHi)를 건다
function show(k){const p=PARTS[k];document.getElementById('pname').textContent=p.name;document.getElementById('pdesc').textContent=p.desc;
  document.getElementById('ptab').innerHTML='<tr><th>등급</th><th>종목</th><th>왜</th></tr>'+p.stocks.map(([g,s,w])=>`<tr><td><span class="pill g${g}">${G[g]}</span></td><td>${s}</td><td>${w||''}</td></tr>`).join('');
  document.querySelectorAll('#plist div').forEach(d=>d.classList.toggle('on',d.dataset.k===k));}
// 부품 목록 — 이름 아래 설명을 바로 보인다 (2026-10-06 재권님 「각 부품별로 설명이 있어야」). 누르면 그 부품을 비추고 위에 종목 표
{const pl=document.getElementById('plist');for(const k of Object.keys(PARTS)){const d=document.createElement('div');d.dataset.k=k;
  const nm=document.createElement('b');nm.textContent=PARTS[k].name;const ds=document.createElement('p');ds.textContent=PARTS[k].desc;d.append(nm,ds);
  d.onclick=()=>{if(onPick)onPick(k);show(k);};pl.appendChild(d);}}   // 모델을 누른 것과 같은 길 — 늘 선택(접기 없음 · 2026-10-06 재권님)
// WebGL 을 못 만들면(옛 기기 · 외부접속 브라우저 설정) 3D 자리에 안내만 두고 목록 · 종목 표는 그대로 쓴다 — 「못 한다」 를 빈 화면으로 두지 않는다
function noGL(why){const s=document.getElementById('stage');s.innerHTML='';const d=document.createElement('div');d.className='nogl';
  d.textContent='이 기기(브라우저)에서는 3D(WebGL)를 그릴 수 없습니다'+(why?' — '+why:'')+'. 부품 목록과 종목은 설명 칸에서 그대로 보실 수 있습니다.';s.appendChild(d);
  document.getElementById('bar').style.display='none';console.warn('[hbm3d] WebGL 없음',why||'');}
const glOK=(()=>{try{const c=document.createElement('canvas');return !!(c.getContext('webgl2')||c.getContext('webgl'));}catch(e){return false;}})();
if(glOK)init3D();else noGL('WebGL 컨텍스트 없음');

function init3D(){
// ── 질감 — 캔버스로 그린다(이미지 파일 없음) ─────────────────────────────
const T0=performance.now(),TM={};const mark=k=>{TM[k]=Math.round(performance.now()-T0);};   // 시작 단계 시간(?stats=1 에 찍는다)
function cv(w,h,f){const c=document.createElement('canvas');c.width=w;c.height=h;const x=c.getContext('2d');f(x,w,h);const t=new THREE.CanvasTexture(c);t.colorSpace=THREE.SRGBColorSpace;t.anisotropy=8;return t;}
const R=(a,b)=>a+Math.random()*(b-a);
const pcbTex=cv(1024,1024,(x,w,h)=>{x.fillStyle='#0d4a33';x.fillRect(0,0,w,h);
  for(let i=0;i<260;i++){x.strokeStyle=`rgba(${R(30,60)|0},${R(120,160)|0},${R(90,120)|0},.9)`;x.lineWidth=R(1,3);x.beginPath();let px=R(0,w),py=R(0,h);x.moveTo(px,py);for(let k=0;k<R(2,6);k++){if(Math.random()<.5)px=R(0,w);else py=R(0,h);x.lineTo(px,py);}x.stroke();}
  x.fillStyle='#d2a74a';for(let i=0;i<w;i+=32)for(let j=0;j<h;j+=32){if(i>120&&i<w-120&&j>120&&j<h-120)continue;x.beginPath();x.arc(i+16,j+16,6,0,7);x.fill();}
  x.fillStyle='#e6c66d';for(let i=0;i<900;i++){x.fillRect(R(130,w-140),R(130,h-140),4,4);}
});
const dieTex=cv(1024,1024,(x,w,h)=>{x.fillStyle='#14161d';x.fillRect(0,0,w,h);
  const cols=['#1b2340','#1f2a4a','#231c3d','#172d3b','#2a2238'];
  for(let i=0;i<8;i++)for(let j=0;j<6;j++){x.fillStyle=cols[(i*7+j*3)%cols.length];x.fillRect(40+i*118,40+j*156,110,148);}
  x.strokeStyle='rgba(120,135,170,.35)';x.lineWidth=1;for(let i=0;i<w;i+=8){x.beginPath();x.moveTo(i,0);x.lineTo(i,h);x.stroke();}for(let j=0;j<h;j+=8){x.beginPath();x.moveTo(0,j);x.lineTo(w,j);x.stroke();}
  x.strokeStyle='rgba(200,210,240,.5)';x.lineWidth=2;for(let i=0;i<60;i++){x.beginPath();x.moveTo(R(40,w-40),R(40,h-40));x.lineTo(R(40,w-40),R(40,h-40));x.stroke();}
  x.fillStyle='#c9ced9';for(let i=0;i<w;i+=20){x.fillRect(i+6,8,8,8);x.fillRect(i+6,h-16,8,8);}
});
const dramTex=cv(1024,512,(x,w,h)=>{const g=x.createLinearGradient(0,0,w,h);g.addColorStop(0,'#caa14a');g.addColorStop(.5,'#e3bf63');g.addColorStop(1,'#b98c35');x.fillStyle=g;x.fillRect(0,0,w,h);
  x.strokeStyle='rgba(90,60,10,.35)';x.lineWidth=1;for(let j=0;j<h;j+=6){x.beginPath();x.moveTo(0,j);x.lineTo(w,j);x.stroke();}
  x.fillStyle='#3a2a10';for(let i=0;i<w;i+=22)for(let j=h*.35;j<h*.65;j+=22){x.beginPath();x.arc(i+11,j+11,4,0,7);x.fill();}
  x.fillStyle='rgba(255,240,200,.25)';for(let i=0;i<40;i++)x.fillRect(R(0,w),R(0,h),R(30,120),2);
});
const interTex=cv(1024,1024,(x,w,h)=>{x.fillStyle='#8f949c';x.fillRect(0,0,w,h);x.fillStyle='#c8ccd2';for(let i=0;i<w;i+=12)for(let j=0;j<h;j+=12){x.beginPath();x.arc(i+6,j+6,2.2,0,7);x.fill();}
  x.strokeStyle='rgba(60,65,75,.5)';x.lineWidth=2;for(let i=0;i<18;i++){x.beginPath();x.moveTo(0,R(0,h));x.lineTo(w,R(0,h));x.stroke();}});
const lidTex=cv(1024,1024,(x,w,h)=>{x.fillStyle='#b4b8bf';x.fillRect(0,0,w,h);for(let j=0;j<h;j+=2){x.fillStyle=`rgba(${R(140,210)|0},${R(145,215)|0},${R(150,220)|0},.55)`;x.fillRect(0,j,w,1);}
  x.fillStyle='rgba(40,45,55,.55)';x.font='bold 150px Roboto, sans-serif';x.textAlign='center';x.fillText('KJC-H1',w/2,h/2+50);x.font='48px Roboto';x.fillText('AI ACCELERATOR · 2.5D',w/2,h/2+130);});
const lidRough=cv(512,512,(x,w,h)=>{for(let j=0;j<h;j++){x.fillStyle=`rgb(${R(70,120)|0},0,0)`;x.fillRect(0,j,w,1);}});lidRough.colorSpace=THREE.NoColorSpace;

mark('텍스처');const M={
  pcb:new THREE.MeshStandardMaterial({map:pcbTex,roughness:.55,metalness:.15}),
  die:new THREE.MeshStandardMaterial({map:dieTex,roughness:.3,metalness:.55}),   // 물리 재질(iridescence · clearcoat) → 표준 — 셰이더 컴파일 줄임(2026-10-06 로딩 개선)
  dram:new THREE.MeshStandardMaterial({map:dramTex,roughness:.32,metalness:.9}),
  base:new THREE.MeshStandardMaterial({color:'#2b2f3a',roughness:.35,metalness:.6}),
  inter:new THREE.MeshStandardMaterial({map:interTex,roughness:.38,metalness:.8}),
  lid:new THREE.MeshStandardMaterial({map:lidTex,roughnessMap:lidRough,roughness:.5,metalness:.75,color:"#dfe3e8"}),
  ball:new THREE.MeshStandardMaterial({color:'#d9dde3',roughness:.25,metalness:1}),
  bump:new THREE.MeshStandardMaterial({color:'#e9d6a0',roughness:.3,metalness:1}),
  // 2026-10-06 더한 부품 — 반투명은 안의 층이 보이게
  mold:new THREE.MeshStandardMaterial({color:'#2a2d33',roughness:.6,metalness:.05,transparent:true,opacity:.28,depthWrite:false}),
  ncf:new THREE.MeshStandardMaterial({color:'#d9c58a',roughness:.7,transparent:true,opacity:.55,depthWrite:false}),
  uf:new THREE.MeshStandardMaterial({color:'#8c8f96',roughness:.8,transparent:true,opacity:.6,depthWrite:false}),
  tim:new THREE.MeshStandardMaterial({color:'#aab4c4',roughness:.9,metalness:.2,transparent:true,opacity:.7,depthWrite:false}),
  c4:new THREE.MeshStandardMaterial({color:'#cfd3d9',roughness:.3,metalness:1}),
  stiff:new THREE.MeshStandardMaterial({color:'#9aa0a8',roughness:.45,metalness:.8}),
  cap:new THREE.MeshStandardMaterial({color:'#6b4a2b',roughness:.6,metalness:.1}),
};

// ── 장면 ────────────────────────────────────────────────────────────────
const stage=document.getElementById('stage');
let renderer;try{renderer=new THREE.WebGLRenderer({antialias:true});}catch(e){noGL(e&&e.message?e.message.slice(0,60):'');return;}renderer.setPixelRatio(Math.min(devicePixelRatio,1.25));/* 2026-10-06 최적화 — 2 → 1.25. 재권님 창(2560 · 배율 1.5)에서 캔버스가 3300×1908 이었다 */renderer.shadowMap.enabled=true;renderer.shadowMap.type=THREE.PCFShadowMap;renderer.toneMapping=THREE.ACESFilmicToneMapping;renderer.toneMappingExposure=1.05;stage.appendChild(renderer.domElement);
const lr=new CSS2DRenderer();lr.domElement.style.position='absolute';lr.domElement.style.top='0';lr.domElement.style.pointerEvents='none';stage.appendChild(lr.domElement);
const scene=new THREE.Scene();scene.background=new THREE.Color(getComputedStyle(document.body).getPropertyValue('--bg').trim()||'#f6f7f9');
mark('렌더러');const pm=new THREE.PMREMGenerator(renderer);scene.environment=pm.fromScene(new RoomEnvironment(),.04).texture;mark('환경맵');
const camera=new THREE.PerspectiveCamera(33,1,.1,500);camera.position.set(128,148,164);   // 2026-10-06 재권님 「지금보다 1/2 정도로」 — 전에는 (64,74,82). 거리를 두 배로
const ctl=new OrbitControls(camera,renderer.domElement);ctl.enableDamping=true;ctl.target.set(0,9,0);ctl.maxPolarAngle=Math.PI*.49;
const sun=new THREE.DirectionalLight('#fff',2.2);sun.position.set(30,60,25);sun.castShadow=true;sun.shadow.mapSize.set(1024,1024);/* 2048 → 1024 (최적화) */Object.assign(sun.shadow.camera,{left:-60,right:60,top:60,bottom:-60,near:1,far:200});sun.shadow.bias=-.0005;scene.add(sun);
scene.add(new THREE.HemisphereLight("#ffffff","#b9c0cc",.9));const fill=new THREE.DirectionalLight("#fff",.8);fill.position.set(-40,30,-30);scene.add(fill);
const floor=new THREE.Mesh(new THREE.PlaneGeometry(400,400),new THREE.ShadowMaterial({opacity:.18}));floor.rotation.x=-Math.PI/2;floor.position.y=-2.6;floor.receiveShadow=true;scene.add(floor);

// ── 부품 만들기 ─────────────────────────────────────────────────────────
let dirty=true;const redraw=()=>{dirty=true;};   // 필요할 때만 그린다(최적화) — 카메라가 움직였거나(자동 회전 · 끌기 · 감쇠) 비추기 · 분해 · 이름표가 바뀌었을 때. 맨 앞에 둔다(layout 이 시작 때 부른다)
const movers=[]; // {obj, baseY, tier, side:[x,z] , layer}
const labels=[];
function box(w,h,d,mat,r=.15){const m=new THREE.Mesh(new RoundedBoxGeometry(w,h,d,3,r),mat);m.castShadow=m.receiveShadow=true;return m;}
// 이름표 — 부품의 가장자리(anchor)에서 꼬리표 자리(tip)까지 선으로 잇는다 (2026-10-06 재권님 「부품이랑 이름이랑 줄로 연결」).
// 좌표는 그 부품(obj) 기준이라 분해 슬라이더로 부품이 움직여도 선이 따라간다. 꼬리표는 점의 바깥쪽(왼쪽 · 오른쪽)에 붙는다
const leadColor=getComputedStyle(document.body).getPropertyValue('--text-sub').trim()||'#4e5968';
M.lead=new THREE.LineBasicMaterial({color:leadColor,transparent:true,opacity:.9,depthTest:false});   // 부품 뒤에 가려지지 않게 늘 위에
M.leadDot=new THREE.MeshBasicMaterial({color:leadColor,depthTest:false});
function tag(obj,key,text,anchor,tip){
  const el=document.createElement('div');el.className='lbl '+(tip[0]<anchor[0]?'l':'r');
  const sp=document.createElement('span');sp.textContent=text;el.appendChild(sp);
  const o=new CSS2DObject(el);o.position.set(...tip);obj.add(o);
  const line=new THREE.Line(new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(...anchor),new THREE.Vector3(...tip)]),M.lead);line.renderOrder=999;obj.add(line);
  const dot=new THREE.Mesh(new THREE.SphereGeometry(.4,8,6),M.leadDot);dot.position.set(...anchor);dot.renderOrder=999;dot.userData.noHi=true;obj.add(dot);   // 비추기 · 고르기 대상 아님
  labels.push({el,key,line,dot});return o;}
function part(key,obj,tier,side=[0,0],layer=0){obj.userData.key=key;obj.traverse(c=>{if(!c.userData.key)c.userData.key=key;});/* 자식이 제 이름(ncf · tim …)을 이미 가졌으면 덮지 않는다 */movers.push({obj,baseY:obj.position.y,tier,side,layer});scene.add(obj);return obj;}

// 기판
const sub=box(56,1.8,56,M.pcb,.3);sub.position.y=0;part('sub',sub,0);
// 디커플링 캐패시터 — 기판 위 네 모서리(스티프너 링 안쪽) · 기판의 자식이라 함께 움직인다
{let capTag=null;[[-23,-21],[-20,-21],[23,21],[20,21],[-23,21],[-20,21],[23,-21],[20,-21]].forEach(([x,z],i)=>{const c=new THREE.Mesh(new THREE.BoxGeometry(1.6,.7,.9),M.cap);c.position.set(x,.9+.35,z);c.castShadow=true;c.userData.key='cap';sub.add(c);if(i===6)capTag=c;});
  tag(capTag,'cap','캐패시터',[0,.35,0],[16,7,-6]);}
// 스티프너 링 — 기판 둘레 금속 테. 리드 벽이 이 위에 얹힌다
{const grp=new THREE.Group();const rm=M.stiff;[[0,-26.3,54,1.6],[0,26.3,54,1.6],[-26.3,0,1.6,54],[26.3,0,1.6,54]].forEach(([x,z,w,d])=>{const b=new THREE.Mesh(new THREE.BoxGeometry(w,1.5,d),rm);b.position.set(x,.9+.75,z);b.castShadow=b.receiveShadow=true;grp.add(b);});
  part('stiff',grp,.5);tag(grp,'stiff','스티프너 링',[27,1.65,14],[44,-1,22]);}tag(sub,'sub','패키지 기판',[28,0,14],[44,-10,16]);
// 솔더볼
{const g=new THREE.SphereGeometry(.42,14,10);const n=22;const im=new THREE.InstancedMesh(g,M.ball,n*n);const d=new THREE.Object3D();let k=0;for(let i=0;i<n;i++)for(let j=0;j<n;j++){d.position.set(-25.2+i*2.4,-1.3,-25.2+j*2.4);d.updateMatrix();im.setMatrixAt(k++,d.matrix);}im.castShadow=true;const grp=new THREE.Group();grp.add(im);grp.position.y=0;part('ball',grp,-0.55);tag(grp,'ball','솔더볼',[-26,-1.3,12],[-40,-14,14]);}
// 인터포저
const inter=box(46,.6,34,M.inter,.08);inter.position.y=1.2;part('inter',inter,1);
{const u=new THREE.Mesh(new THREE.BoxGeometry(47,.28,35),M.uf);u.position.y=-.3-.14;u.userData.key='uf';inter.add(u);   // 인터포저 ↔ 기판 언더필
  const g=new THREE.SphereGeometry(.22,8,6);const nx=22,nz=16;const im=new THREE.InstancedMesh(g,M.c4,nx*nz);const d=new THREE.Object3D();let k=0;
  for(let i=0;i<nx;i++)for(let j=0;j<nz;j++){d.position.set(-21+i*2,-.3-.2,-15+j*2);d.updateMatrix();im.setMatrixAt(k++,d.matrix);}im.userData.key='c4';inter.add(im);
  const c4t=new THREE.Object3D();c4t.position.set(0,-.5,0);inter.add(c4t);tag(c4t,'c4','C4 범프',[-23,0,8],[-40,-9,16]);}tag(inter,'inter','실리콘 인터포저',[-23,0,4],[-42,-3,6]);
// GPU 다이
const gpu=box(21,1.1,17,M.die,.1);gpu.position.y=2.05;part('gpu',gpu,2);
{const u=new THREE.Mesh(new THREE.BoxGeometry(22,.26,18),M.uf);u.position.y=-.55-.13;u.userData.key='uf';gpu.add(u);tag(u,'uf','언더필',[-11,0,0],[-26,-8,8]);}tag(gpu,'gpu','GPU 다이',[0,.6,8.5],[-6,-5,30]);
// HBM 스택 6
const LAY=12, LT=.22, LG=.07;
const G_DRAM=new RoundedBoxGeometry(9.5,LT,10.5,2,.05), G_NF=new THREE.BoxGeometry(9.6,LG,10.6), G_BUMP=new THREE.SphereGeometry(.07,5,4);   // 72층이 한 벌을 나눠 쓴다(최적화 — 전에는 층마다 셋씩)
   // 12단 — 전체 높이는 8단(.34+.1)과 비슷하게 다이를 얇게(삼성 HBM3E 12H 식)
[[-17.5,-11],[-17.5,0],[-17.5,11],[17.5,-11],[17.5,0],[17.5,11]].forEach(([x,z],si)=>{
  const sideV=[Math.sign(x),0];
  const base=box(9.5,.7,10.5,M.base,.08);base.position.set(x,1.85,z);part('base',base,2,sideV);
  {const u=new THREE.Mesh(new THREE.BoxGeometry(10.3,.24,11.3),M.uf);u.position.y=-.35-.12;u.userData.key='uf';base.add(u);}   // 베이스 ↔ 인터포저 언더필
  // 스택 몰드(EMC) — 스택 둘레를 반투명으로. 베이스와 같은 층(tier 2 · 같은 쪽)으로 움직인다
  {const h=LAY*(LT+LG)+.4;const m=new THREE.Mesh(new THREE.BoxGeometry(10.4,h,11.4),M.mold);m.position.set(x,2.2+.35+h/2-.3,z);part('mold',m,2,sideV);if(si===5)tag(m,'mold','스택 몰드',[0,h/2-1,5.7],[0,h/2+2,22]);}if(si===0)tag(base,'base','베이스 다이',[-4.75,0,-3],[-24,9,-10]);
  for(let l=0;l<LAY;l++){
    const y=2.2+.35+l*(LT+LG);
    const g=new THREE.Group();g.position.set(x,y,z);
    const dr=new THREE.Mesh(G_DRAM,M.dram);dr.castShadow=dr.receiveShadow=true;g.add(dr);
    const nf=new THREE.Mesh(G_NF,M.ncf);nf.position.y=-LT/2-LG/2;nf.userData.key='ncf';g.add(nf);   // 층간 충전재(NCF · MUF)
    if(si===0&&l===6)tag(nf,'ncf','층간 충전재',[-4.8,0,0],[-19,-6,0]);
    // 층 사이 마이크로 범프
    const bn=6,bm=7;const im=new THREE.InstancedMesh(G_BUMP,M.bump,bn*bm);/* 110 → 42 개 (최적화) */const d=new THREE.Object3D();let k=0;for(let i=0;i<bn;i++)for(let j=0;j<bm;j++){d.position.set(-3.5+i*1.4,-LT/2-LG/2,-4.2+j*1.4);d.updateMatrix();im.setMatrixAt(k++,d.matrix);}g.add(im);
    part(l<LAY-1?'tsv':'hbm',g,2,sideV,l+1);
    if(si===3&&l===LAY-1)tag(g,'hbm','HBM D램 스택',[4.75,0,0],[19,6,0]);
    if(si===3&&l===3)tag(g,'tsv','TSV · 범프',[4.75,-.2,0],[19,-3,0]);
  }
});
// 리드
{const grp=new THREE.Group();const top=box(54,1.4,54,M.lid,.4);top.position.y=7.6;grp.add(top);
  const wallM=new THREE.MeshStandardMaterial({color:"#c9ced6",roughness:.5,metalness:.75});[[0,-26.3],[0,26.3]].forEach(([x,z])=>{const w=new THREE.Mesh(new THREE.BoxGeometry(54,4.5,1.4),wallM);w.position.set(x,4.65,z);w.castShadow=true;grp.add(w);});
  [[-26.3,0],[26.3,0]].forEach(([x,z])=>{const w=new THREE.Mesh(new THREE.BoxGeometry(1.4,4.5,54),wallM);w.position.set(x,4.65,z);w.castShadow=true;grp.add(w);});
  {const t=new THREE.Mesh(new THREE.BoxGeometry(50,.3,50),M.tim);t.position.y=6.9-.15;t.userData.key='tim';grp.add(t);tag(t,'tim','열 인터페이스(TIM)',[-25,0,-4],[-42,6,-10]);}   // 리드 아래 TIM
  grp.position.y=0;part("lid",grp,5.5);tag(grp,'lid','히트스프레더',[27,7.6,-12],[41,15,-12]);}

mark('장면');
// ── 분해 ────────────────────────────────────────────────────────────────
// 층 벌림 슬라이더(ly)는 2026-10-06 재권님 「없어도 돼」 로 뺐다 — 층 사이는 「분해」 가 조금 띄운다(l=0 · 아래 .3*layer)
const ex=document.getElementById('ex');
function layout(){const e=ex.value/100,l=0;document.getElementById('exv').textContent=ex.value+'%';
  for(const m of movers){let y=m.baseY+m.tier*e*7;if(m.layer)y+=m.layer*l*1.6+e*(m.layer>0?.3*m.layer:0);m.obj.position.y=y;
    m.obj.position.x=(m.obj.userData.x??(m.obj.userData.x=m.obj.position.x))+m.side[0]*e*9;}redraw();}
const q=new URLSearchParams(location.search);if(q.get('ex'))ex.value=q.get('ex');
ex.oninput=layout;layout();

// ── 올리기 · 누르기 ──────────────────────────────────────────────────────
const ray=new THREE.Raycaster(),mouse=new THREE.Vector2();let hover=null,pinned=null;
const keyMats=new Map();
// 비추기 — 원본 재질마다 밝은 판을 한 번만 만들어 둔다(최적화 · 2026-10-06). 전에는 누를 때마다 메시마다 재질을 복제해 쌓였다(tsv 는 132개)
const hiMats=new Map();const hiOf=m=>{if(!('emissive' in m))return m;/* 2026-10-06 사고 — emissive 없는 재질(지시선 점)에 넣으면 그리기 루프가 uniforms.emissive.value 에서 죽어 화면이 얼었다 */let h=hiMats.get(m);if(!h){h=m.clone();h.emissive=new THREE.Color('#3182f6');h.emissiveIntensity=.35;hiMats.set(m,h);}return h;};
const byKey=new Map();   // key → 메시 목록. 매번 장면 전체를 훑지 않는다
function setHi(key,on){if(!byKey.size)scene.traverse(o=>{if(o.isMesh&&o.userData.key&&!o.isInstancedMesh&&!o.userData.noHi){if(!byKey.has(o.userData.key))byKey.set(o.userData.key,[]);byKey.get(o.userData.key).push(o);}});
  for(const o of byKey.get(key)||[]){if(on){if(!keyMats.has(o)){keyMats.set(o,o.material);o.material=hiOf(o.material);}}else if(keyMats.has(o)){o.material=keyMats.get(o);keyMats.delete(o);}}
  for(const L of labels)L.el.classList.toggle('pin',on&&L.key===key);redraw();}
// 광선을 쏘는 대상은 「고를 수 있는 부품」 만 — 범프 · 솔더볼 · C4(인스턴스 수천 개) · 바닥 · 스택 몰드(스택을 감싸 클릭을 가로챈다)는 뺀다.
// 2026-10-06 부품이 늘자 끌기가 안 먹었다(재권님) — 마우스가 움직일 때마다 전부에 쏘던 것이 원인. 끄는 동안은 아예 안 쏜다
const pickables=[];scene.traverse(o=>{if(o.isMesh&&o.userData.key&&!o.isInstancedMesh&&!o.userData.noHi&&o.userData.key!=='mold')pickables.push(o);});
let orbiting=false;ctl.addEventListener('start',()=>{orbiting=true;});ctl.addEventListener('end',()=>{orbiting=false;});
renderer.domElement.addEventListener('pointermove',e=>{if(orbiting)return;const r=renderer.domElement.getBoundingClientRect();mouse.set((e.clientX-r.left)/r.width*2-1,-((e.clientY-r.top)/r.height)*2+1);ray.setFromCamera(mouse,camera);const h=ray.intersectObjects(pickables,false).find(i=>i.object.userData.key);const k=h?h.object.userData.key:null;if(k!==hover){if(hover&&hover!==pinned)setHi(hover,false);hover=k;if(hover)setHi(hover,true);}renderer.domElement.style.cursor=k?'pointer':'grab';});
renderer.domElement.addEventListener('click',()=>{if(hover){if(pinned&&pinned!==hover)setHi(pinned,false);pinned=hover;setHi(pinned,true);show(pinned);}});
onPick=k=>{if(pinned&&pinned!==k)setHi(pinned,false);pinned=k;setHi(k,true);};   // 목록 누르기 → 비추기(목록 자체는 위 공용 자리에서 만든다)
document.getElementById('lab').onchange=e=>{lr.domElement.style.display=e.target.checked?'':'none';for(const L of labels){L.line.visible=L.dot.visible=e.target.checked;}redraw();};

// ── 그리기 ──────────────────────────────────────────────────────────────
function resize(){const w=stage.clientWidth,h=stage.clientHeight;renderer.setSize(w,h);lr.setSize(w,h);camera.aspect=w/h;
  // 세로가 더 긴 틀(폰 · 55vh 칸)에서는 세로 시야각을 넓혀 가로 폭이 데스크톱의 세로 폭만큼 들어오게 한다 — 안 그러면 모델이 좌우로 잘린다(2026-10-07 폰 대응). 가로가 더 길면(데스크톱) 33 그대로
  camera.fov=camera.aspect>=1?33:Math.atan(Math.tan(33*Math.PI/360)/camera.aspect)*360/Math.PI;camera.updateProjectionMatrix();}
addEventListener('resize',()=>{resize();redraw();});resize();
const rot=document.getElementById('rot');ctl.autoRotate=true;ctl.autoRotateSpeed=.6;rot.onchange=()=>ctl.autoRotate=rot.checked;
let loopErr=0,firstFrame=false;
renderer.setAnimationLoop(()=>{const moved=ctl.update();if(moved||dirty){dirty=false;try{renderer.render(scene,camera);lr.render(scene,camera);if(!firstFrame){firstFrame=true;mark('첫그림');}}catch(e){if(loopErr++===0)console.error('[hbm3d] 그리기 오류 — 루프는 계속 돈다',e);if(window.__diagErr)window.__diagErr(e);}}});
// ?stats=1 — 그리기 호출 · 삼각형 · 프레임 시간을 안내 칸에 적는다(최적화 재기 · 2026-10-06). 평소에는 안 돈다
// ?diag=1 — 재권님 창에서 끌기가 안 될 때: 캔버스가 받는 포인터 이벤트 · 조작기(OrbitControls) 신호 · 오류를 안내 칸에 적는다 (2026-10-06)
if(q.get('diag')){const C={down:0,move:0,up:0,start:0,change:0,end:0,click:0,err:''};const h=document.getElementById('hint');
  const paint=()=>{h.textContent=`진단 down=${C.down} move=${C.move} up=${C.up} | ctl start=${C.start} change=${C.change} end=${C.end} | click=${C.click} pinned=${pinned} hover=${hover} orbiting=${orbiting} autoRotate=${ctl.autoRotate} enabled=${ctl.enabled} | cam=${camera.position.x.toFixed(0)},${camera.position.z.toFixed(0)} | ${C.err}`;};
  for(const t of ['pointerdown','pointermove','pointerup']){renderer.domElement.addEventListener(t,e=>{C[t.slice(7)]++;if(t!=='pointermove'||C.move%10===0)paint();});}
  renderer.domElement.addEventListener('click',()=>{C.click++;paint();});
  ctl.addEventListener('start',()=>{C.start++;paint();});ctl.addEventListener('change',()=>{C.change++;if(C.change%10===0)paint();});ctl.addEventListener('end',()=>{C.end++;paint();});
  window.__diagErr=e=>{C.err='그리기 오류: '+e.message+' @ '+String(e.stack||'').split('\n').slice(1,3).map(x=>x.trim().replace(/^at /,'').replace(/https?:\/\/[^ )]*\//g,'')).join(' ← ');paint();};
  window.addEventListener('error',e=>{C.err='오류: '+e.message+' @ '+String(e.error&&e.error.stack||'').split('\n').slice(1,4).map(x=>x.trim().replace(/^at /,'').replace(/https?:\/\/[^ )]*\//g,'')).join(' ← ');paint();});paint();}
if(q.get('stats')){window.__dbg={camera,ctl,renderer,get pinned(){return pinned;},get hover(){return hover;}};const t0=performance.now();let n=0;const tick=()=>{n++;if(performance.now()-t0<3000){requestAnimationFrame(tick);return;}
  const i=renderer.info;document.getElementById('hint').textContent=`단계(ms) ${JSON.stringify(TM)} · 모듈시작 ${Math.round(T0)} | stats calls=${i.render.calls} tris=${i.render.triangles} geom=${i.memory.geometries} tex=${i.memory.textures} ms/frame=${((performance.now()-t0)/n).toFixed(1)} dpr=${renderer.getPixelRatio()} size=${renderer.domElement.width}x${renderer.domElement.height}`;};requestAnimationFrame(tick);}
}   // init3D 끝
