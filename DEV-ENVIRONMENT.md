# DEV-ENVIRONMENT

확인 날짜: 2026-10-19
근거: 명령을 실제로 실행한 결과. 출력은 그대로 옮겼다.

## 운영체제 · 셸
| 항목 | 값 |
|---|---|
| 운영체제 | Microsoft Windows 11 Pro 10.0.22631 |
| 셸 | PowerShell 7.6.7 (Git Bash도 사용 가능) |

## 도구별 버전
| 도구 | 명령 | 결과 |
|---|---|---|
| git | `git --version` | `git version 2.56.0.windows.2` |
| node | `node --version` | 실행 안 됨: `'node' 용어는 cmdlet, 함수, 스크립트 파일 또는 실행 프로그램의 이름으로 인식되지 않습니다.` |
| npm | `npm --version` | 실행 안 됨: `'npm' 용어는 cmdlet, 함수, 스크립트 파일 또는 실행 프로그램의 이름으로 인식되지 않습니다.` |
| uv | `uv --version` | `uv 0.13.1 (62faed335 2026-10-13 x86_64-pc-windows-msvc)` |
| python | `python --version` | `Python` (실제 Python이 아니라 Microsoft Store 바로가기라서 버전이 나오지 않음) |
| python (uv 설치본) | `C:\Users\EZ\.local\bin\python3.12.exe --version` | `Python 3.12.15` |

## 새로 설치한 것
없음. 지금까지는 확인만 했고 아무것도 설치하지 않았다.

## 아직 없는 것 (설치 전)
- node, npm: 설치하지 않았다. React · Vite 화면에 필요하다.
- FastAPI: 프로젝트 가상환경이 아직 없다.
- 명령 줄의 `python`은 실제 Python이 아니다. uv의 Python 3.12.15를 쓴다.
