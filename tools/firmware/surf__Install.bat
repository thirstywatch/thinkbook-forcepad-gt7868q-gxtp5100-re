pushd %~dp0
@ECHO OFF
SET  APP_NAME= Intel ForcePan Driver
SET  SILENT_CMD= pnputil /add-driver "%~dp0*.inf" /install
SET  RETURN_CODE=
SET  APP_LOG=C:\Windows\logs\forcepad.log
IF NOT EXIST C:\Windows\logs\ MD C:\Windows\logs\
REM ===================================
ECHO [%TIME%] == The Installation of %APP_NAME%== >> %APP_LOG%

REM Run Silent Install Command:
CALL %SILENT_CMD%
ECHO Errorlevel=%Errorlevel% >> %APP_LOG%

REM Filter Acceptable Return Codes:
FOR %%i in (0,3010) DO (
	IF %Errorlevel% == %%~i set RETURN_CODE=0
)
SET RETURN_CODE=%errorlevel%
:END
SET errorlevel=%RETURN_CODE%
@ECHO ON