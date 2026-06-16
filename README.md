# Thingspeak_weather_tuner_Version1

# ThingSpeak Weather Tuner & Climate Analyzer

Egy univerzális, moduláris Python keretrendszer DIY meteorológiai állomások (ESP32, Raspberry Pi Pico W, Arduino) nyomás- és hőmérséklet-alapú előrejelző algoritmusainak finomhangolására, valamint hosszú távú mikroklimatikus adatelemzésre.

A projekt összeköti a saját **ThingSpeak** csatornád lokális mérési adatait az **Open-Meteo API** historikus tényadataival, létrehozva egy helyi **Digitális Ikret (Digital Twin)**, amely kiszámítja az állomásod földrajzi elhelyezkedésére optimalizált C++ kód-konstansokat.

---

## 🚀 Főbb funkciók

The software consists of 5 core modules designed for both real-time diagnostics and deep climatological analysis:

1. **Gyors Nyomás-trend Analizátor (24 óra):** Azonnali képet ad a légnyomás változásának dinamikájáról (5 perc, 1 óra, 12 óra és 24 óra visszamenőleg UTC-ben) a rövid távú trendek azonosításához.
2. **Digitális Iker & C++ Kód Optimalizáló (14 nap):** Letölti az elmúlt két hét óránkénti lokális időjárási kódjait és szélirányait. Egy rács-alapú szimulációval (Grid Search) addig teszteli a variációkat, amíg meg nem találja a helyszínedre leginkább pontos barometrikus küszöbértékeket. A végén **generálja a kész C++ kódsorokat**, amiket be lehet másolni az Arduinóba.
3. **Abszolút Zónák & Extrémumok (Teljes múlt):** Végigolvassa a csatorna teljes történetét, kiszámítja az abszolút 5%-os (extrém alacsony), 50% (standard közép) és 95%-os (extrém magas) nyomás-percentiliseket, valamint kigyűjti a valaha mért legalacsonyabb és legmagasabb hőmérsékleteket a pontos időpontokkal.
4. **Havi Hőmérséklet Statisztikák (Teljes múlt):** Hónapokra lebontott, letisztult táblázatban jeleníti meg a kinti minimum, maximum és átlagos hőmérsékleti értékeket.
5. **Éves Hőingás és Mikroklimatikus Küszöbnapok (Teljes múlt):** Kiszámítja az Átlagos Napi Hőingást (DTR) és kigyűjti a hivatalos meteorológiai küszöbnapokat évekre bontva:
   * **Fagyos napok száma** ($T_{min} < 0^\circ C$)
   * **Téli napok száma** ($T_{max} < 0^\circ C$)
   * **Nyári napok száma** ($T_{max} \ge 25^\circ C$)
   * **Hőség napok száma** ($T_{max} \ge 30^\circ C$)

---

## 🛠️ Telepítés és előfeltételek

A futtatáshoz **Python 3.8+** verzió szükséges.

1. Klónozd vagy töltsd le ezt a repozitóriumot.
2. Telepítsd a szükséges külső függőségeket a terminálban:

```bash
pip install requests numpy pandas
