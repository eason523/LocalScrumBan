@echo off
REM ScrumBan 网络放行脚本 — 右键"以管理员身份运行"
REM 放行 mDNS (5353) / UDP 自宣 (57122) / 同步端口 (57123) / 程序本身

echo === ScrumBan 防火墙放行 ===
echo.

REM 1. mDNS (UDP 5353) — mDNS 自动发现
netsh advfirewall firewall delete rule name="ScrumBan mDNS" >nul 2>&1
netsh advfirewall firewall add rule name="ScrumBan mDNS" dir=in action=allow protocol=udp localport=5353
if %errorlevel% neq 0 goto needadmin

REM 2. UDP 57122 — LocalSend 式广播自宣发现
netsh advfirewall firewall delete rule name="ScrumBan UDP announce" >nul 2>&1
netsh advfirewall firewall add rule name="ScrumBan UDP announce" dir=in action=allow protocol=udp localport=57122

REM 3. TCP 57123 — 默认同步端口
netsh advfirewall firewall delete rule name="ScrumBan sync" >nul 2>&1
netsh advfirewall firewall add rule name="ScrumBan sync" dir=in action=allow protocol=tcp localport=57123

REM 4. ScrumBan.exe 本体 — 同步端口可能回退随机,放行程序兜底
netsh advfirewall firewall delete rule name="ScrumBan app" >nul 2>&1
netsh advfirewall firewall add rule name="ScrumBan app" dir=in action=allow program="%ProgramFiles%\ScrumBan\ScrumBan.exe"
netsh advfirewall firewall add rule name="ScrumBan app (user)" dir=in action=allow program="%LocalAppData%\Programs\ScrumBan\ScrumBan.exe" >nul 2>&1

echo.
echo 完成! 请在对方机器上也运行一次此脚本。
echo.
pause
exit /b 0

:needadmin
echo.
echo [错误] 请右键此文件, 选择"以管理员身份运行"。
echo.
pause
exit /b 1
