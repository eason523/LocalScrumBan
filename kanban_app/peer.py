"""peer — P2P 局域网协作层。

每个节点 = 本地 Store + zeroconf mDNS 注册/发现 + 内嵌 HTTP 同步服务。
本地 UI 动作通过 local_* 入口广播事件;远端事件经 apply_remote_event 合入。

事件协议 (JSON):
    { "type": "add_task" | "update_task" | "delete_task"
           | "add_project" | "delete_project",
      "data": {...}, "lamport": int, "origin": node_uuid, "ts": ms }

冲突策略:每实体记录最后写入 lamport,新事件 lamport 更大才覆盖。
"""

from __future__ import annotations

import json
import socket
import sys
import threading
import time
import urllib.request
import uuid
from dataclasses import asdict, dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Callable, Optional

from zeroconf import ServiceBrowser, ServiceInfo, ServiceListener, Zeroconf

from kanban_app.i18n import t
from kanban_app.models import Project, Store, Task

P2P_SERVICE_TYPE = "_kanban._tcp.local."
P2P_BOOTSTRAP_GRACE_MS = 1500   # 启动后等待对等点出现的 grace 期
P2P_ANTI_ENTROPY_SECS = 30      # 周期性反熵合并间隔 (错过的变更自愈)
P2P_MANUAL_PEERS_FILE = "manual_peers.json"

# ---- LocalSend 式发现: 固定端口 + UDP 广播自宣 ----
P2P_UDP_PORT = 57122            # 广播/单播宣包端口 (固定)
P2P_TCP_DEFAULT = 57123         # 默认同步端口 (固定,占用则回退随机)
P2P_ANNOUNCE_SECS = 5           # 广播周期
P2P_PEER_TTL_SECS = 16          # 超过未收到宣包即认为离线 (3 个周期 + 余量)


def _iter_lan_ips() -> list[str]:
    """枚举本机所有网卡 IPv4 (含回环),供广播/直连多地址尝试。"""
    ips: list[str] = []
    try:
        import socket as _s
        # getaddrinfo Trick: 解析本机 hostname 拿到全部 A 记录
        for info in _s.getaddrinfo(_s.gethostname(), None, _s.AF_INET):
            ip = info[4][0]
            if ip not in ips:
                ips.append(ip)
    except OSError:
        pass
    # UDP connect trick: 常见默认路由出口 (无外网时也常能给出正确 LAN 段)
    for target in ("8.8.8.8", "192.168.1.1", "10.0.0.1"):
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.connect((target, 80))
            ip = s.getsockname()[0]
            if ip not in ips:
                ips.append(ip)
        except OSError:
            pass
        finally:
            s.close()
    # 兜底
    if not ips:
        ips.append("127.0.0.1")
    return ips


def get_local_ip() -> str:
    """尽量拿一个真实 LAN IP;失败时回 127.0.0.1。"""
    return _iter_lan_ips()[0]


def get_local_ips() -> list[str]:
    """全部本机 IPv4 (去重、回环垫底)。"""
    ips = _iter_lan_ips()
    if "127.0.0.1" in ips:
        ips.remove("127.0.0.1")
        ips.append("127.0.0.1")
    return ips


@dataclass
class PeerInfo:
    """一个发现到的远端节点。"""
    name: str           # mDNS 服务名
    host: str           # 首选 IP (兼容旧字段)
    port: int           # 同步端口
    node_id: str        # 远端节点 UUID
    hosts: list = None  # 全部候选 IP,连接失败时逐个回退

    def all_hosts(self) -> list[str]:
        """去重后的候选地址列表。"""
        seen, out = set(), []
        for h in ([self.host] + (self.hosts or [])):
            if h and h not in seen:
                seen.add(h)
                out.append(h)
        return out


class PeerSyncListener(ServiceListener):
    """zeroconf 在 zc 浏览线程上回调发现/离开事件。"""

    def __init__(self, peer: "Peer"):
        self.peer = peer

    def update_service(self, zc, stype, name):
        info = zc.get_service_info(stype, name)
        if info is not None:
            self.peer._on_peer_discovered(name, info)

    def remove_service(self, zc, stype, name):
        self.peer._on_peer_removed(name)

    def add_service(self, *args, **kwargs):
        self.update_service(*args, **kwargs)


class SyncHTTPHandler(BaseHTTPRequestHandler):
    """处理 /state (GET) 与 /event (POST) 同步端点。"""

    def log_message(self, *_a, **_kw):  # 静默默认 stderr 日志
        pass

    def _send_json(self, status: int, payload: dict):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = _path_only(self.path)
        if path == "/state":
            self._send_json(200, self.server.peer.snapshot())  # type: ignore[attr-defined]
        elif path == "/ping":
            self._send_json(200, {"ok": True,
                                  "node": self.server.peer.node_id})  # type: ignore[attr-defined]
        else:
            self.send_error(404)

    def do_POST(self):
        if _path_only(self.path) != "/event":
            self.send_error(404)
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(length) if length else b""
            event = json.loads(raw.decode("utf-8"))
        except (ValueError, OSError):
            self.send_error(400)
            return
        ok = self.server.peer.apply_remote_event(event)  # type: ignore[attr-defined]
        self._send_json(200, {"ok": ok})


def _path_only(url: str) -> str:
    from urllib.parse import urlparse
    return urlparse(url).path


class SyncHTTPServer(ThreadingHTTPServer):
    """ThreadingHTTPServer,把 peer 挂到 server 上供 handler 反查。"""
    # Windows 的 SO_REUSEADDR 允许第二个实例绑上同一端口并互抢流量,
    # 广播会回到发送者自己被当回声丢弃 — 必须禁用,让二实例走随机端口回退
    allow_reuse_address = (sys.platform != "win32")

    def __init__(self, host: str, port: int, peer: "Peer"):
        super().__init__((host, port), SyncHTTPHandler)
        self.peer = peer


class Peer:
    """P2P 节点:本地状态 + zeroconf 注册/发现 + 同步 HTTP 服务器 + 广播器。"""

    def __init__(self, store: Store, on_change: Callable[[], None]):
        self.store = store
        self.on_change = on_change  # 由主线程调度 app.refresh
        self.node_id = store.node_id = str(uuid.uuid4())
        self.state_dir = store.path.parent   # manual_peers.json 与 store 同目录

        self._lock = threading.Lock()
        self.lamport = 0
        self._peers: dict[str, PeerInfo] = {}     # 按 node_id 索引
        self._peer_by_name: dict[str, str] = {}   # mDNS name -> node_id
        self._peer_last_seen: dict[str, float] = {}  # node_id -> UDP 最后宣包时刻
        self._manual_peers: list[str] = []        # "host:port" 列表 (持久化)
        self._http: Optional[SyncHTTPServer] = None
        self._http_thread: Optional[threading.Thread] = None
        self._zc: Optional[Zeroconf] = None
        self._browser: Optional[ServiceBrowser] = None
        self._started = False
        self._port = 0
        self._load_manual_peers()

    # ---------------- 启停 ----------------
    def start(self) -> None:
        if self._started:
            return
        self._started = True

        # 1. HTTP server — 优先固定端口 (LocalSend 式),占用则回退随机
        port = P2P_TCP_DEFAULT
        try:
            self._http = SyncHTTPServer("0.0.0.0", port, self)
        except OSError:
            port = 0
            self._http = SyncHTTPServer("0.0.0.0", 0, self)
        try:
            self._port = self._http.server_address[1]
            if self._port == P2P_TCP_DEFAULT:
                print(t("log.peer_fixed_port", port=self._port))
            else:
                print(t("log.peer_port_fallback", port=self._port))
            self._http_thread = threading.Thread(
                target=self._http.serve_forever,
                name="kanban-http", daemon=True,
            )
            self._http_thread.start()
        except OSError as e:
            print(t("log.peer_bind_failed", err=e))
            self._http = None

        # 2. zeroconf register + browse
        try:
            self._zc = Zeroconf()
            local_ip = get_local_ip()
            self._register_service(local_ip)
            self._browser = ServiceBrowser(
                self._zc, P2P_SERVICE_TYPE, PeerSyncListener(self),
            )
            print(t("log.peer_listening",
                    id=self.node_id[:8], ip=local_ip, port=self._port))
        except Exception as e:
            print(t("log.peer_zc_failed", err=e))

        # 3. UDP 广播自宣 (LocalSend 式, mDNS 之外的兜底发现通道)
        threading.Thread(target=self._udp_announce_loop, daemon=True).start()

        # 4. grace 后引导 + 周期性反熵合并 + 手动节点重连
        threading.Thread(target=self._bootstrap_grace, daemon=True).start()
        threading.Thread(target=self._anti_entropy_loop, daemon=True).start()
        threading.Thread(target=self._manual_reconnect_loop, daemon=True).start()

    def stop(self) -> None:
        if not self._started:
            return
        self._started = False
        try:
            if self._zc and getattr(self, "_svc_name", None):
                self._zc.unregister_service(self._svc_info)
        except Exception:
            pass
        try:
            if self._zc:
                self._zc.close()
        except Exception:
            pass
        try:
            if self._http:
                self._http.shutdown()
                self._http.server_close()
        except Exception:
            pass

    def _register_service(self, ip: str) -> None:
        suffix = self.node_id[:8]
        self._svc_name = f"kanban-{suffix}.{P2P_SERVICE_TYPE}"
        # 广播本机全部 IPv4,远端逐个尝试
        addrs = [socket.inet_aton(a) for a in get_local_ips()]
        self._svc_info = ServiceInfo(
            P2P_SERVICE_TYPE,
            self._svc_name,
            addresses=addrs,
            port=self._port,
            properties={"node_id": self.node_id, "ver": "2"},
            server=socket.gethostname(),
        )
        self._zc.register_service(self._svc_info)

    # ---------------- HTTP (多地址逐个尝试) ----------------
    @staticmethod
    def _http_request(peer: PeerInfo, path: str,
                      method: str = "GET", body: bytes = None,
                      timeout: float = 2.0) -> Optional[bytes]:
        """对 peer 的全部候选地址逐个尝试,返回首个成功的响应体。

        成功后把可用地址提到 PeerInfo.host,加速后续请求。
        """
        last_err: Optional[Exception] = None
        for host in peer.all_hosts():
            try:
                if method == "POST":
                    req = urllib.request.Request(
                        f"http://{host}:{peer.port}{path}",
                        data=body, method="POST",
                        headers={"Content-Type": "application/json"},
                    )
                else:
                    req = urllib.request.Request(f"http://{host}:{peer.port}{path}")
                resp = urllib.request.urlopen(req, timeout=timeout).read()
                peer.host = host  # 记住可用地址
                return resp
            except Exception as e:
                last_err = e
                continue
        raise last_err or OSError("no reachable host")

    # ---------------- 状态快照 / 引导 ----------------
    def snapshot(self) -> dict:
        """返回完整状态 (含墓碑),作为新节点的引导种子。"""
        with self._lock:
            return {
                "node_id": self.node_id,
                "lamport": self.lamport,
                "projects": [asdict(p) for p in self.store.projects],
                "tasks": [asdict(t_) for t_ in self.store.tasks],
                "deleted": dict(self.store.deleted),
            }

    def _bootstrap_grace(self) -> None:
        """启动等待若干秒,若发现 peer 则尝试 GET /state 引导。"""
        deadline = time.monotonic() + (P2P_BOOTSTRAP_GRACE_MS / 1000.0)
        bootstrapped = False
        while time.monotonic() < deadline and self._started:
            with self._lock:
                target = next(iter(self._peers.values()), None)
            if target and self._request_state(target):
                bootstrapped = True
                break
            time.sleep(0.2)
        if not bootstrapped:
            print(t("log.peer_bootstrap_miss"))
            self._notify_ui()

    def _request_state(self, target: PeerInfo) -> bool:
        try:
            raw = self._http_request(target, "/state", timeout=2)
            data = json.loads(raw.decode("utf-8"))
        except Exception as e:
            print(t("log.peer_bootstrap_fail", name=target.name, err=e))
            return False
        try:
            self._merge_remote_state(data)
        except Exception as e:
            print(t("log.peer_bootstrap_fail", name=target.name, err=e))
            return False
        print(t("log.peer_bootstrap_ok", name=target.name))
        self._notify_ui()
        return True

    # ---------------- 对等点变化 ----------------
    def _on_peer_discovered(self, name: str, info: ServiceInfo) -> None:
        try:
            node_id = info.properties.get(b"node_id", b"").decode("utf-8")
        except Exception:
            node_id = ""
        if not node_id or node_id == self.node_id:
            return
        hosts = [socket.inet_ntoa(a) for a in info.addresses]
        if not hosts:
            return
        port = info.port
        with self._lock:
            self._peer_by_name[name] = node_id
            self._peers[node_id] = PeerInfo(
                name=name, host=hosts[0], port=port,
                node_id=node_id, hosts=hosts,
            )
            self._peer_last_seen[node_id] = time.monotonic()
        print(t("log.peer_added", name=name, host=hosts[0], port=port))
        self._notify_ui()

    def _on_peer_removed(self, name: str) -> None:
        with self._lock:
            node_id = self._peer_by_name.pop(name, None)
            if node_id:
                self._peers.pop(node_id, None)
                self._peer_last_seen.pop(node_id, None)
        print(t("log.peer_removed", name=name))
        self._notify_ui()

    # ---------------- UDP 广播发现 (LocalSend 式) ----------------
    def _announce_payload(self) -> bytes:
        return json.dumps({
            "app": "scrumban",
            "ver": 2,
            "node": self.node_id,
            "port": self._port,
            "hosts": get_local_ips(),
            "alias": socket.gethostname(),
        }, ensure_ascii=False).encode("utf-8")

    def _udp_announce_loop(self) -> None:
        """每 P2P_ANNOUNCE_SECS 秒向 255.255.255.255:57122 与各网段定向广播自宣;
        同时监听该端口,收到宣包即登记 peer 并单播回宣。"""
        rx = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        rx.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            rx.bind(("", P2P_UDP_PORT))
        except OSError:
            print(t("log.peer_udp_bind_failed", port=P2P_UDP_PORT))
            return
        rx.settimeout(0.5)

        def send_to(addr: tuple) -> None:
            try:
                rx.sendto(self._announce_payload(), addr)
            except OSError:
                pass

        while self._started:
            # --- 发:全网广播 + 每个本机网段的定向广播 (部分路由器拦全网广播) ---
            send_to(("255.255.255.255", P2P_UDP_PORT))
            for ip in get_local_ips():
                if ip.endswith(".0") or ip == "127.0.0.1":
                    continue
                # 简化 /24 定向广播 (家庭/办公网绝大多数是 /24)
                try:
                    prefix = ip.rsplit(".", 1)[0]
                    send_to((f"{prefix}.255", P2P_UDP_PORT))
                except (ValueError, OSError):
                    pass
            # --- TTL 探活: 太久没宣的 peer 判离线 ---
            self._expire_stale_peers()
            # --- 收:非阻塞收包 ---
            deadline = time.monotonic() + P2P_ANNOUNCE_SECS
            while self._started and time.monotonic() < deadline:
                try:
                    data, (src_ip, _src_port) = rx.recvfrom(2048)
                except socket.timeout:
                    continue
                except OSError:
                    break
                self._handle_announce(data, src_ip, rx)

    def _handle_announce(self, data: bytes, src_ip: str,
                         rx_sock: socket.socket) -> None:
        try:
            msg = json.loads(data.decode("utf-8"))
            if msg.get("app") != "scrumban":
                return
            node = msg.get("node", "")
            port = int(msg.get("port", 0))
            hosts = [h for h in msg.get("hosts", []) if isinstance(h, str)]
            if not node or node == self.node_id or not (0 < port < 65536):
                return
        except (ValueError, UnicodeDecodeError):
            return
        # 源 IP 优先 — UDP 包能到说明该地址路由可达
        addr_list = [src_ip] + [h for h in hosts if h != src_ip]
        is_new = False
        with self._lock:
            existing = self._peers.get(node)
            if existing is None:
                is_new = True
                self._peers[node] = PeerInfo(
                    name=f"udp-{node[:8]}", host=addr_list[0], port=port,
                    node_id=node, hosts=addr_list,
                )
            else:
                existing.hosts = addr_list
                # 刷新可用地址序 (src_ip 提前)
                existing.host = addr_list[0]
            self._peer_last_seen[node] = time.monotonic()
        if is_new:
            print(t("log.peer_added", name=addr_list[0], host=addr_list[0],
                    port=port))
            # 单播回宣 — 让对方立刻知道我 (不用等它下一个广播周期)
            try:
                rx_sock.sendto(self._announce_payload(),
                               (src_ip, P2P_UDP_PORT))
            except OSError:
                pass
            # 新 peer 出现,立刻拉一次全量对账
            with self._lock:
                target = self._peers.get(node)
            if target:
                threading.Thread(target=self._request_state_quiet,
                                 args=(target,), daemon=True).start()
            self._notify_ui()

    def _expire_stale_peers(self) -> None:
        """TTL 探活: 超时未宣的 UDP 发现节点移除 (mDNS 管理的除外)。"""
        now = time.monotonic()
        with self._lock:
            stale = [n for n, seen in self._peer_last_seen.items()
                     if now - seen > P2P_PEER_TTL_SECS]
            for n in stale:
                self._peer_last_seen.pop(n, None)
                p = self._peers.pop(n, None)
                if p:
                    print(t("log.peer_removed", name=p.name))
        if stale:
            self._notify_ui()

    def peer_count(self) -> int:
        with self._lock:
            return len(self._peers)

    # ---------------- 手动直连节点 (绕过 mDNS) ----------------
    def _manual_peers_path(self):
        return self.state_dir / P2P_MANUAL_PEERS_FILE

    def _load_manual_peers(self) -> None:
        try:
            path = self._manual_peers_path()
            if path.exists():
                with path.open("r", encoding="utf-8") as f:
                    self._manual_peers = json.load(f)
        except (json.JSONDecodeError, OSError):
            self._manual_peers = []

    def _save_manual_peers(self) -> None:
        try:
            self.state_dir.mkdir(parents=True, exist_ok=True)
            with self._manual_peers_path().open("w", encoding="utf-8") as f:
                json.dump(self._manual_peers, f, ensure_ascii=False, indent=2)
        except OSError:
            pass

    def manual_peers(self) -> list[str]:
        with self._lock:
            return list(self._manual_peers)

    def add_manual_peer(self, host: str, port: int) -> bool:
        """用户手动添加 host:port。立即尝试连接 /ping 并拉状态。"""
        entry = f"{host}:{port}"
        probe = PeerInfo(name=f"manual-{entry}", host=host, port=port,
                         node_id=f"manual-{entry}", hosts=[host])
        try:
            raw = self._http_request(probe, "/ping", timeout=2)
            info = json.loads(raw.decode("utf-8"))
            remote_node = info.get("node", "")
        except Exception as e:
            print(t("log.peer_bootstrap_fail", name=entry, err=e))
            return False
        # 记录为正式对等点 (node_id 来自远端)
        with self._lock:
            if entry not in self._manual_peers:
                self._manual_peers.append(entry)
            self._peers[remote_node] = PeerInfo(
                name=probe.name, host=host, port=port,
                node_id=remote_node, hosts=[host],
            )
        self._save_manual_peers()
        # 立刻拉一次全量状态
        threading.Thread(
            target=self._request_state,
            args=(self._peers[remote_node],), daemon=True,
        ).start()
        return True

    def remove_manual_peer(self, host: str, port: int) -> None:
        entry = f"{host}:{port}"
        with self._lock:
            if entry in self._manual_peers:
                self._manual_peers.remove(entry)
            stale = [nid for nid, p in self._peers.items()
                     if p.name == f"manual-{entry}"]
            for nid in stale:
                self._peers.pop(nid, None)
        self._save_manual_peers()

    def _manual_reconnect_loop(self) -> None:
        """每 5s 重试手动节点,断线自动恢复。"""
        import time as _t
        while self._started:
            for entry in self.manual_peers():
                try:
                    host, port_s = entry.rsplit(":", 1)
                    port = int(port_s)
                except ValueError:
                    continue
                probe = PeerInfo(name=f"manual-{entry}", host=host,
                                 port=port, node_id=f"manual-{entry}",
                                 hosts=[host])
                try:
                    raw = self._http_request(probe, "/ping", timeout=1.5)
                    info = json.loads(raw.decode("utf-8"))
                    remote_node = info.get("node", "")
                    if not remote_node:
                        continue
                    with self._lock:
                        existing = self._peers.get(remote_node)
                        if existing is None:
                            self._peers[remote_node] = PeerInfo(
                                name=probe.name, host=host, port=port,
                                node_id=remote_node, hosts=[host],
                            )
                            print(t("log.peer_added", name=probe.name,
                                    host=host, port=port))
                            self._notify_ui()
                        # 已在册 → 什么都不做 (避免重复拉状态)
                except Exception:
                    pass  # 离线,下轮再试
            _t.sleep(5)

    # ---------------- 反熵自愈 ----------------
    def _anti_entropy_loop(self) -> None:
        """周期性从每个 peer 拉 /state 双向合并,补齐错过的事件。"""
        import time as _t
        # 先等 bootstrap 结束再开始循环
        _t.sleep(P2P_BOOTSTRAP_GRACE_MS / 1000.0 + 1)
        while self._started:
            with self._lock:
                targets = list(self._peers.values())
            for target in targets:
                if not self._started:
                    return
                self._request_state_quiet(target)
            _t.sleep(P2P_ANTI_ENTROPY_SECS)

    def _request_state_quiet(self, target: PeerInfo) -> None:
        """静默版 _request_state:失败不打日志 (周期任务正常会失败)。"""
        try:
            raw = self._http_request(target, "/state", timeout=2)
            data = json.loads(raw.decode("utf-8"))
            self._merge_remote_state(data)
        except Exception:
            return
        self._notify_ui()

    # ---------------- 本地动作入口 (UI 调用) ----------------
    def local_add_project(self, name: str) -> Project:
        proj = Project(
            id=self._gen_id("proj"),
            name=name, is_default=False,
        )
        ev = self._make_event("add_project", proj)
        self.apply_local_event(ev)
        return proj

    def local_delete_project(self, proj_id: str) -> None:
        ev = self._make_event("delete_project", {"id": proj_id})
        self.apply_local_event(ev)

    def local_activate_project(self, proj_id: str) -> None:
        # 本地视图状态,不广播
        self.store.active_project_id = proj_id
        self.store.save()
        self._notify_ui()

    def local_add_task(self, project_id: str, title: str,
                       priority: str, due_date: str) -> Task:
        task = Task(
            id=self._gen_id("task"),
            project_id=project_id, title=title,
            priority=priority, due_date=due_date, status="todo",
        )
        ev = self._make_event("add_task", task)
        self.apply_local_event(ev)
        return task

    def local_delete_task(self, task_id: str) -> None:
        ev = self._make_event("delete_task", {"id": task_id})
        self.apply_local_event(ev)

    def local_update_task_field(self, task_id: str, **fields) -> None:
        ev = self._make_event("update_task", {"id": task_id, **fields})
        self.apply_local_event(ev)

    # ---------------- 事件构造 / 应用 ----------------
    def _make_event(self, etype: str, payload) -> dict:
        with self._lock:
            self.lamport += 1
            lamport = self.lamport
        return {
            "type": etype,
            "data": asdict(payload) if hasattr(payload, "__dataclass_fields__")
                    else payload,
            "lamport": lamport,
            "origin": self.node_id,
            "ts": int(time.time() * 1000),
        }

    @staticmethod
    def _gen_id(prefix: str) -> str:
        """毫秒时间戳 + 随机后缀,避免同毫秒/多机时钟一致时 id 碰撞。"""
        return f"{prefix}-{int(time.time() * 1000)}-{uuid.uuid4().hex[:6]}"

    @staticmethod
    def _sanitize_task_fields(data: dict) -> Optional[dict]:
        """校验远端 update_task 字段值,剔除会让渲染崩溃的畸形值。"""
        out = {}
        for fld in ("title", "priority", "due_date", "status", "project_id"):
            if fld in data:
                val = data[fld]
                if not isinstance(val, str):
                    return None
                if fld == "priority" and val not in ("high", "medium", "low"):
                    return None
                if fld == "status" and val not in ("todo", "doing", "done"):
                    return None
                out[fld] = val
        return out

    def apply_local_event(self, event: dict) -> None:
        """本地动作:写入存储 + 广播给所有对等。"""
        self.apply_event_to_store(event)
        self.store.save()
        self.broadcast(event)
        self._notify_ui()

    def apply_remote_event(self, event: dict) -> bool:
        """处理来自 peer 的事件。返回 ok。"""
        if not isinstance(event, dict):
            return False
        for k in ("type", "data", "lamport", "origin"):
            if k not in event:
                return False
        try:
            lamport_val = int(event["lamport"])
        except (TypeError, ValueError):
            return False
        # 自己刚广播的回声,直接丢弃
        if event.get("origin") == self.node_id:
            return True
        with self._lock:
            self.lamport = max(self.lamport, lamport_val) + 1
        applied = self.apply_event_to_store(event, fallback_lamport=lamport_val)
        if applied:
            self.store.normalize_active_project()
            self.store.save()
            self._notify_ui()
        return True

    def apply_event_to_store(self, event: dict,
                             fallback_lamport: Optional[int] = None) -> bool:
        etype = event["type"]
        data = event["data"]
        if not isinstance(data, dict):
            return False
        lam = event.get("lamport") if event.get("lamport") is not None \
              else (fallback_lamport or 0)
        origin = event.get("origin", "")
        with self._lock:
            try:
                if etype == "add_project":
                    if not isinstance(data.get("id"), str):
                        return False
                    if any(p.id == data["id"] for p in self.store.projects):
                        return False
                    # 对端把已删除实体的 add 补发过来 → 按墓碑丢弃
                    tomb = self.store.deleted.get(data["id"])
                    if tomb is not None and tomb >= lam:
                        return False
                    self.store.projects.append(Project(
                        id=data["id"], name=str(data.get("name", "")),
                        is_default=bool(data.get("is_default", False)),
                        lamport=lam, origin=origin,
                    ))
                    return True
                if etype == "delete_project":
                    proj = next((p for p in self.store.projects
                                 if p.id == data["id"]), None)
                    if proj is not None and proj.lamport > lam:
                        return False
                    # 先记下项目下任务的 id,连同项目一起立墓碑
                    doomed_task_ids = [x.id for x in self.store.tasks
                                       if x.project_id == data["id"]]
                    self.store.projects = [p for p in self.store.projects
                                           if p.id != data["id"]]
                    self.store.tasks = [x for x in self.store.tasks
                                        if x.project_id != data["id"]]
                    self._record_tombstone(data["id"], lam)
                    for tid in doomed_task_ids:
                        self._record_tombstone(tid, lam)
                    return True
                if etype == "add_task":
                    if not isinstance(data.get("id"), str):
                        return False
                    if any(x.id == data["id"] for x in self.store.tasks):
                        return False
                    tomb = self.store.deleted.get(data["id"])
                    if tomb is not None and tomb >= lam:
                        return False
                    self.store.tasks.append(Task(
                        id=data["id"],
                        project_id=str(data.get("project_id", "")),
                        title=str(data.get("title", "")),
                        priority=self._safe_priority(data.get("priority")),
                        due_date=self._safe_due(data.get("due_date")),
                        status=self._safe_status(data.get("status")),
                        lamport=lam, origin=origin,
                    ))
                    return True
                if etype == "update_task":
                    fields = self._sanitize_task_fields(data)
                    if fields is None:
                        return False
                    for x in self.store.tasks:
                        if x.id == data["id"]:
                            if x.lamport > lam:
                                return False
                            for fld, value in fields.items():
                                setattr(x, fld, value)
                            x.lamport = lam
                            x.origin = origin
                            return True
                    return False
                if etype == "delete_task":
                    for x in self.store.tasks:
                        if x.id == data["id"]:
                            if x.lamport > lam:
                                return False
                            self.store.tasks = [y for y in self.store.tasks
                                                if y.id != data["id"]]
                            self._record_tombstone(data["id"], lam)
                            return True
                    # 幂等删除:没见过也记墓碑,防对端 merge 拉回
                    self._record_tombstone(data["id"], lam)
                    return True
            except (KeyError, TypeError):
                return False
        return False

    def _record_tombstone(self, entity_id: str, lam: int) -> None:
        """记录/合并墓碑 (取较大 lamport),供反熵合并防复活。"""
        old = self.store.deleted.get(entity_id)
        if old is None or lam > old:
            self.store.deleted[entity_id] = lam
        # 墓碑无限增长防御:粗略上限,超过即整体丢弃最旧的一半
        if len(self.store.deleted) > 5000:
            keep = sorted(self.store.deleted.items(),
                          key=lambda kv: kv[1], reverse=True)[:2500]
            self.store.deleted = dict(keep)

    # 静态白名单兜底: add_task 用 (值不合法时给安全默认而非拒收)
    @staticmethod
    def _safe_priority(v) -> str:
        return v if v in ("high", "medium", "low") else "medium"

    @staticmethod
    def _safe_status(v) -> str:
        return v if v in ("todo", "doing", "done") else "todo"

    @staticmethod
    def _safe_due(v) -> str:
        if isinstance(v, str) and v:
            return v
        return "1970-01-01"

    def _merge_remote_state(self, data: dict) -> None:
        """从对等节点引导时调用:按 Lamport 合并两边全部实体。

        对端 snapshot 携带其墓碑;本地墓碑较新的实体一律拒收,
        防止错过 delete 事件的节点把已删数据拉回来"复活"。
        """
        with self._lock:
            try:
                remote_lamport = int(data.get("lamport", 0) or 0)
            except (TypeError, ValueError):
                remote_lamport = 0
            self.lamport = max(self.lamport, remote_lamport)

            # 1. 合并远端墓碑 (取较大 lamport)
            remote_deleted = data.get("deleted", {})
            if isinstance(remote_deleted, dict):
                for rid, rlam in remote_deleted.items():
                    try:
                        rlam = int(rlam)
                    except (TypeError, ValueError):
                        continue
                    old = self.store.deleted.get(rid)
                    if old is None or rlam > old:
                        self.store.deleted[rid] = rlam

            # 2. 本地墓碑较新的实体,直接从本地剔除 (远端尚未收到删除)
            for rid, rlam in list(self.store.deleted.items()):
                for p in self.store.projects:
                    if p.id == rid and p.lamport <= rlam:
                        self.store.projects.remove(p)
                        break
                for x in self.store.tasks:
                    if x.id == rid and x.lamport <= rlam:
                        self.store.tasks.remove(x)
                        break

            local_projs = {p.id: p for p in self.store.projects}
            for raw in (data.get("projects") or []):
                if not isinstance(raw, dict):
                    continue
                try:
                    incoming = Project(
                        id=raw["id"], name=str(raw.get("name", "")),
                        is_default=bool(raw.get("is_default", False)),
                        lamport=int(raw.get("lamport", 0) or 0),
                        origin=str(raw.get("origin", "") or ""),
                    )
                except (KeyError, TypeError, ValueError):
                    continue
                # 墓碑拦截: 本地(或刚合并的)墓碑不早于该实体版本 → 丢弃
                tomb = self.store.deleted.get(incoming.id)
                if tomb is not None and tomb >= incoming.lamport:
                    continue
                existing = local_projs.get(incoming.id)
                if not existing:
                    self.store.projects.append(incoming)
                    local_projs[incoming.id] = incoming
                elif incoming.lamport > existing.lamport:
                    existing.name = incoming.name
                    existing.is_default = incoming.is_default
                    existing.lamport = incoming.lamport
                    existing.origin = incoming.origin

            local_tasks = {x.id: x for x in self.store.tasks}
            for raw in (data.get("tasks") or []):
                if not isinstance(raw, dict):
                    continue
                try:
                    incoming = Task(
                        id=raw["id"],
                        project_id=str(raw.get("project_id", "") or ""),
                        title=str(raw.get("title", "") or ""),
                        priority=self._safe_priority(raw.get("priority")),
                        due_date=self._safe_due(raw.get("due_date")),
                        status=self._safe_status(raw.get("status")),
                        lamport=int(raw.get("lamport", 0) or 0),
                        origin=str(raw.get("origin", "") or ""),
                    )
                except (KeyError, TypeError, ValueError):
                    continue
                tomb = self.store.deleted.get(incoming.id)
                if tomb is not None and tomb >= incoming.lamport:
                    continue
                # 项目已删 (按墓碑) 的任务一并丢弃
                proj_tomb = self.store.deleted.get(incoming.project_id)
                if proj_tomb is not None:
                    continue
                existing = local_tasks.get(incoming.id)
                if not existing:
                    self.store.tasks.append(incoming)
                    local_tasks[incoming.id] = incoming
                elif incoming.lamport > existing.lamport:
                    for fld in ("project_id", "title", "priority",
                                "due_date", "status"):
                        setattr(existing, fld, getattr(incoming, fld))
                    existing.lamport = incoming.lamport
                    existing.origin = incoming.origin
            self.store.normalize_active_project()
            self.store.save()

    # ---------------- 广播 ----------------
    def broadcast(self, event: dict) -> None:
        with self._lock:
            snapshot = list(self._peers.values())
        if not snapshot:
            return
        threading.Thread(
            target=self._broadcast_async, args=(event, snapshot),
            daemon=True,
        ).start()

    def _broadcast_async(self, event: dict, peers: list[PeerInfo]) -> None:
        body = json.dumps(event, ensure_ascii=False).encode("utf-8")
        for p in peers:
            try:
                self._http_request(p, "/event", method="POST",
                                   body=body, timeout=2)
            except Exception as e:
                print(t("log.peer_broadcast_fail", name=p.name, err=e))

    # ---------------- UI 通知 ----------------
    def _notify_ui(self) -> None:
        try:
            self.on_change()
        except Exception:
            pass
