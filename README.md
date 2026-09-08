# weather-pipeline

Open-Meteo API에서 서울의 현재 날씨와 대기질을 10분마다 수집해 Postgres에 적재하는 로컬 k8s 데이터 파이프라인.

## 아키텍처

```mermaid
flowchart LR
    subgraph EXT["인터넷"]
        API["Open-Meteo API<br>날씨 15분 · 대기질 1시간 갱신"]
    end

    subgraph HOST["맥 (호스트)"]
        subgraph CLUSTER["kind 클러스터 data"]
            CJ["CronJob<br>weather-collector"]
            JOB["Job Pod<br>collect.py<br>(weather-collector:latest)"]
            SVC["Service<br>postgres:5432"]
            PG["Pod postgres<br>(Deployment, postgres:16-alpine)"]

            subgraph STORAGE["스토리지 — Pod 수명과 분리"]
                PVC[("PVC postgres-data 1Gi")]
            end
        end
    end

    CJ -->|"10분마다 Pod 생성"| JOB
    JOB -->|"HTTP 수집"| API
    JOB -->|"DB_HOST=postgres<br>(Service 이름 = 클러스터 내부 DNS)"| SVC
    SVC --> PG
    PG -->|"마운트 /var/lib/postgresql/data"| PVC
```

- 테이블 2개(`weather`, `air_quality`)로 분리: 두 API의 갱신 주기가 달라(900초 / 3600초) 수집 시각(`collected_ts`)이 서로 다르기 때문.
- 중복 방지: `PRIMARY KEY (collected_ts)` + `ON CONFLICT (collected_ts) DO NOTHING`. 10분마다 수집해도 API 값이 안 바뀌었으면 행이 늘지 않는다.

## 처음부터 실행하기

```bash
# 1. 클러스터 생성
kind create cluster --name data

# 2. 수집기 이미지 빌드 + kind에 로드 (kind는 로컬 docker 이미지를 못 봄)
docker build -t weather-collector .
kind load docker-image weather-collector:latest --name data

# 3. 배포
kubectl apply -f k8s/

# 4. 확인
kubectl get pods                # postgres Running, 10분마다 weather-collector-* Completed
kubectl get pvc                 # postgres-data Bound

# 5. 크론 안 기다리고 즉시 1회 실행
kubectl create job --from=cronjob/weather-collector test-run

# 6. 데이터 확인
kubectl exec deploy/postgres -- psql -U postgres -d weather -c 'SELECT * FROM weather;'
kubectl exec deploy/postgres -- psql -U postgres -d weather -c 'SELECT * FROM air_quality;'
```

## 로컬 개발 (k8s 없이)

```bash
docker run -d --name pg -e POSTGRES_PASSWORD=devpw -e POSTGRES_DB=weather -p 5432:5432 postgres:16-alpine
python3 -m venv .venv && source .venv/bin/activate
pip install "psycopg[binary]"
python3 collect.py                        # DB_HOST 미지정 시 localhost

# 컨테이너로 실행할 땐 localhost가 안 통하므로:
docker run --rm -e DB_HOST=host.docker.internal weather-collector
```

## 밟은 지뢰들

- **코드 고쳤는데 그대로다** → 이미지는 `docker build` 시점의 파일 복사본. 수정하면 리빌드 필수. 트레이스백에 찍힌 코드가 진짜 실행된 코드다.
- **컨테이너 안 localhost는 자기 자신** → Postgres는 밖에 있으므로 connection refused. 접속 주소는 환경변수(`DB_HOST`)로 주입: 로컬 docker는 `host.docker.internal`, k8s는 Service 이름.
- **ON CONFLICT는 unique 제약이 있는 컬럼만** → 대상 컬럼 조합에 정확히 일치하는 unique/PK 제약이 없으면 INSERT 자체가 에러.
- **`:latest` 태그는 imagePullPolicy 기본값이 Always** → 손으로 로드한 로컬 이미지를 무시하고 레지스트리에서 pull 시도하다 실패. `imagePullPolicy: Never`로 차단.
- **`kubectl expose`는 클러스터의 실제 리소스를 참조** → `create --dry-run`과 달리 deployment를 먼저 apply해야 동작.
- **DB Deployment는 `strategy: Recreate`** → 기본 RollingUpdate는 새/옛 Pod가 잠깐 같은 PVC를 동시에 잡아 Postgres 잠금 충돌로 배포가 멈춘다.
- **Pod의 파일시스템은 Pod와 함께 사라진다** → DB 데이터는 PVC에. 볼륨 없이 띄운 데이터는 Pod 교체 시 증발.
- **`NUMERIC(3,1)` 최대값은 99.9** → 미세먼지 심한 날 / 태풍 풍속에 overflow. 컬럼 폭은 극단값 기준으로.

## 다음 후보

- 비밀번호 k8s Secret으로 이동 (지금은 로컬 개발용 평문)
- 대시보드 (Grafana 등)로 시각화
