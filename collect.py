from urllib.request import urlopen
import json
import os
import psycopg

db_host = os.environ.get('DB_HOST', 'localhost')
db_password = os.environ.get('DB_PASSWORD', '')

weather_response = urlopen('https://api.open-meteo.com/v1/forecast?latitude=37.57&longitude=126.98&current=temperature_2m,relative_humidity_2m,wind_speed_10m')
air_quality_response = urlopen('https://air-quality-api.open-meteo.com/v1/air-quality?latitude=37.57&longitude=126.98&current=pm10,pm2_5')

weather_data = json.load(weather_response)
air_quality_data = json.load(air_quality_response)

current_weather = weather_data['current']
current_air_quality = air_quality_data['current']

result_data = {
    'weather': {
        **current_weather,
    },
    'air_quality': {
        **current_air_quality,
    }
}


# 스크립트 분리 예상하며, result_data 분산하지 않음. 데이터가 저렇게 발생한다는 것을 가정
with psycopg.connect(f"host={db_host} dbname=weather user=postgres password={db_password}") as conn:
    with conn.cursor() as cur:
        # CREATE
        # 1) 날씨 테이블
        cur.execute("""
            CREATE TABLE IF NOT EXISTS weather (
                collected_ts            TIMESTAMPTZ NOT NULL,
                temperature_2m          NUMERIC(5,1) NOT NULL,
                relative_humidity_2m    INT NOT NULL,
                wind_speed_10m          NUMERIC(5,1) NOT NULL,
                interval                INT NOT NULL,
                inserted_ts             TIMESTAMPTZ NOT NULL DEFAULT now(),
                PRIMARY KEY (collected_ts)
            )
        """)

        
        cur.execute("""
            CREATE TABLE IF NOT EXISTS air_quality (
                collected_ts            TIMESTAMPTZ NOT NULL,
                pm10                    NUMERIC(5,1) NOT NULL,
                pm2_5                   NUMERIC(5,1) NOT NULL,
                interval                INT NOT NULL,
                inserted_ts             TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                PRIMARY KEY (collected_ts)
            )
        """)

        cur.execute(
            """
            INSERT INTO weather (
                temperature_2m,
                relative_humidity_2m,
                wind_speed_10m,
                interval,
                collected_ts
            ) VALUES (
                %(temperature_2m)s,
                %(relative_humidity_2m)s,
                %(wind_speed_10m)s,
                %(interval)s,
                %(time)s
            )
            ON CONFLICT (collected_ts) DO NOTHING
            """,
            result_data['weather']
        )

        cur.execute(
            """
            INSERT INTO air_quality (
                pm10,
                pm2_5,
                interval,
                collected_ts
            ) VALUES (
                %(pm10)s,
                %(pm2_5)s,
                %(interval)s,
                %(time)s
            )
            ON CONFLICT (collected_ts) DO NOTHING
            """,
            result_data['air_quality']
        )