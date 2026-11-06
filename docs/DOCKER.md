# Docker

Kontenery obsługują panel, profile JSON, API i testy. Nasłuch mikrofonu, przyciski systemowe i zasobnik wymagają aplikacji uruchomionej na Windowsie.

```powershell
docker compose up --build panel
```

Panel jest dostępny pod `http://127.0.0.1:21337`. Token sesji jest wstrzykiwany do panelu. `LOLVOICE_TOKEN` zmienia token deweloperski; nazwa zmiennej pozostaje dla kompatybilności.

```powershell
docker compose --profile dev up
docker compose --profile test run --rm tests
docker compose --profile test run --rm lint
```

W trybie `dev` Vite działa na porcie 5173 i przekazuje `/api` oraz `/ws` do panelu. Profile, ustawienia i logi są w wolumenie `voice-data` pod `/data`, wskazanym przez `VOICE_CONTROL_HOME`.

Porty są mapowane wyłącznie na loopback. `LOLVOICE_TRUSTED_HOSTS` dopuszcza bramę sieci kontenera; poza Dockerem nie jest potrzebna. API nadal wymaga tokenu. Kontenery nie korzystają z Riot API ani automatycznego wykrywania gry.
