# Źródła profili podstawowych

Sprawdzono: 22 października 2026. Plik `data/profile-library-core.json` zawiera 6 profili i 110 komend: trzy zestawy po polsku (`pl_PL`, 55 komend) oraz ich trzy angielskie odpowiedniki (`en_US`, 55 komend). Polskie i angielskie frazy oraz zapis w JSON opracowano dla Voice Control. Z dokumentacji wykorzystano informacje o przyciskach; nie kopiowano tekstu instrukcji, grafiki ani kodu gry.

Każdy zestaw ma wariant PL i EN z tymi samymi przyciskami, trybami, czasem przytrzymania i stanem włączenia komend. Wariant angielski ma identyfikator zakończony `-en` i dopisek `· EN` w nazwie. League of Legends zawiera po 20 komend na język, Minecraft po 22, a League of Legends WASD po 13. Frazy angielskie przygotowano jako osobny zestaw; zmiana języka istniejącego profilu nie tłumaczy jego fraz automatycznie.

Język komend jest zapisany w profilu i steruje językiem rozpoznawania po jego aktywacji. Język interfejsu wybiera się niezależnie. Starsze profile bez pola `language` zachowują swoje komendy i otrzymują domyślnie `pl_PL`. Zestawienie całej biblioteki oraz zasady aktualizacji opisuje [PROFILE_LIBRARY.md](PROFILE_LIBRARY.md).

| Profil | Podstawa |
| --- | --- |
| League of Legends | Dotychczasowy profil projektu, rozszerzony o standardowe akcje Point & Click; [Riot: Hotkeys](https://support.riotgames.com/en-us/league-of-legends/performance/hotkeys-keybindings-faq) i [zestawienie skrótów klienta](https://wiki.leagueoflegends.com/en-us/Hotkeys). |
| Minecraft | [Mojang: Minecraft Controls](https://www.minecraft.net/en-us/article/minecraft-controls), sekcja klawiatury i myszy. Profil dotyczy Java Edition na PC z domyślnymi ustawieniami. |
| League of Legends · WASD | [Riot: Keyboard WASD Input FAQ](https://support.riotgames.com/en-us/league-of-legends/gameplay/league-of-legends-keyboard-wasd-input-faq), publikacja z 4 maja 2026. W grze należy najpierw wybrać sterowanie Keyboard WASD. |

W profilu klasycznym LoL przyciski D/F oznaczają miejsca zaklęć przywoływacza, więc fraza „błysk” wymaga przypisania Błysku do D albo edycji komendy. Zachowana wcześniejsza komenda „atakuj” przytrzymuje A, czyli uzbraja tryb ataku z ruchem; sama nie wybiera celu ani nie wykonuje kliknięcia myszą.

Profile nie zmieniają ustawień gry. Akcje zależne od kursora wykonują się w jego bieżącym położeniu. Komendy `toggle` służą do trzymania przycisku do powtórzenia frazy; nie oznaczają odczytu stanu gry.

