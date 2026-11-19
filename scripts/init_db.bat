@echo off
rem DB 초기화 (Windows) : 스키마 -> 함수·뷰·트리거·프로시저 -> 기초 데이터 -> 도서 -> 대출 이력
rem 사용법 : scripts\init_db.bat            (프로젝트 폴더에서 실행, root 비밀번호를 한 번 입력)
rem 다른 PC 의 DB 서버 : set MYSQL_HOST=100.77.2.39  후 실행 (mysql.exe 가 MYSQL_HOST 를 직접 읽는다)
rem mysql.exe 를 찾지 못하면 아래 MYSQL 경로를 설치 위치에 맞게 고친다.
chcp 65001 > nul
setlocal
cd /d "%~dp0.."

set "MYSQL=mysql"
where mysql > nul 2> nul
if errorlevel 1 (
  for /d %%d in ("C:\Program Files\MySQL\MySQL Server *") do set "MYSQL=%%d\bin\mysql.exe"
)

if not defined MYSQL_HOST set "MYSQL_HOST=localhost"
echo 대상 DB 서버: %MYSQL_HOST% (library_db 를 지우고 다시 만든다)
if not defined MYSQL_PWD set /p "MYSQL_PWD=MySQL root 비밀번호: "

for %%f in (01_schema 02_programs 03_base_data 04_books 05_sample_loans) do (
  echo ^>^> sql\%%f.sql
  "%MYSQL%" -u root --default-character-set=utf8mb4 < "sql\%%f.sql"
  if errorlevel 1 (
    echo 실패: sql\%%f.sql
    exit /b 1
  )
)
echo 완료: library_db 초기화
endlocal
