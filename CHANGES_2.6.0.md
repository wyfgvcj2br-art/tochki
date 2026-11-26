# Изменения 2.6.0

Ветка: `feature/windows-installer`. База: `f021bc1e9abd05ba6d2b2772ac47b0f96f31227b`.
История сохранена без force-push. Main и финальный релиз не изменяются автоматически.

## Коммиты реализации и исправления Windows-проверок

| SHA | Назначение |
| --- | --- |
| [e2a8d9e2](https://github.com/wyfgvcj2br-art/tochki/commit/e2a8d9e269ccdf628af787ad63fce6e4883c97fa) | Refactor application paths and user data storage |
| [884947cb](https://github.com/wyfgvcj2br-art/tochki/commit/884947cbfb09769e7feb3b616f716bbfd768adac) | Implement portable data migration |
| [65e88a19](https://github.com/wyfgvcj2br-art/tochki/commit/65e88a19a7db8fb77449461c24815fc4641ff08c) | Add Windows installer and application metadata |
| [0b6bbf04](https://github.com/wyfgvcj2br-art/tochki/commit/0b6bbf0439c636925de23f145d97360bc8e0f4f6) | Update Windows build pipeline |
| [bea41a6c](https://github.com/wyfgvcj2br-art/tochki/commit/bea41a6c7c070df49f11001906e0c39567156679) | Add installation and migration tests |
| [b58470aa](https://github.com/wyfgvcj2br-art/tochki/commit/b58470aadbdf1f5628642d04d19f8cf4d9de04d5) | Update documentation and release notes |
| [683ce491](https://github.com/wyfgvcj2br-art/tochki/commit/683ce491d353c9bce85169d4288c59c55644442c) | Fix Windows toolchain pin and harden reviewed JSON import |
| [e73035e0](https://github.com/wyfgvcj2br-art/tochki/commit/e73035e0eeab79077129e9ec09fb45b68248d923) | Normalize Windows test paths and retain installation evidence |
| [5641e018](https://github.com/wyfgvcj2br-art/tochki/commit/5641e018c26a6e4ba578e31752cd844df8c26e9e) | Resolve native shortcut paths and capture standard-user diagnostics |
| [8ad8f6ab](https://github.com/wyfgvcj2br-art/tochki/commit/8ad8f6ab32a4d62f360ce6c55135f8e210673500) | Disable local WebView reputation traffic and verify native privacy settings |
| [fc3b6865](https://github.com/wyfgvcj2br-art/tochki/commit/fc3b6865149a7737e41d7f1b054e9e2aa3581ac1) | Verify real shell launch and protect unattended installation paths |
| [4a752f5a](https://github.com/wyfgvcj2br-art/tochki/commit/4a752f5a0ee144e58a6348ea17c8b978b67ce9ad) | Initialize the standard-user test environment from its Windows token |
| [d7ff26fa](https://github.com/wyfgvcj2br-art/tochki/commit/d7ff26fa1527dde1848028bd37031434d87e5a39) | Preserve Cyrillic test scripts in Windows PowerShell 5.1 |
| [ae6debe3](https://github.com/wyfgvcj2br-art/tochki/commit/ae6debe3cf9f0828ed61b5f9d4703a67c8667ef1) | Preflight alternate user profiles using the native Python Windows API |
| [a07cfd0f](https://github.com/wyfgvcj2br-art/tochki/commit/a07cfd0fc6f1ecd055a2ffc9fbfe9b55bcbfebec) | Read Cyrillic smoke-test JSON explicitly as UTF-8 |
| [cf6d45c1](https://github.com/wyfgvcj2br-art/tochki/commit/cf6d45c16676d62795cad222ea91af887e04c22e) | Cache immutable installer inputs while rerunning all Windows validation |
| [7a7e2882](https://github.com/wyfgvcj2br-art/tochki/commit/7a7e28823176d6c5ea09c8cf9162f19d0c64f701) | Verify nonempty directory retention and normal packaged process exit |
| [0b0c9efc](https://github.com/wyfgvcj2br-art/tochki/commit/0b0c9efcd9869c33e62961e5feb65ed75db6e9e4) | Validate the exact final installer on an empty Windows destination |

## Файлы

- `.github/workflows/portable.yml` — removed
- `.github/workflows/windows.yml` — added
- `INSTALLATION.md` — added
- `PORTABLE.txt` — modified
- `README.md` — modified
- `RELEASE_NOTES.md` — modified
- `VALIDATION_REPORT.md` — added
- `VERSION` — modified
- `app/app_paths.py` — added
- `app/desktop.py` — modified
- `app/engine.py` — modified
- `app/portable_migration.py` — added
- `app/server.py` — modified
- `app/settings_store.py` — added
- `app/ui/desktop.js` — modified
- `app/ui/index.html` — modified
- `app/ui/style.css` — modified
- `installer/Tochki.iss` — added
- `installer/app.manifest` — added
- `requirements-build.txt` — modified
- `requirements.txt` — modified
- `scripts/build_installer.py` — added
- `scripts/build_portable.py` — modified
- `scripts/check_user_environment.py` — added
- `scripts/run_installer_user.ps1` — added
- `scripts/smoke_installer.ps1` — added
- `scripts/smoke_portable.py` — modified
- `scripts/verify_user_data.py` — added
- `scripts/windows_metadata.py` — added
- `scripts/windows_test_environment.py` — added
- `tests/test_installation.py` — added
- `CHANGES_2.6.0.md` — список файлов и коммитов.

Актуальная полная история, включая коммит фиксации результатов:
https://github.com/wyfgvcj2br-art/tochki/commits/feature/windows-installer/

Результаты автоматических и ручных проверок разделены в VALIDATION_REPORT.md.
