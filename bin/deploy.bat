@echo off
REM Deploys the addon for Hexchat.
REM Specify argument if config path differs from default: %APPDATA%\HexChat

SET hexchat_path=%1
IF "%hexchat_path%" == "" SET hexchat_path=%APPDATA%\HexChat


IF NOT EXIST %hexchat_path%\* (
    echo Is Hexchat installed? Is Hexchat config located at %hexchat_path% ?
    echo If config is elsewhere, specify the directory to change the location
    exit /B 1
)

SET addons_path="%hexchat_path%\addons"

mkdir "%addons_path%"

IF EXIST "%hexchat_path%\addons\xdcc_store.json" (
    echo %addons_path%
    python tools\store_convert.py "%addons_path%\xdcc_store.json" -o "%addons_path%\xdcc_store.json"
    IF %ERRORLEVEL% EQU 1 (
        echo Config file updated.
    ) ELSE (
        echo Config update failed.
        exit /B 2
    )
) ELSE (
    xcopy /V ".\config\xdcc_store.json" "%addons_path%"
    echo New config file created.
)


xcopy /V /E /Y ".\src\." "%addons_path%"

echo Auto-XDCC installed.
echo Restart Hexchat or type /py load auto_xdcc.py or /py reload auto_xdcc.py to get it working.
pause