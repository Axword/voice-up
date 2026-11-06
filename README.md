# Voice Control by Axword

Lokalne sterowanie głosem dla gier i aplikacji na Windows 10/11. Każdy profil zawiera własne komendy, zapisane w JSON. Rozpoznawanie mowy działa lokalnie przez Whisper.

Biblioteka startowa zawiera 56 profili i 1191 komend: 28 zestawów do gier, aplikacji i podstawowej klawiatury, każdy w wersji polskiej i angielskiej. Powstały na podstawie otwartych profili Talon, dokumentacji sterowania i autorskich mapowań klawiszy. Pełną listę, źródła i wymagane ustawienia opisuje [biblioteka profili](docs/PROFILE_LIBRARY.md).

Interfejs można przełączyć na polski, angielski, niemiecki, hiszpański, francuski lub ukraiński. Każdy profil ma osobny język rozpoznawania; wybór profilu automatycznie ustawia język komend. Edycja języka nie tłumaczy samodzielnie dodanych fraz.

Listę profili można filtrować według języka. Profil podstawowej klawiatury rozpoznaje litery, cyfry i aliasy wymowy, np. polskie „wu” oraz angielskie „double you” naciskają W. Sekcja „Zaawansowane” w panelu komend pozwala ustawić podobieństwo fraz od 0 do 100%; domyślne 100% wymaga dokładnego dopasowania, a pojedyncze litery pozostają dokładne przy każdym progu.

Przy aktualizacji nowe profile są dopisywane do istniejącej konfiguracji. Własne komendy, zmienione profile i wybór aktywnego profilu pozostają zachowane; usunięte wcześniej zestawy nie wracają przy kolejnym uruchomieniu.

## Komendy

- `click`: naciśnięcie i zwolnienie przycisków.
- `timed`: przytrzymanie przycisków przez `duration_ms` (domyślnie 3000 ms).
- `toggle`: przytrzymanie do ponownego wypowiedzenia tej samej frazy.

Wszystkie przyciski jednej komendy są wciskane jednocześnie, np. `ctrl` + `q`. Zatrzymanie nasłuchu lub zmiana profilu zwalnia trzymane przyciski.

```json
{
  "version": 1,
  "active_profile_id": "moja-gra",
  "profiles": [
    {
      "id": "moja-gra",
      "name": "Mój profil",
      "game": "Moja gra",
      "language": "pl_PL",
      "commands": [
        {
          "id": "atak",
          "phrase": "atak",
          "keys": ["ctrl", "q"],
          "mode": "click",
          "duration_ms": 3000,
          "enabled": true
        },
        {
          "id": "bieg",
          "phrase": "biegnij",
          "keys": ["shift", "w"],
          "mode": "toggle",
          "duration_ms": 3000,
          "enabled": true
        }
      ]
    }
  ]
}
```

## Uruchomienie ze źródeł

Wymagane Python 3.11+ i Node.js 22.12+ (zalecany Node 24).

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
cd webui
npm ci
npm run build
cd ..
python main.py
```

Można też uruchomić `install.bat`, a następnie `launch.bat`. Aplikacja otwiera panel w przeglądarce i działa w zasobniku systemowym. Przed pierwszym nasłuchem pobierz model w ustawieniach panelu i wybierz mikrofon.

Podgląd lokalny bez ikony w zasobniku i automatycznego otwierania przeglądarki, z osobnymi danymi w katalogu projektu:

```powershell
$env:VOICE_CONTROL_HOME = Join-Path (Get-Location) '.preview-data'
python main.py --no-tray --no-browser --port 21337
```

Panel jest dostępny pod `http://127.0.0.1:21337`. Zatrzymanie serwera: `Ctrl+C`.

Profile można edytować w panelu oraz importować i eksportować jako JSON. Tekstowy edytor JSON obsługuje cały dokument: wszystkie profile, ich komendy i wybór aktywnego profilu. Ustawienia i profile są w `%APPDATA%\LoLVoice`, a modele i logi w `%LOCALAPPDATA%\LoLVoice`. Dawne katalogi pozostają dla zgodności z pobranymi modelami. Zmienna `VOICE_CONTROL_HOME` przenosi wszystkie dane do wskazanego folderu; wcześniejsza `LOLVOICE_HOME` nadal działa.

## Sprawdzenie i budowanie

```powershell
python -m pytest -m "not slow and not audio"
cd webui
npm run build
cd ..
python build.py --with-webui --app-only
```

Pełny instalator wymaga Inno Setup 6: `python build.py --with-webui`. Wyniki to `dist/AxwordVoice`, `dist/installer/AxwordVoiceSetup.exe` i archiwum portable. Automatyczne aktualizacje ze starego kanału LoL są wyłączone.

Kontenery służą do pracy nad panelem i API, bez sterowania klawiaturą i mikrofonem hosta: [docs/DOCKER.md](docs/DOCKER.md).

Licencja GNU GPL v3 lub nowsza: [LICENSE](LICENSE). Licencje bibliotek: [THIRD-PARTY-NOTICES.md](THIRD-PARTY-NOTICES.md).
