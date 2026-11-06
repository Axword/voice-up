# Biblioteka profili Voice Control

Biblioteka startowa zawiera **56 profili i 1191 komend**: 28 zestawów, każdy z osobnym wariantem polskim i angielskim. Wersje PL zawierają 591 komend, a EN 600. Obejmuje gry, aplikacje oraz podstawowy profil klawiatury, gotowe do edycji i eksportu jako JSON.

Zapisane warianty angielskie mają dopisek `· EN` w nazwie i `-en` w identyfikatorze; w panelu język oznaczono skrótem PL lub EN. W 27 zestawach do gier i aplikacji obie wersje wysyłają te same przyciski, w tym samym trybie i z tym samym czasem przytrzymania. Podstawowa klawiatura zawiera dodatkowo różne aliasy wymowy dla każdego języka, dlatego liczby fraz PL i EN są inne.

## Język interfejsu i komend

Interfejs oraz rozpoznawanie obsługują sześć języków:

| Język | Kod |
| --- | --- |
| Polski | `pl_PL` |
| Angielski | `en_US` |
| Niemiecki | `de_DE` |
| Hiszpański | `es_ES` |
| Francuski | `fr_FR` |
| Ukraiński | `uk_UA` |

**Język interfejsu** zmienia etykiety panelu. **Język komend** zapisuje się osobno w każdym profilu. Rozpoznawanie korzysta z języka aktywnego profilu, więc przełączenie profilu PL na EN zmienia również język rozpoznawania. Zmiana języka panelu nie zmienia fraz ani języka profilu.

Gotowe zestawy zawierają frazy PL i EN. Dla pozostałych języków można utworzyć własny profil i wpisać komendy w wybranym języku. Wybranie języka nie tłumaczy automatycznie własnych fraz. Starsze profile bez pola `language` zachowują swoje frazy i otrzymują domyślnie `pl_PL`.

Filtr „Język profili” zawęża listę zestawów do wybranego języka. „Wszystkie języki” pokazuje całą bibliotekę. Zmiana filtra pozostawia aktywny profil bez zmian, dopóki nie wybierzesz innego.

## Dostępne zestawy

Każdy wiersz odpowiada dwóm profilom: PL i EN. Osobne kolumny uwzględniają dodatkowe aliasy wymowy w podstawowej klawiaturze.

| Zestaw | Gra / aplikacja lub układ | Komendy PL | Komendy EN |
| --- | --- | ---: | ---: |
| League of Legends | Point & Click | 20 | 20 |
| Minecraft | Java Edition na PC | 22 | 22 |
| League of Legends · WASD | Keyboard WASD | 13 | 13 |
| Counter-Strike 2 | Counter-Strike 2 | 18 | 18 |
| Apex Legends | Apex Legends | 18 | 18 |
| Helldivers 2 | Helldivers 2 | 18 | 18 |
| Deep Rock Galactic | Deep Rock Galactic | 18 | 18 |
| Warframe | Warframe | 18 | 18 |
| Stardew Valley | Stardew Valley | 16 | 16 |
| Terraria | Terraria na PC | 18 | 18 |
| Factorio | Factorio | 18 | 18 |
| Inkbound | Inkbound | 14 | 14 |
| Trails Beyond the Horizon | The Legend of Heroes: Trails Beyond the Horizon | 16 | 16 |
| Portal 2 | Portal 2 | 14 | 14 |
| Team Fortress 2 | Team Fortress 2 | 18 | 18 |
| Skyrim | The Elder Scrolls V: Skyrim | 18 | 18 |
| Euro Truck Simulator 2 | Euro Truck Simulator 2 | 18 | 18 |
| American Truck Simulator | American Truck Simulator | 18 | 18 |
| Google Chrome | Windows | 25 | 25 |
| Mozilla Firefox | Windows | 24 | 24 |
| Eksplorator plików | Windows | 20 | 20 |
| Visual Studio Code | Windows | 25 | 25 |
| VLC | VLC media player na Windows | 14 | 14 |
| Blender | Domyślna mapa klawiszy Blender | 18 | 18 |
| Spotify | Windows | 18 | 18 |
| Windows | Pulpit i okna | 18 | 18 |
| Edycja tekstu | Standardowe skróty edytorów na Windows | 18 | 18 |
| Podstawowy · Klawiatura | Pojedyncze klawisze i aliasy wymowy | 98 | 107 |

Katalog jest zapisany w czterech plikach:

| Plik | Profile PL + EN | Komendy łącznie | Szczegółowe źródła |
| --- | ---: | ---: | --- |
| [profile-library-core.json](../data/profile-library-core.json) | 6 | 110 | [Profile podstawowe](profile-sources-core.md) |
| [profile-library-games.json](../data/profile-library-games.json) | 24 | 408 | [Gry](profile-sources-games.md) |
| [profile-library-sim.json](../data/profile-library-sim.json) | 24 | 468 | [Symulatory i aplikacje](profile-sources-sim.md) |
| [profile-library-baseline.json](../data/profile-library-baseline.json) | 2 | 205 | [Podstawowa klawiatura](#podstawowa-klawiatura) |
| **Razem** | **56** | **1191** | |

## Podstawowa klawiatura

Profil „Podstawowy · Klawiatura” oraz jego angielski odpowiednik „Basic · Keyboard · EN” obejmują po 67 podstawowych mapowań: litery A-Z, cyfry 0-9, klawisze specjalne, strzałki, modyfikatory i F1-F12. Wszystkie wykonują pojedyncze naciśnięcie w trybie `click`.

Wersja PL dodaje 31 aliasów wymowy, a EN 40: na przykład `w` i `wu` wysyłają W w polskim profilu, `double u` i `double you` wysyłają W w angielskim, a `jeden` lub `one` wysyła 1 w odpowiednim języku. To autorskie mapowania pojedynczych klawiszy, bez zależności od ustawień konkretnej gry. Nie obejmują dyktowania całych zdań.

## Podobieństwo komendy

W panelu komend rozwiń „Zaawansowane”, aby ustawić suwak „Podobieństwo komendy” od 0 do 100%. Domyślne 100% wymaga dokładnego dopasowania. Porównanie pomija wielkość liter, interpunkcję i znaki diakrytyczne.

Niższy próg dopuszcza większe różnice między rozpoznanym tekstem a zapisaną frazą. Procent opisuje podobieństwo tych tekstów. Dokładne trafienie ma pierwszeństwo; przy równym najlepszym wyniku kilku komend żadna nie zostaje wybrana. Frazy i wejście zawierające do dwóch liter lub cyfr nadal wymagają dokładnego dopasowania, co obejmuje pojedyncze litery profilu klawiatury.

Próg jest wspólnym ustawieniem aplikacji i dotyczy włączonych komend aktywnego profilu. „Sprawdź komendę” używa tego samego dopasowania bez naciskania przycisków.

## Działanie przycisków

- `click` naciska i zwalnia przyciski.
- `timed` przytrzymuje je przez zadany czas, w gotowych zestawach zwykle 3000 ms.
- `toggle` przytrzymuje je do ponownego wypowiedzenia tej samej frazy.

Od jednego do czterech przycisków jednej komendy działa jednocześnie. Na przykład sprint może przytrzymywać Shift i W, a komenda „obie ręce” w Skyrim naciska oba przyciski myszy. Format nie wykonuje sekwencji kroków ani skryptów. Zatrzymanie nasłuchu, zmiana profilu oraz przycisk „Zwolnij przyciski” zwalniają przytrzymania.

Profile opierają się na opisanych w źródłach mapowaniach PC, zwykle domyślnych. Nie zmieniają ustawień gry i nie przenoszą fokusu do jej okna. Po zmianie klawiszy w grze należy dopasować profil. Działania zależne od kursora korzystają z jego bieżącej pozycji.

Przy celowaniu, sprincie lub kucaniu wymagającym ciągłego naciśnięcia wybierz w grze wariant **Hold**, jeśli dokument danego profilu tego wymaga. Gdy sama gra przełącza stan jednym naciśnięciem, komenda pozostaje w trybie `click`. Profil `toggle` nie odczytuje stanu menu ani postaci.

Przykładowe ustawienia zależne od zestawu:

- LoL WASD wymaga wcześniejszego wybrania Keyboard WASD w grze.
- CS2 i TF2 zakładają przytrzymanie Ctrl dla kucania; Apex rozróżnia kucanie przełączane C i przytrzymywane Ctrl.
- Menu wsparcia Helldivers 2 zakłada Hold dla Ctrl; sekwencje stratagemów nie są częścią profilu.
- Blender wymaga domyślnej mapy Blender oraz właściwego obszaru i trybu edytora.
- W ETS2 i ATS przycisk S może również cofać w prostym automacie.

Szczegółowe wymagania i kontekst poszczególnych komend podają trzy dokumenty źródłowe powyżej. Sprawdzenie katalogu obejmuje schemat, przyciski, unikalność fraz i pary językowe. Nie oznacza testu każdej komendy w uruchomionej grze ani na każdym mikrofonie.

## Aktualizacja istniejącej konfiguracji

Przy uruchomieniu aplikacja dopisuje nowe zestawy, zachowując istniejące profile, kolejność, komendy, własne przypisania oraz wybór aktywnego profilu. Profil o identyfikatorze już występującym w konfiguracji nie jest zastępowany wersją katalogową.

Plik `profile-library-state.json` pamięta identyfikatory zestawów już zaoferowanych przez bibliotekę. Usunięty później profil startowy nie wraca przy następnym uruchomieniu. Nowe identyfikatory z kolejnych aktualizacji mogą zostać dopisane. Dokument mieści do 100 profili; osiągnięcie limitu nie usuwa własnych zestawów, a pominięte pozycje katalogu również są zapamiętywane.

Przed pierwszym dopisaniem zestawów do istniejącego pliku powstaje kopia `profiles.before-library.json`. Kolejne aktualizacje jej nie nadpisują. Kopia i rejestr biblioteki znajdują się obok `profiles.json`, standardowo w `%APPDATA%\LoLVoice`; przy ustawionym `VOICE_CONTROL_HOME` w wybranym katalogu konfiguracji.

## Źródła, adaptacje i licencje

Źródła sprawdzono 22 października 2026. Dokumenty [core](profile-sources-core.md), [games](profile-sources-games.md) i [sim](profile-sources-sim.md) wskazują konkretne pliki profili, dokumentację producentów, konfiguracje gier oraz wiki. Rozróżniają adaptacje istniejących zestawów od nowych fraz opartych na faktach o przypisaniach.

- **Talon Community:** Chrome, Firefox, Eksplorator plików i VS Code w obu językach adaptują rzeczywiste intencje komend z [talonhub/community](https://github.com/talonhub/community). Wybrano pojedyncze akordy Windows, opracowano frazy PL/EN i pominięto działania wymagające rozszerzeń, tekstu lub sekwencji. Obowiązuje MIT; [pełny tekst i informacja copyright](licenses/talonhub-community-MIT.txt) są dołączone do projektu. Copyright (c) 2021 Jeff Knaus, Ryan Hileman, Zach Dwiel, Michael Arntzenius, and others. Dokładne pliki i commit podaje [dokument sim](profile-sources-sim.md).
- **Talon Games:** Inkbound i Trails Beyond the Horizon korzystają z mapowań opublikowanych przez [orlekc](https://github.com/orlekc/talon-games). Repozytorium deklaruje MIT w README; zakres adaptacji i stan dostępnych informacji licencyjnych zachowano w [nocie źródłowej](licenses/orlekc-talon-games-NOTICE.md).
- **VoiceAttack:** [profil Helldivers 2 autorstwa Artmos](https://github.com/Artmos/helldivers-2-voice-attack) na GPL-3.0 przejrzano jako odniesienie. Nie importowano pliku VAP, makr ani sekwencji. Mapowania naszego zestawu sprawdzono w oficjalnej dokumentacji gry.
- **Pozostałe źródła:** wykorzystano fakty o klawiszach i działaniach, z własnymi frazami oraz zapisem JSON. Nie dołączono tekstów instrukcji, grafik ani kodu gier. Warunki i atrybucje poszczególnych źródeł znajdują się przy odpowiednich profilach.

Licencję aplikacji określa [LICENSE](../LICENSE), a licencje zależności opisuje [THIRD-PARTY-NOTICES.md](../THIRD-PARTY-NOTICES.md).

