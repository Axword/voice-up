# Źródła profili symulatorów i aplikacji

Stan weryfikacji: 22 października 2026. Plik `data/profile-library-sim.json` zawiera 24 profile i 468 komend: 12 wariantów polskich (`pl_PL`) oraz 12 angielskich (`en_US`). Najpierw zapisane są wszystkie warianty polskie, następnie angielskie z identyfikatorami zakończonymi `-en` i nazwami z dopiskiem `· EN`. Każda para ma identyczne przyciski, tryby i czasy; zmienia się język fraz. Liczby przy poszczególnych profilach poniżej dotyczą jednego wariantu językowego.

Profile są przeznaczone dla Windows i domyślnych skrótów klawiatury. Najpierw ustaw fokus na właściwym oknie; wybór profilu sam go nie przenosi. Własne mapowania klawiszy wymagają dostosowania komend. Język profilu określa język komend; rozpoznawanie wymaga pasującego modelu mowy.

Każda komenda wysyła jednocześnie podane przyciski. `timed` przytrzymuje je przez 3000 ms; `toggle` przytrzymuje do ponownego wypowiedzenia tej samej frazy. Skróty aplikacji pozostają w trybie `click`, także gdy aplikacja sama przełącza stan funkcji. Nie ma sekwencji klawiszy, wklejania tekstu, skryptów ani integracji z API gry.

## Adaptacja istniejących komend głosowych: Talon Community

Źródło: [talonhub/community](https://github.com/talonhub/community), zbadany commit [245cd44f7c88b175d92bcf329b6403cd11e78d98](https://github.com/talonhub/community/tree/245cd44f7c88b175d92bcf329b6403cd11e78d98).

Licencja: [MIT w repozytorium](https://github.com/talonhub/community/blob/245cd44f7c88b175d92bcf329b6403cd11e78d98/LICENSE); pełny tekst jest dołączony w [licenses/talonhub-community-MIT.txt](licenses/talonhub-community-MIT.txt).

Copyright (c) 2021 Jeff Knaus, Ryan Hileman, Zach Dwiel, Michael Arntzenius, and others.

Cztery zestawy poniżej adaptują rzeczywiste intencje komend z tego projektu, każdy w dwóch językach. Opracowano polskie i angielskie frazy, wybrano skróty Windows, zapisano je jako pojedyncze akordy i uzupełniono na podstawie dokumentacji producentów. Pominięto komendy wymagające rozszerzeń Talona, tekstu, opóźnień lub wieloetapowych działań. Nie jest wymagany Talon.

### Google Chrome: 25 komend

Pliki źródłowe komend głosowych:

- [browser.talon](https://github.com/talonhub/community/blob/245cd44f7c88b175d92bcf329b6403cd11e78d98/tags/browser/browser.talon) i [browser.py](https://github.com/talonhub/community/blob/245cd44f7c88b175d92bcf329b6403cd11e78d98/tags/browser/browser.py): zakładki, historia, pobieranie, odświeżanie, nawigacja i narzędzia programisty.
- [chrome.talon](https://github.com/talonhub/community/blob/245cd44f7c88b175d92bcf329b6403cd11e78d98/apps/chrome/chrome.talon) i [chrome.py](https://github.com/talonhub/community/blob/245cd44f7c88b175d92bcf329b6403cd11e78d98/apps/chrome/chrome.py): menu profilu i wyszukiwanie kart.

Uzupełnienie: [oficjalne skróty Chrome dla Windows](https://support.google.com/chrome/answer/157179?hl=en). Zachowano m.in. Ctrl+Shift+N dla okna prywatnego; „wybierz profil” otwiera menu profilu, a „zapisz wszystkie karty” otwiera okno zakładek.

### Mozilla Firefox: 24 komendy

Pliki źródłowe komend głosowych:

- Wspólne [browser.talon](https://github.com/talonhub/community/blob/245cd44f7c88b175d92bcf329b6403cd11e78d98/tags/browser/browser.talon) i [browser.py](https://github.com/talonhub/community/blob/245cd44f7c88b175d92bcf329b6403cd11e78d98/tags/browser/browser.py).
- [firefox.talon](https://github.com/talonhub/community/blob/245cd44f7c88b175d92bcf329b6403cd11e78d98/apps/firefox/firefox.talon) i [firefox_win_linux.py](https://github.com/talonhub/community/blob/245cd44f7c88b175d92bcf329b6403cd11e78d98/apps/firefox/firefox_win_linux.py): panele zakładek i historii, dodatki, pobieranie i tryb prywatny.

Uzupełnienie: [oficjalne skróty Firefox](https://support.mozilla.org/en-US/kb/keyboard-shortcuts-perform-firefox-tasks-quickly). Okno prywatne używa Ctrl+Shift+P. Przechodzenie do sąsiedniej karty używa Ctrl+PageDown/PageUp, niezależnie od ustawienia kolejności Ctrl+Tab. Wieloetapowe skupienie adresu z Talona zastąpiono pojedynczym Ctrl+L.

### Eksplorator plików: 20 komend

Pliki źródłowe komend głosowych: [windows_explorer.talon](https://github.com/talonhub/community/blob/245cd44f7c88b175d92bcf329b6403cd11e78d98/apps/windows_explorer/windows_explorer.talon) i [windows_explorer.py](https://github.com/talonhub/community/blob/245cd44f7c88b175d92bcf329b6403cd11e78d98/apps/windows_explorer/windows_explorer.py).

Adaptowano m.in. folder nadrzędny, adres, właściwości i tworzenie folderu. „Nowy folder” rozpoczyna nadawanie nazwy; profil nie wpisuje jej za użytkownika. Pozostałe skróty pochodzą z sekcji File Explorer w [dokumentacji Microsoft](https://support.microsoft.com/en-us/accessibility/windows/keyboard-shortcuts-in-windows).

### Visual Studio Code: 25 komend

Źródło intencji: [vscode.talon](https://github.com/talonhub/community/blob/245cd44f7c88b175d92bcf329b6403cd11e78d98/apps/vscode/vscode.talon), w tym panele, symbole, definicje, referencje, formatowanie i debugowanie.

Wywołania poleceń VS Code zastąpiono skrótami z [oficjalnej karty Windows](https://code.visualstudio.com/shortcuts/keyboard-shortcuts-windows.pdf). Zachowano np. Alt+Z, Shift+Alt+F, F9 i F10. Debugowanie wymaga konfiguracji projektu. Pominięto wieloetapowe skróty Ctrl+K.

## Autorskie profile na podstawie oficjalnych mapowań

Poniższe polskie i angielskie komendy opracowano dla tej aplikacji. Dokumentację wykorzystano do ustalenia faktów o sterowaniu; nie skopiowano z niej opisów ani obcych profili.

| Profil | Komendy | Pierwotne źródło |
| --- | ---: | --- |
| Skyrim | 18 | [Podręcznik Bethesda, Gameplay Controls, drukowana strona 2](https://steamcdn-a.akamaihd.net/steam/apps/72850/manuals/skyrim_gfw_manual-07.pdf) |
| Euro Truck Simulator 2 | 18 | [Podręcznik SCS Software, Control Keys, strona 9 PDF](https://cdn.cloudflare.steamstatic.com/steam/apps/227300/manuals/ETS2_manual_en.pdf) |
| American Truck Simulator | 18 | [Podręcznik SCS Software, Control Keys, strona 6 PDF](https://cdn.akamai.steamstatic.com/steam/apps/270880/manuals/ATS_manual_digital.pdf) |
| VLC | 14 | [VideoLAN, Hotkeys](https://docs.videolan.me/vlc-user/desktop/3.0/en/basic/hotkeys.html) |
| Blender | 18 | [Oficjalne źródło domyślnej mapy klawiszy](https://github.com/blender/blender/blob/main/scripts/presets/keyconfig/keymap_data/blender_default.py) |
| Spotify | 18 | [Spotify Support, Keyboard shortcuts](https://support.spotify.com/us/article/keyboard-shortcuts/) |
| Windows | 18 | [Microsoft, Windows key i Multiple desktops shortcuts](https://support.microsoft.com/en-us/accessibility/windows/keyboard-shortcuts-in-windows) |
| Edycja tekstu | 18 | [Microsoft, Text editing shortcuts](https://support.microsoft.com/en-us/accessibility/windows/keyboard-shortcuts-in-windows) |

Numery stron PDF powyżej liczone są od zera, zgodnie z odczytem źródeł.

### Uwagi do sterowania

- **Skyrim:** Alt+W to trzysekundowy sprint; W w trybie `toggle` to ruch do ponowienia tej samej frazy. C uruchamia automatyczny ruch samej gry i dlatego jest pojedynczym kliknięciem. „Obie ręce” naciska jednocześnie oba przyciski myszy, zależnie od wyposażenia postaci. Klawiatura i mysz muszą być aktywną metodą sterowania; [Bethesda opisuje wyłączenie kontrolera](https://help.bethesda.net/app/answers/detail/a_id/36588/~/how-do-i-disable-my-controller-and-use-the-keyboard-and-mouse-instead-for-the).
- **ETS2 i ATS:** klakson oraz S mają przytrzymanie trzysekundowe, a „trzymaj gaz” utrzymuje W do ponowienia frazy. S przy małej prędkości lub na postoju może uruchomić jazdę wstecz w prostym automacie. E, Space, L, P, C, nawiasy, F i kamery są pojedynczymi naciśnięciami. Źródła to podręczniki SCS © 2012 i © 2016; nie kopiowano ich treści.
- **VLC:** standardowe skróty działają w aktywnym oknie VLC. Skróty globalne wymagają oddzielnej konfiguracji odtwarzacza; profil jej nie zmienia. Prędkość odtwarzania używa znaków +, - oraz =.
- **Blender:** wymagana domyślna mapa Blender, nie Industry Compatible. Dla operacji obiektów kursor powinien znajdować się nad widokiem 3D w Object Mode. G, R, S i Shift+D rozpoczynają operację; Enter ją zatwierdza, Esc anuluje. Użyto wyłącznie faktów o mapowaniach, bez kopiowania kodu Blendera.
- **Spotify:** profil dotyczy aktywnej aplikacji Windows; Space i M mogą mieć inne działanie, gdy fokus znajduje się w polu tekstowym. Skróty biblioteki i nawigacji odpowiadają bieżącej oficjalnej dokumentacji.
- **Windows:** zapis `cmd` oznacza klawisz Windows. Przełączanie pulpitów wymaga istniejących dodatkowych pulpitów. „Zmniejsz okno” wysyła Win+Down; wynik zależy od aktualnego stanu okna.
- **Edycja tekstu:** profil skupia się na schowku, cofnięciu, wyszukiwaniu i zaznaczaniu. Programy z własną mapą skrótów mogą zachowywać się inaczej. Nie jest to profil dyktowania tekstu.

## Zakres weryfikacji

Sprawdzono składnię komend wszystkich 24 profili przez model `Profile`: obsługiwane przyciski, maksymalnie cztery jednocześnie, unikalne identyfikatory i znormalizowane frazy oraz dozwolone tryby. Dodatkowo sprawdzono kompletność par językowych i identyczne działania polskich oraz angielskich wariantów. Weryfikacja nie uruchamiała gier ani nie modyfikowała zapisanych profili użytkownika. Słownik nie jest potwierdzeniem testu rozpoznawania na fizycznym mikrofonie.

