@echo off
setlocal EnableExtensions

set "DEFAULT_HEROKU_APP=ban-bot-huydc"
set "PROCESS_TYPE=worker"
set "HEROKU_APP=%DEFAULT_HEROKU_APP%"

if /I "%~1"=="--help" goto usage
if /I "%~1"=="-h" goto usage
if /I "%~1"=="/?" goto usage
if not "%~1"=="" set "HEROKU_APP=%~1"

set "SCRIPT_DIR=%~dp0"
for %%I in ("%SCRIPT_DIR%..") do set "REPO_ROOT=%%~fI"

echo Heroku app: %HEROKU_APP%
echo Process type: %PROCESS_TYPE%
echo Repo root: %REPO_ROOT%
echo.

where heroku >nul 2>nul
if errorlevel 1 (
    echo ERROR: Heroku CLI is not installed or not in PATH.
    exit /b 1
)

where docker >nul 2>nul
if errorlevel 1 (
    echo ERROR: Docker is not installed or not in PATH.
    exit /b 1
)

pushd "%REPO_ROOT%"
if errorlevel 1 exit /b 1

if not exist "dockerfile" (
    echo ERROR: dockerfile not found at "%REPO_ROOT%\dockerfile".
    popd
    exit /b 1
)

echo Logging in to Heroku Container Registry...
heroku container:login
if errorlevel 1 goto fail

echo.
echo Building and pushing linux/amd64 image to Heroku...
docker buildx build --platform linux/amd64 --provenance=false --sbom=false --output "type=image,name=registry.heroku.com/%HEROKU_APP%/%PROCESS_TYPE%,push=true,oci-mediatypes=false" .
if errorlevel 1 goto fail

echo.
echo Releasing %PROCESS_TYPE% image...
heroku container:release %PROCESS_TYPE% --app %HEROKU_APP%
if errorlevel 1 goto fail

echo.
echo Scaling %PROCESS_TYPE% dyno to 1...
heroku ps:scale %PROCESS_TYPE%=1 --app %HEROKU_APP%
if errorlevel 1 goto fail

echo.
echo Recent releases:
heroku releases -n 3 --app %HEROKU_APP%
if errorlevel 1 goto fail

echo.
echo Dyno status:
heroku ps --app %HEROKU_APP%
if errorlevel 1 goto fail

echo.
echo Recent %PROCESS_TYPE% logs:
heroku logs --num 80 --ps %PROCESS_TYPE% --app %HEROKU_APP%
if errorlevel 1 goto fail

popd
echo.
echo Deploy completed.
exit /b 0

:fail
set "EXIT_CODE=%ERRORLEVEL%"
popd
echo.
echo Deploy failed with exit code %EXIT_CODE%.
exit /b %EXIT_CODE%

:usage
echo Usage:
echo   build\deploy-heroku.bat [heroku-app-name]
echo.
echo Defaults:
echo   heroku-app-name = %DEFAULT_HEROKU_APP%
echo   process type    = %PROCESS_TYPE%
echo.
echo This script builds and releases the Docker image only.
echo It does not read .env or set Heroku config vars, so keep TOKEN in Heroku Config Vars.
exit /b 0
