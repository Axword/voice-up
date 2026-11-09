# DESIGN.md — panel Voice Control

Panel (`webui/`) wygląda i zachowuje się jak aplikacja Windows 11: spokojne, neutralne tła, jedna barwa akcentu, miękkie rogi i czcionka systemowa. Użytkownik to pracownik biurowy, który ma zobaczyć trzy rzeczy: czy aplikacja słucha, który profil jest teraz używany i co powiedzieć, żeby coś się stało.

Kierunek wybrany przez właściciela produktu: **natywny Windows 11 (Fluent)**. Nie bazuje na przeglądzie stron z UXKIN (serwer nie był połączony), tylko na konwencjach Windows 11 i na istniejącym panelu.

## Zasady

1. **Jedna rzecz zapada w pamięć: stan nasłuchu.** Karta na górze zmienia kolor na zielony, a ikona mikrofonu pulsuje, gdy aplikacja słucha. To jedyny ruch, który zaczyna się sam.
2. **Powierzchnie, nie pudełka.** Tło okna (Mica) jest szare, karty są białe. Listy są jedną kartą z cienkimi liniami, a nie osobnymi kafelkami.
3. **Tekst zdaniowy.** Bez wersalików, bez etykiet nad etykietami. Najmniejszy tekst ma 12 px.
4. **Stan niesie kształt i tekst, nie sam kolor.** Przełączniki, wybrany profil i błędy mają ikonę lub napis obok barwy.
5. **Klawiatura jest pełnoprawna.** Widoczna ramka fokusu, link „Przejdź do treści”, `aria-current` w nawigacji.

## Kolor

Role, nie nazwy odcieni. Wartości w `webui/src/styles/tokens.css`.

| Rola | Jasny | Ciemny | Użycie |
|---|---|---|---|
| `--bg` | `#f3f3f3` | `#202020` | tło okna, pasek tytułu, nawigacja |
| `--layer` | `#ffffff` | `#2b2b2b` | karty, tabela, okna dialogowe |
| `--layer-alt` | `#f9f9f9` | `#272727` | nagłówek tabeli, wstawki |
| `--text` | `#1a1a1a` | `#f5f5f5` | tekst podstawowy |
| `--muted` | `#5c5c5c` | `#b3b3b3` | opisy, podpowiedzi (≥ 6:1 na kartach) |
| `--stroke` | `#e5e5e5` | `#3a3a3a` | obramowania kart i linie podziału |
| `--stroke-strong` | `#8a8a8a` | `#9a9a9a` | obramowanie pól i przełączników (≥ 3:1) |
| `--accent` | `#005fb8` | `#60cdff` | akcje główne, fokus, wybrany element |
| `--ok` | `#0f7b0f` | `#6ccb5f` | nasłuch włączony, połączenie |
| `--danger` | `#c42b1c` | `#ff99a4` | błędy i usuwanie |

Akcent jest tylko jeden. Zielony oznacza wyłącznie stan „działa”.

## Typografia

Czcionki systemowe, bez pobierania: `Segoe UI Variable` (Windows 11), dalej `Segoe UI`, `system-ui`. Kod i skróty: `Cascadia Mono`, `Consolas`.

| Rola | Rozmiar / interlinia | Waga |
|---|---|---|
| Tytuł strony | 28 / 36 | 600 |
| Tytuł okna | 20 / 28 | 600 |
| Tytuł karty | 16 / 22 | 600 |
| Tekst | 14 / 20 | 400, wyróżnienie 600 |
| Opis | 12 / 16 | 400 |

## Odstępy, kształt, głębia

- Skala odstępów: 4, 8, 12, 16, 20, 24, 32 px.
- Promień: 4 px (przyciski, pola, segmenty), 8 px (karty, okna), pełny (przełączniki).
- Karty mają obramowanie, bez cienia. Cień ma tylko okno dialogowe: `0 8px 16px #00000024, 0 0 2px #0000001f`.
- Wysokość kontrolek: 32 px. Przełącznik ma powiększony obszar kliknięcia (48 × 28 px).

## Komponenty

- **Przycisk**: główny (akcent), zwykły (karta + obramowanie), cichy (bez tła), niebezpieczny (tekst w kolorze błędu). Stany: spoczynek, hover, wciśnięty, fokus, wyłączony.
- **Przełącznik**: 40 × 20 px, wyłączony z obramowaniem, włączony w kolorze akcentu.
- **Kontrolka segmentowa**: filtry trybów i wybór trybu komendy.
- **Karta nasłuchu**: stan, przycisk, a pod spodem wiersze ustawień (profil, model, mikrofon) i rozwijane ustawienia zaawansowane.
- **Tabela komend**: jedna karta z wierszami. Poniżej 680 px szerokości (zapytanie o kontener) wiersz zapisuje się w dwóch liniach.
- **Pasek informacji**: „Teraz używany: …” (akcent) i błędy (kolor błędu, `role="alert"`).
- **Okno dialogowe**: natywny `<dialog>`, ciemna zasłona bez rozmycia.

## Ruch

Czasy 120 ms (hover, wciśnięcie) i 200 ms (przełączniki, rozwijanie), krzywa `cubic-bezier(.16, 1, .3, 1)`. Jedyna animacja bez udziału użytkownika to puls ikony przy włączonym nasłuchu. `prefers-reduced-motion` wyłącza ruch, a `forced-colors` zachowuje obramowania i stany.

## Czego unikamy

Gradientów, rozmycia tła, ikon w kolorowych kafelkach, wersalików, identycznych kafelków dla każdej treści i kilku akcentów naraz.
