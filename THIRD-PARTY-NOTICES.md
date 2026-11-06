# Licencje zaleznosci

Voice Control by Axword jest na GPL-3.0-or-later (plik LICENSE). Instalator i
paczka portable zawieraja ponizsze biblioteki, kazda na wlasnej licencji.

Dwie z nich, `pynput` i `pystray`, sa na LGPL-3.0. Licencja ta wymaga, aby
uzytkownik mogl podmienic te biblioteki na wlasna wersje. Warunek jest
spelniony: aplikacja jest wolnym oprogramowaniem, kod zrodlowy jest publiczny,
a biblioteki leza jako osobne pliki w katalogu `_internal` obok programu.

Zestawienie generuje `tools/generate_notices.py` z metadanych zainstalowanych
pakietow, wiec odswieza sie razem z zaleznosciami.

## Biblioteka profili

Polskie i angielskie profile zawieraja adaptacje otwartych zestawow komend Talon
oraz mapowania oparte na dokumentacji gier i programow. Zrodla, zakres adaptacji
i atrybucje opisuje `docs/PROFILE_LIBRARY.md`; teksty licencji sa w `docs/licenses/`.

## Biblioteki programu

| Pakiet | Licencja | Strona |
| --- | --- | --- |
| fastapi | MIT | https://github.com/fastapi/fastapi |
| faster-whisper | MIT | https://github.com/SYSTRAN/faster-whisper |
| numpy | BSD-3-Clause | https://numpy.org |
| pillow | MIT-CMU | https://pillow.readthedocs.io/en/stable/releasenotes/index.html |
| pydantic | MIT | https://github.com/pydantic/pydantic |
| pynput | LGPLv3 | https://github.com/moses-palmer/pynput |
| pystray | LGPLv3 | https://github.com/moses-palmer/pystray |
| pywhispercpp | MIT | https://absadiki.github.io/pywhispercpp/ |
| requests | Apache-2.0 | https://requests.readthedocs.io |
| setuptools | MIT License | https://github.com/pypa/setuptools |
| sounddevice | MIT | https://python-sounddevice.readthedocs.io/ |
| truststore | MIT | https://truststore.readthedocs.io |
| uvicorn | BSD-3-Clause | https://uvicorn.dev/release-notes |
| webrtcvad | MIT | https://github.com/wiseman/py-webrtcvad |
| websockets | BSD-3-Clause | https://github.com/python-websockets/websockets |
