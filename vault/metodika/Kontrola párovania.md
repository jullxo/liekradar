# Ručná kontrola párovania ČR–SR

Vzorka 50 účinných látok (polovica s najviac výpadkami, polovica náhodne). Ku každej jeden liek z ČR a jeden zo SR, podľa možnosti od toho istého výrobcu. Kontroloval človek podľa názvu, sily a držiteľa registrácie. Podklad: `kontrola_parov.csv`.

| Kontrola | Výsledok |
|---|---|
| Rovnaká účinná látka pod rovnakým ATC kódom | 49 z 50 |
| Systém spojil výrobcu a je to naozaj ten istý výrobca (skupina) | 49 z 49 |
| Systém výrobcu nespojil, hoci je to ten istý | 0 z 1 |

Nájdené chyby:

- B05BB01 ELEKTROLYTY: ISOLYTE INF SOL 20X500ML (Fresenius Kabi s.r.o., Praha) × Sodium chloride Fresenius Kabi 0,9 % sol inf 10x1 000 ml (vak Freeflex+) (Fresenius Kabi s.r.o.) – široký ATC kód, rôzne roztoky
