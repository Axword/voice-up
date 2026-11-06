# Kontrakty wewnętrzne Axword Voice Control

Aplikacja działa lokalnie: Python rozpoznaje mowę i steruje wejściami systemowymi, a panel Preact edytuje profile gier.

## Dane i ustawienia

`app.paths` wskazuje katalogi konfiguracji, modeli, logów i danych. `LOLVOICE_HOME` przekierowuje je do jednego katalogu, m.in. w testach i wydaniu portable. Zachowanie tej zmiennej i nazwy danych zapewnia zgodność z wcześniejszym wydaniem.

`app.config.Settings` zawiera: `language`, `ui_language`, `engine_id`, `matching_threshold`, `audio_device`, `start_with_windows`, `start_listening_on_launch`, `theme`, `skipped_version`, `check_updates`. Domyślny motyw to `light`. Starsze pola dotyczące bohaterów, zaklęć, liter i sekwencji są ignorowane przy migracji.

Profile są oddzielnym dokumentem JSON. Każdy profil identyfikuje grę i zawiera niezależne komendy:

```json
{
  "version": 1,
  "active_profile_id": "league-of-legends",
  "profiles": [
    {
      "id": "league-of-legends",
      "name": "League of Legends",
      "game": "League of Legends",
      "language": "pl_PL",
      "commands": [
        {
          "id": "flash",
          "phrase": "błysk",
          "keys": ["d"],
          "mode": "click",
          "duration_ms": 3000,
          "enabled": true
        },
        {
          "id": "move",
          "phrase": "naprzód",
          "keys": ["shift", "w"],
          "mode": "timed",
          "duration_ms": 3000,
          "enabled": true
        },
        {
          "id": "hold",
          "phrase": "trzymaj",
          "keys": ["right_click"],
          "mode": "toggle",
          "duration_ms": 3000,
          "enabled": true
        }
      ]
    }
  ]
}
```

`id` jest stabilnym identyfikatorem. `active_profile_id` musi wskazywać istniejący profil. Komendy dopasowują całą wypowiedź po normalizacji tekstu; komendy wyłączone nie wykonują akcji. `keys` to przyciski naciskane równocześnie, również z modyfikatorami lub przyciskami myszy `left_click`, `right_click`, `middle_click`.

`settings.matching_threshold` to liczba od 0 do 1, domyślnie 1. Panel pokazuje ją w procentach w rozwijanej sekcji Zaawansowane. Pełne dopasowanie ma pierwszeństwo; poniżej 1 serwis wybiera najwyższy wynik `difflib.SequenceMatcher` spełniający próg. Remis najlepszych wyników oznacza brak dopasowania. Wypowiedzi oraz komendy o co najwyżej dwóch znakach alfanumerycznych wymagają dopasowania dokładnego, niezależnie od progu. Zmiana progu nie restartuje mikrofonu. Test tekstowy i nasłuch korzystają z tej samej funkcji dopasowania.

`Profile.language` określa język rozpoznawania komend: `pl_PL`, `en_US`, `de_DE`, `es_ES`, `fr_FR` albo `uk_UA`. Dokumenty bez tego pola zachowują `pl_PL`. Panel zapisuje je jako `profiles[].language` przez `PUT /profiles`. Inicjalizacja serwisu i zmiana aktywnego profilu synchronizują `settings.language`; zapis profilu wznawia nasłuch, jeśli wcześniej działał. Ręczna zmiana `language` przez `PUT /settings` aktualizuje również aktywny profil. `settings.ui_language` obsługuje te same sześć kodów i pozostaje niezależnym językiem interfejsu.

Tryby: `click` naciska i puszcza zestaw przycisków, `timed` puszcza go po `duration_ms`, `toggle` przełącza przytrzymanie po ponownym wypowiedzeniu tej samej frazy. Zatrzymanie nasłuchu, zmiana profilu lub zapis konfiguracji zwalnia trzymane przyciski. Zapis dokumentu jest walidowany przed atomową podmianą pliku.

### Początkowa biblioteka i migracja

Pełny katalog dostarczają cztery tablice JSON w `data/`: `profile-library-core.json`, `profile-library-games.json`, `profile-library-sim.json` i `profile-library-baseline.json`. Nowe dane użytkownika otrzymują cały katalog. Kolejność profili w plikach pozostaje kolejnością początkową. Panel sortuje profil podstawowej klawiatury na początek i filtruje listę według języka, zapamiętując filtr w przeglądarce. Profil podstawowy zawiera pojedyncze kliknięcia klawiszy oraz osobne komendy z fonetycznymi nazwami liter i cyfr.

`app.profiles.synchronize_library(document)` dopisuje wyłącznie brakujące profile o identyfikatorach katalogowych, których ta instalacja wcześniej nie widziała. Nie zmienia istniejących profili, komend, kolejności ani `active_profile_id`. Pierwsze rozszerzenie istniejącego dokumentu zachowuje jego dokładną kopię w `profiles.before-library.json`.

Plik `profile-library-state.json` obok `profiles.json` przechowuje `schema: 1` i `seen_catalog_ids`. Aktualizuje się atomowo dopiero po udanym zapisie dokumentu profili. Pamięta również usunięte profile oraz wpisy pominięte z powodu limitu 100 profili, więc kolejne uruchomienie ich samoczynnie nie przywraca. Uszkodzony dokument, stan migracji lub katalog wywołuje błąd przed podmianą danych użytkownika. Pakiet Windows zawiera całe katalogi `data/` i `docs/`, wraz ze źródłami i licencjami profili.

## VoiceService

`controller.service.get_service()` zwraca singleton. Konstruktor nie uruchamia mikrofonu ani modelu.

| Metoda | Zachowanie |
| --- | --- |
| `profiles_document()` | zwraca pełny dokument profili |
| `replace_profiles(document)` | waliduje, zapisuje i zwraca dokument |
| `test_command(text)` | zwraca dopasowanie bez naciskania przycisków |
| `handle_transcript(text)` | wykonuje komendę aktywnego profilu |
| `release_all()` | zwalnia wszystkie przytrzymane przyciski |
| `start()` / `stop()` | uruchamia lub zatrzymuje nasłuch |
| `status()` | zwraca status panelu |
| `apply_settings(settings, profile_language=False)` | przyjmuje ustawienia audio i panelu; `True` zapisuje żądaną zmianę języka rozpoznawania w aktywnym profilu |
| `reload_engine()` | przeładowuje lokalny model mowy |
| `list_audio_devices()` | zwraca urządzenia wejściowe |
| `test_microphone(seconds)` | nagrywa próbkę i zwraca poziom oraz transkrypcję |
| `set_event_sink(fn)` | podpina odbiornik zdarzeń panelu |
| `feed_pcm(pcm)` / `set_transcriber(fn)` | pozwala sprawdzić pełny przepływ z kontrolowaną transkrypcją |

## REST API

Prefiks `/api/v1`. Nasłuch na `127.0.0.1`; każdy endpoint API wymaga `X-Auth-Token` lub parametru `token`. Serwer wstrzykuje sesję do HTML jako `window.__LOLVOICE__`. To wewnętrzna, zachowana nazwa protokołu. Opcjonalne `LOLVOICE_TRUSTED_HOSTS` dopuszcza wskazane adresy lub podsieci dla uruchomień kontenerowych; token nadal jest wymagany.

| Metoda | Ścieżka | Odpowiedź |
| --- | --- | --- |
| GET | `/status` | status opisany poniżej |
| GET | `/profiles` | cały dokument profili |
| PUT | `/profiles` | przyjmuje i zwraca cały dokument; 422 przy błędach walidacji, 500 przy błędzie zapisu |
| POST | `/commands/test` | przyjmuje `{text}`; zwraca `{text, matched, command, profile_id}` bez wykonania akcji |
| POST | `/keys/release` | `{released: true}` |
| POST | `/listening/start` lub `/listening/stop` | `{listening, error}` |
| GET | `/settings` | pełny model ustawień |
| PUT | `/settings` | częściowy patch; zwraca pełny model |
| GET | `/engines` | `{engines: [...]}` |
| POST | `/engines/{id}/download` | `{started: true}`; postęp przez WebSocket |
| POST | `/engines/{id}/cancel` | `{cancelled: true}` |
| POST | `/engines/{id}/activate` | `{engine_id}` |
| GET | `/audio/devices` | `{devices: [{id, name, default}]}` |
| POST | `/audio/test` | przyjmuje `{seconds: 1..10}`; zwraca `{level, transcript, error?}` |
| GET | `/logs` | `{files: [{name, size, modified}], tail: [...]}` |
| GET | `/logs/download` | archiwum ZIP z logami i informacją systemową |
| GET | `/update/check` | `{current, latest, available, url, notes}` |
| POST | `/update/install` | `{started, reason?}` |
| POST | `/app/quit` | `{ok: true}` |

Status zawiera: `listening`, `active_profile_id`, `profile_name`, `held_keys`, `held_command_ids`, `engine_id`, `engine_name`, `version`, `mappings_count`, `last_command`, `last_heard`, `update_available`, `error`. Pola dotyczące bohatera i wykrywania rozgrywki zostały usunięte.

Nieprawidłowy token daje HTTP 401, niedopuszczony adres HTTP 403, a niedostępny serwis profili HTTP 503. Walidacja zwraca listę błędów w `detail`.

## WebSocket

`/ws/status` wymaga tego samego tokenu i dozwolonego adresu klienta. Ramki mają `type`: `status`, `heard`, `download`, `log`, `update`. Status zawiera te same pola co REST. `heard` opisuje rozpoznany tekst i dopasowane klawisze; podgląd `/commands/test` nie generuje wejść systemowych.

## Panel

Panel buduje się do `webui/dist`. Główna interakcja to fraza, przyciski i wybór jednego z trzech trybów. Profile można zapisać i przenosić jako JSON. Interfejs wizualnie nawiązuje do Axword: jasne tło, białe powierzchnie, zielony akcent i proste obrysy.
