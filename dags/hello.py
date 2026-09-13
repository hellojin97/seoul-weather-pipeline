from airflow.sdk import dag, task
from datetime import datetime

@dag(schedule="@hourly", start_date=datetime(2026, 9 ,14), catchup=False)
def hello():
    @task
    def say_hello():
        print("안녕, 나 Airflow에서 돌고 있어.")

    say_hello()


hello()