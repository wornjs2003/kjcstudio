# thekjc.co.kr 앞문 서버 — 설정 사본 · 다시 세우는 순서 · 사고 대응

**쉬운 말로 — 이 폴더만 있으면 가비아 서버를 잃어도 새로 세울 수 있다. 비밀값(열쇠 · 비밀번호)은 여기 없다.**

룰은 `CLAUDE.md` 「thekjc.co.kr 앞문 서버 — 관리 열쇠는 잠가 메일에 · 1년마다 간다 · GitHub 에는 설정만」. 레인은 개념정의.

## 생김새 (2026-11-04)

    방문자 → https://thekjc.co.kr → 가비아 서버(Caddy · 아이디·비밀번호 문 · fail2ban)
             → 127.0.0.1:18764 ⇄ [맥미니가 SSH 로 걸어 둔 통로] ⇄ 맥미니 메인(8764)

| 무엇 | 값 |
|---|---|
| 서버 | 가비아 클라우드 `thekjc-front` · 공인 IP 1.201.111.167 · Ubuntu 24.04 · 관리 계정 `ubuntu` |
| DNS(가비아) | A `@` → 1.201.111.167 · A `www` → 1.201.111.167 |
| 보안 그룹 | 들어옴 — 443 · 80 전부 · **22 는 사무실 IP 만**(값은 가비아 보안 그룹에서 본다 — 공개 저장소라 여기 안 적는다) · 나감 전부 |
| 맥미니 통로 | `launchd/kr.kjcstudio.thekjc-tunnel.plist` · 열쇠 `~/.ssh/thekjc-tunnel` |
| 관리 열쇠 | `~/.ssh/thekjc-front.pem` — 사본은 잠가서 재권님 메일에(`admin-key.py`) |

## 이 폴더

| 파일 | 서버 자리 |
|---|---|
| `server/Caddyfile` | `/etc/caddy/Caddyfile` — 비밀번호 해시 자리는 비워 두었다 |
| `server/thekjc.conf` | `/etc/fail2ban/jail.d/thekjc.conf` — 10분 안에 5번 틀리면 1시간 · 사무실 IP 제외 |
| `server/caddy-thekjc.conf` | `/etc/fail2ban/filter.d/caddy-thekjc.conf` — 비밀번호를 넣었는데 틀린 것만 센다 |
| `server/60-tunnel.conf` | `/etc/ssh/sshd_config.d/60-tunnel.conf` — 통로 사용자의 죽은 연결을 90초 안에 끊는다 |
| `admin-key.py` | 관리 열쇠 — 갈기 · 잠그기 · 알림 · 풀기 |

**서버 설정을 고치면 이 폴더 사본도 같이 고친다.** 안 고치면 다시 세울 때 옛 설정이 나온다.
대조 도구는 아직 없다 — `ssh … sudo cat <자리>` 와 `diff` 로 손으로 본다.

## 사고 대응 — 위에서부터

| 무슨 일 | 어떻게 되나 | 대응 |
|---|---|---|
| 맥미니가 꺼짐 · 고장 | 회사 페이지가 안 뜬다(502) · 서버와 비밀번호 문은 멀쩡 | 맥미니를 켜고 로그인하면 통로가 저절로 다시 걸린다 |
| 사무실 인터넷 IP 가 바뀜 | 통로가 끊겨 회사 페이지가 안 뜬다 · 관리도 못 들어감 | 가비아 보안 그룹 22번 줄의 IP 를 새 사무실 IP 로(재권님 손). 새 IP 는 `curl -s https://api.ipify.org` |
| 통로 열쇠가 샘 | 그 열쇠로는 명령을 못 치고 18764 하나만 연다 | 새 열쇠를 만들어 `/home/tunnel/.ssh/authorized_keys` 를 갈고 옛 것을 지운다 |
| 관리 열쇠가 샘 | 사무실 인터넷 밖에서는 문에 안 닿는다 | `admin-key.py rotate` → `seal` → 메일 → `sent` |
| **관리 열쇠를 잃음** | 서버 설정을 못 고친다 · 회사 페이지는 계속 돈다 | ① 메일의 잠근 파일 → `! python3 tools/thekjc-front/admin-key.py open <파일>` |
| 메일도 없음 · 비밀번호도 잊음 | 〃 | ② 가비아 웹 콘솔 — **있는지 확인 안 됨.** 있어도 계정에 비밀번호가 없어(`passwd -S` L) 그대로는 못 들어간다 |
| 그것도 안 됨 · 서버를 잃음 | 〃 | ③ 아래 「다시 세우기」 — 가비아에 새 서버를 만들고 이 폴더대로 |

## 다시 세우기

1. 가비아에 새 서버 — Ubuntu 24.04 · 받은 열쇠를 `~/.ssh/thekjc-front.pem`(600)으로. 공인 IP 가 바뀌면 DNS 두 줄 · 이 문서 · `admin-key.py` 의 `HOST` · 통로 등록 파일을 함께 고친다
2. 보안 그룹 — 위 표대로
3. `sudo apt update && sudo apt full-upgrade -y` · `unattended-upgrades` 켜기
4. Caddy — 공식 저장소(`https://caddyserver.com/docs/install` 의 Debian/Ubuntu 줄) · `server/Caddyfile` 을 놓고
   비밀번호 해시는 `caddy hash-password` 로 새로 만들어 넣는다(재권님께 새 비밀번호를 드린다)
   - `caddy validate` 는 **`sudo -u caddy`** 로 — root 로 돌리면 기록 파일이 root 것이 되어 다시 읽기가 실패한다(2026-11-04 겪음)
5. fail2ban — `sudo apt install fail2ban` · `server/thekjc.conf` · `server/caddy-thekjc.conf` 를 제자리에 · `fail2ban-client status caddy-thekjc`
6. 통로 사용자 — `sudo useradd -m -s /usr/sbin/nologin tunnel` · `server/60-tunnel.conf` · `/home/tunnel/.ssh/authorized_keys`(700/600 · 주인 tunnel)에 한 줄
   `restrict,port-forwarding,permitlisten="127.0.0.1:18764",command="/bin/false" <맥미니 ~/.ssh/thekjc-tunnel.pub>`
7. 맥미니 — `ssh -i ~/.ssh/thekjc-front.pem ubuntu@<IP> true` 로 서버 지문을 한 번 받아 두고 통로 등록 파일을 다시 켠다(파일 머리의 끄기 · 켜기)
8. 재기 — 바깥에서 비밀번호 없음 401 · 틀림 401 · 맞음 200 · www 301 · http 308 · 사무실 밖 IP 로 5번 틀려 막히는지
9. 관리 열쇠를 `admin-key.py seal` 로 잠가 메일에

## 1년 갱신

`launchd/kr.kjcstudio.thekjc-key-remind.plist` 가 달마다 1일 10:00 에 `admin-key.py remind --send` 를 부른다 —
메일로 보낸 지 1년(값은 `admin-key.py` 의 `RENEW_DAYS`)이 넘었거나 보낸 기록이 없으면 텔레그램 한 통. **설치는 켜기라 재권님 지시로.**

    알림이 오면     재권님 「해」 뒤 개념정의가 rotate → 재권님이 `! … seal` → 메일로 보냄 → 세션이 sent
    지금 상태      python3 tools/thekjc-front/admin-key.py status
