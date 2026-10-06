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
  gpu:   {name:'GPU 다이(연산)', desc:'TSMC 4N 급 로직 다이. 설계는 엔비디아, 제조는 TSMC — 둘 다 해외. 국내는 직접 대장주가 없고 후공정 장비 · 테스트가 붙는다.',
          stocks:[[1,'NVIDIA(해외)','설계'],[2,'TSMC(해외)','파운드리'],[3,'리노공업 032500','테스트 소켓(판단)']]},
  hbm:   {name:'HBM — D램 8단 스택', desc:'D램 다이를 TSV 로 수직으로 쌓은 고대역폭 메모리. 주신 그림의 「D램」 층. 재권님 그림대로 GPU 위에 수직 적층(HBM4 식)으로 놓았다.',
          stocks:[[1,'SK하이닉스 000660','HBM 1위'],[2,'삼성전자 005930','HBM3E·HBM4'],[3,'한미반도체 042700','TC 본더']]},
  tsv:   {name:'TSV · 마이크로 범프', desc:'D램 층을 관통하는 미세 전극과 층 사이의 범프. 「HBM 층 벌림」 을 올리면 층 사이 범프가 보인다.',
          stocks:[[1,'한미반도체 042700','TC 본더'],[2,'한화세미텍(비상장)','본더'],[3,'이오테크닉스 039030','레이저'],[3,'피에스케이홀딩스 031980','범프 장비(판단)']]},
  base:  {name:'베이스 다이(로직)', desc:'HBM 스택 맨 아래 로직 다이. HBM4 부터 파운드리 공정(삼성 · TSMC)으로 만든다 — 메모리 회사와 파운드리의 접점.',
          stocks:[[1,'삼성전자 005930','파운드리+메모리'],[2,'TSMC(해외)','HBM4 베이스 다이'],[3,'—','미정']]},
  inter: {name:'실리콘 인터포저(2.5D)', desc:'GPU 와 HBM 을 잇는 실리콘 판(TSMC CoWoS). 국내 직접 대장주는 없다 — 유리기판 · 하이브리드 본딩이 다음 자리.',
          stocks:[[1,'TSMC(해외)','CoWoS'],[2,'—','유리기판은 별도 지도'],[3,'하나마이크론 067310','패키징(판단)']]},
  sub:   {name:'패키지 기판(FC-BGA)', desc:'인터포저 아래 유기 기판. 신호를 보드로 내린다. 국내 대장은 삼성전기.',
          stocks:[[1,'삼성전기 009150','FC-BGA'],[2,'LG이노텍 011070','FC-BGA 진입'],[3,'대덕전자 353200','기판'],[3,'심텍 222800','기판']]},
  ball:  {name:'솔더볼(BGA)', desc:'기판 아래 수천 개 주석 공. 보드와 붙는 자리.',
          stocks:[[1,'덕산하이메탈 077360','솔더볼'],[2,'MK전자 033160','본딩 와이어·솔더'],[3,'—','']]},
};

// ── 질감 — 캔버스로 그린다(이미지 파일 없음) ─────────────────────────────
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

const M={
  pcb:new THREE.MeshStandardMaterial({map:pcbTex,roughness:.55,metalness:.15}),
  die:new THREE.MeshPhysicalMaterial({map:dieTex,roughness:.3,metalness:.55,iridescence:.6,iridescenceIOR:1.6,clearcoat:.4}),
  dram:new THREE.MeshStandardMaterial({map:dramTex,roughness:.32,metalness:.9}),
  base:new THREE.MeshPhysicalMaterial({color:'#2b2f3a',roughness:.35,metalness:.6,clearcoat:.3}),
  inter:new THREE.MeshStandardMaterial({map:interTex,roughness:.38,metalness:.8}),
  lid:new THREE.MeshStandardMaterial({map:lidTex,roughnessMap:lidRough,roughness:.5,metalness:.75,color:"#dfe3e8"}),
  ball:new THREE.MeshStandardMaterial({color:'#d9dde3',roughness:.25,metalness:1}),
  bump:new THREE.MeshStandardMaterial({color:'#e9d6a0',roughness:.3,metalness:1}),
};

// ── 장면 ────────────────────────────────────────────────────────────────
const stage=document.getElementById('stage');
const renderer=new THREE.WebGLRenderer({antialias:true});renderer.setPixelRatio(Math.min(devicePixelRatio,2));renderer.shadowMap.enabled=true;renderer.shadowMap.type=THREE.PCFSoftShadowMap;renderer.toneMapping=THREE.ACESFilmicToneMapping;renderer.toneMappingExposure=1.05;stage.appendChild(renderer.domElement);
const lr=new CSS2DRenderer();lr.domElement.style.position='absolute';lr.domElement.style.top='0';lr.domElement.style.pointerEvents='none';stage.appendChild(lr.domElement);
const scene=new THREE.Scene();scene.background=new THREE.Color(getComputedStyle(document.body).getPropertyValue('--bg').trim()||'#f6f7f9');
const pm=new THREE.PMREMGenerator(renderer);scene.environment=pm.fromScene(new RoomEnvironment(),.04).texture;
const camera=new THREE.PerspectiveCamera(33,1,.1,500);camera.position.set(64,74,82);
const ctl=new OrbitControls(camera,renderer.domElement);ctl.enableDamping=true;ctl.target.set(0,9,0);ctl.maxPolarAngle=Math.PI*.49;
const sun=new THREE.DirectionalLight('#fff',2.2);sun.position.set(30,60,25);sun.castShadow=true;sun.shadow.mapSize.set(2048,2048);Object.assign(sun.shadow.camera,{left:-60,right:60,top:60,bottom:-60,near:1,far:200});sun.shadow.bias=-.0005;scene.add(sun);
scene.add(new THREE.HemisphereLight("#ffffff","#b9c0cc",.9));const fill=new THREE.DirectionalLight("#fff",.8);fill.position.set(-40,30,-30);scene.add(fill);
const floor=new THREE.Mesh(new THREE.PlaneGeometry(400,400),new THREE.ShadowMaterial({opacity:.18}));floor.rotation.x=-Math.PI/2;floor.position.y=-2.6;floor.receiveShadow=true;scene.add(floor);

// ── 부품 만들기 ─────────────────────────────────────────────────────────
const movers=[]; // {obj, baseY, tier, side:[x,z] , layer}
const labels=[];
function box(w,h,d,mat,r=.15){const m=new THREE.Mesh(new RoundedBoxGeometry(w,h,d,3,r),mat);m.castShadow=m.receiveShadow=true;return m;}
function tag(obj,key,text,y){const el=document.createElement('div');el.className='lbl';el.textContent=text;const o=new CSS2DObject(el);o.position.set(0,y,0);obj.add(o);labels.push({el,key});return o;}
function part(key,obj,tier,side=[0,0],layer=0){obj.userData.key=key;obj.traverse(c=>c.userData.key=key);movers.push({obj,baseY:obj.position.y,tier,side,layer});scene.add(obj);return obj;}

// 기판
const sub=box(56,1.8,56,M.pcb,.3);sub.position.y=0;part('sub',sub,0);tag(sub,'sub','패키지 기판',-1.6);
// 솔더볼
{const g=new THREE.SphereGeometry(.42,14,10);const n=22;const im=new THREE.InstancedMesh(g,M.ball,n*n);const d=new THREE.Object3D();let k=0;for(let i=0;i<n;i++)for(let j=0;j<n;j++){d.position.set(-25.2+i*2.4,-1.3,-25.2+j*2.4);d.updateMatrix();im.setMatrixAt(k++,d.matrix);}im.castShadow=true;const grp=new THREE.Group();grp.add(im);grp.position.y=0;part('ball',grp,-0.55);tag(grp,'ball','솔더볼',-2.4);}
// 인터포저
const inter=box(46,.6,34,M.inter,.08);inter.position.y=1.2;part('inter',inter,1);tag(inter,'inter','실리콘 인터포저',-.6);
// GPU 다이
const gpu=box(21,1.1,17,M.die,.1);gpu.position.y=2.05;part('gpu',gpu,2);tag(gpu,'gpu','GPU 다이',1.2);
// HBM 스택 6
const LAY=8, LT=.34, LG=.1;
[[-17.5,-11],[-17.5,0],[-17.5,11],[17.5,-11],[17.5,0],[17.5,11]].forEach(([x,z],si)=>{
  const sideV=[Math.sign(x),0];
  const base=box(9.5,.7,10.5,M.base,.08);base.position.set(x,1.85,z);part('base',base,2,sideV);if(si===0)tag(base,'base','베이스 다이',-.9);
  for(let l=0;l<LAY;l++){
    const y=2.2+.35+l*(LT+LG);
    const g=new THREE.Group();g.position.set(x,y,z);
    const dr=box(9.5,LT,10.5,M.dram,.05);g.add(dr);
    // 층 사이 마이크로 범프
    const bg=new THREE.SphereGeometry(.07,6,5);const bn=10,bm=11;const im=new THREE.InstancedMesh(bg,M.bump,bn*bm);const d=new THREE.Object3D();let k=0;for(let i=0;i<bn;i++)for(let j=0;j<bm;j++){d.position.set(-3.6+i*.8,-LT/2-LG/2,-4+j*.8);d.updateMatrix();im.setMatrixAt(k++,d.matrix);}g.add(im);
    part(l<LAY-1?'tsv':'hbm',g,2,sideV,l+1);
    if(si===3&&l===LAY-1)tag(g,'hbm','HBM D램 스택',1);
    if(si===3&&l===3)tag(g,'tsv','TSV · 범프',0);
  }
});
// 리드
{const grp=new THREE.Group();const top=box(54,1.4,54,M.lid,.4);top.position.y=7.6;grp.add(top);
  const wallM=new THREE.MeshStandardMaterial({color:"#c9ced6",roughness:.5,metalness:.75});[[0,-26.3],[0,26.3]].forEach(([x,z])=>{const w=new THREE.Mesh(new THREE.BoxGeometry(54,6,1.4),wallM);w.position.set(x,4,z);w.castShadow=true;grp.add(w);});
  [[-26.3,0],[26.3,0]].forEach(([x,z])=>{const w=new THREE.Mesh(new THREE.BoxGeometry(1.4,6,54),wallM);w.position.set(x,4,z);w.castShadow=true;grp.add(w);});
  grp.position.y=0;part("lid",grp,5.5);tag(grp,'lid','히트스프레더',9.2);}

// ── 분해 ────────────────────────────────────────────────────────────────
const ex=document.getElementById('ex'),ly=document.getElementById('ly');
function layout(){const e=ex.value/100,l=ly.value/100;document.getElementById('exv').textContent=ex.value+'%';document.getElementById('lyv').textContent=ly.value+'%';
  for(const m of movers){let y=m.baseY+m.tier*e*7;if(m.layer)y+=m.layer*l*1.6+e*(m.layer>0?.3*m.layer:0);m.obj.position.y=y;
    m.obj.position.x=(m.obj.userData.x??(m.obj.userData.x=m.obj.position.x))+m.side[0]*e*9;}}
const q=new URLSearchParams(location.search);if(q.get('ex'))ex.value=q.get('ex');if(q.get('ly'))ly.value=q.get('ly');
ex.oninput=ly.oninput=layout;layout();

// ── 올리기 · 누르기 ──────────────────────────────────────────────────────
const ray=new THREE.Raycaster(),mouse=new THREE.Vector2();let hover=null,pinned=null;
const keyMats=new Map();
function setHi(key,on){scene.traverse(o=>{if(o.isMesh&&o.userData.key===key&&!o.isInstancedMesh){if(on){if(!keyMats.has(o))keyMats.set(o,o.material);o.material=o.material.clone();o.material.emissive=new THREE.Color('#3182f6');o.material.emissiveIntensity=.35;}else if(keyMats.has(o)){o.material=keyMats.get(o);keyMats.delete(o);}}});
  for(const L of labels)L.el.classList.toggle('pin',on&&L.key===key);}
renderer.domElement.addEventListener('pointermove',e=>{const r=renderer.domElement.getBoundingClientRect();mouse.set((e.clientX-r.left)/r.width*2-1,-((e.clientY-r.top)/r.height)*2+1);ray.setFromCamera(mouse,camera);const h=ray.intersectObjects(scene.children,true).find(i=>i.object.userData.key);const k=h?h.object.userData.key:null;if(k!==hover){if(hover&&hover!==pinned)setHi(hover,false);hover=k;if(hover)setHi(hover,true);}renderer.domElement.style.cursor=k?'pointer':'grab';});
renderer.domElement.addEventListener('click',()=>{if(hover){if(pinned&&pinned!==hover)setHi(pinned,false);pinned=hover;setHi(pinned,true);show(pinned);}});
function show(k){const p=PARTS[k];document.getElementById('pname').textContent=p.name;document.getElementById('pdesc').textContent=p.desc;
  document.getElementById('ptab').innerHTML='<tr><th>등급</th><th>종목</th><th>왜</th></tr>'+p.stocks.map(([g,s,w])=>`<tr><td><span class="pill g${g}">${G[g]}</span></td><td>${s}</td><td>${w||''}</td></tr>`).join('');
  document.querySelectorAll('#plist div').forEach(d=>d.classList.toggle('on',d.dataset.k===k));}
const pl=document.getElementById('plist');for(const k of Object.keys(PARTS)){const d=document.createElement('div');d.dataset.k=k;d.textContent='· '+PARTS[k].name;d.onclick=()=>{if(pinned)setHi(pinned,false);pinned=k;setHi(k,true);show(k);};pl.appendChild(d);}
document.getElementById('lab').onchange=e=>{lr.domElement.style.display=e.target.checked?'':'none';};

// ── 그리기 ──────────────────────────────────────────────────────────────
function resize(){const w=stage.clientWidth,h=stage.clientHeight;renderer.setSize(w,h);lr.setSize(w,h);camera.aspect=w/h;camera.updateProjectionMatrix();}
addEventListener('resize',resize);resize();
const rot=document.getElementById('rot');ctl.autoRotate=true;ctl.autoRotateSpeed=.6;rot.onchange=()=>ctl.autoRotate=rot.checked;
renderer.setAnimationLoop(()=>{ctl.update();renderer.render(scene,camera);lr.render(scene,camera);});
