import requests
import numpy as np
from datetime import datetime, timedelta
import pandas as pd
import sys
import warnings
import time

# Figyelmeztetések kikapcsolása a letisztultabb konzol kimenetért
warnings.filterwarnings("ignore")

# ==============================================================================
# --- GLOBÁLIS BEÁLLÍTÁSOK (Módosítsd a saját állomásod adatai alapján) ---
# ==============================================================================
STATION_NAME       = "Saját Időjárás Állomás" # Az állomásod neve a kiírásokban
THINGSPEAK_CHANNEL = "X"                     # ThingSpeak Csatorna Száma (Channel ID)
READ_API_KEY       = "X"                     # ThingSpeak Olvasási (Read) API Kulcs

# Földrajzi koordináták az Open-Meteo tényadatok szinkronizálásához
LATITUDE           = "X"                     # Pl. "47.4979"
LONGITUDE          = "X"                     # Pl. "19.0402"

# ThingSpeak mezők (Fields) hozzárendelése
OUTDOOR_TEMP_FIELD = "field1"                # Kinti hőmérséklet mezője
INDOOR_TEMP_FIELD  = "field2"                # Benti hőmérséklet mezője
PRESSURE_FIELD     = "field3"                # Légnyomás mezője

# ==============================================================================
# --- 1. MODUL: GYORS TREND ANALIZÁTOR (24 ÓRA) ---
# ==============================================================================
def run_trend_analyzer():
    print(f"\n[ Gyors Nyomás-trend Analizátor indítása ({STATION_NAME})... ]")
    start_time = datetime.utcnow() - timedelta(hours=24)
    start_str = start_time.strftime('%Y-%m-%dT%H:%M:%SZ')
    url = f"https://api.thingspeak.com/channels/{THINGSPEAK_CHANNEL}/feeds.json?api_key={READ_API_KEY}&start={start_str}"
    
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        feeds = [f for f in data.get('feeds', []) if f.get(PRESSURE_FIELD) and str(f[PRESSURE_FIELD]).lower() != 'null']
        
        if not feeds:
            print("Nincs elegendő adat az elmúlt 24 órában.")
            return

        last_feed = feeds[-1]
        last_p = float(last_feed[PRESSURE_FIELD])
        last_time = datetime.strptime(last_feed['created_at'], '%Y-%m-%dT%H:%M:%SZ')
        
        print("\n--- NYOMÁS TRENDEK (Minden időpont UTC-ben) ---")
        print(f"Aktuális idő:   {last_time.strftime('%Y-%m-%d %H:%M:%S')} UTC")
        print(f"Aktuális nyomás: {last_p:.1f} hPa\n")

        intervals = [24, 12, 1, 0.0833] 
        labels = ["24h", "12h", "1h ", "5m "]

        for hours, label in zip(intervals, labels):
            target_time = last_time - timedelta(hours=hours)
            closest_feed = min(feeds, key=lambda x: abs(datetime.strptime(x['created_at'], '%Y-%m-%dT%H:%M:%SZ') - target_time))
            
            p_past = float(closest_feed[PRESSURE_FIELD])
            time_past = datetime.strptime(closest_feed['created_at'], '%Y-%m-%dT%H:%M:%SZ')
            diff = last_p - p_past
            
            if diff > 0.05: trend_text = "Nyomásnövekedés"
            elif diff < -0.05: trend_text = "Nyomáscsökkenés"
            else: trend_text = "Stabil         "
            
            print(f"{label} trend: {trend_text} ({diff:+.2f} hPa) | Referencia idő: {time_past.strftime('%H:%M:%S')} UTC")

    except Exception as e:
        print(f"Hiba történt a lekérdezés során: {e}")


def get_wind_dir_str(deg):
    if 337.5 <= deg or deg < 22.5: return "N"
    elif 22.5 <= deg < 67.5: return "NE"
    elif 67.5 <= deg < 112.5: return "E"
    elif 112.5 <= deg < 157.5: return "SE"
    elif 157.5 <= deg < 202.5: return "S"
    elif 202.5 <= deg < 247.5: return "SW"
    elif 247.5 <= deg < 292.5: return "W"
    else: return "NW"


# ==============================================================================
# --- 2. MODUL: DIGITÁLIS IKER ÉS MODELL OPTIMALIZÁLÁS (14 NAP) ---
# ==============================================================================
def run_model_optimization():
    print(f"\n[ Digitális Iker optimalizálás indítása a(z) {STATION_NAME} koordinátái alapján... ]")
    try:
        print("[1/3] Meteorológiai tényadatok letöltése az Open-Meteo-ról (UTC)...")
        om_url = f"https://api.open-meteo.com/v1/forecast?latitude={LATITUDE}&longitude={LONGITUDE}&hourly=weather_code,wind_direction_10m&past_days=14&forecast_days=0&timezone=UTC"
        om_data = requests.get(om_url, timeout=15).json()
        
        times = [datetime.strptime(t, "%Y-%m-%dT%H:%M") for t in om_data['hourly']['time']]
        df_meteo = pd.DataFrame({
            'weather_code': om_data['hourly']['weather_code'], 
            'wind_deg': om_data['hourly']['wind_direction_10m']
        }, index=times)
        
        df_meteo['is_storm'] = df_meteo['weather_code'].isin([95, 96, 99])
        df_meteo['is_bad']   = df_meteo['weather_code'].isin([51, 53, 55, 61, 63, 65, 80, 81])
        df_meteo['is_clear'] = df_meteo['weather_code'].isin([0, 1])
        df_meteo['wind_dir'] = df_meteo['wind_deg'].apply(get_wind_dir_str)

        print("[2/3] ThingSpeak mintavétel letöltése...")
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(days=14)
        ts_url = f"https://api.thingspeak.com/channels/{THINGSPEAK_CHANNEL}/feeds.json?api_key={READ_API_KEY}&start={start_time.strftime('%Y-%m-%dT%H:%M:%SZ')}&end={end_time.strftime('%Y-%m-%dT%H:%M:%SZ')}&results=8000"
        ts_data = requests.get(ts_url, timeout=15).json()
        
        ts_times, ts_pressures = [], []
        for f in ts_data.get('feeds', []):
            if f.get(PRESSURE_FIELD) and f[PRESSURE_FIELD] != 'null':
                p = float(f[PRESSURE_FIELD])
                if 950.0 < p < 1060.0:
                    ts_times.append(datetime.strptime(f['created_at'], "%Y-%m-%dT%H:%M:%SZ"))
                    ts_pressures.append(p)
                    
        df_raw = pd.DataFrame({'pressure': ts_pressures}, index=ts_times).sort_index()
        df_1min = df_raw.resample('1min').mean().interpolate()
        df_1min['diff_5min'] = df_1min['pressure'].diff(periods=5)
        df_1min['diff_1h'] = df_1min['pressure'].diff(periods=60)
        
        df_hourly = df_1min.resample('1h').last()
        df_final = df_meteo.join(df_hourly, how='inner').dropna()

        storm_events = df_final[df_final['is_storm']]
        storm_th = float(np.percentile(storm_events['diff_5min'].dropna(), 15)) if not storm_events.empty else -1.8
        
        clear_events = df_final[df_final['is_clear']]
        sunny_clear_th = float(np.percentile(clear_events['diff_1h'], 75)) if not clear_events.empty else 1.2
        slow_improv_th = sunny_clear_th * 0.4

        current_month = datetime.now().month
        seasonal_offset = 0.5 * np.cos(2 * np.pi * (current_month - 1) / 12)

        print("[3/3] Rács-alapú lokális szimuláció futtatása...")
        best_score, best_th, best_mult = -1, -0.8, 0.0
        th_range = np.linspace(-2.0, -0.4, 25)
        mult_range = np.linspace(0.0, 1.2, 25)
        
        for th in th_range:
            for mult in mult_range:
                correct, total = 0, 0
                for idx in range(12, len(df_final)):
                    current_row = df_final.iloc[idx]
                    row_1h_ago = df_final.iloc[idx - 1]
                    row_12h_ago = df_final.iloc[idx - 12]
                    
                    raw_trend = current_row['pressure'] - row_1h_ago['pressure']
                    wind_dir = current_row['wind_dir']
                    
                    wind_mod = 0.0
                    if wind_dir in ["S", "SW"]: wind_mod = 2.0
                    elif wind_dir in ["SE", "W"]: wind_mod = 0.5
                    elif wind_dir == "NW": wind_mod = 0.6 if raw_trend < 0 else -0.2
                    elif wind_dir in ["E", "NE", "N"]: wind_mod = -0.6
                    
                    trend = raw_trend - (wind_mod * mult)
                    macro_trend = current_row['pressure'] - row_12h_ago['pressure']
                    
                    pred_bad = False
                    if macro_trend <= -3.0 and trend <= th: pred_bad = True
                    elif macro_trend >= 3.0 and trend <= th: pred_bad = False
                    elif trend <= th: pred_bad = True
                        
                    if pred_bad == current_row['is_bad']: correct += 1
                    total += 1
                    
                if total > 0 and correct > best_score:
                    best_score, best_th, best_mult = correct, th, mult

        print("\n====================================================")
        print("          MODELL OPTIMALIZÁLÁS SIKERES!            ")
        print("====================================================\n")
        print(f"Lokális predikciós pontosság a mintán: {best_score/total*100:.1f}%\n")
        print(f"// ---> MÁSOLD BE EZT A BLOKKOT A C++ KÓDODBA <---\")")
        print(f"const float STORM_THRESHOLD         = {min(storm_th, -0.5):.2f};")
        print(f"const float BAD_WEATHER_THRESHOLD   = {best_th:.2f};")
        print(f"const float SUNNY_CLEAR_THRESHOLD   = {max(sunny_clear_th, 0.5):.2f};")
        print(f"const float SLOW_IMPROV_THRESHOLD   = {max(slow_improv_th, 0.2):.2f};")
        print(f"const float SEASONAL_OFFSET         = {seasonal_offset:.2f};")
        print(f"const float WIND_MULTIPLIER         = {best_mult:.2f};  // Helyszínre optimalizálva")
        print("====================================================\n")

    except Exception as e:
        print(f"\nHiba történt az optimalizálás során: {e}")


# ==============================================================================
# --- 3. MODUL: TOTAL HISTORIKUS ANALIZÁTOR (ABSZOLÚT ZÓNÁK & EXTRÉMUMOK) ---
# ==============================================================================
def run_historical_pressure_zones():
    print("\n====================================================")
    print("[ DÖNTŐ CSATORNA-SZINTŰ HISTORIKUS ADATANALIZÁTOR ]")
    print("====================================================")
    
    confirm = input("Biztosan elindítod a teljes adatbázis elemzést? (i/n): ")
    if confirm.lower() != 'i': return

    try:
        meta_url = f"https://api.thingspeak.com/channels/{THINGSPEAK_CHANNEL}/feeds.json?api_key={READ_API_KEY}&results=0"
        meta_data = requests.get(meta_url, timeout=12).json()
        channel_info = meta_data.get('channel', {})
        created_at_str = channel_info.get('created_at')
        start_date = datetime.strptime(created_at_str, '%Y-%m-%dT%H:%M:%SZ') if created_at_str else (datetime.utcnow() - timedelta(days=730))
        active_fields = {f"field{i}": channel_info[f"field{i}"] for i in range(1, 9) if f"field{i}" in channel_info}

        detected_indoor, detected_outdoor = None, None
        for f_key, f_name in active_fields.items():
            n_low = f_name.lower()
            if any(kw in n_low for kw in ['bent', 'belso', 'belső', 'indoor', 'room', 'szoba', 'benti']): detected_indoor = f_key
            elif any(kw in n_low for kw in ['kint', 'kulso', 'külső', 'outdoor', 'out', 'terasz', 'kert', 'kinti']): detected_outdoor = f_key

        final_indoor_field  = detected_indoor if detected_indoor else INDOOR_TEMP_FIELD
        final_outdoor_field = detected_outdoor if detected_outdoor else OUTDOOR_TEMP_FIELD
    except Exception as e:
        print(f"Hiba csatorna inicializálásakor: {e}")
        return

    all_pressures = []
    field_mins = {f_key: float('inf') for f_key in active_fields}
    field_maxs = {f_key: float('-inf') for f_key in active_fields}
    field_min_times = {f_key: None for f_key in active_fields}
    field_max_times = {f_key: None for f_key in active_fields}
    
    end_date = datetime.utcnow()
    total_days = (end_date - start_date).days
    step_days = 5
    steps_needed = int(np.ceil(total_days / step_days))
    
    current_start = start_date
    step_count = 0
    
    while current_start < end_date:
        current_end = current_start + timedelta(days=step_days)
        if current_end > end_date: current_end = end_date
        url = f"https://api.thingspeak.com/channels/{THINGSPEAK_CHANNEL}/feeds.json?api_key={READ_API_KEY}&start={current_start.strftime('%Y-%m-%dT%H:%M:%SZ')}&end={current_end.strftime('%Y-%m-%dT%H:%M:%SZ')}&results=8000"
        
        try:
            response = requests.get(url, timeout=12)
            if response.status_code == 200:
                feeds = response.json().get('feeds', [])
                for f in feeds:
                    if not f.get('created_at'): continue
                    f_time = datetime.strptime(f['created_at'], '%Y-%m-%dT%H:%M:%SZ')
                    
                    p_str = f.get(PRESSURE_FIELD)
                    if p_str and p_str != 'null':
                        try:
                            p = float(p_str)
                            if 950.0 < p < 1060.0: all_pressures.append(p)
                        except ValueError: pass
                    
                    for f_key in active_fields:
                        val_str = f.get(f_key)
                        if val_str and val_str != 'null':
                            try:
                                val = float(val_str)
                                if -50.0 < val < 60.0:
                                    if val < field_mins[f_key]:
                                        field_mins[f_key] = val
                                        field_min_times[f_key] = f_time
                                    if val > field_maxs[f_key]:
                                        field_maxs[f_key] = val
                                        field_max_times[f_key] = f_time
                            except ValueError: pass
                step_count += 1
                sys.stdout.write(f"\rHaladás: [{step_count}/{steps_needed}] blokk | Rekordok: {len(all_pressures):,}")
                sys.stdout.flush()
        except Exception: pass
        current_start = current_end
        time.sleep(0.08)
        
    print("\n\n-> Analízis futtatása...")
    if len(all_pressures) < 100: return

    p_extreme_high = float(np.percentile(all_pressures, 95))
    p_standard_mid = float(np.percentile(all_pressures, 50))
    p_extreme_low  = float(np.percentile(all_pressures, 5))

    fmt = lambda dt: dt.strftime('%Y-%m-%d %H:%M') if dt else "Nincs adat"
    print("\n====================================================")
    print(f"    TELJES HISTORIKUS KALIBRÁCIÓ SIKERESEN KÉSZ!   ")
    print("====================================================\n")
    print(f"// ABSZOLÚT NYOMÁSZÓNÁK ({STATION_NAME})")
    print(f"const float PRESSURE_EXTREME_HIGH   = {p_extreme_high:.1f};")
    print(f"const float PRESSURE_STANDARD_MID   = {p_standard_mid:.1f};")
    print(f"const float PRESSURE_EXTREME_LOW    = {p_extreme_low:.1f};\n")
    print(f"Maximum kinti hőmérséklet: {field_maxs.get(final_outdoor_field, 0.0):.1f} °C ({fmt(field_max_times.get(final_outdoor_field))} UTC)")
    print(f"Minimum kinti hőmérséklet: {field_mins.get(final_outdoor_field, 0.0):.1f} °C ({fmt(field_min_times.get(final_outdoor_field))} UTC)")


# ==============================================================================
# --- 4. MODUL: HAVI BONTÁSÚ KINTI HŐMÉRSÉKLET STATISZTIKÁK ---
# ==============================================================================
def run_monthly_temperature_stats():
    print("\n====================================================")
    print("[ HAVI KINTI HŐMÉRSÉKLET MIN / MAX / ÁTLAG ANALÍZIS ]")
    print("====================================================")
    confirm = input("Elindítod a havi szintű historikus elemzést? (i/n): ")
    if confirm.lower() != 'i': return

    try:
        meta_url = f"https://api.thingspeak.com/channels/{THINGSPEAK_CHANNEL}/feeds.json?api_key={READ_API_KEY}&results=0"
        channel_info = requests.get(meta_url, timeout=12).json().get('channel', {})
        created_at_str = channel_info.get('created_at')
        start_date = datetime.strptime(created_at_str, '%Y-%m-%dT%H:%M:%SZ') if created_at_str else (datetime.utcnow() - timedelta(days=730))
        
        detected_outdoor = None
        for i in range(1, 9):
            f_key = f"field{i}"
            if f_key in channel_info and any(kw in channel_info[f_key].lower() for kw in ['kint', 'kulso', 'külső', 'outdoor', 'out', 'kinti']):
                detected_outdoor = f_key
        final_outdoor_field = detected_outdoor if detected_outdoor else OUTDOOR_TEMP_FIELD
    except Exception as e:
        print(f"Hiba: {e}"); return

    monthly_records = {}
    end_date = datetime.utcnow()
    total_days = (end_date - start_date).days
    step_days = 5
    steps_needed = int(np.ceil(total_days / step_days))
    current_start = start_date
    step_count = 0
    
    while current_start < end_date:
        current_end = current_start + timedelta(days=step_days)
        if current_end > end_date: current_end = end_date
        url = f"https://api.thingspeak.com/channels/{THINGSPEAK_CHANNEL}/feeds.json?api_key={READ_API_KEY}&start={current_start.strftime('%Y-%m-%dT%H:%M:%SZ')}&end={current_end.strftime('%Y-%m-%dT%H:%M:%SZ')}&results=8000"
        
        try:
            response = requests.get(url, timeout=12)
            if response.status_code == 200:
                feeds = response.json().get('feeds', [])
                for f in feeds:
                    if not f.get('created_at'): continue
                    f_time = datetime.strptime(f['created_at'], '%Y-%m-%dT%H:%M:%SZ')
                    month_key = f_time.strftime('%Y-%m')
                    val_str = f.get(final_outdoor_field)
                    if val_str and val_str != 'null':
                        try:
                            val = float(val_str)
                            if -50.0 < val < 60.0:
                                if month_key not in monthly_records: monthly_records[month_key] = []
                                monthly_records[month_key].append(val)
                        except ValueError: pass
                step_count += 1
                sys.stdout.write(f"\rHaladás: [{step_count}/{steps_needed}] blokk")
                sys.stdout.flush()
        except Exception: pass
        current_start = current_end
        time.sleep(0.08)
        
    print(f"\n\n====================================================")
    print(f"      HAVI STATISZTIKAI JELENTÉS - {STATION_NAME}   ")
    print(f"====================================================")
    print(f"{'Hónap':<9} | {'Minimum':<10} | {'Maximum':<10} | {'Átlaghőmérséklet':<16}")
    print("-" * 55)
    for month in sorted(monthly_records.keys()):
        temps = monthly_records[month]
        print(f"{month:<9} | {min(temps):>6.1f} °C  | {max(temps):>6.1f} °C  | {np.mean(temps):>11.2f} °C")


# ==============================================================================
# --- 5. MODUL: ÉVES HŐINGÁS ÉS MIKROKLIMATIKUS KÜSZÖBNAPOK (TÁBLÁZATOS) ---
# ==============================================================================
def run_annual_climate_stats():
    print("\n====================================================")
    print("[ 5. ÉVES HŐINGÁS ÉS MIKROKLIMATIKUS KÜSZÖBNAPOK ]")
    print("====================================================")
    print("Ez a modul naponkénti felbontásban elemzi a kinti hőmérsékletet,")
    print("majd ÉVEKRE lebontva egy strukturált táblázatban jeleníti meg")
    print("az éves abszolút és napi átlagos hőingásokat, valamint a küszöbnapokat.\n")
    
    confirm = input("Elindítod a teljes éves klíma-elemzést? (i/n): ")
    if confirm.lower() != 'i': return

    try:
        meta_url = f"https://api.thingspeak.com/channels/{THINGSPEAK_CHANNEL}/feeds.json?api_key={READ_API_KEY}&results=0"
        channel_info = requests.get(meta_url, timeout=12).json().get('channel', {})
        created_at_str = channel_info.get('created_at')
        start_date = datetime.strptime(created_at_str, '%Y-%m-%dT%H:%M:%SZ') if created_at_str else (datetime.utcnow() - timedelta(days=730))
        
        detected_outdoor = None
        for i in range(1, 9):
            f_key = f"field{i}"
            if f_key in channel_info and any(kw in channel_info[f_key].lower() for kw in ['kint', 'kulso', 'külső', 'outdoor', 'out', 'kinti']):
                detected_outdoor = f_key
        final_outdoor_field = detected_outdoor if detected_outdoor else OUTDOOR_TEMP_FIELD
    except Exception as e:
        print(f"Hiba az inicializálás során: {e}"); return

    daily_data = {}
    end_date = datetime.utcnow()
    total_days = (end_date - start_date).days
    step_days = 5
    steps_needed = int(np.ceil(total_days / step_days))
    current_start = start_date
    step_count = 0
    
    print("\n[1/2] Adatok letöltése és napok szerinti strukturálása...")
    while current_start < end_date:
        current_end = current_start + timedelta(days=step_days)
        if current_end > end_date: current_end = end_date
        url = f"https://api.thingspeak.com/channels/{THINGSPEAK_CHANNEL}/feeds.json?api_key={READ_API_KEY}&start={current_start.strftime('%Y-%m-%dT%H:%M:%SZ')}&end={current_end.strftime('%Y-%m-%dT%H:%M:%SZ')}&results=8000"
        
        try:
            response = requests.get(url, timeout=12)
            if response.status_code == 200:
                feeds = response.json().get('feeds', [])
                for f in feeds:
                    if not f.get('created_at'): continue
                    f_time = datetime.strptime(f['created_at'], '%Y-%m-%dT%H:%M:%SZ')
                    day_key = f_time.date()
                    
                    val_str = f.get(final_outdoor_field)
                    if val_str and val_str != 'null':
                        try:
                            val = float(val_str)
                            if -50.0 < val < 60.0:
                                if day_key not in daily_data:
                                    daily_data[day_key] = []
                                daily_data[day_key].append(val)
                        except ValueError: pass
                step_count += 1
                sys.stdout.write(f"\rHaladás: [{step_count}/{steps_needed}] blokk | Beolvasott napok: {len(daily_data)}")
                sys.stdout.flush()
        except Exception: pass
        current_start = current_end
        time.sleep(0.08)
        
    print("\n\n[2/2] Meteorológiai indexek kiszámítása...")
    
    yearly_stats = {}
    for day, temps in daily_data.items():
        if len(temps) < 12: continue  # Méréshiányos töredéknapok kiszűrése
        
        d_max = max(temps)
        d_min = min(temps)
        d_range = d_max - d_min
        year = day.year
        
        if year not in yearly_stats:
            yearly_stats[year] = {
                'daily_ranges': [],
                'frost_days': 0,
                'winter_days': 0,
                'summer_days': 0,
                'hot_days': 0,
                'abs_max': float('-inf'),
                'abs_min': float('inf'),
                'analyzed_days': 0
            }
            
        stats = yearly_stats[year]
        stats['daily_ranges'].append(d_range)
        stats['analyzed_days'] += 1
        
        if d_min < 0:   stats['frost_days'] += 1
        if d_max < 0:   stats['winter_days'] += 1
        if d_max >= 25: stats['summer_days'] += 1
        if d_max >= 30: stats['hot_days'] += 1
        
        if d_max > stats['abs_max']: stats['abs_max'] = d_max
        if d_min < stats['abs_min']: stats['abs_min'] = d_min

    print("\n=========================================================================================")
    print(f"               ÉVENKÉNTI MIKROKLÍMA JELENTÉS - {STATION_NAME.upper()}")
    print("=========================================================================================")
    if not yearly_stats:
        print("Nem találtam feldolgozható évenkénti adatot.")
        return

    print(f"{'Év':<5} | {'Átl.Napi Hőing.':<15} | {'Absz.Éves Hőing.':<16} | {'Fagyos n.':<9} | {'Téli n.':<8} | {'Nyári n.':<9} | {'Hőség n.':<9} | {'Napok':<5}")
    print("-" * 96)
    
    for year in sorted(yearly_stats.keys()):
        st = yearly_stats[year]
        if st['analyzed_days'] == 0: continue
        
        mean_dtr = np.mean(st['daily_ranges'])
        abs_range = st['abs_max'] - st['abs_min']
        
        print(f"{year:<5} | {mean_dtr:>11.2f} °C  | {abs_range:>11.1f} °C   | {st['frost_days']:>9} | {st['winter_days']:>8} | {st['summer_days']:>9} | {st['hot_days']:>9} | {st['analyzed_days']:>5}")
    print("=========================================================================================\n")


# ==============================================================================
# --- FŐPROGRAM ---
# ==============================================================================
def main():
    while True:
        print("\n====================================================")
        print(f"  THINGSPEAK WEATHER TUNER & CLIMATE ANALYZER v5.2")
        print(f"  Aktuális célpont: {STATION_NAME}")
        print("====================================================")
        print("1. Gyors Nyomás-trend Analizátor (utolsó 24 óra)")
        print("2. Modell-Optimalizálás & Digitális Iker (utolsó 14 nap)")
        print("3. Abszolút Zónák & Hőmérsékleti Extrémumok (A TELJES MÚLT)")
        print("4. Havi kinti hőmérsékleti statisztikák (A TELJES MÚLT)")
        print("5. Éves hőingás és mikroklimatikus küszöbnapok (A TELJES MÚLT)")
        print("6. Kilépés")
        print("====================================================")
        
        choice = input("Válassz egy menüpontot (1/2/3/4/5/6): ")
        
        if choice == '1':
            run_trend_analyzer()
        elif choice == '2':
            run_model_optimization()
        elif choice == '3':
            run_historical_pressure_zones()
        elif choice == '4':
            run_monthly_temperature_stats()
        elif choice == '5':
            run_annual_climate_stats()
        elif choice == '6':
            print("Kilépés. Sikeres repó építést és jó fejlesztést kívánok!")
            sys.exit()
        else:
            print("Érvénytelen választás. Kérlek, 1 és 6 közötti számot adj meg.")

if __name__ == "__main__":
    main()