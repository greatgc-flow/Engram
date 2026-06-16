@echo off
setlocal
chcp 65001 >nul 2>&1
cd /d P:\

echo =========================================
echo  Engram _sys Swap Finalizer
echo  Run this AFTER closing Claude Code
echo =========================================
echo.

:: 전제조건 확인
if not exist "_sys_new" (
    echo [ERROR] _sys_new not found. Already swapped?
    pause & exit /b 1
)
if not exist "_sys" (
    echo [ERROR] _sys not found. Check environment.
    pause & exit /b 1
)

:: 타임스탬프 생성
for /F "delims=" %%I in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMddHHmmss"') do set "STAMP=%%I"
set "ROLLBACK=_sys_old_rollback_%STAMP%"

echo [1/5] _sys 백업: _sys → %ROLLBACK%
ren _sys %ROLLBACK%
if %errorlevel% neq 0 (
    echo [ERROR] _sys rename 실패 - 프로세스가 파일을 잠금 중일 수 있습니다.
    echo         Claude Code, VS Code, Python 프로세스를 모두 닫고 다시 시도하세요.
    pause & exit /b 1
)

echo [2/5] _sys_new → _sys 승격
ren _sys_new _sys
if %errorlevel% neq 0 (
    echo [ERROR] _sys_new rename 실패. 롤백 중...
    ren %ROLLBACK% _sys
    pause & exit /b 1
)

echo [3/5] Junction 재설정 (virtualizer.py)
_sys\env\venv\Scripts\python.exe _sys\core\virtualizer.py apply --force
if %errorlevel% neq 0 (
    echo [WARN] virtualizer.py 실패 - Junction은 수동 확인 필요
)

echo [4/5] 임시 폴더 정리
if exist "Garbage" rmdir /s /q "Garbage" && echo   Garbage 삭제 완료
if exist "tmp" rmdir /s /q "tmp" && echo   tmp 삭제 완료

echo [5/5] 기본 테스트 실행
_sys\env\venv\Scripts\python.exe -m pytest _sys\tests\unit -q --tb=short -x 2>nul
if %errorlevel% neq 0 (
    echo [WARN] 일부 테스트 실패 - 로그 확인 필요
    echo        롤백하려면: ren _sys _sys_new ^& ren %ROLLBACK% _sys
) else (
    echo [OK] 테스트 통과
    echo.
    echo 롤백 폴더(%ROLLBACK%)가 안정 확인 후 삭제 가능합니다.
)

echo.
echo =========================================
echo  Swap 완료! Claude Code를 다시 시작하세요.
echo =========================================
pause
